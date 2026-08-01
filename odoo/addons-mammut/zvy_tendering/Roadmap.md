# zvy_tendering — Implementation Roadmap

**Product:** Mammut Procurement & Tendering  
**Related:** [README.md](README.md) (PRD) · [Architecture.md](Architecture.md) (design)

Phasing follows PRD §10: backend Stories **1–23** and **27–30** first; supplier portal Stories **24–26** last. Each phase lists stories/FRs, checklists, suggested tests, and exit criteria. Dependency order: foundation → PR/CM intake → inquiry & routing → commission & CE seal → sign-off & PO → portal UI.

---

## Phase overview

| Phase | Focus | Stories / FRs | Depends on |
|-------|--------|---------------|------------|
| **0 — Foundation** | Module shell, groups, settings, sequences, AVL | Config §8; foundation for FR-9 | — |
| **1 — PR & CM intake** | PR lifecycle, CM queues, reject/return, planner notify | 1–4 (FR-1..4) | 0 |
| **2 — Inquiry & routing** | Assign experts, AVL quotes, minima, CM quote review, auto-route | 5–6, 8–10, 27 | 1 |
| **3 — Holding Commission** | Cases, reviews, meetings, CE list/seal/open/award (manual bids) | 11, 15–23, 29–30 | 2 |
| **4 — Sign-off & PO** | Sequential Approvals, CEO sole source, create PO | 7, 12–14, 28 | 2 (and 3 if commission path) |
| **5 — Supplier portal** | `/my/tenders`, sealed submit, notifications | 24–26 | 3 |

**First delivery (MVP backend):** Phases 0–4 complete.  
**Second delivery:** Phase 5.

---

## Phase 0 — Foundation

**Goal:** Installable addon with security, config, and AVL so later phases have somewhere to hang data.

### Scope

- [x] `__manifest__.py` with depends: `mail`, `product`, `purchase`, `approvals`, `portal`
- [x] Module category + groups (Planner, CM, CCE, Commission Manager/Expert, Admin) — [Architecture.md](Architecture.md) §5
- [x] ACL CSV stubs for models introduced in later phases (or create models empty and ACL as they land)
- [x] Multi-company record-rule pattern
- [x] Menus shell (Procurement & Tendering)
- [x] `res.company` / `res.config.settings`: high-value threshold, default bid window, signatory approval category
- [x] `product.category.zvy_is_commission_item`
- [x] `ir.sequence` for PR (and CE/case if needed)
- [x] `zvy.avl.entry` CRUD + views (active vendor by company / product / category)

### Stories / FRs

| Item | Notes |
|------|--------|
| PRD §8 Configuration | All product-facing settings editable |
| FR-9 foundation | AVL model exists for Phase 2 domains |

### Suggested tests

- [x] Settings write/read on company
- [x] AVL `active` filter; multi-company isolation

### Done when

Module installs cleanly; Admin can maintain AVL and thresholds; role groups assignable to users.

---

## Phase 1 — PR & CM intake

**Goal:** Planner creates/submits PRs; CM sees queues and can reject or return; planner notified and can correct.

### Scope

- [x] Models: `zvy.purchase.request`, `zvy.purchase.request.line`
- [x] States: `draft`, `submitted`, `cm_review`, `correction`, `rejected` (other states stubbed or blocked until later)
- [x] Actions: submit, reject (mandatory reason), return for correction (mandatory reason)
- [x] Sequence number on create (FR-1)
- [x] CM dashboard / list filters for new & awaiting review
- [x] Planner notifications (mail/activity) on reject, return, and relevant terminal outcomes (FR-2)
- [x] Chatter logging for reject/return
- [x] Web service: create + `action_submit` via RPC (FR-1)
- [x] Record rules: planner own PRs; CM all company PRs

### Stories / FRs checklist

