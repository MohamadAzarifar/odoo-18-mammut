# zvy_tendering — Product Requirements Document (PRD)

**Product:** Mammut Procurement & Tendering  
**Platform:** Odoo 18 (standalone addon `zvy_tendering`)  
**Status:** Draft for implementation  
**Related:** [Architecture.md](Architecture.md) · [Roadmap.md](Roadmap.md)

---

## 1. Overview

### 1.1 Problem

Purchasing today is fragmented across informal requests, ad-hoc quotes, and unclear approval paths. Planners cannot reliably track Purchase Requests (PRs); commercial teams lack a controlled inquiry process (AVL compliance, quote minima, closed-envelope tenders); Holding Commission review of high-value or policy-sensitive buys is manual; and suppliers have no secure channel for sealed bids.

### 1.2 Solution

A standalone procurement and tendering application on Odoo 18 that:

1. Captures and workflows **Purchase Requests** end to end.
2. Runs **company-level inquiry** (RFQ/quotes) and **closed-envelope** tenders with AVL-only vendors.
3. Routes work automatically to **company signatories** or **Holding Commission** by value and commodity type.
4. Creates standard **Purchase Orders** only after all required approvals.
5. Exposes a **supplier portal** for invited vendors (closed-envelope bids and related notifications).

### 1.3 Goals

| Goal | Success signal |
|------|----------------|
| Controlled PR lifecycle | Every PR moves through defined states; reject/return paths are auditable |
| AVL compliance | No inquiry/CE supplier outside active AVL |
| Quote integrity | ≥3 quotes (standard) or ≥1 with a shortfall reason / ≥1 (sole source) before CM review |
| Correct routing | High-value / commission items always reach Commission; others follow company sign-off |
| Sealed tenders | Closed-envelope bids invisible until official opening (except bidder’s own portal view) |
| Traceable award → PO | Only Commercial Manager creates PO after `po_ready` |

### 1.4 Non-goals (this product revision)

- Using `approval.request` or `purchase.requisition` as the PR document itself.
- External AVL API sync (AVL is maintained in Odoo).
- Replacing standard Odoo `/my/purchase` PO portal (tender portal is separate).
- Sales commission / unrelated modules.

---

## 2. Personas & roles

| Persona | Type | Primary job |
|---------|------|-------------|
| **Planner** | Internal requester | Create/submit PRs; act on corrections |
| **Company Commercial Manager (CM)** | Initial reviewer / owner of PO | Review PRs, assign experts, approve quotes, create PO |
| **Company Commercial Expert (CCE)** | Inquiry officer | Collect AVL quotes; prepare closed-envelope supplier lists |
| **Company Signatory** | Approver (e.g. Finance, CEO) | Sequential approve/refuse on linked approval documents |
| **Commission Manager** | Holding | High-value / commission cases, meetings, CE list approval & award |
| **Commission Expert** | Holding analyst | Audit quotes, policy, suppliers; recommend outcome |
| **Supplier** | External vendor (portal) | View invitations; submit sealed bids; receive results |
| **System** | Automated rules | Routing, sequential enforcement, portal open, bid sealing |

Security groups and technical mapping: see [Architecture.md](Architecture.md).

---

## 3. Scope summary

| Area | In scope | Stories |
|------|----------|---------|
| PR create (UI + web service), notify planner | Yes | 1–2 |
| CM dashboard, reject/return, assign lines, quote review, create PO | Yes | 3–7 |
| Expert inquiry, AVL, quote minima, CE supplier list | Yes | 8–11 |
| Sequential company signatories + CEO on sole source | Yes | 12–14 |
| Commission case, experts, meeting/MOM, CE approve & award | Yes | 15–23 |
| Supplier portal (view, bid, notify) | Yes | 24–26 |
| Auto-route, sequential lock, portal_open, bid seal, mixed-PR split | Yes | 27–31 |

Delivery phasing: [Roadmap.md](Roadmap.md).

---

## 4. End-to-end process (business)

```text
Planner creates PR (products are Enquiry or Tendering)
    → If mixed types: planner must split into two PRs before submit
    → Commercial Manager reviews (reject / return / assign experts)
    → Enquiry: Commercial Experts collect quotes
      Tendering: Commercial Experts prepare closed-envelope supplier list
    → CM approves quote set / CE award
    → System routes:
         High-value OR (Enquiry Need Commission) → Commission (experts → manager / meeting)
         Else → Company signatory chain
    → Sole source: CEO always in signatory chain
    → CM creates Purchase Order(s)
```

Closed envelope (Tendering products only):

```text
Expert submits invited AVL suppliers
    → Commission Manager approves list → portal opens
    → Suppliers bid (portal or manual fallback)
    → Bids sealed until opening
    → Commission Manager opens & selects winner → continues to sign-off / PO
```

---

## 5. Functional requirements by role

Requirements are derived from user stories. Each FR maps to one or more stories.

### 5.1 Planning Unit (Requester)

#### FR-1 Create Purchase Request *(Story 1)*

| | |
|--|--|
| **As a** | Planner |
| **I want** | To create a Purchase Request in the system (or via web service) |
| **So that** | It can be reviewed and processed |

**Acceptance criteria**

- [x] Planner can create a PR with header (requester, company, description) and one or more lines (product, qty, UoM, estimate).
- [x] **Requester** defaults to the creating user, is read-only on the form, and cannot be changed (UI or RPC); create always forces `requester_id = env.user`.
- [x] Line **Sole Source**, **Commission Item**, and **Procurement Type** are computed and read-only (not planner-editable):
  - Sole Source = product has exactly one active AVL vendor for the PR company.
  - Procurement Type = product **Enquiry** or **Tendering** (product default Enquiry).
  - Commission Item = Enquiry product has **Need Commission** checked (default No; hidden on Tendering products).
- [x] PR starts in `draft`; Planner can submit a homogeneous PR → `submitted` / CM queue.
- [x] Mixed Enquiry+Tendering PRs cannot be submitted (FR-31).
- [x] External systems can create/submit equivalent PRs via documented web service (XML-RPC/JSON-RPC or REST as implemented). Mixed `action_submit` raises; call `action_split_mixed` first.
- [x] Each PR receives a unique sequence number.

#### FR-2 Planner notifications *(Story 2)*

| | |
|--|--|
| **As a** | Planner |
| **I want** | Notifications when my PR is approved or rejected (and returned for correction) |
| **So that** | I know next steps or required fixes |

