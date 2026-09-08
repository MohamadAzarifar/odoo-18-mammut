# Manual Test Catalogue

**Product:** Mammut Procurement & Tendering (`zvy_tendering` 18.0.2.9)  
**App name in Odoo:** Procurement & Tendering  
**Source of truth:** the screens and buttons in this module, mapped to PRD 1.3 and [Roadmap.md](Roadmap.md)

Use this document to walk a real Odoo database as a person, not a developer. Each scenario names **who logs in**, **where to click**, and **what must happen**. Tick the checkboxes as you go.

---

## How to use this document

1. Complete **Before you start** once. Most later scenarios reuse the same users, products, and vendors.
2. Run the two **happy paths** first (Enquiry, then Tendering). If those fail, stop and fix before the edge cases.
3. Then run the **scenario catalogue**. Scenarios that say “start from …” expect you to reuse an earlier request instead of building a new one from scratch.
4. Mark **Pass** only when every “You should see” line is true. If something differs, write the actual result next to the step.

Convention in this file:

- **Menus** look like `Procurement & Tendering → Purchase Requests → Awaiting Review`.
- **Buttons** are written in bold, exactly as on the form (`Submit`, `Assign Experts`, `Create PO`).
- **Statuses** are the words on the status bar (Draft, Submitted, Inquiry, PO Ready, …).
- **Log in as Planner** means a user who has only the Planner role under Procurement & Tendering (unless the step says otherwise).

---

## What you are testing

A purchase request (PR) is created by a planner, reviewed by the company Commercial Manager, then either:

- **Enquiry** — Commercial Experts collect vendor quotes, the CM awards a quote per line, company signatories sign, and (only if needed) Holding Commission reviews. Then the CM creates Purchase Orders.
- **Tendering** — Commercial Experts invite AVL vendors on a Closed Envelope, vendors bid on the portal (sealed until opening), the Commission Manager awards **per item**, then company signatories sign and POs are created.

One PR can produce several POs. Mixed Enquiry + Tendering on the same PR must be split before submit.

**Not in this product (do not file bugs):** full PO lifecycle after issue, accounting, SAP / Bridge master data, AVL as a separate product, holding org-chart management. SAP checks 3 and 10 on the commission Validation Report are stubs and must **not** fail the case.

---

## Roles (who does what)

Assign roles on the user form → **Access Rights**, without debug mode. Under **Procurement & Tendering** you should see seven independent roles. Each role’s selectable value is **User**.

| Role on the user form | What they do in the app | Main menus they see |
|---|---|---|
| Planner | Create / submit PRs; fix returned drafts | Purchase Requests → All Requests |
| Commercial Manager | Review PRs, assign experts, award quotes, create POs | All Requests, Awaiting Review, Quote Review |
| Commercial Expert | Collect quotes (Enquiry) or invite vendors (Tendering) | All Requests, My Assignments |
| Signatory | Approve or refuse the linked Approvals document | No Tendering menus — they work in **Approvals** |
| Commission Manager | Holding cases, meetings, CE list / open / award; may also Create PO | Commission → Cases, Meetings, Closed Envelopes, CE Lists Pending |
| Commission Expert | Write audit reviews on assigned cases | Commission → Cases, My Assignments, My Reviews, Meetings, Closed Envelopes |
| Administrator | Everything above plus Configuration | All of the above + Configuration (Products, AVL, Product Procurement Overrides, Settings) |

A user can hold more than one role. For clean tests, give each person **one** role (except the Administrator used for setup).

**Company vs holding:** PRs, AVL, quotes, closed envelopes, purchase level, and signatories belong to the **requesting company**. Commission cases, reviews, meetings, and commission settings belong to the **head holding** (the top parent company, or the company itself if it has no parent).

---

## Before you start

### 1. Install the app

1. Apps → search **Mammut Procurement & Tendering** → Install (or Upgrade if it is already there).
2. Open the app switcher.
3. You should see **Procurement & Tendering**.

- [ ] Module installs without errors
- [ ] App appears in the switcher

### 2. Create companies (for multi-company tests)

Use this tree if you will test Holding Commission later. For a single-company smoke test you can skip Company B and the mid parent.

```text
Holding Co          ← head holding (no parent)
 ├── Mid Co         ← optional, to prove holding is the top parent, not the mid one
 │    └── Company A ← operating company (planners / CM / experts live here)
 └── Company B      ← second operating company
```

Give each test user **Allowed Companies** that match their job:

- Company A Planner / CM / Expert / Signatory → Company A only
- Holding Commission Manager / Expert → Holding Co only (they must still see Company A and B cases)
- Administrator → all companies

### 3. Create users

Create these logins in Company A (plus holding users). Give each the **Internal User** type except the portal vendors.