- [x] **Story 1 / FR-1** — Create PR (UI + web service); unique sequence; draft → submitted
- [x] **Story 2 / FR-2** — Notify planner on reject / return / outcomes; edit & resubmit from `correction`
- [x] **Story 3 / FR-3** — CM dashboard of new / awaiting review PRs
- [x] **Story 4 / FR-4** — Reject (terminal) or return with mandatory reason; logged

### Suggested tests

- [x] Submit moves to CM queue
- [x] Reject requires reason → `rejected`
- [x] Return → `correction`; planner can resubmit
- [x] RPC create/submit with ACL user

### Done when

Acceptance criteria for FR-1..4 are met; planner and CM can run the intake loop without inquiry yet.

---

## Phase 2 — Inquiry & routing

**Goal:** CM assigns lines to experts; experts collect AVL-only quotes with minima; CM approves/rejects quote set; system routes to commission vs signatory (signatory spawn can stub until Phase 4).

### Scope

- [x] Line `expert_user_ids`; assign wizard/action (FR-5); PR → `inquiry`
- [x] Expert dashboard: only assigned lines (FR-8)
- [x] Assigned-line / quote forms: product/qty/expert (and quote fields outside inquiry) UI-readonly via `request_state` — no edit-then-error UX
- [x] `zvy.quote` with AVL domain (FR-9 / BR-1) — vendor picker filtered by computed `allowed_partner_ids`, not an onchange domain
- [x] Quote minima: ≥3 standard / ≥1 sole source before submit (FR-10 / BR-2)
- [x] Expert submit → `quote_review`
- [x] Per-line submit by the assigned expert; PR advances to `quote_review` only when all lines are submitted (CM cannot submit)
- [x] CM approve quotes → `_action_route_after_quotes` (FR-27); CM reject quotes → back to `inquiry` with reason (FR-6)
- [x] Compute `is_high_value`, `is_commission_item`, `has_sole_source`
- [x] On route to commission: create `zvy.commission.case` shell (full UX in Phase 3) **or** set state `commission` ready for Phase 3
- [x] On route to company path: set state `signatory` placeholder / spawn Approvals in Phase 4

### Stories / FRs checklist

- [x] **Story 5 / FR-5** — Assign lines to one or more Commercial Experts
- [x] **Story 6 / FR-6** — CM review quotes; approve → routing; reject → inquiry
- [x] **Story 8 / FR-8** — Expert sees only assigned items
- [x] **Story 9 / FR-9** — AVL-only supplier selection
- [x] **Story 10 / FR-10** — Quote minima and submit to CM
- [x] **Story 27 / FR-27** — Auto-route by high value / commission item vs company path

### Suggested tests

- [x] Expert cannot edit unassigned lines
- [x] Assigned line product/qty locked outside draft/correction (server + view readonly)
- [x] Non-AVL partner rejected on quote
- [x] Quote vendor dropdown lists only AVL vendors for the line’s company/product
- [x] Expert saves a quote from the line one2many while the PR is in inquiry (parent content lock exempts `quote_ids`)
- [x] Minima block/allow submit
- [x] Split assignment: each expert submits their own line; PR advances only when all lines are in (no cross-line `AccessError`)
- [x] Router: below threshold, no commission → company path; high value or commission flag → commission case

### Done when

FR-5, 6, 8–10, 27 pass; quote-approved PRs land on the correct path (commission or signatory stub).

---

## Phase 3 — Holding Commission & closed envelope

**Goal:** Holding reviews high-value/commission cases; CE supplier list approval opens bidding; bids sealed until open; award winner. Manual sealed bid entry until Phase 5.

### Scope

#### Commission

- [x] `zvy.commission.case` dashboard (FR-15)
- [x] Assign Commission Experts (FR-16)
- [x] `zvy.commission.review`: accuracy / policy / suppliers notes; recommendation approve / reject / corrections (FR-21–23)
- [x] Approve without meeting when all experts approve (FR-17) → advance toward signatory
- [x] `zvy.commission.meeting`: link cases, datetime, MOM upload; record outcomes (FR-18)
- [x] Corrections path returns work to company quote review as designed

