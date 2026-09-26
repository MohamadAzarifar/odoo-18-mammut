def migrate(cr, version):
    """Set Approval state on PRs that already have linked Approvals app requests."""
    cr.execute(
        """
        UPDATE zvy_purchase_request AS request
        SET state = 'approval'
        WHERE request.state IS DISTINCT FROM 'approval'
          AND EXISTS (
            SELECT 1
            FROM approval_request AS approval
            WHERE approval.zvy_purchase_request_id = request.id
          )
        """
    )