| Suggested login | Role | Company |
|---|---|---|
| `planner.a` | Planner | Company A |
| `cm.a` | Commercial Manager | Company A |
| `expert.a` | Commercial Expert | Company A |
| `expert.a2` | Commercial Expert (second person, for split assignment) | Company A |
| `signatory.1` | Signatory | Company A |
| `signatory.2` | Signatory | Company A |
| `ceo.a` | Signatory (used as sole-source / large-level approver) | Company A |
| `board.a` | Signatory | Company A |
| `comm.mgr` | Commission Manager | Holding Co |
| `comm.exp` | Commission Expert | Holding Co |
| `admin.tender` | Administrator | all |
| `vendor.a` / `vendor.b` / `vendor.c` | Portal | linked to vendor contacts (see vendors below) |
| `vendor.outsider` | Portal | a vendor **not** on the AVL invite list |

Also create `planner.b` (Planner, Company A) so you can prove planners only see their own PRs, and `cm.b` (Commercial Manager, Company B) for isolation tests.

### 4. Create vendors and AVL

Create three supplier partners, for example **Vendor A**, **Vendor B**, **Vendor C**, each with an email and a phone number. Create a fourth supplier **Outsider Vendor**.

For each of A, B, and C, add a **Contact** child and turn that contact into a **Portal** user (Grant Portal Access). Those portal users log in later at `/my/tenders`.

Then, as Administrator:

1. `Procurement & Tendering → Configuration → Approved Vendor List → New`
2. Add **Vendor A**, **Vendor B**, **Vendor C** for **Company A** (leave Product empty so they apply to all products).
3. Optionally add validity dates. Leave them active.

- [ ] Three AVL rows exist for Company A
- [ ] Archived entries disappear from the default list and reappear with the **Archived** filter

### 5. Create products

As Administrator: `Procurement & Tendering → Configuration → Products → New`. Other roles do not see this menu.

On each product form, after the category, you should see **Default Procurement Type** and (when type is Enquiry) **Default Need Commission**.

| Product | Default Procurement Type | Default Need Commission |
|---|---|---|
| Enquiry Standard | Enquiry | off |
| Enquiry Commission | Enquiry | on |
| Tender Item | Tendering | hidden / off |

- [ ] Switching a product to Tendering hides Need Commission
- [ ] Enquiry Standard is the default type on a new product

### 6. Configure settings

`Procurement & Tendering → Configuration → Settings`

Work in **Company A** first. For commission checkboxes, switch to **Holding Co** — those four fields are editable only on the head holding.

**Company Scale & Purchase Level (Company A)**

For manual tests, turn **Override Purchase-Level Bands** on and use small numbers so you do not need billions of rials:

| Field | Suggested test value |
|---|---|
| Company Scale | Small Scale |
| Override Purchase-Level Bands | on |
| Operational Minor / Medium / Major Max | 200 / 500 / 5 000 |
| Operational Large CEO Max | 10 000 |
| Non-Operational bands | same numbers |

(Production uses the baked-in R-PL tables when the override is off. You do not need those huge amounts for this catalogue.)

**Signatory Approvers (Company A)**

1. In the **Approvals** app, create a category, for example **PR Signatories**.
2. Turn **Approvers Sequence** on. You can leave the category’s own approver list empty — tendering replaces it from the company lists below.
3. Back in Tendering Settings, set **Signatory Approval Category** to that category.
4. Fill the lists (use the users you created):

| Setting | Who to put on it |
|---|---|
| Minor Signatories | `signatory.1` |
| Medium Signatories | `signatory.1` then `signatory.2` |
| Major Signatories | `ceo.a` |
| Large Signatories | `ceo.a` |
| Board Signatories | `board.a` |
| Formalities Signatories | `signatory.2` (extra person, used when a line has fewer than 3 valid quotes) |
| Sole-Source Approvers | `ceo.a` |

**Commission Pre-checks (Holding Co)**

| Setting | Suggested test value |
|---|---|
| Commission Notice Days | 0 (disables the date window until commission-laws exist) |
| Require Awarded Proforma | off for the happy path; turn on only for the dossier fail test |
| Require Comparison Document | off, then on for the fail test |
| Require Technical Request | off, then on for the fail test |

**Routing**

| Setting | Suggested test value |
|---|---|
| Default Bid Window | 72 hours |
| High-Value Threshold (deprecated) | ignore — routing uses Purchase Level **Large**, not this field |

Save.

- [ ] Values persist after you reopen Settings
- [ ] On Company A, the four commission pre-check fields are read-only and show the holding values

### 7. Website / portal

Portal vendors must be able to open `/my` and `/my/tenders` on this database. Confirm the website/portal is reachable before the tendering happy path.

---

## Statuses you will see

**Purchase request**

Draft → Submitted → CM Review → Inquiry → Quote Review → Commission and/or Signatory → PO Ready → Done

Side paths: **Correction** (planner must edit and resubmit), **Rejected** (terminal).

**Closed envelope**

Draft → List Pending → Portal Open → Opened → Awarded  
(or Cancelled)

**Commission case**

Open → In Review → Meeting (optional) → Approved  
Other outcomes: Corrections, Returned, Rejected

**Commission meeting**

Scheduled → Held → Signed  
(or Cancelled)

**Line purchase state** (after PO Ready)

Pending → Ordered, or Cancelled if the PR is rejected with leftover lines

---

## Happy path A — Enquiry, no commission, one PO