**Acceptance criteria**

- [ ] Planner is notified on reject, return for correction, and terminal approval outcomes that affect their PR.
- [ ] Notifications include PR reference and reason/comment when provided.
- [ ] Planner can reopen/edit and resubmit from `correction` state.

#### FR-31 Split mixed Enquiry/Tendering *(Story 31)*

| | |
|--|--|
| **As a** | Planner |
| **I want** | To be blocked from submitting a PR that mixes Enquiry and Tendering products, and to split it automatically if I accept |
| **So that** | Each request follows a single inquiry path |

**Acceptance criteria**

- [x] Submit is blocked while the PR has both Enquiry and Tendering lines.
- [x] UI Submit opens a confirmation wizard; Cancel leaves the PR unsubmitted.
- [x] If the planner accepts, Tendering lines move to a new draft PR; Enquiry lines stay on the original. Neither PR is auto-submitted.
- [x] RPC `action_submit` raises; callers invoke `action_split_mixed` then submit each PR.

---

### 5.2 Company Commercial Manager

#### FR-3 CM dashboard *(Story 3)*

| | |
|--|--|
| **As a** | Company Commercial Manager |
| **I want** | New PRs on my dashboard |
| **So that** | I can review and process them |

**Acceptance criteria**

- [ ] CM sees queues for new / awaiting review PRs (and correction returnees as designed).
- [ ] Opening a PR shows header, lines, and current status.

#### FR-4 Reject or return *(Story 4)*

| | |
|--|--|
| **As a** | Company Commercial Manager |
| **I want** | To reject a PR or send it back for corrections if incomplete |
| **So that** | The process stays clean |

**Acceptance criteria**

- [ ] CM can **reject** (terminal) with mandatory reason.
- [ ] CM can **return for correction** with mandatory reason; PR returns to Planner.
- [ ] Both actions are logged (chatter/activity).

#### FR-5 Assign line items to experts *(Story 5)*

| | |
|--|--|
| **As a** | Company Commercial Manager |
| **I want** | To assign specific PR line items to one or multiple Commercial Experts |
| **So that** | They can run the inquiry |

**Acceptance criteria**

- [ ] Assignment is per line (or line set); multiple experts allowed across lines.
- [ ] Assigned experts only see their lines for inquiry work.
- [ ] PR moves to inquiry stage once assignment is done (per state machine).

#### FR-6 Review quotes *(Story 6)*

| | |
|--|--|
| **As a** | Company Commercial Manager |
| **I want** | To review prices/quotes collected by the Commercial Expert and approve or reject them |
| **So that** | Only acceptable quotes proceed |

**Acceptance criteria**

- [ ] CM sees all submitted quotes per line (vendor, price, currency, attachments).
- [ ] CM can approve the quote set → routing stage.
- [ ] CM can reject → experts return to inquiry with reason.

#### FR-7 Create Purchase Order *(Story 7)*

| | |
|--|--|
| **As a** | Company Commercial Manager |
| **I want** | To issue the final command to create the PO after all approvals |
| **So that** | Purchasing concludes in standard Odoo POs |

**Acceptance criteria**

- [x] “Create PO” is available only when PR is `po_ready` and a winning vendor / awarded quotes exist.
- [x] System creates one or more `purchase.order` records from awarded lines.
- [x] On success, PR moves to `done`.

---

### 5.3 Company Commercial Expert

#### FR-8 View assigned items *(Story 8)*

| | |
|--|--|
| **As a** | Company Commercial Expert |
| **I want** | To view PR items assigned to me |
| **So that** | I can start requesting quotes |

**Acceptance criteria**

- [ ] Expert dashboard lists only assigned lines/PRs.
- [ ] Expert cannot edit unassigned lines.
- [ ] On assigned lines (inquiry/quote review), product/qty and other intake fields are read-only in the UI; experts can still add/edit quotes while the PR is in `inquiry`.

#### FR-9 AVL-only suppliers *(Story 9)*

| | |
|--|--|
| **As a** | Company Commercial Expert |
| **I want** | To select suppliers exclusively from the AVL |
| **So that** | Inquiry stays compliant |

**Acceptance criteria**

- [ ] Quote and CE supplier fields are domain-restricted to active `zvy.avl.entry` matching product/category (and company).
- [ ] Non-AVL partners cannot be selected — they are absent from the dropdown, not merely rejected on save.

#### FR-10 Quote collection minima *(Story 10)*

| | |
|--|--|
| **As a** | Company Commercial Expert |
| **I want** | To request and record at least 3 quotes for standard items (or 1 for Sole Source), then submit to CM |
| **So that** | Management can compare offers fairly |

**Acceptance criteria**

- [x] Standard **Enquiry** line: submit blocked until ≥3 quotes recorded, **or** ≥1 quote plus a written reason for the shortfall.
- [x] Fewer than 3 quotes (UI): **Submit Quotes** opens a justification wizard; RPC without a reason raises.
- [x] Sole-source Enquiry line (exactly one active AVL vendor for the product/company): ≥1 quote required.
- [x] Submit sends quote set to CM quote review.
- [x] Expert submits **per assigned line**, from My Assignments — no need to open the purchase request.
- [x] The request moves to quote review only once every line has been submitted; the CM cannot submit on the Expert's behalf.
- [x] Tendering PRs cannot collect or submit quotes; they use the closed-envelope path (FR-11).

#### FR-11 Closed-envelope supplier list *(Story 11)*

| | |
|--|--|
| **As a** | Company Commercial Expert |
| **I want** | To enter suppliers participating in a Closed Envelope tender and submit them for approval |
| **So that** | Holding can validate the invitation list |

**Acceptance criteria**

- [x] Expert can create a closed-envelope document linked to a **Tendering** PR (or line set) and add AVL suppliers.
- [x] Submit moves list to Commission Manager approval (`list_pending`).
- [x] Enquiry PRs cannot create a closed envelope.

---

### 5.4 Company Signatories

#### FR-12 Sequential receipt *(Story 12)*

| | |
|--|--|
| **As a** | Company Signatory |
| **I want** | To receive documents requiring my signature in the sequential order defined by the system |
| **So that** | Approvals follow policy order |

**Acceptance criteria**

- [x] Signatory work is driven by a linked sequential `approval.request` (configured category).
- [x] A signatory is not asked to act before prior approvers complete.

