from odoo import models, fields


class DailySummary(models.Model):
    _name = "polymarket_bot.daily_summary"
    _description = "Daily Trading Summary"
    _order = "date desc"
    _sql_constraints = [
        ("date_paper_uniq", "UNIQUE(date, paper)", "One summary per date per mode"),
    ]

    date = fields.Date(
        index=True,
        required=True,
    )
    total_signals = fields.Integer()
    entry_signals = fields.Integer()
    hedge_signals = fields.Integer()
    total_trades = fields.Integer()
    positions_delta_neutral = fields.Integer()
    positions_hedged = fields.Integer()
    positions_unhedged = fields.Integer()
    gross_pnl = fields.Float(
        digits=(10, 4),
    )
    net_pnl = fields.Float(
        digits=(10, 4),
    )
    avg_pair_cost = fields.Float(
        digits=(10, 6),
    )
    paper = fields.Boolean(
        default=True,
    )
