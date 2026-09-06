# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Backfill line purchase_state from the parent PR terminal state."""
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zvy_purchase_request_line'
          AND column_name = 'purchase_state'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        UPDATE zvy_purchase_request_line line
        SET purchase_state = CASE
            WHEN pr.state = 'done' THEN 'ordered'
            WHEN pr.state = 'rejected' THEN 'cancelled'
            ELSE COALESCE(line.purchase_state, 'pending')
        END
        FROM zvy_purchase_request pr
        WHERE line.request_id = pr.id
    """)
