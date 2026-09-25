def migrate(cr, version):
    """Align offer locked state: submitted → in_review (Reject targets In Review)."""
    cr.execute(
        """
        UPDATE zvy_purchase_offer
        SET state = 'in_review'
        WHERE state = 'submitted'
        """
    )
