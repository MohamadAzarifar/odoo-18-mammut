def migrate(cr, version):
    cr.execute(
        """
        UPDATE zvy_purchase_commission_case
           SET state = 'in_review'
         WHERE state IS NULL
            OR state = ''
        """
    )
