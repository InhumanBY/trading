from odoo import models, fields, api
from . import utils


class Position(models.Model):
    _name = "polymarket_bot.position"
    _description = "Polymarket Position"
    _order = "opened_at desc"

    market_id = fields.Many2one(
        "polymarket_bot.market",
        string="Market",
        index=True,
        ondelete="cascade",
    )
    state = fields.Selection(
        selection=[
            ("empty", "Empty"),
            ("one_side_yes", "Have YES, need NO"),
            ("one_side_no", "Have NO, need YES"),
            ("hedged", "Hedged"),
            ("delta_neutral", "Delta Neutral"),
            ("unhedged_expiry", "Unhedged Expiry"),
            ("closed", "Closed"),
        ],
        default="empty",
        required=True,
    )

    qty_yes = fields.Float(
        digits=(16, 6),
    )
    qty_no = fields.Float(
        digits=(16, 6),
    )
    cost_yes = fields.Float(
        digits=(16, 6),
    )
    cost_no = fields.Float(
        digits=(16, 6),
    )

    avg_yes = fields.Float(
        compute="_compute_averages",
        digits=(10, 6),
    )
    avg_no = fields.Float(
        compute="_compute_averages",
        digits=(10, 6),
    )
    delta = fields.Float(
        compute="_compute_averages",
        digits=(16, 6),
    )
    pair_cost = fields.Float(
        compute="_compute_averages",
        digits=(10, 6),
    )
    locked_profit = fields.Float(
        compute="_compute_averages",
        digits=(10, 6),
    )
    projected_pnl_yes_wins = fields.Float(
        compute="_compute_averages",
        digits=(10, 6),
    )
    projected_pnl_no_wins = fields.Float(
        compute="_compute_averages",
        digits=(10, 6),
    )

    paper = fields.Boolean(
        default=True,
    )
    market_end_time = fields.Datetime()
    opened_at = fields.Datetime(
        default=fields.Datetime.now,
    )
    hedged_at = fields.Datetime()
    delta_neutral_at = fields.Datetime()
    closed_at = fields.Datetime()
    final_pnl = fields.Float(
        digits=(10, 6),
    )
    unhedged = fields.Boolean(
        default=False,
    )
    winning_side = fields.Selection(
        [('yes', 'Up (Yes)'), ('no', 'Down (No)'), ('unknown', 'Unknown')],
        string="Winning Side",
        default='unknown',
    )
    result_label = fields.Char(
        string="Result",
        compute="_compute_result_label",
    )
    state_log = fields.Text()

    trade_ids = fields.One2many(
        "polymarket_bot.trade",
        "position_id",
        string="Trades",
    )

    @api.depends("winning_side")
    def _compute_result_label(self):
        labels = {"yes": "Up Won", "no": "Down Won", "unknown": "Unknown"}
        for rec in self:
            rec.result_label = labels.get(rec.winning_side, "Unknown")

    def _auto_init(self):
        utils.migrate_market_id_to_fk(self.env.cr, self._table)
        return super()._auto_init()

    @api.depends("qty_yes", "qty_no", "cost_yes", "cost_no", "state")
    def _compute_averages(self):
        for rec in self:
            rec.avg_yes = rec.cost_yes / rec.qty_yes if rec.qty_yes > 0 else 0.0
            rec.avg_no = rec.cost_no / rec.qty_no if rec.qty_no > 0 else 0.0
            rec.delta = rec.qty_yes - rec.qty_no
            rec.pair_cost = rec.avg_yes + rec.avg_no

            if rec.state in ("hedged", "delta_neutral"):
                min_qty = min(rec.qty_yes, rec.qty_no)
                rec.locked_profit = min_qty - (rec.cost_yes + rec.cost_no)
            else:
                rec.locked_profit = 0.0

            rec.projected_pnl_yes_wins = rec.qty_yes - rec.cost_yes - rec.cost_no
            rec.projected_pnl_no_wins = rec.qty_no - rec.cost_yes - rec.cost_no