Goal: a standard Enquiry PR with 3 quotes, awarded to the lowest vendor, signed, and turned into one Purchase Order.

Use product **Enquiry Standard**, Purchase Nature **Operational**, line estimate about **100** so Purchase Level is **Minor**.

### A1. Planner creates and submits

1. Log in as `planner.a`.
2. `Procurement & Tendering → Purchase Requests → All Requests → New`.
3. Confirm **Requester** is you and you cannot change it.
4. Fill **Description**. Leave **Purchase Nature** as Operational.
5. On **Lines**, add one line: product Enquiry Standard, quantity 2, a price estimate.
6. Save.

You should see:

- [ ] Number like `PR/2026/00001` (not “New”)
- [ ] **Procurement Type** = Enquiry
- [ ] **Commission Item** unchecked
- [ ] **Sole Source** unchecked (three AVL vendors)
- [ ] **Purchase Level** = Minor
- [ ] **Formalities** unchecked (no quotes yet — this flag is computed from valid inquiries later)
- [ ] Status **Draft**
- [ ] Header button **Submit**

7. Click **Submit**.

- [ ] Status **Submitted**
- [ ] Description and lines are no longer editable
- [ ] Chatter notes the submission

### A2. Commercial Manager assigns an expert

1. Log in as `cm.a`.
2. `Purchase Requests → Awaiting Review` — the PR is in the list.
3. Open it. You should see **Reject**, **Return for Correction**, and **Assign Experts**.
4. Click **Assign Experts**.
5. On the wizard, put `expert.a` on the line. Click **Assign & Start Inquiry**.

- [ ] Status **Inquiry**
- [ ] Line shows the expert as a tag
- [ ] Chatter notes the assignment

### A3. Expert records three AVL quotes

1. Log in as `expert.a`.
2. `Purchase Requests → My Assignments` — only this line appears.
3. Open the line (or click **Quotes**).
4. Confirm product, quantity, and experts are greyed out.
5. On the Quotes tab, add three quotes:

   | Vendor | Unit Price |
   |---|---|
   | Vendor A | 10 |
   | Vendor B | 12 |
   | Vendor C | 15 |

6. Open one quote form and confirm:
   - **Contact Name** / **Contact Phone** filled from the vendor, editable
   - **Total** = unit price × quantity
   - **Received Date** is today
   - **Valid Inquiry** is checked
   - optional Commercial Terms (delivery, payment, warranty, …) can be filled
   - **Proforma** can be attached on the Attachments tab
7. Click **Submit Quotes** on the line (or on the PR header).

- [ ] Vendor dropdown listed only AVL vendors; you could not create a new contact from it
- [ ] After submit, a **Quotes Submitted** ribbon appears on the line
- [ ] PR status becomes **Quote Review** (only one line, so it advances immediately)
- [ ] `expert.a` does **not** see menus Awaiting Review or Quote Review

### A4. CM awards the lowest quote and approves

1. Log in as `cm.a`.
2. `Purchase Requests → Quote Review` — the PR is there.
3. Open it. A blue banner tells you to **Select as Awarded** on each line, then **Approve Quotes**.
4. Open the line’s quotes. Click **Select as Awarded** on Vendor A (price 10).
5. Click header **Approve Quotes**.

- [ ] Awarded quote becomes Accepted; others Rejected
- [ ] Status **Signatory**
- [ ] **Signatory** smart button appears (count 1)
- [ ] No commission case is created
- [ ] Chatter says the request was routed to the company signatory path

### A5. Signatory approves

1. Log in as `signatory.1`.
2. Open the **Approvals** app → the document named `Signatory: PR/…`.
3. Confirm you can open the **Purchase Request** smart button, see lines and quotes, and **cannot** edit the PR.
4. Click **Approve**.

- [ ] Approval status Approved
- [ ] PR status **PO Ready**
- [ ] A later signatory (if any) could not approve before this one — only one person is on the Minor list in this setup

### A6. CM creates the Purchase Order

1. Log in as `cm.a`.
2. Open the PR. Click **Create PO**.
3. On the wizard, leave the line **Include** checked. Click **Create PO**.

- [ ] One draft Purchase Order, vendor = Vendor A, price from the awarded quote
- [ ] PO origin is the PR number
- [ ] Line **Purchase State** = Ordered
- [ ] PR status **Done**
- [ ] **POs** smart button opens the order
- [ ] `expert.a` never saw a Create PO button

---

## Happy path B — Tendering with portal bids and one winner per item

Goal: a Tendering PR, invited vendors bid on `/my/tenders`, Commission Manager opens and awards, then sign-off and PO.

Use product **Tender Item**, two lines (so you can later test partial award if you want). For the happy path, award **both** lines to Vendor A. Keep the total in the Minor band so Holding Commission is skipped after quotes.

### B1. Planner submits a Tendering PR

1. Log in as `planner.a` → New PR → one or two lines of **Tender Item** → **Submit**.

- [ ] **Procurement Type** = Tendering
- [ ] **Commission Item** is false
- [ ] Status **Submitted**

### B2. CM assigns the expert

Same as A2: `cm.a` → **Assign Experts** → `expert.a` → **Assign & Start Inquiry**.

