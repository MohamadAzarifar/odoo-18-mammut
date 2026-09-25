def migrate(cr, version):
    """Backfill purchase-item Selected from offers already Selected."""
    cr.execute(
        """
        UPDATE zvy_purchase_item AS item
        SET state = 'selected'
        WHERE item.state IS DISTINCT FROM 'selected'
          AND EXISTS (
            SELECT 1
            FROM zvy_purchase_offer AS offer
            WHERE offer.item_id = item.id
              AND offer.state = 'selected'
          )
        """
    )
