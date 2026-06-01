# -*- coding: utf-8 -*-


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api
    from odoo.addons.approval_ext import hooks as approval_ext_hooks

    env = api.Environment(cr, SUPERUSER_ID, {})
    approval_ext_hooks.unlink_legacy_documents_approvals_workspace(env)
