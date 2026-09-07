# -*- coding: utf-8 -*-
"""Add product.template columns before the upgraded Python fields are registered.

Keep in sync with ``hooks.ensure_product_template_columns`` (do not import the
addon here: pre-migrate runs before ``load_openerp_module``).
"""
from odoo.tools.sql import column_exists, create_column

_PRODUCT_TEMPLATE_COLUMNS = (
    ('zvy_procurement_type', 'varchar'),
    ('zvy_need_commission', 'bool'),
)


def migrate(cr, version):
    for name, coltype in _PRODUCT_TEMPLATE_COLUMNS:
        if not column_exists(cr, 'product_template', name):
            create_column(cr, 'product_template', name, coltype)
    if column_exists(cr, 'product_template', 'zvy_procurement_type'):
        cr.execute("""
            UPDATE product_template
               SET zvy_procurement_type = 'enquiry'
             WHERE zvy_procurement_type IS NULL
        """)
    if column_exists(cr, 'product_template', 'zvy_need_commission'):
        cr.execute("""
            UPDATE product_template
               SET zvy_need_commission = false
             WHERE zvy_need_commission IS NULL
        """)
