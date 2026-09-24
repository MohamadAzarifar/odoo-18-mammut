def migrate(cr, version):
    """Backfill purchase-item workflow states from request state and experts."""
    cr.execute(
        """
        UPDATE zvy_purchase_item AS item
        SET state = CASE
            WHEN EXISTS (
                SELECT 1
                FROM zvy_purchase_item_commercial_expert_rel AS rel
                WHERE rel.item_id = item.id
            ) THEN 'in_review'
            WHEN request.state = 'in_review' THEN 'submitted'
            ELSE 'draft'
        END
        FROM zvy_purchase_request AS request
        WHERE item.request_id = request.id
          AND (
            item.state IS NULL
            OR item.state = 'draft'
          )
        """
    )
