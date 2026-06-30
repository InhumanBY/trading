from odoo import models, fields


class MarketPrice(models.Model):
    _name = "polymarket_bot.market_price"
    _description = "Polymarket Price Tick"
    _order = "tick_time desc"

    market_id = fields.Many2one(
        "polymarket_bot.market",
        required=True,
        index=True,
        ondelete="cascade",
        string="Market",
    )
    tick_time = fields.Datetime(required=True, index=True, default=fields.Datetime.now, string="Time")
    yes_ask = fields.Float(digits=(10, 6), string="UP Ask")
    no_ask = fields.Float(digits=(10, 6), string="DOWN Ask")
