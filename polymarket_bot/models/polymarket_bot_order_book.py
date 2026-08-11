from odoo import models, fields


class OrderBookSnapshot(models.Model):
    _name = "polymarket_bot.order_book_snapshot"
    _description = "Order Book Depth Level"
    _order = "snapshot_time desc, level asc"

    market_id = fields.Many2one(
        "polymarket_bot.market",
        required=True,
        index=True,
        ondelete="cascade",
        string="Market",
    )
    snapshot_time = fields.Datetime(
        required=True,
        index=True,
        default=fields.Datetime.now,
        string="Time",
    )
    token_side = fields.Selection(
        [("yes", "Yes/UP"), ("no", "No/DOWN")],
        required=True,
        string="Token",
    )
    book_side = fields.Selection(
        [("bid", "Bid"), ("ask", "Ask")],
        required=True,
        string="Side",
    )
    level = fields.Integer(required=True, default=0, string="Level")
    price = fields.Float(digits=(10, 4), string="Price")
    size = fields.Float(digits=(16, 4), string="Size")
    source = fields.Selection(
        [("ws", "WS book event"), ("rest", "REST poll")],
        default="rest",
        string="Source",
    )
