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
| Quote integrity | ≥3 quotes (standard) / ≥1 (sole source) before CM review |
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
| Supplier portal (view, bid, notify) | Yes (later phase) | 24–26 |
| Auto-route, sequential lock, portal_open, bid seal | Yes | 27–30 |

Delivery phasing: [Roadmap.md](Roadmap.md).

---

## 4. End-to-end process (business)

```text
Planner creates PR
    → Commercial Manager reviews (reject / return / assign experts)
    → Commercial Experts collect quotes (or CE supplier list)
    → CM approves quote set
    → System routes:
         High-value OR commission item → Commission (experts → manager / meeting)
         Else → Company signatory chain
    → Sole source: CEO always in signatory chain
    → CM creates Purchase Order(s)
```

Closed envelope (parallel path where applicable):

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

- [ ] Planner can create a PR with header (requester, company, description) and one or more lines (product, qty, UoM, estimate, sole-source flag where applicable).
- [ ] PR starts in `draft`; Planner can submit → `submitted` / CM queue.
- [ ] External systems can create/submit equivalent PRs via documented web service (XML-RPC/JSON-RPC or REST as implemented).
- [ ] Each PR receives a unique sequence number.

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

- [ ] “Create PO” is available only when PR is `po_ready` and a winning vendor / awarded quotes exist.
- [ ] System creates one or more `purchase.order` records from awarded lines.
- [ ] On success, PR moves to `done`.

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

#### FR-9 AVL-only suppliers *(Story 9)*

| | |
|--|--|
| **As a** | Company Commercial Expert |
| **I want** | To select suppliers exclusively from the AVL |
| **So that** | Inquiry stays compliant |

**Acceptance criteria**

- [ ] Quote and CE supplier fields are domain-restricted to active `zvy.avl.entry` matching product/category (and company).
- [ ] Non-AVL partners cannot be selected.

#### FR-10 Quote collection minima *(Story 10)*

| | |
|--|--|
| **As a** | Company Commercial Expert |
| **I want** | To request and record at least 3 quotes for standard items (or 1 for Sole Source), then submit to CM |
| **So that** | Management can compare offers fairly |

**Acceptance criteria**

- [ ] Standard line: submit blocked until ≥3 quotes recorded.
- [ ] Sole-source line: ≥1 quote required.
- [ ] Submit sends quote set to CM quote review.

#### FR-11 Closed-envelope supplier list *(Story 11)*

| | |
|--|--|
| **As a** | Company Commercial Expert |
| **I want** | To enter suppliers participating in a Closed Envelope tender and submit them for approval |
| **So that** | Holding can validate the invitation list |

**Acceptance criteria**

- [ ] Expert can create a closed-envelope document linked to the PR (or line set) and add AVL suppliers.
- [ ] Submit moves list to Commission Manager approval (`list_pending`).

---

### 5.4 Company Signatories

#### FR-12 Sequential receipt *(Story 12)*

| | |
|--|--|
| **As a** | Company Signatory |
| **I want** | To receive documents requiring my signature in the sequential order defined by the system |
| **So that** | Approvals follow policy order |

**Acceptance criteria**

- [ ] Signatory work is driven by a linked sequential `approval.request` (configured category).
- [ ] A signatory is not asked to act before prior approvers complete.

#### FR-13 Approve or reject *(Story 13)*

| | |
|--|--|
| **As a** | Company Signatory |
| **I want** | To review PR details and approve (sign) or reject, sending it back to the Commercial Manager |
| **So that** | Accountability is clear |

**Acceptance criteria**

- [ ] Approver can open PR context (summary, amounts, attachments) from the approval document.
- [ ] Approve advances the chain; full approval → PR `po_ready`.
- [ ] Refuse returns PR to CM (`cm_review`) with reason.

#### FR-14 CEO on Sole Source *(Story 14)*

| | |
|--|--|
| **As a** | CEO |
| **I want** | To specifically review and sign all Sole Source requests before they proceed |
| **So that** | Non-standard tenders get executive oversight |

**Acceptance criteria**

- [ ] Any PR with sole-source line(s) includes CEO in the signatory chain before `po_ready`.
- [ ] Applies also after Commission approval when that path was used.

---

### 5.5 Commission Manager (Holding)

#### FR-15 High-value / commission dashboard *(Story 15)*

| | |
|--|--|
| **As a** | Commission Manager |
| **I want** | To see all PRs flagged High Value or containing Commission Items |
| **So that** | Holding can review them |

**Acceptance criteria**

- [ ] Dashboard lists open `zvy.commission.case` records for high-value and/or commission-item PRs.
- [ ] Flags are consistent with routing rules (FR-27).

