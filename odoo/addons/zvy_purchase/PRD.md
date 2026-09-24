# Purchase — Product Requirements Document

Source: `Draft.md` (read-only). This document is the product spec for the custom **Purchase** module (`zvy_purchase`).

## 1. Summary

Purchase is a new custom Odoo module for collecting vendor offers against requested products.

A **Purchase Request** is the working document. It holds **Purchase Items**. Each item is one **product** and the **Offers** collected for that product. Each offer is tied to one **vendor**.

The module is not Odoo’s core Purchase app (`purchase`). Core purchase orders, RFQs, receipts, and vendor bills are out of scope unless later requirements add them.

## 2. Goals

- Represent a purchase request as a list of products to buy.
- Collect multiple vendor offers per product on that request.
- Keep the three-level structure as the source of truth: Request → Item → Offer.
- Number new records hierarchically: `PR-1`, `PR-1-PI-1`, `PR-1-PI-1-OFR-1`.
- Maintain an AVL (vendor ↔ product). Offer vendors are limited to that list.
- Configure each product’s **purchase type** and **need commission?** flag, with holding-company defaults that a child company can override.
- Restrict those two product attributes to the **Commission Manager** role.
- Send a purchase request from **Draft** to **In Review**.
- Log every change on Purchase Request, Purchase Item, and Offer in chatter.
- Assign **Commercial Experts** on each purchase item — only a **Commercial Manager** may assign them.
- Give assigned experts a **To Review** menu of their purchase items.
- On In Review requests, Commercial Managers use **Assign Expert** to set experts per purchase item via a wizard.
- On In Review requests, Commercial Managers can use **Back to Draft** to return the request to Draft; a mandatory reason is collected and logged in chatter.
- Purchase items have their own workflow: **Draft** → **Submitted** (when the request is sent) → **In Review** (when a commercial expert is assigned).
- Restrict creating purchase requests and adding items to **Planner** and **Commercial Manager**.
- Limit Planner visibility to their own requests; Commercial Manager sees all purchase requests in their company (any status).
- Only the request creator may add purchase items, and only while the request is Draft. After **In Review**, purchase items are locked.
- Only **Commercial Expert** and **Commercial Manager** may add offers on a purchase item. Commercial Experts may do so only when both the purchase request and the purchase item are **In Review**.

## 3. Non-goals (until specified)

- Approval workflows beyond Draft → In Review, tender envelopes, commission calculation, or AVL routing beyond the vendor–product list.
- Creating or replacing `purchase.order` / RFQ / receipt / vendor bill flows.
- Vendor portal bidding.
- Automatic vendor selection or award.

## 4. Users

Internal purchasing users create requests, add items, and record offers.

**Commission Manager** is a named role. Only that role can change a product’s purchase type and need-commission flag. Other users may see the values.

**Commercial Expert** is a named role. Purchase items can list users who have this role and belong to the current company. Together with Commercial Managers, they can add offers on purchase items — Commercial Experts only when both the request and the item are In Review. They can open the related purchase request from an assigned item (read-only); they do not get the Purchase Requests menu.

**Planner** is a named role. Planners can create purchase requests and add items. They only see purchase requests they created.

**Commercial Manager** is a named role. Commercial Managers can create purchase requests and add items. In the Purchase Requests list they see all purchase requests in their company, regardless of status. Only they can assign Commercial Experts on purchase items. They can also add offers.

## 5. Domain model

```text
Purchase Request  1 ──*  Purchase Item  1 ──*  Offer
                         │                     │
                         *                     *
                      Product               Vendor
                         *                     *
                         └────── AVL ──────────┘
```

| Entity | Cardinality | Meaning |
|---|---|---|
| Purchase Request | 1 request → many items | Header document for a set of needed products. |
| Purchase Item | 1 item → 1 product; 1 item → many offers | One product line on a request, with the offers collected for it. |
| Offer | 1 offer → 1 vendor; many offers → 1 item | A vendor’s response for that item. |
| AVL | vendor ↔ product | Vendors that may procure a given product. |

Rules implied by the draft:

- A request with no items is allowed as an empty draft; items are what give it content.
- An item without a product is invalid.
- An item may have zero offers (not yet inquired) or several offers (competing vendors).
- An offer without a vendor is invalid.
- The same product may appear on more than one request. Whether it may appear twice on the **same** request is open.

## 6. Functional requirements

### FR-1 — Purchase Request

- Only **Planner** and **Commercial Manager** can create purchase requests.
- Only Planner and Commercial Manager have the **Purchase Requests** menu and action (Commercial Experts do not see that menu and cannot browse all requests).
- Commercial Experts can open a related purchase request (read-only) from the purchase-item **Purchase Request** field, only for requests that have a purchase item assigned to them.
- Planners list only purchase requests they created. Commercial Managers list all purchase requests in their company (any status).
- Commercial Experts use **To Review** for assigned items only.
- Each request contains an ordered list of purchase items. The items list on the request form shows the **offer count** per item.
- Deleting a request deletes its items and their offers.
- A request starts in **Draft**.
- Each request has a read-only **Company** set from the creator’s active company when the request is created.
- The request form (and list) show the **Creator** name (`create_uid`).
- The form has a **Send** button. Clicking it sets the request to **In Review**.
- Send is shown only while the request is Draft **and** the current user is the request creator. After Send (In Review, or any later status), or for non-creators, the button is hidden.
- Commercial Managers can return an **In Review** request to **Draft** with **Back to Draft** (mandatory reason wizard; see FR-2).

