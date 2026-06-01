# approval_ext



**Technical name:** `approval_ext`  

**Odoo version:** 18.0



## Problem statement



Standard **Documents - Approvals** (`documents_approvals`) keeps approval files in a flat workspace. The business also needs a **restartable approval flow**: approvers can send a request back to the creator for corrections, with every prior approval cleared.



## Features



### Documents



- Pinned Documents workspace **Approval** (root folder).

- On first attachment (chatter or **Attach Document**), creates a subfolder under that root named from `approval.request`’s `name` (sequence when automated), with a ` (#id)` suffix when the same name exists.

- Documents created from chatter attachments land in that subfolder via `_get_document_folder()`.

- Install hook enables **Centralize files attached to Approvals**, points companies to **Approval**, migrates existing linked files into per-request folders, then removes the redundant **Approvals** root from Enterprise `documents_approvals`.



### Workflow



- Adds status **Editing**: request is back with the creator, same editable behaviour as **To Submit**.

- Removes **Withdraw** on the request (server-side blocked).

- **Return for editing** (form + kanban menu): wizard captures a mandatory reason → chatter note → clears approval activities → resets **all** approvers to `new`, clears confirmation date → status **Editing**.

- Visible only while the request is **Submitted** (`pending`) and the current user is an approver who has **not** yet approved/refused (`approved`/`refused`/`cancel` are excluded).

- **Submit** is available again in **Editing**; submitting clears the editing flag and restarts confirmation / activities like a first submission.

- Sequential approval still works via standard `action_confirm`.



## Configuration / usage



1. Install **Documents**, **Approvals**, **Documents - Approvals**, then **Approvals Documents Extension**.

2. **Documents:** no manual setup beyond the hook; files appear under `Approval /<request reference>/`.

3. **Workflow:** as approver still in the running chain, open a submitted request → **Return for editing** → enter reason.



## Dependencies



- `documents_approvals` (→ `documents`, `approvals`)



## Models / key fields



| Model | Field | Purpose |

|-------|--------|---------|

| `approval.request` | `documents_folder_id` | Folder for this request in Documents |

| `approval.request` | `approval_ext_in_editing` | Internal flag forcing status **Editing** |

| `approval.request` | `approval_ext_can_return_for_edit` | UI: current user may open the return wizard |

| `approval.return.to.edit.wizard` | `reason` | Explanation shown to the creator |



## UI



- Inherits **documents_approvals** form (technical `documents_folder_id`).

- Extra inherits: Submit from **Editing**, status bar, editable fields parity with **new**, withdrawal removed, Return button + wizard, list/kanban/search tweaks.



## Security / permissions



- Transient **`approval.return.to.edit.wizard`** : `base.group_user` CRUD.

- Documents folder ops still use elevated rights where Odoo Documents requires it.



## Limitations



- Enterprise **Documents** required for folder features.

- `post_init_hook` runs once on install; migrations handle some cross-version tidy-up.

- Deleted requests do not auto-delete Documents subfolders.

- Returning for editing cancels pending approval activities and resets every approver (by design).



## Testing notes



- **Documents:** attachments under correct subfolders; duplicate names suffixed.

- **Workflow:** submit → approver uses Return → chatter shows reason → employee edits → submit again → all approvers must re-approve.

- **Frontend:** after pulling JS changes (`attach_document_stat`), upgrade the module and regenerate backend assets (`-u approval_ext`), start Odoo with `--dev=assets` while developing, and hard-reload the browser (Ctrl+F5). If the bundle is stale, Owl may log `KeyNotFoundError: Cannot find key "attach_document_stat" in the "view_widgets" registry`—that means the registrar JS is not in `web.assets_web` yet; upgrading and refreshing assets fixes it. If markup still matches an old bundle, the wrapper will lack `flex-grow-1` and the inner button will lack `oe_stat_button`.