#### FR-16 Assign Commission Experts *(Story 16)*

| | |
|--|--|
| **As a** | Commission Manager |
| **I want** | To assign high-value requests to specific Commission Experts |
| **So that** | Detailed analysis can proceed |

**Acceptance criteria**

- [ ] Manager assigns one or more experts per case.
- [ ] Assigned experts receive the case on their queue.

#### FR-17 Approve without meeting *(Story 17)*

| | |
|--|--|
| **As a** | Commission Manager |
| **I want** | To approve without a meeting when expert reviews are positive and standard |
| **So that** | Low-risk cases are not delayed |

**Acceptance criteria**

- [ ] If all expert recommendations are approve (and no policy block), Manager can approve the case without scheduling a meeting.
- [ ] Approved case advances PR toward signatory stage.

#### FR-18 Meetings and MOM *(Story 18)*

| | |
|--|--|
| **As a** | Commission Manager |
| **I want** | To schedule Commission meetings, aggregate requests, and upload minutes (MOM) |
| **So that** | Deliberations are recorded |

**Acceptance criteria**

- [ ] Manager can create a meeting, link multiple cases, set date/time.
- [ ] Manager can upload MOM attachment after the meeting.
- [ ] Case outcome can be recorded after meeting.

#### FR-19 Select CE winner *(Story 19)*

| | |
|--|--|
| **As a** | Commission Manager |
| **I want** | To select the winning vendor for Closed Envelope tenders and update results |
| **So that** | Award is official |

**Acceptance criteria**

- [ ] Winner selection is allowed only after bids are opened.
- [ ] Selected vendor is stored on the CE / PR award data used for PO creation.
- [ ] Invited suppliers can be notified of results (portal phase).

#### FR-20 Approve CE supplier list *(Story 20)*

| | |
|--|--|
| **As a** | Commission Manager |
| **I want** | To approve the list of suppliers invited to a Closed Envelope tender |
| **So that** | Invitation is fair and controlled |

**Acceptance criteria**

- [ ] Manager can approve or reject the submitted list.
- [ ] Approval requires `opening_datetime` and `bid_deadline` (or equivalent).
- [ ] Approval transitions CE to `portal_open` (FR-29).

---

### 5.6 Commission Expert

#### FR-21 Receive assignments *(Story 21)*

| | |
|--|--|
| **As a** | Commission Expert |
| **I want** | To receive assigned high-value PRs |
| **So that** | I can analyze them |

**Acceptance criteria**

- [ ] Expert sees only cases/reviews assigned to them.

#### FR-22 Verify compliance *(Story 22)*

| | |
|--|--|
| **As a** | Commission Expert |
| **I want** | To verify quote accuracy, Holding policy compliance, and supplier validity |
| **So that** | Recommendations are evidence-based |

**Acceptance criteria**

- [ ] Expert can inspect quotes, PR lines, AVL status, and related attachments.
- [ ] Review form captures notes on accuracy, policy, and suppliers.

#### FR-23 Submit audit report *(Story 23)*

| | |
|--|--|
| **As a** | Commission Expert |
| **I want** | To submit an audit report (approve / reject / request corrections) to the Commission Manager |
| **So that** | The Manager can decide |

**Acceptance criteria**

- [ ] Recommendation is one of: approve, reject, request corrections.
- [ ] Submit notifies / queues for Commission Manager.
- [ ] Corrections path can return work to company quote review as designed.

---

### 5.7 Suppliers (Vendors)

#### FR-24 Supplier portal — view tenders *(Story 24)*

| | |
|--|--|
| **As a** | Supplier |
| **I want** | A dedicated portal to view tender documents and RFQs I was selected for |
| **So that** | I can prepare a bid |

**Acceptance criteria**

- [ ] Portal user linked to vendor partner sees `/my/tenders` invitations only for themselves.
- [ ] Detail shows reference, deadlines, line summary, downloadable published documents.
- [ ] Non-invited portal users see nothing / 403.

#### FR-25 Submit bids *(Story 25)*

| | |
|--|--|
| **As a** | Supplier |
| **I want** | To submit sales proposals securely via the portal before the deadline |
| **So that** | My offer is recorded sealed |

**Acceptance criteria**

- [ ] Bid (price, currency, notes, attachments) accepted while CE is `portal_open` and before `bid_deadline`.
- [ ] Update/withdraw allowed only before deadline and before official opening.
- [ ] After deadline or open: submit rejected with clear error.
- [ ] Bid stored as sealed `zvy.closed.envelope.bid`; other suppliers never see it.

#### FR-26 Supplier notifications *(Story 26)*