#### FR-13 Approve or reject *(Story 13)*

| | |
|--|--|
| **As a** | Company Signatory |
| **I want** | To review PR details and approve (sign) or reject, sending it back to the Commercial Manager |
| **So that** | Accountability is clear |

**Acceptance criteria**

- [x] Approver has the **Signatory** tendering role (`group_zvy_signatory`) and can open PR context (summary, amounts, lines, quotes, awarded quote) from the approval document; PR is read-only.
- [x] Approve advances the chain; full approval → PR `po_ready`.
- [x] Refuse returns PR to CM (`cm_review`) with reason.

#### FR-14 CEO on Sole Source *(Story 14)*

| | |
|--|--|
| **As a** | CEO |
| **I want** | To specifically review and sign all Sole Source requests before they proceed |
| **So that** | Non-standard tenders get executive oversight |

**Acceptance criteria**

- [x] Sole-source lines are detected automatically from AVL (exactly one active vendor for the product/company); planners cannot toggle the flag.
- [x] Any PR with sole-source line(s) includes CEO / company sole-source approver(s) in the signatory chain before `po_ready`.
- [x] Applies also after Commission approval when that path was used.

---

### 5.5 Commission Manager (Holding)

#### FR-15 High-value / commission dashboard *(Story 15)*

| | |
|--|--|
| **As a** | Commission Manager |
| **I want** | To see all PRs flagged High Value or containing Commission Items |
| **So that** | Holding can review them |

**Acceptance criteria**

- [x] Dashboard lists open `zvy.commission.case` records for high-value and/or commission-item PRs.
- [x] Flags are consistent with routing rules (FR-27).

#### FR-16 Assign Commission Experts *(Story 16)*

| | |
|--|--|
| **As a** | Commission Manager |
| **I want** | To assign high-value requests to specific Commission Experts |
| **So that** | Detailed analysis can proceed |

**Acceptance criteria**

- [x] Manager assigns one or more experts per case.
- [x] Assigned experts receive the case on their queue.

#### FR-17 Approve without meeting *(Story 17)*

| | |
|--|--|
| **As a** | Commission Manager |
| **I want** | To approve without a meeting when expert reviews are positive and standard |
| **So that** | Low-risk cases are not delayed |

**Acceptance criteria**

- [x] If all expert recommendations are approve (and no policy block), Manager can approve the case without scheduling a meeting.
- [x] Approved case advances PR toward signatory stage.

#### FR-18 Meetings and MOM *(Story 18)*

| | |
|--|--|
| **As a** | Commission Manager |
| **I want** | To schedule Commission meetings, aggregate requests, and upload minutes (MOM) |
| **So that** | Deliberations are recorded |

**Acceptance criteria**

- [x] Manager can create a meeting, link multiple cases, set date/time.
- [x] Manager can upload MOM attachment after the meeting.
- [x] Case outcome can be recorded after meeting.

#### FR-19 Select CE winner *(Story 19)*

| | |
|--|--|
| **As a** | Commission Manager |
| **I want** | To select the winning vendor for Closed Envelope tenders and update results |
| **So that** | Award is official |

**Acceptance criteria**

- [x] Winner selection is allowed only after bids are opened.
- [x] Selected vendor is stored on the CE / PR award data used for PO creation.
- [x] Invited suppliers can be notified of results (portal phase).

#### FR-20 Approve CE supplier list *(Story 20)*

| | |
|--|--|
| **As a** | Commission Manager |
| **I want** | To approve the list of suppliers invited to a Closed Envelope tender |
| **So that** | Invitation is fair and controlled |

**Acceptance criteria**

- [x] Manager can approve or reject the submitted list.
- [x] Approval requires `opening_datetime` and `bid_deadline` (or equivalent).
- [x] Approval transitions CE to `portal_open` (FR-29).

---

### 5.6 Commission Expert

#### FR-21 Receive assignments *(Story 21)*

| | |
|--|--|
| **As a** | Commission Expert |
| **I want** | To receive assigned high-value PRs |
| **So that** | I can analyze them |

**Acceptance criteria**

- [x] Expert sees only cases/reviews assigned to them.

#### FR-22 Verify compliance *(Story 22)*

| | |
|--|--|
| **As a** | Commission Expert |
| **I want** | To verify quote accuracy, Holding policy compliance, and supplier validity |
| **So that** | Recommendations are evidence-based |

**Acceptance criteria**

- [x] Expert can inspect quotes, PR lines, AVL status, and related attachments.
- [x] Review form captures notes on accuracy, policy, and suppliers.

#### FR-23 Submit audit report *(Story 23)*

| | |
|--|--|
| **As a** | Commission Expert |
| **I want** | To submit an audit report (approve / reject / request corrections) to the Commission Manager |
| **So that** | The Manager can decide |

**Acceptance criteria**

- [x] Recommendation is one of: approve, reject, request corrections.
- [x] Submit notifies / queues for Commission Manager.
- [x] Corrections path can return work to company quote review as designed.

---

### 5.7 Suppliers (Vendors)

#### FR-24 Supplier portal — view tenders *(Story 24)*

| | |
|--|--|
| **As a** | Supplier |
| **I want** | A dedicated portal to view tender documents and RFQs I was selected for |
| **So that** | I can prepare a bid |

**Acceptance criteria**

- [x] Portal user linked to vendor partner sees `/my/tenders` invitations only for themselves.
- [x] Detail shows reference, deadlines, line summary, downloadable published documents.
- [x] Non-invited portal users see nothing / 403.

#### FR-25 Submit bids *(Story 25)*

| | |
|--|--|
| **As a** | Supplier |
| **I want** | To submit sales proposals securely via the portal before the deadline |
| **So that** | My offer is recorded sealed |

**Acceptance criteria**

- [x] Bid (price, currency, notes, attachments) accepted while CE is `portal_open` and before `bid_deadline`.
- [x] Update/withdraw allowed only before deadline and before official opening.
- [x] After deadline or open: submit rejected with clear error.
- [x] Bid stored as sealed `zvy.closed.envelope.bid`; other suppliers never see it.

#### FR-26 Supplier notifications *(Story 26)*

| | |
|--|--|
| **As a** | Supplier |
| **I want** | Notifications about tender results or clarification requests |
| **So that** | I stay informed |

**Acceptance criteria**

