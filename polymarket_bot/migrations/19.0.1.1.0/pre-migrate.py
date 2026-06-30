def migrate(cr, version):
    """Save existing char market_id values before ORM replaces the column with an integer FK."""
    for table in (
        "polymarket_bot_position",
        "polymarket_bot_trade",
        "polymarket_bot_arb_signal",
    ):
        cr.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS market_id_old VARCHAR"
        )
        cr.execute(
            f"UPDATE {table} SET market_id_old = market_id::text WHERE market_id IS NOT NULL"
        )
        # Drop the varchar column so Odoo's _auto_init creates a fresh integer column.
        cr.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS market_id")