### FR-2 — Purchase Item

- Only **Planner** and **Commercial Manager** can add purchase items, and only on requests they created.
- Items can be added, edited, or removed only while the parent request is **Draft**. After **In Review**, no one can edit purchase items (product, quantity, UoM, and structure). Exception: see commercial-expert assignment below while still Draft.
- Each item must reference exactly one product.
- Each item has a **Quantity** and **Unit of Measure**. UoM defaults from the product’s purchase UoM (falling back to the product UoM) and is limited to that product’s UoM category.
- Only the request creator can edit quantity and UoM (same Draft + creator rule as other item fields).
- The item list and item form show **Purchase Type** derived from the product: **Enquiry**, **Enquiry / Commission**, or **Tendering**.
- Each item contains a list of offers for that product.
- Each item has a chip list of **Commercial Experts**: users in the current company who have the Commercial Expert role. Users without that role, or who cannot access the current company, are not offered.
- Only a **Commercial Manager** can assign (add/remove) Commercial Experts on an item. Planners and Commercial Experts cannot.
- On an **In Review** purchase request, Commercial Managers get an **Assign Expert** button. It opens a wizard listing each purchase item with its product and commercial-expert chips; confirming writes the selected experts onto those items.
- Next to Assign Expert, Commercial Managers get a **Back to Draft** button (shown only while the request is **In Review**). It opens a wizard with a mandatory **Reason** field; confirming sets the request back to **Draft**, resets all purchase items to **Draft**, and logs the reason in the request chatter. For other roles and other statuses the button is hidden.
- Each purchase item has its own **status** workflow (system-driven; not manual buttons):
  - Starts in **Draft**.
  - When the creator **Send**s the parent purchase request, every purchase item moves to **Submitted**.
  - When a Commercial Manager assigns one or more Commercial Experts to a purchase item, that item moves to **In Review**.
  - Status is shown on the item form (statusbar) and on item lists (including the request’s items list).

### FR-3 — Offer

- Only **Commercial Expert** and **Commercial Manager** can add offers on a purchase item. Planners cannot.
- A **Commercial Expert** can add offers only when both the parent purchase request and the purchase item are **In Review**. Before that (or if either is not In Review), offer create is hidden and denied server-side.
- Users can **create** offers according to their offer ACL (Commercial Expert and Commercial Manager). A user may **edit or delete** only offers they created; nobody can change another user’s offer (including Commercial Managers).
- Each offer must reference exactly one vendor.
- The offer form shows the purchase item and, below it in the same group, the related **product** name (readonly).
- The vendor must be on the AVL for the item’s product. Vendors that do not procure that product are not offered in the selector.
- From an offer, a user can create a new vendor. That creates a contact and an AVL row for the item’s product, then uses that vendor on the offer.
- Several offers on one item may come from different vendors. Whether two offers on the same item may share a vendor is open.
- Each offer records commercial terms:
  - **Unit price** (monetary, company currency).
  - **Quantity** (defaults from the parent purchase item’s quantity; editable).
  - **Total price** = quantity × unit price (computed, readonly).
  - **Payment method** (free text, e.g. cash, cheque, credit).
  - **Payment duration** (free text, e.g. 30 days, 60 days).
  - **Delivery time** (date).
  - **Discount % / unit** as a decimal rate (e.g. `0.1` for 10%; UI percentage widget).
  - **Final price** = unit price × (1 − discount) × quantity (computed, readonly).

### FR-4 — Navigation

- From a request, users can see all items and, for each item, its offers.
- Product and vendor are standard Odoo records (catalog / contact), not free text.
- Purchase has a **To Review** menu. It lists Purchase Items where the current user is one of the Commercial Experts.

### FR-5 — Numbering

- New records receive a number on create. Numbers are not typed by the user.
- Purchase Request: `PR-1`, `PR-2`, …
- Purchase Item: parent request number + item index on that request, e.g. `PR-1-PI-1`, `PR-1-PI-2`.
- Offer: parent item number + offer index on that item, e.g. `PR-1-PI-1-OFR-1`, `PR-1-PI-1-OFR-2`.
- Item and offer indexes are per parent, not global. Deleting a child does not renumber the rest; the next new child takes the next index.
- The number is the record name and is shown on lists and forms.

### FR-6 — AVL

- Configuration has an **AVL** menu.
- Each AVL row connects one vendor to one product. The same vendor may be listed for several products, and the same product for several vendors.
- The same vendor–product pair cannot be listed twice.
- On an offer, the vendor field lists only AVL vendors for that item’s product. If the product has no AVL rows, the list is empty.
- Creating a vendor from an offer creates the contact and links it to the item’s product in AVL.

