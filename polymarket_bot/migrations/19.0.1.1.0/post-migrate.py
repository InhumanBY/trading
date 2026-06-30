def migrate(cr, version):
    """Create polymarket_bot.market rows from saved condition_ids and backfill FK columns."""
    tables = (
        "polymarket_bot_position",
        "polymarket_bot_trade",
        "polymarket_bot_arb_signal",
    )

    # Only work with tables that actually have the temp column
    tables_with_old = []
    for table in tables:
        cr.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = 'market_id_old'",
            (table,),
        )
        if cr.fetchone():
            tables_with_old.append(table)

    if not tables_with_old:
        return

    # Collect all unique condition_ids across present temp columns
    union_parts = " UNION ".join(
        f"SELECT market_id_old FROM {t} WHERE market_id_old IS NOT NULL"
        for t in tables_with_old
    )
    cr.execute(f"SELECT DISTINCT market_id_old FROM ({union_parts}) sub")
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

    for table in tables_with_old:
        cr.execute(f"""
            UPDATE {table} t
            SET    market_id = m.id
            FROM   polymarket_bot_market m
            WHERE  t.market_id_old = m.condition_id
              AND  t.market_id IS NULL
        """)
        cr.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS market_id_old")