- [x] Email (and optional portal note) on portal open / invitation available.
- [x] Notification when buyer posts a clarification on that supplier’s invitation/bid.
- [x] Notification of result (awarded / not awarded / cancelled) after winner selection.

---

### 5.8 System (automated rules)

#### FR-27 Auto-routing *(Story 27)*

| | |
|--|--|
| **As a** | System |
| **I want** | To route the PR to Company level or Holding Commission by commodity type and total value |
| **So that** | Manual misrouting is avoided |

**Acceptance criteria**

- [x] After quote approval: if `is_commission_item` **or** `is_high_value` → create/open commission case.
- [x] Else → spawn company sequential signatory path.
- [x] `is_high_value` = total ≥ company configurable threshold.
- [x] `is_commission_item` = any Enquiry line whose product has **Need Commission** (computed on the line; not a manual line override). Tendering products never set this flag.

#### FR-28 Sequential approval enforcement *(Story 28)*

| | |
|--|--|
| **As a** | System |
| **I want** | To enforce sequential approval so documents cannot skip signatories |
| **So that** | Policy order is guaranteed |

**Acceptance criteria**

- [x] PR cannot enter `po_ready` while linked approval is still pending.
- [x] Approvals module sequential rules are respected; no bypass action for unauthorized roles.

#### FR-29 Open portal after CE list approval *(Story 29)*

| | |
|--|--|
| **As a** | System |
| **I want** | To automatically open the supplier portal for Closed Envelope once the supplier list is approved |
| **So that** | Invited vendors can bid without manual portal toggles |

**Acceptance criteria**

- [x] On Commission Manager list approval → CE state `portal_open`.
- [x] Invited suppliers gain portal access per FR-24 (when portal phase is live).
- [x] Until portal UI ships, backend may still accept manual sealed bid entry by Commission Manager.

#### FR-30 Seal closed-envelope bids *(Story 30)*

| | |
|--|--|
| **As a** | System |
| **I want** | To restrict access to Closed Envelope bids exclusively to the Commission Manager until official opening |
| **So that** | Tender integrity is preserved |

**Acceptance criteria**

- [x] Before opening: backend users other than Commission Manager (and authorized seal roles) cannot read bid amounts/attachments.
- [x] Portal supplier may always read **own** bid.
- [x] After `action_open_bids`, authorized roles can see bids for award.

---

## 6. Business rules

| ID | Rule |
|----|------|
| BR-1 | Inquiry vendors must be on active AVL for the relevant product/category/company. |
| BR-2 | Standard lines require ≥3 quotes before expert submit, or ≥1 with a shortfall reason; sole source (exactly one AVL vendor) ≥1. |
| BR-3 | High-value threshold is company-configurable (not hard-coded). |
| BR-4 | Commission items (Enquiry product **Need Commission**) force Holding Commission path; line flag is computed, not editable. Tendering products have no commission checkbox. |
| BR-5 | Sole source (exactly one active AVL vendor for the line product/company) always requires CEO / sole-source approvers in the signatory chain before PO. |
| BR-6 | PO creation only from `po_ready` with award data set; only Commercial Manager. |
| BR-7 | Closed-envelope bids remain sealed until opening datetime / open action. |
| BR-8 | Signatory refuse returns control to Commercial Manager, not Planner (unless CM then returns). |
| BR-9 | Planner corrections use return path with reason; reject is terminal unless process reopens by policy. |
| BR-10 | A PR may contain only Enquiry or only Tendering products; mixed PRs cannot be submitted until split (FR-31). |

---

## 7. Non-functional requirements

| Area | Requirement |
|------|-------------|
| Auditability | Status changes, reject/return reasons, assignments, awards, and approvals visible in chatter / linked docs |
| Security | Role-based groups + record rules (expert own lines; commission own cases; sealed bids; portal by partner) |
| Usability | Role-specific dashboards/queues; clear next-action buttons |
| Notifications | Mail/activities for planner, assignees, signatories, and suppliers (portal phase) |
| Extensibility | Web service for PR create/submit; settings for threshold, signatory category, product procurement type / commission |
| Testability | Automated tests for quote minima, AVL domain, router, signatory bridge, bid seal, portal isolation |

---

## 8. Configuration (product-facing)

| Setting | Purpose |
|---------|---------|
| High-value threshold | Triggers Holding Commission routing |
| Product procurement type (Enquiry / Tendering) | Forces quote inquiry vs closed-envelope path; mixed PRs cannot submit |
| Need Commission on Enquiry product | Sets line/header `is_commission_item` (computed); triggers Holding Commission routing |
| Active AVL (one vendor for product/company) | Sets line `sole_source` (computed); quote minimum becomes ≥1 |
| Approval category (sequential) | Company signatory chain |
| CEO / sole-source approvers | Injected last in signatory chain when PR has sole-source lines (FR-14) |
| Default bid window | Suggests `bid_deadline` when CE opens |

---

## 9. User story index

| # | Role | Story (short) | FR |
|---|------|---------------|----|
| 1 | Planner | Create PR (UI / web service) | FR-1 |
| 2 | Planner | Notify on approve / reject / correction | FR-2 |
| 31 | Planner | Split mixed Enquiry/Tendering PRs | FR-31 |
| 3 | CM | New PRs on dashboard | FR-3 |
| 4 | CM | Reject or return for corrections | FR-4 |
| 5 | CM | Assign lines to Commercial Experts | FR-5 |
| 6 | CM | Review quotes; approve / reject | FR-6 |
| 7 | CM | Create PO after approvals | FR-7 |
| 8 | CCE | View assigned PR items | FR-8 |
| 9 | CCE | AVL-only suppliers | FR-9 |
| 10 | CCE | ≥3 / ≥1+reason / ≥1 sole source; submit to CM | FR-10 |
| 11 | CCE | Closed Envelope supplier list | FR-11 |
| 12 | Signatory | Sequential documents | FR-12 |
| 13 | Signatory | Approve or reject → CM | FR-13 |
| 14 | CEO | Sign all Sole Source | FR-14 |
| 15 | Comm. Mgr | High Value / Commission dashboard | FR-15 |
| 16 | Comm. Mgr | Assign Commission Experts | FR-16 |
| 17 | Comm. Mgr | Approve without meeting | FR-17 |
| 18 | Comm. Mgr | Meetings + MOM | FR-18 |
| 19 | Comm. Mgr | Select CE winner | FR-19 |
| 20 | Comm. Mgr | Approve CE supplier list | FR-20 |
| 21 | Comm. Exp | Receive assigned cases | FR-21 |
| 22 | Comm. Exp | Verify quotes / policy / AVL | FR-22 |
| 23 | Comm. Exp | Submit audit report | FR-23 |
| 24 | Supplier | Portal: view tenders / RFQs | FR-24 |
| 25 | Supplier | Portal: submit bids before deadline | FR-25 |
| 26 | Supplier | Portal: results & clarifications | FR-26 |
| 27 | System | Route by type & value | FR-27 |
| 28 | System | Enforce sequential approvals | FR-28 |
| 29 | System | Open portal after CE list approved | FR-29 |
| 30 | System | Seal CE bids until opening | FR-30 |

