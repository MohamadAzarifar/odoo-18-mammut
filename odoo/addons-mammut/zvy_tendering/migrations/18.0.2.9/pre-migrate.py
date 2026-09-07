# -*- coding: utf-8 -*-
"""Add res.company columns before the upgraded Python fields are registered.

Keep in sync with ``hooks.ensure_res_company_columns`` (do not import the
addon here: pre-migrate runs before ``load_openerp_module``).
"""
from odoo.tools.sql import column_exists, create_column

_RES_COMPANY_COLUMNS = (
    ('zvy_high_value_threshold', 'numeric'),
    ('zvy_default_bid_window_hours', 'int4'),
    ('zvy_signatory_approval_category_id', 'int4'),
    ('zvy_company_scale', 'varchar'),
    ('zvy_use_custom_bands', 'bool'),
    ('zvy_op_minor_max', 'numeric'),
    ('zvy_op_medium_max', 'numeric'),
    ('zvy_op_major_max', 'numeric'),
    ('zvy_op_large_ceo_max', 'numeric'),
    ('zvy_nop_minor_max', 'numeric'),
    ('zvy_nop_medium_max', 'numeric'),
    ('zvy_nop_major_max', 'numeric'),
    ('zvy_nop_large_ceo_max', 'numeric'),
    ('zvy_commission_notice_days', 'int4'),
    ('zvy_commission_require_proforma', 'bool'),
    ('zvy_commission_require_comparison', 'bool'),
    ('zvy_commission_require_technical', 'bool'),
)


def migrate(cr, version):
    for name, coltype in _RES_COMPANY_COLUMNS:
        if not column_exists(cr, 'res_company', name):
            create_column(cr, 'res_company', name, coltype)
    if column_exists(cr, 'res_company', 'zvy_company_scale'):
        cr.execute("""
            UPDATE res_company
               SET zvy_company_scale = 'small'
             WHERE zvy_company_scale IS NULL
        """)
    if column_exists(cr, 'res_company', 'zvy_default_bid_window_hours'):
        cr.execute("""
            UPDATE res_company
               SET zvy_default_bid_window_hours = 72
             WHERE zvy_default_bid_window_hours IS NULL
        """)
    if column_exists(cr, 'res_company', 'zvy_commission_notice_days'):
        cr.execute("""
            UPDATE res_company
               SET zvy_commission_notice_days = 0
             WHERE zvy_commission_notice_days IS NULL
        """)