- [ ] Status **Inquiry**
- [ ] Header shows **Closed Envelope** (this button is hidden on Enquiry PRs)

### B3. Expert invites AVL vendors

1. Log in as `expert.a`. Open the PR. Click **Closed Envelope**.
2. On **Invited Suppliers**, add Vendor A and Vendor B (dropdown is AVL-only).
3. Optionally attach files under **Published Documents**.
4. Set **Opening Datetime** a few minutes in the future if you want to test the seal; for a faster test you can set it a minute in the past after list approval. Set **Bid Deadline** a few hours in the future.
5. Click **Submit List**.

- [ ] Envelope status **List Pending**
- [ ] Envelope is linked on the PR
- [ ] `Procurement & Tendering → Commission → CE Lists Pending` shows it for the Commission Manager

### B4. Commission Manager opens the portal

1. Log in as `comm.mgr`.
2. Open the envelope (from **CE Lists Pending** or **Closed Envelopes**).
3. Confirm Opening Datetime is set. Bid Deadline may be left empty — on approve it defaults from **Default Bid Window**.
4. Click **Approve List**.

- [ ] Status **Portal Open**
- [ ] Invited vendors with email receive an invitation (check Discuss / outgoing mail)
- [ ] Approving with no Opening Datetime is refused

### B5. Vendors submit sealed bids

1. Log in to the website as portal user **Vendor A** → `/my` → **Tenders**, or open `/my/tenders`.
2. Open the invitation. Confirm Bid deadline, Opening, line summary (product / qty), and published documents.
3. For each line enter a **Unit price**, optional Delivery / Payment / Comments / Proforma. Click **Submit bid**.
4. Change a price and click **Update bid**. Confirm you can **Withdraw bid** and submit again while the window is open.
5. Log in as **Vendor B** and submit different prices. Confirm you never see Vendor A’s amounts.
6. Log in as **Outsider Vendor** → `/my/tenders`.

- [ ] Invited vendors see only their invitations
- [ ] Outsider sees “There are currently no tender invitations for your account.”
- [ ] Guessing `/my/tenders/<id>` as the outsider is denied
- [ ] In the backend, `expert.a` still sees **bid count only** — amounts stay hidden until Open Bids
- [ ] `comm.mgr` can see amounts (managers are allowed)

### B6. Open bids and award per item

1. Wait until Opening Datetime (or set it in the past as Admin).
2. As `comm.mgr`, click **Open Bids**.

- [ ] Status **Opened**
- [ ] Line prices are visible
- [ ] Opening before the datetime is refused
- [ ] If this envelope is on a **Scheduled** meeting agenda, Open Bids is refused until the meeting is **Held**

3. Open each bid. Tick **Winner** on Vendor A’s line(s) (one winner per item).
4. Optionally set **Discount %** on a winning line.

- [ ] **Final Price** = unit price × (1 − discount/100)
- [ ] Chatter logs the discount change

5. Click **Select Winner**.

- [ ] Envelope **Awarded**
- [ ] PR status **Quote Review**
- [ ] Winner / not-awarded mails go out
- [ ] Select Winner was not available before Open Bids

### B7. CM approves and signatories sign

1. As `cm.a`, open the PR in Quote Review. Click **Approve Quotes** (CE winners already sit on the lines).
2. For a **Minor** tender, status becomes **Signatory** (no commission case).
3. As `signatory.1`, **Approve** in Approvals.
4. As `cm.a`, **Create PO**.

- [ ] PO vendor and prices come from the per-item winners (`final_price`)
- [ ] PR **Done** when every line is Ordered

---

## Scenario catalogue

Run these after the happy paths. Each one is independent unless it says otherwise.

### 1. Foundation and access

#### 1.1 Role menus

| Log in as | Should see | Should not see |
|---|---|---|
| Planner | All Requests | Awaiting Review, Quote Review, Configuration, Commission |
| Commercial Manager | All Requests, Awaiting Review, Quote Review | My Assignments, Configuration, Commission |
| Commercial Expert | All Requests, My Assignments | Awaiting Review, Quote Review, Configuration |
| Signatory | (Approvals app only) | Procurement & Tendering root |
| Commission Manager | Commission → Cases, Meetings, Closed Envelopes, CE Lists Pending | Purchase Requests menus |
| Commission Expert | Cases, My Assignments, My Reviews, Meetings, Closed Envelopes | CE Lists Pending, Configuration |
| Administrator | everything, including Configuration → Products, AVL, Overrides, Settings | — |

- [ ] Menus match the table
- [ ] Roles are visible on Access Rights with debug **off**

#### 1.2 Planner isolation

1. As `planner.a`, create a draft PR.
2. As `planner.b` (same company), open All Requests.

- [ ] `planner.b` does not see `planner.a`’s PR
- [ ] `cm.a` sees both planners’ PRs for Company A

#### 1.3 AVL isolation

1. Create an AVL row for Company B.
2. Log in as a Company A–only Administrator.

- [ ] Company B’s AVL row is not in the list

#### 1.4 Sequence

With developer mode: Settings → Technical → Sequences → code `zvy.purchase.request`.

