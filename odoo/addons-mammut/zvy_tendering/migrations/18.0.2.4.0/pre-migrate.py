# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Snapshot bid header amounts before they become computed from lines."""
    cr.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'zvy_closed_envelope_bid'
    """)
    if not cr.fetchone():
        return
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zvy_closed_envelope_bid'
          AND column_name = 'amount'
    """)
    if not cr.fetchone():
        return
    cr.execute("DROP TABLE IF EXISTS zvy_ce_bid_amount_bak")
    cr.execute("""
        CREATE TABLE zvy_ce_bid_amount_bak AS
        SELECT id, envelope_id, amount FROM zvy_closed_envelope_bid
    """)