---

## 10. Open questions / assumptions

| Topic | Assumption (locked unless revisited) |
|-------|--------------------------------------|
| PR document | Standalone `zvy.purchase.request` |
| Signatories | Hybrid Approvals only for Stories 12–14 |
| AVL | In-Odoo `zvy.avl.entry` |
| First delivery | Backend Stories 1–23, 27–30; portal UI 24–26 follows |
| Final PO | Standard `purchase.order` |

Details and model design: [Architecture.md](Architecture.md). Phasing and checklist: [Roadmap.md](Roadmap.md).

---

## 11. Manual testing

Scenarios track [Roadmap.md](Roadmap.md) progress. Expand this section when each phase is marked Done.

**Current coverage:** Phase 0 — Foundation; Phase 1 — PR & CM intake; Phase 2 — Inquiry & routing; Phase 3 — Commission & CE; Phase 4 — Sign-off & PO; Phase 5 — Supplier portal.

### Prerequisites

1. Install (or upgrade) `zvy_tendering` (depends: `mail`, `product`, `purchase`, `approvals`, `portal`).
2. As Administrator, open a user form → **Access Rights** (**without** debug mode).
3. Confirm a **Procurement & Tendering** section lists: Planner, Commercial Manager, Commercial Expert, Signatory, Commission Manager, Commission Expert, Administrator (each as a selectable role). Roles must be assignable here; debug mode must not be required.
4. Prepare users for Phases 1–2 (same company): **Planner** only, **Commercial Manager** only, **Commercial Expert** only (optionally a second Expert for assignment isolation).
5. For Phase 2: ensure ≥3 active **AVL** vendors for the company (and product/category as needed); set a known **high-value threshold** in Settings.
6. For Phase 3: prepare **Commission Manager** and **Commission Expert** users; confirm Settings **default bid window (hours)**.
7. For Phase 4: create a sequential **Approvals** category (Approvers Sequence on; ≥1 required approver); set it as **Signatory Approval Category** in Tendering Settings. Assign the **Signatory** role to those approvers and to Sole-Source Approver(s) (e.g. CEO). Commercial Manager implies Purchase User so they can open created POs.
8. For Phase 5: create **Portal** users linked to ≥2 invited AVL vendors (and one non-invited portal vendor). Ensure those partners have email addresses. Website/portal must be reachable so suppliers can open `/my` and `/my/tenders`.

### Phase 0 — Foundation

#### MT-0.1 Install & app shell

| Step | Action | Expected |
|------|--------|----------|
| 1 | Install / upgrade the module | Completes without errors |
| 2 | Open the app switcher as Admin | **Procurement & Tendering** is listed |
| 3 | Open the app | **Purchase Requests** and **Configuration** are visible. **Commission** shows Cases / Meetings / Closed Envelopes for commission roles |
| 4 | Open **Configuration** | **Approved Vendor List** and **Settings** are available |

#### MT-0.2 Role groups

| Step | Action | Expected |
|------|--------|----------|
| 1 | On a user form → **Access Rights** (debug **off**), set **Planner** only; save; log in as that user | Sees **Purchase Requests** (All Requests). **Configuration** is not available |
| 2 | Set **Administrator** on another user (or use Admin); save | That user sees **Configuration**; Admin implies all operational roles |
| 3 | Assign Commercial Manager / Expert / Signatory / Commission roles independently on separate users | Each role appears under Procurement & Tendering and can be combined (roles are not mutually exclusive). **Signatory** has no Tendering menus; opens PR from Approvals only |

#### MT-0.3 Tendering settings (PRD §8)

| Step | Action | Expected |
|------|--------|----------|
| 1 | **Configuration → Settings** (or company settings app block for Procurement & Tendering) | Block shows high-value threshold, default bid window (hours), signatory approval category, sole-source approvers |
| 2 | Set threshold (e.g. `50000`), bid window (e.g. `48`), pick a sequential Approvals category, set sole-source approver(s); Save | Values persist after reopen |
| 3 | Open the same company again | Fields match what was saved |

#### MT-0.4 Product procurement type and commission (FR-1 / BR-4)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open any **Product** form | **Procurement Type** (Enquiry / Tendering) is visible; default **Enquiry** |
| 2 | Leave Enquiry; confirm **Need Commission** is visible and unchecked | Default is do not need commission |
| 3 | Enable **Need Commission**; save; reopen | Flag remains checked |
| 4 | Switch type to **Tendering** | **Need Commission** disappears and is cleared |
| 5 | As Planner, create a PR line with an Enquiry product that needs commission | Line **Commission Item** is checked and read-only; header `is_commission_item` is true |
| 6 | Create a PR line with a Tendering product | Line **Procurement Type** is Tendering; **Commission Item** is false |

#### MT-0.5 Approved Vendor List (FR-9 foundation)

| Step | Action | Expected |
|------|--------|----------|
| 1 | **Configuration → Approved Vendor List → New** | Form: vendor, optional product / category, company, validity dates |
| 2 | Create an active entry for the current company | Record appears in the list |
| 3 | Archive the entry (Action → Archive) | Entry hidden from default list; visible with Archived filter |
| 4 | Create entries scoped by product and by category | Both save; list/search can filter by partner, product, category |
| 5 | Ensure a product has **exactly one** active AVL vendor for the company; add that product on a draft PR line | Line **Sole Source** is checked and read-only |
| 6 | Add a second active AVL vendor that covers the same product; reopen the draft line | **Sole Source** clears automatically |

#### MT-0.6 Multi-company AVL isolation

