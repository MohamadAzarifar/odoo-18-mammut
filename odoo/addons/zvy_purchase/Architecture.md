# Purchase — Architecture

Source: `Draft.md` (read-only) and `PRD.md`. This document is the technical design for `zvy_purchase`. It records **specified** structure vs **proposed** Odoo mapping. Do not treat proposed fields as requirements.

## 1. Module identity

| | |
|---|---|
| Technical name | `zvy_purchase` (addon folder already uses this) |
| Display name | Purchase (draft). Collides with core `purchase`; confirm before `__manifest__.py` |
| Category | Inventory/Purchase (proposed) |
| Location | `odoo/addons/zvy_purchase`. Custom addons in this repo usually live under `odoo/addons-mammut`. Confirm the install path. |
| Odoo version | 18 |

This module is a **new** document model. It does not extend `purchase.order`.

## 2. Specified structure

```text
Purchase Request
  └── Purchase Item[]          # each item: product + qty + UoM + Offers[]
        ├── product            # required
        ├── quantity           # required
        ├── UoM                # required, same category as product
        └── Offer[]            # each offer: vendor + price/qty/payment/delivery terms
              ├── vendor       # required, AVL for item.product
              ├── unit_price, quantity, total_price, final_price
              ├── payment_method, payment_duration
              ├── deliver_time
              └── discount_percent_per_unit

AVL
  └── vendor + product         # who may procure which product
```

## 3. Proposed Odoo models

| Draft entity | Model | Persistence |
|---|---|---|
| Purchase Request | `zvy.purchase.request` | Independent `models.Model` |
| Purchase Item | `zvy.purchase.item` | Child of request (`_name`, not `_inherits`) |
| Offer | `zvy.purchase.offer` | Child of item |
| AVL | `zvy.purchase.avl` | Vendor–product pair |
| Product | `product.product` | Existing. Matches core PO lines (variant, not template). |
| Vendor | `res.partner` | Existing. Offer domain is AVL for the item’s product. |

```mermaid
erDiagram
    zvy_purchase_request ||--o{ zvy_purchase_item : item_ids
    zvy_purchase_item }o--|| product_product : product_id
    zvy_purchase_item }o--|| uom_uom : product_uom_id
    zvy_purchase_item ||--o{ zvy_purchase_offer : offer_ids
    zvy_purchase_offer }o--|| res_partner : vendor_id
    zvy_purchase_avl }o--|| res_partner : vendor_id
    zvy_purchase_avl }o--|| product_product : product_id
    product_product {
        string zvy_purchase_type
        bool zvy_need_commission
    }
    zvy_purchase_item {
        float product_qty
    }
```

### 3.1 `zvy.purchase.request`

Specified: owns `item_ids`. Numbered `PR-1`, `PR-2`, … on create.

| Field | Type | Notes |
|---|---|---|
| `name` | Char, readonly, copy=False | Sequence `zvy.purchase.request`, prefix `PR-`, no padding |
| `company_id` | Many2one `res.company`, required, readonly, copy=False | Set on create from the creator’s active company (`env.company`); not editable afterward |
| `create_uid` | Many2one `res.users` (standard) | Shown as **Creator** on form/list |
| `state` | Selection `draft` / `in_review`, default `draft`, tracking | Specified. Widget statusbar. |
| `item_ids` | One2many → `zvy.purchase.item` | `request_id`, cascade delete |
| `can_edit_items` | Boolean, computed | True when Draft, current user is `create_uid`, and user is Planner or Commercial Manager |

`action_send()` writes `state = 'in_review'`. Allowed only from `draft` and only by the request creator (`create_uid`); otherwise `UserError` / `AccessError`. Form header **Send** button is `invisible="not can_edit_items"` (Draft + creator + Planner/CM). On Send, all purchase items are set to `submitted`; items that already have commercial experts are then promoted to `in_review`.

`action_back_to_draft()` (Commercial Manager only, `state == 'in_review'`) opens transient wizard `zvy.purchase.back.to.draft.wizard` with a mandatory `reason` Text field. Confirm writes request `state = 'draft'`, resets all items to `draft`, and `_message_log`s the reason on the request chatter. Form header **Back to Draft** sits next to Assign Expert; `groups="…group_commercial_manager"` and `invisible="state != 'in_review'"`.