- [ ] Prefix `PR/%(year)s/`, padding 5
- [ ] Commission cases use `CASE/%(year)s/`

---

### 2. Intake: reject, return, mixed split

#### 2.1 Reject is terminal

1. Planner submits a new PR.
2. As CM, click **Reject** and confirm with an empty reason.

- [ ] Wizard requires a reason

3. Enter a reason → **Reject**.

- [ ] Status **Rejected**
- [ ] Reason shown on the form and in chatter
- [ ] Planner gets an activity / mail with the PR number and reason
- [ ] Planner cannot edit the PR
- [ ] Create PO is not available

#### 2.2 Return from Submitted goes to the planner

1. Planner submits a PR.
2. As CM, **Return for Correction** with a reason.

- [ ] No **Return To** choice (that appears only from CM Review)
- [ ] Status **Correction**
- [ ] Planner can edit description and lines
- [ ] Planner **Submit** sends it back to **Submitted** / Awaiting Review

#### 2.3 Mixed Enquiry + Tendering must split

1. Planner creates a draft with one Enquiry Standard line and one Tender Item line.

- [ ] Yellow warning: the request mixes Enquiry and Tendering
- [ ] Header **Mixed Enquiry and Tendering** is visible

2. Click **Submit**. On the wizard click **Cancel**.

- [ ] PR stays Draft

3. **Submit** again → **Split**.

- [ ] Original PR keeps Enquiry lines and its number
- [ ] A new draft PR holds the Tendering lines
- [ ] **Split PR** smart button links the siblings
- [ ] Neither PR is submitted — planner submits each one separately

---

### 3. Inquiry quotes

#### 3.1 AVL only

On an Inquiry line, try to use Outsider Vendor (RPC or any forced partner).

- [ ] Save is refused: vendor is not on the active AVL
- [ ] UI dropdown does not list Outsider Vendor

#### 3.2 Quote minima

| Situation | What to do | Expected |
|---|---|---|
| Zero quotes | **Submit Quotes** | Blocked |
| 1 or 2 **valid** quotes on a normal line | **Submit Quotes** | Wizard **Fewer than 3 Valid Inquiries** — reason required; after confirm, reason stored on the line as **Fewer Quotes Reason** |
| 3 valid quotes | **Submit Quotes** | Goes through with no wizard |
| Sole source (exactly one AVL vendor for that product + company) | 1 valid quote | Allowed, no shortfall reason |
| Priced quote with **Received Date** older than 30 days | Count it toward the 3 | It is **not** a valid inquiry; minima still fail |
| Unpriced quote (empty unit price, fill Comments) | Save, then submit with only that quote | Saves; **Valid Inquiry** is off; does **not** count toward the 3 |

- [ ] Totals auto-compute when priced
- [ ] Unpriced quotes never count as valid
- [ ] Formalities on the PR header turns on if **any** line has fewer than 3 valid inquiries (whole PR, not per line)

#### 3.3 Split assignment

1. PR with two Enquiry lines.
2. CM assigns `expert.a` to line 1 and `expert.a2` to line 2.
3. `expert.a` submits line 1 only.

- [ ] `expert.a` cannot see line 2
- [ ] PR stays **Inquiry** until `expert.a2` submits
- [ ] Then status **Quote Review**

#### 3.4 Last purchase on the line

1. Confirm a standard Purchase Order in Company A for Enquiry Standard / Vendor A (any price).
2. Create a new PR with that product.

- [ ] Line shows **Last Vendor**, **Last Price**, **Last Purchase Date** from that PO

#### 3.5 CM rejects the quote set

On Quote Review, **Reject Quotes** with a reason.

- [ ] Status back to **Inquiry**
- [ ] Quotes return to Draft
- [ ] Assigned experts get an activity
- [ ] Empty reason is refused

#### 3.6 Award is not the lowest price

On Quote Review, **Select as Awarded** on the **highest** price.

- [ ] Wizard **Not the Lowest Price** requires a reason
- [ ] Reason stored on the line (**Not Lowest Price Reason**)
- [ ] **Approve Quotes** without that reason is refused

---

### 4. Purchase level, formalities, signature chain

Purchase Level is computed from **Amount for Purchase Level** (awarded totals if awarded, otherwise line estimates) against the company scale and **Purchase Nature**.

With the custom bands from setup:

| Amount | Purchase Level |
|---|---|
| ≤ 200 | Minor |
| ≤ 500 | Medium |
| ≤ 5 000 | Major |
| above | Large |

**Large** is treated as high value (Holding Commission after enquiry signatures). Inside Large, amounts above **Large CEO Max** add **Board Signatories**.

#### 4.1 Level changes the signatory list

Run three small Enquiry PRs (3 quotes, award, Approve Quotes) at Minor / Medium / Large amounts.

- [ ] Minor: only `signatory.1`
- [ ] Medium: `signatory.1` then `signatory.2` (sequential — the second cannot approve first)
- [ ] Large enquiry: after the chain completes, status becomes **Commission** (not PO Ready), and a case is created

#### 4.2 Formalities add extra signatories

