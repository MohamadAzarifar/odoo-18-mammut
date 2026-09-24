def migrate(cr, version):
    """Backfill offer quantity from the parent purchase item."""
    cr.execute(
        """
        UPDATE zvy_purchase_offer AS offer
        SET quantity = item.product_qty
        FROM zvy_purchase_item AS item
        WHERE offer.item_id = item.id
          AND (offer.quantity IS NULL OR offer.quantity = 0)
          AND item.product_qty IS NOT NULL
          AND item.product_qty <> 0
        """
    )
