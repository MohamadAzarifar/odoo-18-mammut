def migrate(cr, version):
    cr.execute(
        """
        UPDATE zvy_purchase_tender
           SET state = 'evaluation'
         WHERE state = 'opened'
        """
    )
