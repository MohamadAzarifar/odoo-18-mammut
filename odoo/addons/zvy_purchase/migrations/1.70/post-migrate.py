def migrate(cr, version):
    """Set Tendering state on purchase items already linked to a tender."""
    cr.execute(
        """
        UPDATE zvy_purchase_item AS item
        SET state = 'tendering'
        WHERE item.state IS DISTINCT FROM 'tendering'
          AND EXISTS (
            SELECT 1
            FROM zvy_purchase_tender_item_rel AS rel
            WHERE rel.item_id = item.id
          )
        """
    )