1. Enquiry PR, submit **two** valid quotes with a shortfall reason.
2. Award and Approve Quotes.

- [ ] Header **Formalities** is checked
- [ ] Signatory chain includes **Formalities Signatories** (`signatory.2`) in addition to the band list

#### 4.3 Effective change resets the chain

While status is **Signatory**, as someone who can edit (planner cannot; CM/admin in signatory can change nature / qty per the form):

Change **quantity**, or **Purchase Nature**, on a PR that already has a pending approval.

- [ ] Current approval is kept in history (Signatory smart button count increases)
- [ ] A **new** approval is spawned
- [ ] Only the new chain can reach PO Ready
- [ ] Old approval remains readable

#### 4.4 Sole source always includes the CEO

1. Archive AVL for Vendor B and C on this product/company so exactly **one** vendor remains.
2. Line **Sole Source** checks itself.
3. Expert submits **one** quote. CM awards and approves.

- [ ] Approval list includes **Sole-Source Approvers** (`ceo.a`) last
- [ ] PR stays Signatory until the CEO approves
- [ ] Same CEO inject happens on the **pre-commission** chain of a large sole-source enquiry

---

### 5. Routing after quotes (enquiry vs tendering)

Remember:

- **Enquiry** always goes to **Signatory first**. Holding Commission runs **after** that chain, and only if Need Commission **or** Purchase Level is Large.
- **Tendering** runs Closed Envelope during Inquiry. After CM **Approve Quotes**: Large → Commission then Signatory; otherwise Signatory directly.
- Need Commission on a Tendering product is ignored.
- The deprecated high-value threshold must **not** send an enquiry to commission before signatures.

| Setup | After Approve Quotes | After sign-off |
|---|---|---|
| Enquiry, not commission, not Large | Signatory | **PO Ready** (no case) |
| Enquiry + Need Commission, below Large | Signatory | **Commission** (`Routed: Commission Item`) |
| Enquiry Large, Need Commission off | Signatory | **Commission** (`Routed: High Value`) |
| Tendering, not Large | Signatory | PO Ready |
| Tendering Large | **Commission** (no signatory yet) | After commission approve → Signatory, then PO Ready |

- [ ] Enquiry commission approve does **not** create a second approval — PR goes straight to PO Ready
- [ ] Tendering commission approve **does** spawn the signatory document

---

### 6. Holding Commission and pre-checks

These apply to **enquiry** PRs when they enter Commission (after signatures). Tendering cases do not run the ten-check Validation Report.

#### 6.1 Green report — manager can proceed

1. Take an Enquiry + Need Commission PR through award and full sign-off.
2. As `comm.mgr`, open `Commission → Cases`.

- [ ] Case number like `CASE/2026/00001`
- [ ] **Holding Company** is Holding Co; **Company** is Company A
- [ ] **Validation Report** has 10 rows
- [ ] Checks 3 (SAP product) and 10 (SAP split) are **Skipped**, not Fail
- [ ] Other checks Pass (notice days = 0, three valid quotes, AVL vendors, arithmetic, lowest awarded, signatures complete)
- [ ] Case stays **Open** (actionable)

3. **Assign Experts** → `comm.exp`.
4. As `comm.exp`, `My Reviews` → fill Accuracy / Policy / Suppliers notes, Recommendation **Approve**, **Submit Review**.
5. As `comm.mgr`, **Approve Without Meeting**.

- [ ] Allowed even if another expert had recommended Reject (manager is not bound by unanimous approve)
- [ ] Enquiry PR → **PO Ready**
- [ ] Existing approval stays Approved (no new chain)

#### 6.2 Hard fail returns to the company CM

Force a fail, then complete sign-off so the PR enters commission:

| Check | How to fail it | You should see |
|---|---|---|
| 6 Vendors on AVL | (Hard to do in UI if quotes are AVL-only; skip if you cannot inject a non-AVL quote) | Return to **CM Review** |
| 8 Lowest valid selected | Award a non-lowest quote **without** a reason | Fail + return |
| 9 Prior signature chain | Would require entering commission without signatures — enquiry path should never allow this | Fail + return if it happens |
| 5 Dossier | Turn on **Require Comparison Document** on the holding, leave the PR **Commission Dossier** empty | Fail + return |
| 2 Proforma age | Awarded quote older than 30 days | Fail + return |

On any hard fail:

- [ ] Case status **Returned**
- [ ] PR status **CM Review**
- [ ] Chatter on PR and case contains the system comment listing failed checks
- [ ] Case is not left actionable for the manager

Then turn the holding flags back off for the rest of the tests.

#### 6.3 Manager reject / request corrections

On an open/in-review case:

- **Reject** with a reason → case Rejected; PR Rejected (terminal).
- **Request Corrections** with a reason:
  - Enquiry (signatures already done) → new signatory document pending on the **last** signatory; old chain kept in history
  - Tendering (no company chain yet) → PR **CM Review**

- [ ] Empty reason is refused
- [ ] Chatter names the actor and the reason

---

### 7. Commission meetings