`action_assign_expert()` (Commercial Manager only, `state == 'in_review'`) opens transient wizard `zvy.purchase.assign.expert.wizard` with one line per purchase item. Confirm writes `commercial_expert_ids` on each item (which promotes assigned items to `in_review`).

`item_ids` is readonly when `not can_edit_items`. Item create/write/unlink also enforces creator + Draft server-side.

`mail.thread` + form `<chatter/>`. Tracked: `state`. Item/offer create, tracked writes, and unlink are also `_message_log`’d here.

### 3.2 `zvy.purchase.item`

Specified: one product, list of offers, belongs to one request. Numbered `{request.name}-PI-{n}` per request.

| Field | Type | Source |
|---|---|---|
| `name` | Char, readonly, copy=False | Specified number, e.g. `PR-1-PI-1` |
| `sequence_number` | Integer, copy=False | Per-request index `n` |
| `request_id` | Many2one `zvy.purchase.request`, required, `ondelete='cascade'` | Specified parent; readonly clickable on item form (including Commercial Expert via assigned-item rule) |
| `request_state` | related `request_id.state`, stored | For readonly UI without browsing when needed |
| `request_name` | related `request_id.name`, stored | Kept for search/display helpers |
| `request_create_uid` | related `request_id.create_uid`, stored | For `can_edit` without browsing the request |
| `state` | Selection `draft` / `submitted` / `in_review`, default `draft`, tracking | Item workflow. Statusbar on item form; badge on lists. |
| `can_edit` | Boolean, computed | Planner/CM + Draft + creator; False for Commercial Experts |
| `can_assign_experts` | Boolean, computed | Commercial Manager (on requests they can access) |
| `can_add_offers` | Boolean, computed | CM: always True. CE: True only when `request_state` and item `state` are both `in_review`. |
| `product_id` | Many2one `product.product`, required, tracking | Specified |
| `product_qty` | Float, required, default `1.0`, digits `Product Unit of Measure`, tracking | Specified quantity |
| `product_uom_category_id` | related `product_id.uom_id.category_id` | Domain helper for UoM |
| `product_uom_id` | Many2one `uom.uom`, required, domain same category as product, tracking | Specified UoM; defaults to `product.uom_po_id` or `product.uom_id` |
| `purchase_type_display` | Selection computed | `enquiry` → Enquiry; enquiry + need commission → Enquiry / Commission; `tendering` → Tendering. Uses product company-resolved flags. |
| `commercial_expert_ids` | Many2many `res.users`, tracking | Specified chip list; writable only by Commercial Manager |
| `offer_ids` | One2many → `zvy.purchase.offer` | Specified |
| `offer_count` | Integer, computed from `offer_ids` | Shown on the Purchase Request items list |

Item workflow transitions (system-driven; not manual buttons):

1. Create → `draft`.
2. Parent request **Send** → all items `submitted` (then any item that already has commercial experts → `in_review`).
3. Commercial Manager assigns one or more commercial experts (wizard or chip write) → that item `in_review`.
4. Parent request **Back to Draft** → all items reset to `draft`.

`mail.thread` + form `<chatter/>`. Sequence writes use `mail_notrack`. Create/unlink and product / qty / UoM changes are also logged on `request_id`.

Create/write/unlink of item structure (product, quantity, UoM, unlink, etc.) raise `AccessError` unless the parent request is Draft and `create_uid` is the current user (and the user is Planner or Commercial Manager via ACL). After In Review, those edits are denied. Writing `state` alone (system transitions) skips the structure-edit check.

`commercial_expert_ids` may be written only by Commercial Manager (allowed even when the CM is not the request creator, including after In Review). Planners cannot assign experts. Product / quantity / UoM / structure fields stay locked after In Review.

Widget `many2many_tags`. Domain is a field lambda (not a computed Many2many): `share=False`, Commercial Expert group, `company_ids` in current company. That works on new/unsaved items; `id in allowed_*` does not until the record is reopened. No create from the chip field. Readonly when `not can_assign_experts`.

`offer_ids` UI uses `create="0"` when `not can_add_offers`. Only Commercial Expert and Commercial Manager may create offers (ACL + server check). Commercial Experts additionally require both the parent request and the item to be `in_review` (`_zvy_check_can_add_offers` on offer create).

On product change (onchange / create without UoM / write without UoM), `product_uom_id` is set from `product.uom_po_id` or `product.uom_id`. Quantity and UoM are readonly in views when `not can_edit` (creator + Draft + Planner/CM).