| | |
|--|--|
| **As a** | Supplier |
| **I want** | Notifications about tender results or clarification requests |
| **So that** | I stay informed |

**Acceptance criteria**

- [ ] Email (and optional portal note) on portal open / invitation available.
- [ ] Notification when buyer posts a clarification on that supplier’s invitation/bid.
- [ ] Notification of result (awarded / not awarded / cancelled) after winner selection.

---

### 5.8 System (automated rules)

#### FR-27 Auto-routing *(Story 27)*

| | |
|--|--|
| **As a** | System |
| **I want** | To route the PR to Company level or Holding Commission by commodity type and total value |
| **So that** | Manual misrouting is avoided |

**Acceptance criteria**

- [ ] After quote approval: if `is_commission_item` **or** `is_high_value` → create/open commission case.
- [ ] Else → spawn company sequential signatory path.
- [ ] `is_high_value` = total ≥ company configurable threshold.
- [ ] `is_commission_item` from line flag and/or product category flag.

#### FR-28 Sequential approval enforcement *(Story 28)*

| | |
|--|--|
| **As a** | System |
| **I want** | To enforce sequential approval so documents cannot skip signatories |
| **So that** | Policy order is guaranteed |

**Acceptance criteria**

- [ ] PR cannot enter `po_ready` while linked approval is still pending.
- [ ] Approvals module sequential rules are respected; no bypass action for unauthorized roles.

#### FR-29 Open portal after CE list approval *(Story 29)*

| | |
|--|--|
| **As a** | System |
| **I want** | To automatically open the supplier portal for Closed Envelope once the supplier list is approved |
| **So that** | Invited vendors can bid without manual portal toggles |

**Acceptance criteria**

- [ ] On Commission Manager list approval → CE state `portal_open`.
- [ ] Invited suppliers gain portal access per FR-24 (when portal phase is live).
- [ ] Until portal UI ships, backend may still accept manual sealed bid entry by Commission Manager.

#### FR-30 Seal closed-envelope bids *(Story 30)*

| | |
|--|--|
| **As a** | System |
| **I want** | To restrict access to Closed Envelope bids exclusively to the Commission Manager until official opening |
| **So that** | Tender integrity is preserved |

**Acceptance criteria**

- [ ] Before opening: backend users other than Commission Manager (and authorized seal roles) cannot read bid amounts/attachments.
- [ ] Portal supplier may always read **own** bid.
- [ ] After `action_open_bids`, authorized roles can see bids for award.

---

## 6. Business rules

| ID | Rule |
|----|------|
| BR-1 | Inquiry vendors must be on active AVL for the relevant product/category/company. |
| BR-2 | Standard lines require ≥3 quotes before expert submit; sole source ≥1. |
| BR-3 | High-value threshold is company-configurable (not hard-coded). |
| BR-4 | Commission items (line or category) force Holding Commission path. |
| BR-5 | Sole source always requires CEO in signatory chain before PO. |
| BR-6 | PO creation only from `po_ready` with award data set; only Commercial Manager. |
| BR-7 | Closed-envelope bids remain sealed until opening datetime / open action. |
| BR-8 | Signatory refuse returns control to Commercial Manager, not Planner (unless CM then returns). |
| BR-9 | Planner corrections use return path with reason; reject is terminal unless process reopens by policy. |

---

## 7. Non-functional requirements

| Area | Requirement |
|------|-------------|
| Auditability | Status changes, reject/return reasons, assignments, awards, and approvals visible in chatter / linked docs |
| Security | Role-based groups + record rules (expert own lines; commission own cases; sealed bids; portal by partner) |
| Usability | Role-specific dashboards/queues; clear next-action buttons |
| Notifications | Mail/activities for planner, assignees, signatories, and suppliers (portal phase) |
| Extensibility | Web service for PR create/submit; settings for threshold, signatory category, commission flags |
| Testability | Automated tests for quote minima, AVL domain, router, signatory bridge, bid seal, portal isolation |

---

## 8. Configuration (product-facing)

| Setting | Purpose |
|---------|---------|
| High-value threshold | Triggers Holding Commission routing |
| Commission item on product category / line | Triggers Holding Commission routing |
| Approval category (sequential) | Company signatory chain |
| CEO / sole-source approvers | Via category (or equivalent) for FR-14 |
| Default bid window | Suggests `bid_deadline` when CE opens |

---

## 9. User story index