#### Closed envelope

- [x] `zvy.closed.envelope` + invite AVL partners (FR-11)
- [x] Submit list → `list_pending`
- [x] Commission Manager approve/reject list; require `opening_datetime` + `bid_deadline` (FR-20)
- [x] Approve → `portal_open` (FR-29); default bid window from settings
- [x] `zvy.closed.envelope.bid` with seal rules (FR-30); manual entry by Commission Manager
- [x] `action_open_bids` after opening; select winner (FR-19); store award for PO
- [x] Optional notify stubs for results (full mail in Phase 5)

### Stories / FRs checklist

- [x] **Story 11 / FR-11** — CE supplier list by expert
- [x] **Story 15 / FR-15** — Commission Manager dashboard
- [x] **Story 16 / FR-16** — Assign Commission Experts
- [x] **Story 17 / FR-17** — Approve without meeting
- [x] **Story 18 / FR-18** — Meetings + MOM
- [x] **Story 19 / FR-19** — Select CE winner after open
- [x] **Story 20 / FR-20** — Approve CE supplier list
- [x] **Story 21 / FR-21** — Expert receives assignments
- [x] **Story 22 / FR-22** — Verify quotes / policy / AVL
- [x] **Story 23 / FR-23** — Submit audit report
- [x] **Story 29 / FR-29** — Auto `portal_open` on list approval
- [x] **Story 30 / FR-30** — Seal bids until opening

### Suggested tests

- [x] Bid amounts hidden from non-manager before open
- [x] Bidder (portal user later; sudo partner check now) can read own bid
- [x] List approval without deadlines fails
- [x] Winner selection blocked before open
- [x] Commission approve-without-meeting when all reviews approve

### Done when

FR-11, 15–23, 29–30 pass with **manual** bids; sealed integrity holds; approved commission cases ready for Phase 4 sign-off.

---

## Phase 4 — Sign-off & Purchase Order

**Goal:** Sequential company signatories via Approvals; CEO on sole source; refuse returns to CM; CM creates standard POs from `po_ready`.

### Scope

- [x] Spawn sequential `approval.request` from company signatory category (FR-12)
- [x] Link PR ↔ approval; PR context from approval form (FR-13)
- [x] Full approval → `po_ready`; refuse → `cm_review` with reason (BR-8)
- [x] Sole source always includes CEO / sole-source approvers in chain, including after commission (FR-14)
- [x] Enforce no `po_ready` while approval pending (FR-28)
- [x] After commission approval, enter same signatory path
- [x] `action_create_po`: CM only, `po_ready` + award data → one or more `purchase.order`; PR → `done` (FR-7 / BR-6)
- [x] Optional `purchase.order.zvy_purchase_request_id` for traceability

### Stories / FRs checklist

- [x] **Story 7 / FR-7** — Create PO after approvals
- [x] **Story 12 / FR-12** — Sequential signatory documents
- [x] **Story 13 / FR-13** — Approve or refuse → CM
- [x] **Story 14 / FR-14** — CEO on all sole source
- [x] **Story 28 / FR-28** — Sequential enforcement; no unauthorized bypass

### Suggested tests

- [x] Signatory bridge: approve → `po_ready`; refuse → `cm_review`
- [x] Sole-source PR includes CEO before `po_ready`
- [x] Cannot create PO from non-`po_ready` or without award
- [x] Non-CM cannot create PO

### Done when

FR-7, 12–14, 28 pass; end-to-end company path and commission→signatory→PO path work without portal.

**MVP backend complete** (Stories 1–23, 27–30).

---

## Phase 5 — Supplier portal

**Goal:** Invited vendors view tenders, submit sealed bids before deadline, and receive invitation/result/clarification notifications.

### Scope