Constraint (open in PRD): unique `(request_id, product_id)` only if duplicate products on one request are forbidden.

### 3.3 `zvy.purchase.offer`

Specified: one vendor, belongs to one item. Numbered `{item.name}-OFR-{n}` per item.

| Field | Type | Source |
|---|---|---|
| `name` | Char, readonly, copy=False | Specified number, e.g. `PR-1-PI-1-OFR-1` |
| `sequence_number` | Integer, copy=False | Per-item index `n` |
| `item_id` | Many2one `zvy.purchase.item`, required, `ondelete='cascade'` | Specified parent |
| `product_id` | related `item_id.product_id` | AVL domain; shown readonly on offer form below item |
| `allowed_vendor_ids` | computed Many2many `res.partner` | AVL vendors for `product_id` |
| `vendor_id` | Many2one `res.partner`, required, domain `id in allowed_vendor_ids`, tracking | Specified |
| `currency_id` | related `item_id.company_id.currency_id` | Company currency for Monetary fields |
| `unit_price` | Monetary, tracking | Specified |
| `quantity` | Float, digits Product UoM, default from item `product_qty`, tracking | Specified; `default_get` / create / onchange from parent item |
| `total_price` | Monetary, computed readonly | `quantity * unit_price` |
| `payment_method` | Char, tracking | Free text (cash, cheque, credit, …) |
| `payment_duration` | Char, tracking | Free text (e.g. 30 days, 60 days) |
| `deliver_time` | Date, tracking | Specified delivery time |
| `discount_percent_per_unit` | Float, tracking | Decimal rate (0.1 = 10%); percentage widget |
| `final_price` | Monetary, computed readonly | `unit_price * (1 - discount_percent_per_unit) * quantity` |
| `can_edit` | Boolean, computed | True when `create_uid` is empty (new) or equals the current user |

`mail.thread` + form `<chatter/>`. Sequence writes use `mail_notrack`. Create/unlink and vendor / commercial-term changes are also logged on the item and the request.

Write and unlink raise `AccessError` unless the current user is the offer `create_uid` (or superuser). Cascade delete of offers when an item is removed uses `sudo()` so parent cleanup still works. ACL still gates who may create offers; creator-only is an additional server check on modify/delete.

Offer form: left group item / product / creator / vendor; right group prices (unit, qty, total, discount, final); then Payment & Delivery (method, duration, delivery time). Editable fields are `readonly="not can_edit"`. Item offers list shows name, creator (optional), vendor, unit price, quantity, total, discount, final (payment/delivery optional columns); row fields readonly when `not can_edit`.

Offer vendor many2one allows create. Context passes `zvy_avl_product_id` (the item’s product) and `default_is_company`. Creating a partner in that context (or saving an offer whose vendor is not yet on AVL) calls `zvy.purchase.avl._ensure(vendor, product)`. Domain stays AVL vendors, plus the currently selected `vendor_id` so a just-created contact remains valid before the compute refreshes.

Constraint (open in PRD): unique `(item_id, vendor_id)` only if one offer per vendor per item is required.

### 3.4 `zvy.purchase.avl`

Specified: vendor–product connection. Unique `(vendor_id, product_id)`.

| Field | Type | Source |
|---|---|---|
| `vendor_id` | Many2one `res.partner`, required, `ondelete='restrict'` | Specified |
| `product_id` | Many2one `product.product`, required, `ondelete='restrict'` | Specified |

Menu: Purchase → Configuration → AVL. List + form. Offer `vendor_id` is restricted to AVL rows for the item’s product. Creating a vendor from an offer inserts the AVL row.

`zvy.purchase.avl._ensure(vendor, product)` creates the pair if missing (unique constraint).

### 3.5 Product (`product.product`)

Specified: purchase type, need commission, holding-company default with per-company override, Commission Manager write-only. Menu: Purchase → Configuration → Products.

| Field | Type | Source |
|---|---|---|
| `zvy_purchase_type` | Selection `enquiry` / `tendering`, default `enquiry` | Specified. Label **Enquiry** (draft spelling “Enquery”). |
| `zvy_need_commission` | Boolean, default False | Specified **Need Commission?** |
| `zvy_purchase_type_company_values` | Json `{company_id: value}` | Storage for holding default + override |
| `zvy_need_commission_company_values` | Json `{company_id: value}` | Storage for holding default + override |

