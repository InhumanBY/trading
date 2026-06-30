def migrate_market_id_to_fk(cr, table):
    """
    Called from _auto_init on models that changed market_id from Char to Many2one.

    If the column is still VARCHAR (upgrade scenario), saves the condition_id values
    to market_id_old and drops the column so Odoo can create the integer FK column.
    After super()._auto_init() has created the integer column, the post-migrate script
    (or the next call from each model's _auto_init) backfills the FK via market_id_old.

    This runs inside the ORM initialisation transaction, so it executes before Odoo's
    own column-type conversion attempt — which would fail on hex condition_id strings.
    """
    # Step 1: if market_id is still varchar, save and drop it
    cr.execute(
        "SELECT udt_name FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = 'market_id'",
        (table,),
    )
    row = cr.fetchone()
    if row and row[0] == "varchar":
        cr.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS market_id_old VARCHAR")
        cr.execute(
            f"UPDATE {table} SET market_id_old = market_id WHERE market_id IS NOT NULL"
        )
        cr.execute(f"ALTER TABLE {table} DROP COLUMN market_id")
        # super()._auto_init() will now create a fresh integer column named market_id
