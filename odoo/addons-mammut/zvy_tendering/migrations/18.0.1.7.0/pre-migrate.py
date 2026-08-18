# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Copy category commission flags onto product templates before the column drops."""
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'product_category'
          AND column_name = 'zvy_is_commission_item'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'product_template'
          AND column_name = 'zvy_procurement_type'
    """)
    if not cr.fetchone():
        cr.execute("""
            ALTER TABLE product_template
                ADD COLUMN zvy_procurement_type varchar,
                ADD COLUMN zvy_need_commission boolean
        """)

    cr.execute("""
        UPDATE product_template pt
        SET zvy_procurement_type = COALESCE(pt.zvy_procurement_type, 'enquiry'),
            zvy_need_commission = COALESCE(
                pt.zvy_need_commission,
                COALESCE(pc.zvy_is_commission_item, false)
            )
        FROM product_category pc
        WHERE pt.categ_id = pc.id
    """)