`zvy_purchase_type` and `zvy_need_commission` are computed from the JSON maps. Resolve by walking `env.company` then parents up to the holding company (`parent_ids` via `sudo()` so users without `res.company` read on parents can still resolve values); the first stored key wins. Writing stores an override on the current company only. Clearing an override (value equal to the inherited value) drops the current-company key so the parent value applies again.

Native `company_dependent=True` is not used: it has no parent-company fallback, and a missing boolean cannot be distinguished from `False`.

When type is `tendering`, need commission is forced false (onchange, inverse, compute, constraint) and the field is invisible.

Write of these attributes raises `AccessError` unless the user is in `zvy_purchase.group_commission_manager` (or superuser). Views show the fields to everyone; they are readonly without that group.

## 4. Integrity

- Item without `request_id` or `product_id`: invalid.
- Offer without `item_id` or `vendor_id`: invalid.
- Request `name` from `ir.sequence` code `zvy.purchase.request` (`PR-` + next integer).
- Item/offer numbers are per parent (`max(sequence_number) + 1`), not global `ir.sequence`. Deleting a child does not reuse its index.
- Delete request → delete items → delete offers (`ondelete='cascade'`).
- Product and vendor are links only; deleting a product/vendor in use should be restricted (`ondelete='restrict'`), not cascade.
- Offers never point at the request directly. Request-level offer lists, if needed, are related through items.
- Offer `vendor_id` must be an AVL vendor for `item_id.product_id` (UI domain). Empty AVL for that product → empty vendor list.
- Request `state` is `draft` on create. Send may run only from `draft` → `in_review`, and only by the request creator.

## 5. Dependencies

Minimum to support the specified links:

| Addon | Why |
|---|---|
| `product` | `product.product` |
| `mail` | Chatter and field tracking on request / item / offer |
| `base` | `res.partner` (pulled in via `product`) |

Do **not** depend on `purchase` unless a later requirement creates RFQs/POs from offers.

`mail.activity.mixin` is not specified; chatter is for logging changes only.

## 6. Addon layout (proposed)

```text
zvy_purchase/
  __init__.py
  __manifest__.py
  models/
    __init__.py
    zvy_purchase_request.py
    zvy_purchase_avl.py
    product_product.py
    res_partner.py
  wizard/
    __init__.py
    zvy_purchase_assign_expert_wizard.py
    zvy_purchase_assign_expert_wizard_views.xml
    zvy_purchase_back_to_draft_wizard.py
    zvy_purchase_back_to_draft_wizard_views.xml
  views/
    zvy_purchase_request_views.xml
    zvy_purchase_avl_views.xml
    product_product_views.xml
  security/
    ir.model.access.csv
    zvy_purchase_security.xml
  data/
    ir_sequence_data.xml
  PRD.md
  Architecture.md
  Draft.md                # read-only input; do not edit
```

UX mapping:

- Form for `zvy.purchase.request` with an items list (product, quantity, UoM, purchase type, commercial experts, offer count last), statusbar, Send (Draft + creator), Assign Expert and Back to Draft (In Review, Commercial Manager), and chatter.
- Item and offer forms include chatter.
- Each item row: product, quantity, UoM + embedded offers list (or a smart button to offers).
- Offer row: vendor, unit price, quantity, totals, discount, final price. Offer form shows item/product/vendor, price block, and payment/delivery.
- Menu under a Purchase app root (name TBD because of the core Purchase clash).
- **Purchase Requests** menu and window action: Planner and Commercial Manager only. Menu `groups_id` is force-replaced with `(6, 0, [...])` so upgrades do not leave a stale Commercial Expert link.
- **To Review**: list of `zvy.purchase.item` with domain `commercial_expert_ids in uid`. Opens the existing item form. Create/delete not offered from this menu. Commercial Expert group only. Item form shows clickable readonly `request_id` for all roles that can open the item.
- Configuration → Products: list + form of `product.product` with purchase type and need commission. Standard product form also shows the same group.

Items are also reachable from **To Review** when assigned; offers stay edited in context of the item. Standalone offer menus are not required.

## 7. Security

