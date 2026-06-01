# -*- coding: utf-8 -*-
"""Bootstrap / cleanup helpers callable from install and migration scripts."""

import logging

_logger = logging.getLogger(__name__)


def unlink_legacy_documents_approvals_workspace(env):
    """Remove pinned 'Approvals' root from Enterprise ``documents_approvals`` once using ``Approval``.

    - Reassigns ``res.company.approvals_folder_id`` if it still pointed to the legacy folder.
    - Moves direct children under our ``approval_ext`` Approval root when possible.
    - Unlinks legacy folder or archives if unlink fails.
    """
    legacy = env.ref('documents_approvals.document_approvals_folder', raise_if_not_found=False)
    if not legacy or not legacy.exists():
        return

    new_root = env.ref('approval_ext.document_approval_root_folder', raise_if_not_found=False)
    if not new_root or not new_root.exists():
        _logger.warning('approval_ext: approval root folder xml id missing; skip legacy cleanup')
        return

    if legacy.id == new_root.id:
        return

    Folder = env['documents.document'].sudo()

    companies = env['res.company'].sudo().search([('approvals_folder_id', '=', legacy.id)])
    if companies:
        companies.write({'approvals_folder_id': new_root.id})

    # Move everything still sitting under legacy root so unlink is safe / data not lost.
    dangling = Folder.search([('folder_id', '=', legacy.id)])
    if dangling:
        dangling.write({'folder_id': new_root.id})
        _logger.info(
            'approval_ext: reassigned %s items from legacy Approvals workspace to Approval',
            len(dangling),
        )

    legacy_id = legacy.id
    try:
        legacy.unlink()
        _logger.info(
            'approval_ext: removed legacy documents_approvals Approvals workspace (id=%s)',
            legacy_id,
        )
    except Exception as exc:
        _logger.warning(
            'approval_ext: could not unlink legacy Approvals workspace; archiving. Reason: %s',
            exc,
        )
        legacy.action_archive()


def apply_security_rules(env):
    """Re-apply approval_ext security after core approvals 1.1+ upgrades.

    Core ``approvals`` 1.1 removes old approver rules and may reset the owner
    unlink rule via ``post-rm-rules`` / manifest ``function`` writes.
    """
    unlink_rule = env.ref(
        'approvals.approval_request_unlink_request_owner_rule',
        raise_if_not_found=False,
    )
    if unlink_rule:
        unlink_rule.sudo().write({
            'domain_force': (
                "[('request_owner_id', '=', user.id), ('request_status', '=', 'new')]"
            ),
        })
