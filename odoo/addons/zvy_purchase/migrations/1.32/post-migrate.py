def migrate(cr, version):
    """Set purchase-item UoM from the product when still on a wrong-category placeholder."""
    cr.execute(
        """
        UPDATE zvy_purchase_item AS item
        SET product_uom_id = COALESCE(pt.uom_po_id, pt.uom_id)
        FROM product_product AS pp
        JOIN product_template AS pt ON pt.id = pp.product_tmpl_id
        WHERE item.product_id = pp.id
          AND COALESCE(pt.uom_po_id, pt.uom_id) IS NOT NULL
          AND (
            item.product_uom_id IS NULL
            OR item.product_uom_id NOT IN (
                SELECT u.id
                FROM uom_uom AS u
                JOIN uom_uom AS product_uom
                    ON product_uom.category_id = u.category_id
                WHERE product_uom.id = COALESCE(pt.uom_po_id, pt.uom_id)
            )
          )
        """
    )