1. As `comm.mgr`, `Commission → Meetings → New`.
2. Set **Title**, **Meeting Date**, **Location**, **Requesting Company** = Company A.
3. Confirm **Holding Company** is Holding Co (read-only).
4. On **Agenda**, add two open Company A cases.
5. On **Attendees**:
   - Kind **Internal** → pick a user (name fills in)
   - Kind **External** → type a name and role, **no user**

- [ ] External attendee saves
- [ ] Adding a Company B case is refused (all PRs on one meeting must share the requesting company)

6. Click **Mark Held** with no **Minutes** file.

- [ ] Refused

7. Attach minutes → **Mark Held**.

- [ ] Status **Held**

8. On the agenda, set PR 1 decision **Approved**. Leave PR 2 **Undecided**. Click **Transfer** on PR 2 to another scheduled meeting for Company A.

- [ ] First meeting still shows both rows; transferred row **Removed**
- [ ] Second meeting has a new Pending row
- [ ] Case’s current Meeting is the later one

9. **Cancel Meeting** on a scheduled meeting that has agenda rows.

- [ ] History kept; pending cases can be put on another meeting

10. **Mark Signed** from Held.

- [ ] Status **Signed**; agenda locked

---

### 8. Closed envelope extras

#### 8.1 Reject list

On List Pending, **Reject List** with a reason.

- [ ] Back to Draft; reason stored; expert can edit invites and resubmit

#### 8.2 Clarification and cancel

While Portal Open:

1. **Post Clarification** → invited vendors get mail; text is on the envelope chatter.
2. On another envelope, **Cancel**.

- [ ] Invitees get cancelled mail
- [ ] Portal detail shows “This tender has been cancelled.”

#### 8.3 Deadline and withdraw rules

- After Bid Deadline: portal Submit / Update / Withdraw show a clear “bidding closed” error.
- After Open Bids: same — cannot change bids.
- After deadline, while still Portal Open: `comm.mgr` **Re-open Bidding** extends the deadline (from Default Bid Window) and logs chatter. Open Bids is still blocked until Opening Datetime.

#### 8.4 Partial item award and re-tender

PR with **three** Tendering lines, two vendors bidding.

1. After Open Bids, mark winners on **two** lines only → **Select Winner**.

- [ ] Third line **Re-tender** is checked
- [ ] Awarded lines continue; PR is not fully awarded
- [ ] As CM/Expert, **Closed Envelope** opens a new envelope scoped to the leftover line
- [ ] After that line is awarded, Create PO can group by per-item winner

---

### 9. Signatory refuse (return to last actor)

Use a **Medium** enquiry (two signatories), no commission.

1. `signatory.1` **Approve**.
2. `signatory.2` clicks **Refuse**. Wizard **Return for Correction** requires a reason.

- [ ] PR stays **Signatory** (not Correction)
- [ ] `signatory.1` is pending again
- [ ] Chatter logs actor and reason

3. `signatory.1` **Refuse** with a reason.

- [ ] Approval Refused
- [ ] PR **CM Review** (not the planner)

4. As CM you now have **Resubmit to Signatories**, **Reject**, **Return for Correction**, **Assign Experts**.

**Resubmit to Signatories**

- [ ] New approval spawned; PR Signatory again; completing it reaches PO Ready (or Commission if the PR still needs it)

**Return for Correction from CM Review** — the wizard shows **Return To**:

| Return To | Result |
|---|---|
| **Planner** | Status **Correction**; planner edits and Submit → Submitted |
| **Commercial Expert** | Status **Inquiry**; quotes editable; keep assignment, or tick **Re-assign Experts** |
| Empty reason | Refused |

After the planner or expert finishes and the PR is awarded again, the **signature chain restarts** (new approval; old ones remain in history).

---

### 10. Partial Purchase Orders

Start from a **PO Ready** Enquiry PR with **two** awarded lines (two products, can be the same vendor).

1. As `cm.a`, **Create PO**. Uncheck the second line. Confirm.

- [ ] One PO
- [ ] Selected line **Ordered**; other line **Pending**
- [ ] PR stays **PO Ready** (not Done)
- [ ] One PO must not close leftover lines

2. **Create PO** again for the remaining line.

- [ ] Second PO
- [ ] PR **Done**

3. Repeat step 1 on another two-line PR, then **Reject** with a reason.

- [ ] Remaining Pending line **Cancelled**
- [ ] Existing PO kept
- [ ] Further Create PO blocked
- [ ] PR **Rejected**

4. Two lines awarded to **different** vendors; Create PO with all included.

- [ ] Two POs (grouped by vendor)
- [ ] PR Done

5. Permission: `expert.a` cannot Create PO. `comm.mgr` **can** Create PO on PO Ready.

---

### 11. Product overrides (per company / holding)

On the product form, group **Company Procurement Overrides**, or `Configuration → Product Procurement Overrides`.

#### 11.1 Operating-company type overlay

1. Product default = Enquiry.
2. Add a row: Company A, **Procurement Type** = Tendering.
3. Company A PR with that product → line is **Tendering**.
4. Company B PR with the same product → line stays **Enquiry**.
5. Company A PR mixing this product with a still-Enquiry product → Submit requires **Split** (resolved types, not the template default).