| Step | Action | Expected |
|------|--------|----------|
| 1 | Create Company A and Company B; add one AVL vendor entry per company | Two entries exist (as Admin / multi-company user) |
| 2 | Log in as a user allowed only on Company A, with Tendering Admin | User sees Company A’s AVL entry only; Company B’s entry is not in search results |

#### MT-0.7 PR sequence

| Step | Action | Expected |
|------|--------|----------|
| 1 | Technical → Sequences (or Settings with developer mode): find code `zvy.purchase.request` | Sequence exists with prefix `PR/%(year)s/` and padding 5 |

### Phase 1 — PR & CM intake

#### MT-1.1 Create & submit PR (FR-1)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Log in as **Planner** → **Purchase Requests → All Requests → New** | Form opens in `draft`; **Requester** is current user and not editable |
| 2 | Enter description; add ≥1 line (product, qty, UoM, price estimate) | Line subtotals and header total estimate compute; **Sole Source** / **Commission Item** / **Procurement Type** are read-only and filled from AVL / product |
| 3 | Try to change **Requester** (UI) | Field remains locked to the creating user |
| 4 | Save | Number is assigned (e.g. `PR/2026/00001`), not `New` |
| 5 | Click **Submit** | State → `submitted`; chatter notes submission |
| 6 | Try **Submit** again, or edit description while submitted | Submit/edit blocked (only draft/correction are editable) |

#### MT-1.2 CM queue (FR-3)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Log in as **Commercial Manager** → **Purchase Requests → Awaiting Review** | Submitted PR from MT-1.1 appears (domain: `submitted` / `cm_review`) |
| 2 | Open the PR | Header, lines, and status are visible; **Reject** and **Return for Correction** are available |
| 3 | As Planner, open **Awaiting Review** | Menu is not available (CM-only) |

#### MT-1.3 Reject with reason (FR-4 / FR-2)

| Step | Action | Expected |
|------|--------|----------|
| 1 | As CM on a submitted PR, click **Reject** without a reason and confirm | Wizard requires a reason |
| 2 | Enter a reason and confirm | State → `rejected`; reason stored; chatter logs reject |
| 3 | Switch to Planner | Activity / notification references the PR and reason; PR is no longer editable |

#### MT-1.4 Return for correction & resubmit (FR-4 / FR-2)

| Step | Action | Expected |
|------|--------|----------|
| 1 | As Planner, create and submit another PR | State `submitted` |
| 2 | As CM, **Return for Correction** with a mandatory reason | State → `correction`; reason stored; chatter logs return; planner gets activity |
| 3 | As Planner, edit description or lines; **Submit** again | State → `submitted`; PR reappears in CM **Awaiting Review** |

#### MT-1.5 Planner own-record isolation

| Step | Action | Expected |
|------|--------|----------|
| 1 | As Planner A, create a draft PR | Visible under All Requests (My Requests) |
| 2 | As Planner B (same company), open All Requests | Planner A’s PR is not visible |
| 3 | As CM, open All Requests / Awaiting Review | Sees both planners’ company PRs |

#### MT-1.6 Web service create + submit (FR-1)

| Step | Action | Expected |
|------|--------|----------|
| 1 | As an integration / Planner user, call XML-RPC or JSON-RPC `create` on `zvy.purchase.request` with header + `line_ids` (optionally passing another `requester_id`) | Record created in `draft` with sequence number; **requester is always the authenticated user** (spoofed `requester_id` ignored) |
| 2 | Call `action_submit` on that id | State → `submitted`; appears in CM queue |
| 3 | As a CM-only user, attempt `create` | Access denied (no create ACL) |

#### MT-1.7 Mixed Enquiry/Tendering split (FR-31)

| Step | Action | Expected |
|------|--------|----------|
| 1 | As Planner, create a draft PR with one Enquiry product and one Tendering product | Header shows mixed; warning that submit will require a split |
| 2 | Click **Submit** | Wizard explains they must split; **Cancel** leaves the PR in `draft` |
| 3 | Click **Submit** again, then **Split** | Original keeps Enquiry lines and its number; a new draft PR holds Tendering lines; neither is submitted; chatter links the siblings |
| 4 | Submit each PR separately | Both appear in the CM queue |
| 5 | Via RPC, `action_submit` a mixed PR without splitting | Error; `action_split_mixed` then submit each |

### Phase 2 — Inquiry & routing

#### MT-2.1 Assign experts → inquiry (FR-5)

| Step | Action | Expected |
|------|--------|----------|
| 1 | As Planner, create a PR with ≥1 line; **Submit** | State `submitted`; appears in CM **Awaiting Review** |
| 2 | As CM, open the PR → **Assign Experts** | Wizard lists each line with Commercial Expert many2many |
| 3 | Leave experts blank and confirm | Validation: every line needs ≥1 expert |
| 4 | Assign one or more Experts per line; confirm | State → `inquiry`; line `expert_user_ids` set; chatter notes assignment; assigned experts get a todo activity |
| 5 | As CM, open the same PR again | **Assign Experts** still available (re-assign while in inquiry) |

#### MT-2.2 Expert dashboard & isolation (FR-8)

| Step | Action | Expected |
|------|--------|----------|
| 1 | As the assigned **Commercial Expert** → **Purchase Requests → My Assignments** | Only lines assigned to this user appear (parent in `inquiry` / `quote_review`) |
| 2 | Open an assigned line / related PR | Can add and save quotes on assigned lines; product/qty/expert/**Sole Source**/**Commission Item** fields are greyed out (read-only), not editable-then-rejected |
| 3 | As a second Expert **not** assigned to that PR | PR / line not visible; cannot create quotes on those lines |
| 4 | As Expert, open **Awaiting Review** / **Quote Review** | Menus not available (CM-only) |

#### MT-2.3 AVL-only quotes (FR-9 / BR-1)

| Step | Action | Expected |
|------|--------|----------|
| 1 | As assigned Expert → **My Assignments** → open a line → **Quotes** → add a quote and save | Quote saves while the PR is in `inquiry`; vendor dropdown lists **only** active AVL vendors for the company (+ product/category scope) — not all contacts; creating a new contact from the dropdown is disabled |
| 1b | As the same Expert, open the PR → **Quotes** tab | Read-only, with a hint pointing to My Assignments (experts cannot write the PR); as CM the same tab is editable in `inquiry` |
| 2 | Try to save a quote with a non-AVL vendor (e.g. via RPC or forced partner) | Validation error: vendor not on active AVL |
| 3 | Save quotes with ≥3 distinct AVL vendors (standard line) | Quotes stored in `draft` with unit price / total; **Recorded By** = current Expert (read-only); **State** = Draft (read-only, advanced by Submit Quotes / CM actions) |

