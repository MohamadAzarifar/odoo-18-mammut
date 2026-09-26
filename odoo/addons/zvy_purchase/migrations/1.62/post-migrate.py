def migrate(cr, version):
    """Set Commission state on PRs that already have a commission case."""
    cr.execute(
        """
        UPDATE zvy_purchase_request AS request
        SET state = 'commission'
        WHERE request.state IS DISTINCT FROM 'commission'
          AND EXISTS (
            SELECT 1
            FROM zvy_purchase_commission_case AS commission_case
            WHERE commission_case.request_id = request.id
          )
        """
    )
