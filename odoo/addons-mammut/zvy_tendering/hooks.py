# -*- coding: utf-8 -*-
"""Install/upgrade hooks.

New stored columns on ``res.company`` and ``product.template`` must exist
before the ORM prefetches those models. That happens during Apps
install/upgrade on a running server (``registry.ready`` is True) and on
worker restart when the Python fields are already loaded but ``-u`` has
not run yet. PostgreSQL then errors with
``column res_company.zvy_company_scale does not exist`` or
``column product_template.zvy_procurement_type does not exist``.
"""
from odoo.tools.sql import create_column

# Stored columns on res.company (Many2many uses separate tables).
_RES_COMPANY_COLUMNS = (
    ('zvy_default_bid_window_hours', 'int4'),
    ('zvy_signatory_approval_category_id', 'int4'),
    ('zvy_signatory_minor_job_id', 'int4'),
    ('zvy_signatory_medium_job_id', 'int4'),
    ('zvy_signatory_major_job_id', 'int4'),
    ('zvy_signatory_large_job_id', 'int4'),
    ('zvy_signatory_board_job_id', 'int4'),
    ('zvy_signatory_formalities_job_id', 'int4'),
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


def ensure_res_company_columns(cr):
    """Create missing zvy_* columns on res_company and backfill required defaults."""
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'res_company' AND column_name IN %s
        """,
        [tuple(name for name, _unused in _RES_COMPANY_COLUMNS)],
    )
    existing = {row[0] for row in cr.fetchall()}
    created = []
    for name, coltype in _RES_COMPANY_COLUMNS:
        if name not in existing:
            create_column(cr, 'res_company', name, coltype)
            created.append(name)
    if not created:
        return
    if 'zvy_company_scale' in created:
        cr.execute("""
            UPDATE res_company
               SET zvy_company_scale = 'small'
             WHERE zvy_company_scale IS NULL
        """)
    if 'zvy_default_bid_window_hours' in created:
        cr.execute("""
            UPDATE res_company
               SET zvy_default_bid_window_hours = 72
             WHERE zvy_default_bid_window_hours IS NULL
        """)
    if 'zvy_commission_notice_days' in created:
        cr.execute("""
            UPDATE res_company
               SET zvy_commission_notice_days = 0
             WHERE zvy_commission_notice_days IS NULL
        """)


_PRODUCT_TEMPLATE_COLUMNS = (
    ('zvy_procurement_type', 'varchar'),
    ('zvy_need_commission', 'bool'),
)


def ensure_product_template_columns(cr):
    """Create missing zvy_* columns on product_template and backfill defaults."""
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'product_template' AND column_name IN %s
        """,
        [tuple(name for name, _unused in _PRODUCT_TEMPLATE_COLUMNS)],
    )
    existing = {row[0] for row in cr.fetchall()}
    created = []
    for name, coltype in _PRODUCT_TEMPLATE_COLUMNS:
        if name not in existing:
            create_column(cr, 'product_template', name, coltype)
            created.append(name)
    if not created:
        return
    if 'zvy_procurement_type' in created:
        cr.execute("""
            UPDATE product_template
               SET zvy_procurement_type = 'enquiry'
             WHERE zvy_procurement_type IS NULL
        """)
    if 'zvy_need_commission' in created:
        cr.execute("""
            UPDATE product_template
               SET zvy_need_commission = false
             WHERE zvy_need_commission IS NULL
        """)


def pre_init_hook(env):
    ensure_res_company_columns(env.cr)
    ensure_product_template_columns(env.cr)