- [x] Portal controllers: `/my/tenders` list + detail (FR-24)
- [x] Invitation isolation: non-invited → empty / 403
- [x] Bid submit/update/withdraw while `portal_open` and before `bid_deadline` (FR-25)
- [x] Reject submit after deadline or after open with clear error
- [x] Store as `zvy.closed.envelope.bid` (`source=portal`); seal rules unchanged (FR-30)
- [x] Mail (+ optional portal note): portal open / invitation; clarification; award / not awarded / cancelled (FR-26)
- [x] Published tender documents downloadable on detail page

### Stories / FRs checklist

- [x] **Story 24 / FR-24** — Portal view tenders / RFQs
- [x] **Story 25 / FR-25** — Submit sealed bids before deadline
- [x] **Story 26 / FR-26** — Results & clarification notifications

### Suggested tests

- [x] Portal isolation (invited vs not)
- [x] Bid seal: other suppliers never see amounts
- [x] Deadline and pre-open update rules
- [x] Notification triggers on open / result

### Done when

FR-24–26 pass; CE path usable end-to-end from invitation to award without relying on manual bid entry.

---

## Cross-phase non-functionals

Track throughout (PRD §7):

| Area | Checkpoint |
|------|------------|
| Auditability | Chatter on status, reasons, assignments, awards |
| Security | Groups + rules as models appear (Architecture §5) |
| Usability | Role queues and clear next-action buttons per phase |
| Notifications | Planner/assignees early; suppliers in Phase 5 |
| Extensibility | RPC PR create from Phase 1; settings from Phase 0 |
| Testability | Add tests listed per phase; keep green in CI |

---

## Story → phase index

| Story | FR | Phase |
|-------|-----|-------|
| 1 | FR-1 | 1 |
| 2 | FR-2 | 1 |
| 3 | FR-3 | 1 |
| 4 | FR-4 | 1 |
| 5 | FR-5 | 2 |
| 6 | FR-6 | 2 |
| 7 | FR-7 | 4 |
| 8 | FR-8 | 2 |
| 9 | FR-9 | 0 (AVL) + 2 (enforcement) |
| 10 | FR-10 | 2 |
| 11 | FR-11 | 3 |
| 12 | FR-12 | 4 |
| 13 | FR-13 | 4 |
| 14 | FR-14 | 4 |
| 15 | FR-15 | 3 |
| 16 | FR-16 | 3 |
| 17 | FR-17 | 3 |
| 18 | FR-18 | 3 |
| 19 | FR-19 | 3 |
| 20 | FR-20 | 3 |
| 21 | FR-21 | 3 |
| 22 | FR-22 | 3 |
| 23 | FR-23 | 3 |
| 24 | FR-24 | 5 |
| 25 | FR-25 | 5 |
| 26 | FR-26 | 5 |
| 27 | FR-27 | 2 |
| 28 | FR-28 | 4 |
| 29 | FR-29 | 3 |
| 30 | FR-30 | 3 |

---

## Progress log

| Phase | Status | Notes |
|-------|--------|-------|
| 0 Foundation | Done | Module shell, groups, settings, PR sequence, AVL + foundation tests |
| 1 PR & CM intake | Done | PR lifecycle, CM queues, reject/return, planner notify, intake tests |
| 2 Inquiry & routing | Done | Assign experts, AVL quotes, minima, quote review, auto-route + case shell; expert line/quote UI readonly aligned with write rules (`18.0.1.3.1`); AVL-only vendor pickers on quote + CE invites (`18.0.1.3.2`); quote collection unblocked on locked parents, PR Quotes tab CM-only (`18.0.1.3.3`); Recorded By / State system-only (`18.0.1.3.4`); per-line expert submit drives PR advancement (`18.0.1.4.0`) |
| 3 Commission & CE | Done | Cases, reviews, meetings/MOM, CE list/open/award, manual bids + seal (`18.0.1.4.x`) |
| 4 Sign-off & PO | Done | Sequential Approvals bridge, sole-source CEO inject, award→PO, CM Create PO (`18.0.1.5.0`) |
| 5 Supplier portal | Done | `/my/tenders`, sealed portal bids, invite/result/clarification mail (`18.0.1.6.0`) |