### FR-7 — Products (configuration)

- Configuration has a **Products** menu that opens the product catalog used by this module (product variants).
- Each product has **Purchase Type**: Enquiry or Tendering. Default is Enquiry.
- Each product has **Need Commission?**: boolean. Default is false.
- When purchase type is Tendering, need commission is false and hidden.
- Values are set on the parent holding company and apply to child companies unless a child company sets its own value.
- Only a Commission Manager can change these two attributes.

### FR-8 — Chatter

- Purchase Request, Purchase Item, and Offer each have a chatter.
- Create, field changes, and delete of those records are logged.
- Item and offer activity is also logged on the parent Purchase Request chatter so the request is a full audit trail.
- Auto-assigned numbers (`PR-n-PI-m`, `PR-n-PI-m-OFR-k`) are not logged as user changes.

## 7. Data fields in scope

Only these facts are required by the draft:

| Record | Required content |
|---|---|
| Purchase Request | Number (`PR-n`), company (read-only, creator’s company), creator name, list of purchase items, status (Draft / In Review; default Draft) |
| Purchase Item | Number (`PR-n-PI-m`), product, quantity, unit of measure, purchase type display (Enquiry / Enquiry / Commission / Tendering), list of offers, commercial experts (users in the current company with the Commercial Expert role), status (Draft / Submitted / In Review; default Draft) |
| AVL | Vendor, product |
| Offer | Number (`PR-n-PI-m-OFR-k`), vendor (from AVL for the item’s product), unit price, quantity (default from item), total price (computed), payment method, payment duration, delivery time, discount % / unit (decimal rate), final price (computed) |
| Product | Purchase type (Enquiry / Tendering, default Enquiry), Need commission? (default false; hidden and forced false when type is Tendering). Company-specific, holding default with per-company override. |

Price and commercial terms on offers are in scope (unit price, quantity, totals, payment method/duration, delivery time, discount, final price). Currency follows the request company. Other fields not listed above remain out of scope until added here.

## 8. Success criteria

- A user can open a draft purchase request they created, add several products as items (with quantity and UoM), record vendor offers, and Send it to In Review. Send is not shown after that, or to non-creators.
- New requests / items / offers are named `PR-1`, `PR-1-PI-1`, `PR-1-PI-1-OFR-1` (indexes increase per parent).
- Offer vendor selection only includes vendors linked to that product in AVL.
- Creating a vendor on an offer adds the contact and an AVL row for that product.
- Configuration → Products shows each product’s purchase type and need-commission flag.
- A holding-company value is used until a child company overrides it. Tendering hides and clears need commission.
- Only Commission Managers can change those two product attributes.
- The three-level structure is visible and editable without using core Purchase orders.
- Product and vendor always resolve to existing Odoo records.
- Chatter on the request shows request, item, and offer changes. Item and offer forms show their own chatter.
- A purchase item can be assigned Commercial Experts only by a Commercial Manager (Assign Expert wizard on In Review, or direct write).
- Purchase items start in Draft; Send moves them to Submitted; assigning commercial experts moves the assigned item to In Review; Back to Draft resets items to Draft.
- **To Review** shows only Purchase Items assigned to the logged-in user as a Commercial Expert.
- Commercial Experts can open the related purchase request from an assigned item (read-only); they still have no Purchase Requests menu.
- Only Planners and Commercial Managers can create purchase requests and add items; only the request creator can add items; items are locked after In Review.
- Planners see only their own requests; Commercial Managers see all requests in their company (any status).
- Only Commercial Experts and Commercial Managers can add offers. Commercial Experts only when both request and item are In Review.
- Only the creator of an offer can edit or delete it; other users see it readonly.

## 9. Open questions

1. ~~Who creates and owns a request (employee, department, purchaser)?~~ Answered: Planner or Commercial Manager creates; creator owns item edits.
2. What states exist after request In Review (done, cancelled, …)? Send / Draft / In Review are specified for the request. Item workflow Draft → Submitted → In Review is specified.
3. ~~Does an item need quantity, UoM, required date, or specification text?~~ Answered: quantity and UoM are required on each item; only the request creator may edit them (Draft). Required date and specification text remain open.
4. ~~Does an offer need price, currency, validity date, lead time, or comments?~~ Answered: unit price, quantity (default from item), total/final price, payment method, payment duration, delivery time, and discount % / unit. Validity date and free-text comments remain open.
5. May the same product appear twice on one request?
6. May the same vendor submit two offers for one item?
7. Should an awarded offer later create a core `purchase.order`?
8. Display name is **Purchase**, which collides with Odoo’s core Purchase app. Confirm the UI name.
9. Relationship to the existing `zvy_tendering` purchase-request models in this repo: replace, coexist, or ignore?

Update this PRD when those answers are known. Do not encode them as decided behavior in code first.
