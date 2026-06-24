from odoo import models, fields


class Trade(models.Model):
    _name = "polymarket_bot.trade"
    _description = "Polymarket Trade"
    _order = "trade_time desc"

    market_id = fields.Char(index=True)
    side = fields.Selection([("yes", "YES"), ("no", "NO")], required=True)
    qty = fields.Float(digits=(16, 6))
    price = fields.Float(digits=(10, 6))
    cost = fields.Float(digits=(10, 6))
    order_id = fields.Char()
    trade_type = fields.Selection(
        [
            ("entry", "Entry"),
            ("hedge", "Hedge"),
            ("delta_balance", "Delta Balance"),
        ],
        required=True,
    )
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("filled", "Filled"),
            ("partial", "Partial"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
    )
    paper = fields.Boolean(default=True)
    trade_time = fields.Datetime(default=fields.Datetime.now, index=True)
    position_id = fields.Many2one("polymarket_bot.position", ondelete="set null")