#### 11.2 Need Commission overlay is holding-only

1. On a **Holding Co** overlay for an Enquiry product, tick **Override Need Commission** and Need Commission.

- [ ] Company A line **Commission Item** is checked
- [ ] After award + signatures, PR goes to Commission (`Routed: Commission Item`) even if the product default is off

2. Try the same Need Commission override on Company A (a subsidiary).

- [ ] Refused / field hidden (`Override Need Commission` only on holding)

3. Overlay type Tendering (even if holding Need Commission is on).

- [ ] Line is Tendering; Commission Item is false

---

### 12. Holding company commission (multi-company)

Use the company tree from setup.

| Test | Expected |
|---|---|
| `comm.mgr` allowed **only** on Holding Co | Sees and acts on cases and closed envelopes from Company A **and** B |
| Company A CM | Cannot read Company B commission / CE |
| PR from a company under Mid Co | Case **Holding Company** = Holding Co, not Mid Co |
| Standalone company (no parent) | It is its own holding |
| Commission Notice Days / dossier flags | Stored on Holding Co; Company A Settings shows them read-only |
| Company A CM (no commission role) searching holding cases | No write; they are not the holding queue owner |
| Need Commission overlay on Company A | Ignored; only Holding Co overlay applies |

- [ ] All rows in the table pass

---

### 13. Notifications and audit

You do not need to verify every mail template body. Confirm a **chatter** line (and an activity or mail when the role is a person waiting to act) for:

- Submit, reject, return (with reason)
- Expert assignment (todo on the expert)
- Quote submit / quote reject
- Award selection (including not-lowest reason)
- Route to signatory / commission / PO Ready
- Commission assign, review submit, approve, reject, corrections
- CE list approve (portal open), clarification, award, not awarded, cancel
- Bid discount change
- Re-open bidding
- Create PO / split PR

- [ ] Planner is notified on reject and return
- [ ] Invited vendors are notified on portal open, clarification, result, cancel
- [ ] Status changes are in chatter with the user who did them

---

### 14. Permissions cheat-sheet (negative tests)

| Action | Who is allowed | Who is refused |
|---|---|---|
| Create / submit PR | Planner, Admin | CM-only, Expert-only |
| Reject / return intake | CM | Planner, Expert |
| Assign commercial experts | CM | Expert |
| Submit Quotes | Assigned Expert | CM, unassigned expert |
| Approve / reject quotes | CM | Expert |
| Closed Envelope (create / submit list) | Assigned Expert (CM can open) | Planner |
| Approve CE list / Open Bids / Select Winner | Commission Manager | CCE, company CM |
| See bid amounts before open | Commission Manager, Admin | CCE, company CM, other vendors |
| Approve / Refuse signatory document | Current pending signatory | Other signatories (waiting), non-approvers |
| Signatory reads PR | Only if they are an approver on the linked approval | Other Signatory users |
| Create PO | CM, Commission Manager | Expert, Planner, Signatory |
| Commission Assign / Approve Without Meeting | Commission Manager | Commission Expert |
| Submit Review | Assigned Commission Expert | Other experts |
| Maintain products (`Configuration → Products`) | Admin | Planner, CM, Expert, Commission roles |

- [ ] Spot-check the table on one PR so a wrong role cannot skip the path

---

## Suggested order for a full pass

If you have one tester and one day, run in this order:

1. Before you start (install, users, AVL, settings)
2. Happy path A (Enquiry → PO)
3. Happy path B (Tender → portal → PO)
4. Mixed split (2.3)
5. Return / reject (2.1, 2.2, 9)
6. Quote minima + formalities (3.2, 4.2)
7. Need-commission enquiry → signatures → Validation Report → Approve Without Meeting (5 + 6.1)
8. Meeting + transfer (7)
9. Partial PO (10)
10. Per-item re-tender (8.4)
11. Product overlay + holding isolation (11, 12)

That set covers every PRD 1.3 path that is implemented. The remaining catalogue rows are extra confidence (sole source, board signatories, dossier fail, portal outsider, etc.).

---

## Out of scope (expected “missing” behaviour)

Do **not** fail the release for these:

- SAP product matching and SAP “split count” (Validation Report checks 3 and 10 stay Skipped)
- Creating vendors from Bridge / master data — AVL is maintained in Odoo
- Accounting or stock after the Purchase Order is created
- Holding organisation chart (parent/child companies in Odoo are enough)
- Commission-laws extra notice windows (Notice Days = 0 disables the check)
- High-Value Threshold in Settings — unused; Large purchase level is the switch

---

## Sign-off

| Area | Tester | Date | Pass / Fail | Notes |
|---|---|---|---|---|
| Setup & roles | | | | |
| Happy path A — Enquiry | | | | |
| Happy path B — Tendering / portal | | | | |
| Intake, split, return | | | | |
| Quotes, AVL, minima, formalities | | | | |
| Signatories, sole source, reset | | | | |
| Commission, pre-checks, meetings | | | | |
| Closed envelope, seal, per-item award | | | | |
| Partial PO | | | | |
| Holding / overlays / isolation | | | | |
