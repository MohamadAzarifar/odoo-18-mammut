# -*- coding: utf-8 -*-
"""Make AVL global: collapse per-company duplicates and drop company_id."""
from odoo.tools.sql import column_exists, table_exists


def migrate(cr, version):
    if not table_exists(cr, 'zvy_avl_entry'):
        return
    if not column_exists(cr, 'zvy_avl_entry', 'company_id'):
        return

    cr.execute("""
        DELETE FROM zvy_avl_entry
         WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY partner_id,
                                        COALESCE(product_id, 0),
                                        COALESCE(categ_id, 0)
                           ORDER BY active DESC, id ASC
                       ) AS rn
                  FROM zvy_avl_entry
            ) ranked
            WHERE rn > 1
         )
    """)
    cr.execute('ALTER TABLE zvy_avl_entry DROP COLUMN company_id')
