def migrate(cr, version):
    """Create polymarket_bot.market rows from saved condition_ids and backfill FK columns."""
    cr.execute("""
        SELECT DISTINCT market_id_old
        FROM (
            SELECT market_id_old FROM polymarket_bot_position  WHERE market_id_old IS NOT NULL
            UNION
            SELECT market_id_old FROM polymarket_bot_trade      WHERE market_id_old IS NOT NULL
            UNION
            SELECT market_id_old FROM polymarket_bot_arb_signal WHERE market_id_old IS NOT NULL
        ) sub
    """)
    cids = [row[0] for row in cr.fetchall()]

    for cid in cids:
        cr.execute(
            """
            INSERT INTO polymarket_bot_market
                (condition_id, name, state, create_uid, write_uid, create_date, write_date)
            VALUES (%s, %s, 'active', 1, 1, now(), now())
            ON CONFLICT (condition_id) DO NOTHING
            """,
            (cid, cid[:8]),
        )

    for table in (
        "polymarket_bot_position",
        "polymarket_bot_trade",
        "polymarket_bot_arb_signal",
    ):
        cr.execute(f"""
            UPDATE {table} t
            SET    market_id = m.id
            FROM   polymarket_bot_market m
            WHERE  t.market_id_old = m.condition_id
        """)
        cr.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS market_id_old")