#### MT-2.4 Quote minima & submit (FR-10 / BR-2)

| Step | Action | Expected |
|------|--------|----------|
| 1 | As Expert → **My Assignments** → open a line with only 1–2 quotes → **Submit Quotes** | Wizard asks for a reason; submit is blocked until a reason is given (or a third quote is added). Zero quotes stay blocked. |
| 2 | Enter a reason and confirm, or add a third quote; **Submit Quotes** (from the line form or the row button in My Assignments) | Line shows **Quotes Submitted**; quotes move to `submitted`; shortfall reason is stored on the line when used; chatter notes which line was submitted |
| 3 | When **every** line of the PR is submitted | PR state → `quote_review` automatically; chatter notes all quote sets submitted |
| 4 | On a PR whose lines are split between two Experts, have only one submit | PR stays in `inquiry` until the second Expert submits their line |
| 5 | As **CM**, try **Submit Quotes** | Not available / refused — the CM reviews, Experts submit |
| 6 | Create another PR whose product has **exactly one** active AVL vendor (Sole Source auto-checked); assign Expert; record **1** AVL quote; **Submit Quotes** | Allowed (≥1); line submitted and PR → `quote_review` |

#### MT-2.5 CM reject quotes (FR-6)

| Step | Action | Expected |
|------|--------|----------|
| 1 | As CM → **Purchase Requests → Quote Review** | Submitted PR from MT-2.4 appears |
| 2 | Open PR → **Reject Quotes** without a reason | Wizard requires a reason |
| 3 | Enter a reason and confirm | State → `inquiry`; reason stored; quotes back to `draft`; assigned experts get an activity; chatter logs reject |

#### MT-2.6 CM approve → company path (FR-6 / FR-27)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Ensure company **high-value threshold** is above the PR total; lines are **not** commission items | Routing flags: not high value, not commission item |
| 2 | Bring a PR through inquiry with valid quote minima → `quote_review` | Ready for CM |
| 3 | As CM → **Purchase Requests → Quote Review** → open the PR | Status is `quote_review`; header shows **Approve Quotes** / **Reject Quotes**; info banner explains the steps |
| 4 | On each line’s **Quotes**, click **Select as Awarded** on the winning vendor (or set **Awarded Quote** many2one — shows vendor name + price, no Create) | Awarded quote set; other quotes on that line → `rejected`; chatter notes the selection |
| 5 | Click header **Approve Quotes** | Winning quote → `accepted`; state → `signatory`; linked sequential `approval.request` created; chatter notes routing |
| 6 | Try **Approve Quotes** without selecting awarded quotes | Validation: awarded quote required on every line |

#### MT-2.7 CM approve → Holding Commission (FR-27)

| Step | Action | Expected |
|------|--------|----------|
| 1 | **High value:** set threshold below PR total estimate; complete inquiry + quote review; **Approve Quotes** | State → `commission`; `zvy.commission.case` created (e.g. `CASE/…`); case linked on PR; `reason_high_value` set |
| 2 | **Commission item:** use an Enquiry product with **Need Commission** (line flag auto-checked, read-only); keep total below threshold; approve quotes | State → `commission`; case has `reason_commission_item` |
| 3 | Open the linked commission case (Admin / Commission Manager) | Case in `open` with request link and routing reason flags; Assign Experts and decision buttons available |

### Phase 3 — Holding Commission & closed envelope

#### MT-3.1 Commission dashboard & assign experts (FR-15 / FR-16 / FR-21)

| Step | Action | Expected |
|------|--------|----------|
| 1 | As Commission Manager → **Commission → Cases** | High-value / commission-item cases from MT-2.7 appear |
| 2 | Open a case; set Commission Experts; **Assign Experts** | State → `in_review`; draft reviews created; experts get activities |
| 3 | As Commission Expert → **My Assignments** / **My Reviews** | Only assigned case/review visible |

#### MT-3.2 Expert review & approve without meeting (FR-17 / FR-22 / FR-23)

| Step | Action | Expected |
|------|--------|----------|
| 1 | As Commission Expert, open review; fill accuracy/policy/suppliers notes; recommendation **Approve**; **Submit Review** | Review `submitted`; case chatter notes submission |
| 2 | As Commission Manager, **Approve Without Meeting** | Case `approved`; PR → `signatory` with linked sequential `approval.request` |
| 3 | On another case where an expert recommended corrections, try **Approve Without Meeting** | Blocked until all reviews approve |

#### MT-3.3 Meeting + corrections (FR-18)

| Step | Action | Expected |
|------|--------|----------|
| 1 | As Commission Manager → **Meetings → New**; link open/in-review cases; set datetime; save | Linked cases move to `meeting`; MOM attachments can be uploaded |
| 2 | On a meeting case, **Request Corrections** | Case `corrections`; PR → `quote_review` |

#### MT-3.4 Closed envelope list (FR-11 / FR-20 / FR-29)

| Step | Action | Expected |
|------|--------|----------|
| 1 | As CCE on a **Tendering** inquiry PR, **Closed Envelope**; add ≥1 AVL invite; **Submit List** | CE `list_pending`; linked on PR |
| 2 | As Commission Manager, approve list without opening datetime | Validation error |
| 3 | Set opening datetime (bid deadline optional); **Approve List** | State → `portal_open`; deadline defaults from Settings bid window if empty |
| 4 | As CCE on an **Enquiry** inquiry PR | **Closed Envelope** is not available |

#### MT-3.5 Sealed bids, open, award (FR-19 / FR-30)

| Step | Action | Expected |
|------|--------|----------|
| 1 | As Commission Manager, enter a manual bid with amount while `portal_open` | Bid stored |
| 2 | As CCE (or non-manager), read the bid amount | Amount hidden / zero before open |
| 3 | After opening datetime, **Open Bids**; set winner; **Select Winner** | CE `awarded`; PR `award_partner_id` set; PR → `quote_review`. Winner before open is blocked |

### Phase 4 — Sign-off & Purchase Order

