# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Scope existing envelopes to all PR lines and turn lump amounts into bid lines."""
    cr.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'zvy_closed_envelope_request_line_rel'
    """)
    if cr.fetchone():
        cr.execute("""
            INSERT INTO zvy_closed_envelope_request_line_rel
                (envelope_id, request_line_id)
            SELECT ce.id, line.id
            FROM zvy_closed_envelope ce
            JOIN zvy_purchase_request_line line ON line.request_id = ce.request_id
            WHERE NOT EXISTS (
                SELECT 1 FROM zvy_closed_envelope_request_line_rel rel
                WHERE rel.envelope_id = ce.id AND rel.request_line_id = line.id
            )
        """)

    cr.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'zvy_closed_envelope_bid_line'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'zvy_ce_bid_amount_bak'
    """)
    has_bak = bool(cr.fetchone())
    amount_source = 'zvy_ce_bid_amount_bak' if has_bak else 'zvy_closed_envelope_bid'

    cr.execute("""
        INSERT INTO zvy_closed_envelope_bid_line
            (bid_id, request_line_id, price_unit, discount_percent, final_price,
             is_winner, create_uid, write_uid, create_date, write_date)
        SELECT
            bid.id,
            line.id,
            CASE
                WHEN COALESCE(line.product_uom_qty, 0) = 0 THEN COALESCE(bak.amount, 0)
                ELSE COALESCE(bak.amount, 0) / line.product_uom_qty
            END,
            0,
            CASE
                WHEN COALESCE(line.product_uom_qty, 0) = 0 THEN COALESCE(bak.amount, 0)
                ELSE COALESCE(bak.amount, 0) / line.product_uom_qty
            END,
            FALSE,
            1, 1, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC'
        FROM zvy_closed_envelope_bid bid
        JOIN %s bak ON bak.id = bid.id
        JOIN zvy_closed_envelope ce ON ce.id = bid.envelope_id
        JOIN zvy_purchase_request_line line ON line.request_id = ce.request_id
        WHERE NOT EXISTS (
            SELECT 1 FROM zvy_closed_envelope_bid_line bl
            WHERE bl.bid_id = bid.id AND bl.request_line_id = line.id
        )
        AND line.id = (
            SELECT MIN(l2.id) FROM zvy_purchase_request_line l2
            WHERE l2.request_id = ce.request_id
        )
    """ % amount_source)

    if has_bak:
        cr.execute("DROP TABLE IF EXISTS zvy_ce_bid_amount_bak")
