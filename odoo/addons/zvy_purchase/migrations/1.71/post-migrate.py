def migrate(cr, version):
    """Set In Review on existing tenders that have no status yet."""
    cr.execute(
        """
        UPDATE zvy_purchase_tender
        SET state = 'in_review'
        WHERE state IS NULL
           OR state = ''
        """
    )