#### MT-4.1 Company path → sequential approval (FR-12 / FR-13 / FR-28)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Complete MT-2.6 (company path; award quotes; approve) | PR `signatory`; **Signatory** smart button opens linked `approval.request` |
| 2 | Open the approval as the **first** signatory | Status pending for that user; later approvers are waiting (sequential) |
| 3 | As a later approver, try to approve before prior signatories | Blocked (cannot approve while waiting) |
| 4 | Approve in order until the chain completes | Approval `approved`; PR → `po_ready`; chatter notes sign-off complete |
| 5 | As Admin/CM, try to force PR to `po_ready` while approval is still pending | Transition blocked (FR-28) |

#### MT-4.2 Refuse → CM review & resubmit (FR-13 / BR-8)

| Step | Action | Expected |
|------|--------|----------|
| 1 | On another company-path PR in `signatory`, as a pending signatory click **Refuse** | Approval `refused`; PR → `cm_review` (not Planner); chatter notes refuse |
| 2 | As CM on that PR | **Resubmit to Signatories**, Reject, Return for Correction, Assign Experts available |
| 3 | **Resubmit to Signatories** | New `approval.request` spawned; PR → `signatory` again |
| 4 | Complete the new chain | PR → `po_ready` |

#### MT-4.3 Sole source includes CEO (FR-14 / BR-5)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Create a PR with a product that has exactly one active AVL vendor (**Sole Source** auto-checked); collect ≥1 quote; award; approve (company path, below high-value threshold) | PR `signatory`; approval approvers include category signatories **and** company Sole-Source Approver(s) as required, last in sequence |
| 2 | Approve category signatories only | PR stays `signatory` until CEO / sole-source approver(s) approve |
| 3 | CEO approves last | PR → `po_ready` |
| 4 | Repeat after a Holding Commission approve (high-value sole-source PR) | Same CEO inject on the post-commission signatory document |

#### MT-4.4 Create PO (FR-7 / BR-6)

| Step | Action | Expected |
|------|--------|----------|
| 1 | On a `po_ready` PR with awarded quotes, as **Commercial Expert** try **Create PO** | Not available / refused |
| 2 | As CM on a `signatory` (not yet `po_ready`) PR, try **Create PO** | Not available / blocked |
| 3 | As CM on `po_ready`, **Create PO** | One or more draft `purchase.order` created (grouped by awarded vendor); lines use awarded quote prices; `origin` = PR number; `zvy_purchase_request_id` set; PR → `done`; **POs** smart button opens the order(s) |
| 4 | CE path: after MT-3.5 award + CM **Approve Quotes** (no line awards needed) → signatory → approve → **Create PO** | Single PO to `award_partner_id`; PR → `done` |

#### MT-4.5 Commission → signatory → PO (end-to-end)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Route a high-value PR through commission (MT-3.2 approve without meeting) | PR `signatory` with approval linked |
| 2 | Complete signatory chain | PR `po_ready` |
| 3 | As CM, **Create PO** | PO(s) created; PR `done` |

### Phase 5 — Supplier portal

#### MT-5.1 Portal view & isolation (FR-24)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Complete MT-3.4 through **Approve List** (`portal_open`); optionally attach **Published Documents** on the CE | CE open for bidding; invitees notified (see MT-5.4) |
| 2 | Log in as an **invited** portal vendor → `/my` | **Tenders** entry appears with a non-zero count |
| 3 | Open `/my/tenders` | Only this vendor’s invitations appear (reference, deadlines, status) |
| 4 | Open the tender detail | Shows reference, bid deadline, opening datetime, PR line summary, downloadable published documents |
| 5 | Log in as a **non-invited** portal user → `/my/tenders` | Empty list (no invitations) |
| 6 | As non-invited user, open `/my/tenders/<id>` for an invite-only CE (guessed id) | Redirected / access denied (not readable) |

#### MT-5.2 Submit / update / withdraw sealed bid (FR-25 / FR-30)

| Step | Action | Expected |
|------|--------|----------|
| 1 | As invited portal vendor on a `portal_open` tender before deadline, enter amount (+ optional notes / attachments); **Submit bid** | Bid stored as `zvy.closed.envelope.bid` with `source=portal`; success message shown |
| 2 | Change amount / notes; **Update bid** | Same bid updated; `submitted_at` refreshed |
| 3 | As a **second** invited portal vendor, open the same tender | Sees only own bid form — never sees the first vendor’s amount |
| 4 | As Commission Manager / CCE in backend before open | First vendor’s amount sealed for non-managers (FR-30 unchanged) |
| 5 | As first vendor, **Withdraw bid** while still open | Bid removed; can submit again while window is open |

#### MT-5.3 Deadline and post-open rejection (FR-25)

| Step | Action | Expected |
|------|--------|----------|
| 1 | On a CE still `portal_open`, set **Bid Deadline** in the past (as CM/Admin); as portal vendor try submit/update/withdraw | Clear error: bidding closed |
| 2 | Restore a future deadline; submit a bid; after **Opening Datetime**, as CM **Open Bids** | CE → `opened` |
| 3 | As portal vendor, try submit / update / withdraw | Clear error: bidding closed / cannot withdraw |

#### MT-5.4 Notifications (FR-26)

| Step | Action | Expected |
|------|--------|----------|
| 1 | On **Approve List** (MT-3.4 / MT-5.1) | Each invited partner with email receives invitation mail with portal link; CE chatter notes portal open |
| 2 | As Commission Manager on `portal_open` / `opened` CE → **Post Clarification**; enter body; confirm | Clarification on CE chatter; invitees receive clarification mail |
| 3 | After open + **Select Winner** | Winner receives awarded mail; other invitees receive not-awarded mail |
| 4 | On another CE in `portal_open`, **Cancel** | Invitees receive cancelled mail; portal detail shows cancelled banner |

#### MT-5.5 Portal CE path end-to-end (no manual bid)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Inquiry PR → CE list → approve → portal open (MT-3.4) | Invitees can bid on `/my/tenders` |
| 2 | ≥1 invited vendor submits a sealed portal bid (MT-5.2) | Bid `source=portal` visible to CM after open |
| 3 | After opening datetime: **Open Bids** → set winner → **Select Winner** | CE `awarded`; PR `award_partner_id` + `quote_review` |
| 4 | Continue MT-4.4 CE path (approve quotes → signatory → **Create PO**) | PO to winner without relying on manual CM bid entry |