- Group `zvy_purchase.group_planner` (**Planner**). Implies `base.group_user`. Create/write/unlink on request and item. Read-only on offers. Record rule: own requests (`create_uid = user.id`) in allowed companies.
- Group `zvy_purchase.group_commercial_manager` (**Commercial Manager**). Implies `base.group_user`. Create/write/unlink on request, item, and offer. Record rule: all requests in allowed companies (any state). Only this group may write `commercial_expert_ids`.
- Only Planner and Commercial Manager may create purchase requests or purchase items (ACL). Adding/editing item structure (including quantity and UoM) also requires the current user to be the request `create_uid` and the request to be Draft (server-side). After In Review, item structure create/write/unlink is denied for everyone.
- Group `zvy_purchase.group_commercial_expert` (**Commercial Expert**). Implies `base.group_user`. Read/write on assigned items (write used so offer one2many create works); create/write/unlink on offers for assigned items. Read-only ACL on purchase requests limited by record rule to requests that have an item where the user is in `commercial_expert_ids` (so the item’s request many2one can open). No Purchase Requests menu. Record rules: items/offers where the user is in `commercial_expert_ids`.
- Only Commercial Expert and Commercial Manager may create offers (ACL + `AccessError` on create for others). Commercial Experts may create offers only when both the purchase request and the purchase item are In Review.
- Only the offer **creator** may write or unlink that offer (`AccessError` otherwise), including when the other user is a Commercial Manager. Views use `can_edit` so non-creators see others’ offers readonly.
- Group `zvy_purchase.group_commission_manager` (**Commission Manager**). Implies `base.group_user`. Written access on `product.product` so the configuration form can save the two attributes. Create/unlink on products stay with product managers.
- Only that group may change `zvy_purchase_type` / `zvy_need_commission` (server-side check + readonly views).
- AVL CRUD stays with `base.group_user`.
- Do not copy `zvy_tendering` planner / CM / commission *calculation* rules. Commission Manager only gates the product flags above.

## 8. Relation to other modules

| Module | Relation |
|---|---|
| `purchase` | Different document. No inherit, no replace. |
| `zvy_tendering` | This repo already has purchase-request / quote models. `zvy_purchase` is specified as a new module. Whether it replaces, sits beside, or stays a prototype is an open product question — not an architecture decision yet. |

Do not reuse `zvy.purchase.request` from tendering until that question is answered. This module’s models stay in the `zvy.purchase.*` namespace above.

## 9. Implementation order

1. Manifest, security, empty models with the specified fields only.
2. Request form: items with `product_id`.
3. Item offers with `vendor_id`.
4. Sequence + list/search views + menu.
5. Hierarchical names: `PR-n`, `PR-n-PI-m`, `PR-n-PI-m-OFR-k`.
6. AVL under Configuration; offer vendor domain from AVL.
7. Product purchase type / need commission; Configuration → Products; Commission Manager group.
8. Request state Draft / In Review and Send button.
9. Chatter on request, item, and offer; child changes also logged on the request.
10. Create vendor from offer → contact + AVL for the item product.
11. Commercial Expert group + item chip list (current-company members of that group).
12. To Review menu: items where current user is in `commercial_expert_ids`.
13. Planner and Commercial Manager groups; request `company_id`; record rules (own vs company); creator-only item edits; lock items after In Review.
14. Offer create limited to Commercial Expert + Commercial Manager; commercial-expert chips writable only by Commercial Manager.
15. Assign Expert wizard on In Review requests (Commercial Manager).
16. Quantity and UoM on purchase items (creator-only edit while Draft).
17. Back to Draft wizard with mandatory reason logged in chatter (Commercial Manager, In Review).
18. Purchase item workflow: Draft → Submitted (on request Send) → In Review (when commercial experts assigned); Back to Draft resets items to Draft.
19. Offer commercial terms: unit price, quantity (default from item), total/final price, payment method/duration, delivery time, discount rate.
20. Offer edit/delete limited to the offer creator.
21. Stop. Add further states, approvals, or PO integration only after `PRD.md` is updated.

## 10. Open technical decisions

1. Confirm display name vs core Purchase.
2. Confirm addon path (`odoo/addons` vs `odoo/addons-mammut`).
3. `product.product` vs `product.template`.
4. Unique product per request; unique vendor per item.
5. Whether attachments or activities (not just change logs) are needed on chatter.
6. Whether purchase type / need commission should live on `product.template` (shared by variants) instead of `product.product`.
