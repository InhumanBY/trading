from odoo import models, fields
from . import utils


class ArbSignal(models.Model):
    _name = "polymarket_bot.arb_signal"
    _description = "Arbitrage Signal"
    _order = "signal_time desc"

    market_id = fields.Many2one(
        "polymarket_bot.market", string="Market", index=True, ondelete="restrict"
    )
    signal_type = fields.Selection(
        [
            ("entry_yes", "Entry YES"),
            ("entry_no", "Entry NO"),
            ("hedge_no", "Hedge NO"),
            ("hedge_yes", "Hedge YES"),
            ("delta_balance", "Delta Balance"),
        ],
        required=True,
    )
    yes_ask = fields.Float(digits=(10, 6))
    no_ask = fields.Float(digits=(10, 6))
    avg_yes_position = fields.Float(digits=(10, 6))
    avg_no_position = fields.Float(digits=(10, 6))
    projected_pair_cost = fields.Float(digits=(10, 6))
    position_state_before = fields.Char()
    acted_on = fields.Boolean(default=False)
    skip_reason = fields.Char()
    signal_time = fields.Datetime(default=fields.Datetime.now, index=True)

    def _auto_init(self):
        utils.migrate_market_id_to_fk(self.env.cr, self._table)
        return super()._auto_init()