| # | Role | Story (short) | FR |
|---|------|---------------|----|
| 1 | Planner | Create PR (UI / web service) | FR-1 |
| 2 | Planner | Notify on approve / reject / correction | FR-2 |
| 3 | CM | New PRs on dashboard | FR-3 |
| 4 | CM | Reject or return for corrections | FR-4 |
| 5 | CM | Assign lines to Commercial Experts | FR-5 |
| 6 | CM | Review quotes; approve / reject | FR-6 |
| 7 | CM | Create PO after approvals | FR-7 |
| 8 | CCE | View assigned PR items | FR-8 |
| 9 | CCE | AVL-only suppliers | FR-9 |
| 10 | CCE | ≥3 / ≥1 quotes; submit to CM | FR-10 |
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

**Current coverage:** Phase 0 — Foundation; Phase 1 — PR & CM intake.

### Prerequisites

1. Install (or upgrade) `zvy_tendering` (depends: `mail`, `product`, `purchase`, `approvals`, `portal`).
2. As Administrator, open a user form → **Access Rights** (**without** debug mode).
3. Confirm a **Procurement & Tendering** section lists: Planner, Commercial Manager, Commercial Expert, Commission Manager, Commission Expert, Administrator (each as a selectable role). Roles must be assignable here; debug mode must not be required.
4. Prepare two internal users for Phase 1: one with **Planner** only, one with **Commercial Manager** only (same company).

### Phase 0 — Foundation

#### MT-0.1 Install & app shell

| Step | Action | Expected |
|------|--------|----------|
| 1 | Install / upgrade the module | Completes without errors |
| 2 | Open the app switcher as Admin | **Procurement & Tendering** is listed |
| 3 | Open the app | **Purchase Requests** and **Configuration** are visible. **Commission** remains a Phase 3 shell (hidden until children exist) |
| 4 | Open **Configuration** | **Approved Vendor List** and **Settings** are available |

#### MT-0.2 Role groups

| Step | Action | Expected |
|------|--------|----------|
| 1 | On a user form → **Access Rights** (debug **off**), set **Planner** only; save; log in as that user | Sees **Purchase Requests** (All Requests). **Configuration** is not available |
| 2 | Set **Administrator** on another user (or use Admin); save | That user sees **Configuration**; Admin implies all operational roles |
| 3 | Assign Commercial Manager / Expert / Commission roles independently on separate users | Each role appears under Procurement & Tendering and can be combined (roles are not mutually exclusive) |

#### MT-0.3 Tendering settings (PRD §8)

| Step | Action | Expected |
|------|--------|----------|
| 1 | **Configuration → Settings** (or company settings app block for Procurement & Tendering) | Block shows high-value threshold, default bid window (hours), signatory approval category |
| 2 | Set threshold (e.g. `50000`), bid window (e.g. `48`), pick an Approvals category; Save | Values persist after reopen |
| 3 | Open the same company again | Fields match what was saved |

#### MT-0.4 Commission flag on product category

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open any **Product Category** form | **Commission Item** checkbox is visible |
| 2 | Enable it and save; reopen | Flag remains checked |

#### MT-0.5 Approved Vendor List (FR-9 foundation)

| Step | Action | Expected |
|------|--------|----------|
| 1 | **Configuration → Approved Vendor List → New** | Form: vendor, optional product / category, company, validity dates |
| 2 | Create an active entry for the current company | Record appears in the list |
| 3 | Archive the entry (Action → Archive) | Entry hidden from default list; visible with Archived filter |
| 4 | Create entries scoped by product and by category | Both save; list/search can filter by partner, product, category |

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
| 1 | Log in as **Planner** → **Purchase Requests → All Requests → New** | Form opens in `draft`; requester defaults to current user |
| 2 | Enter description; add ≥1 line (product, qty, UoM, price estimate; optional sole source) | Line subtotals and header total estimate compute |
| 3 | Save | Number is assigned (e.g. `PR/2026/00001`), not `New` |
| 4 | Click **Submit** | State → `submitted`; chatter notes submission |
| 5 | Try **Submit** again, or edit description while submitted | Submit/edit blocked (only draft/correction are editable) |

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
| 1 | As an integration / Planner user, call XML-RPC or JSON-RPC `create` on `zvy.purchase.request` with header + `line_ids` | Record created in `draft` with sequence number |
| 2 | Call `action_submit` on that id | State → `submitted`; appears in CM queue |
| 3 | As a CM-only user, attempt `create` | Access denied (no create ACL) |

### Later phases

Not started in the roadmap — no manual scenarios yet:

| Phase | Status | Manual scenarios |
|-------|--------|------------------|
| 2 Inquiry & routing | Not started | — |
| 3 Commission & CE | Not started | — |
| 4 Sign-off & PO | Not started | — |
| 5 Supplier portal | Not started | — |
