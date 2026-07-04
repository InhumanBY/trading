from odoo import models, fields, api


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
    tick_time = fields.Datetime(
        required=True,
        index=True,
        default=fields.Datetime.now,
        string="Time",
    )
    yes_ask = fields.Float(digits=(10, 4), string="UP Ask")
    no_ask = fields.Float(digits=(10, 4), string="DOWN Ask")

    # Bid-сторона стакана (только из WS; при REST fallback = ask)
    yes_bid = fields.Float(digits=(10, 4), string="UP Bid")
    no_bid = fields.Float(digits=(10, 4), string="DOWN Bid")

    # Спреды: ask - bid для каждой стороны
    yes_spread = fields.Float(digits=(10, 4), string="UP Spread", compute="_compute_spreads", store=True)
    no_spread  = fields.Float(digits=(10, 4), string="DOWN Spread", compute="_compute_spreads", store=True)

    # Источник цены: ws (WebSocket) или rest (REST fallback)
    price_source = fields.Selection(
        [("ws", "WebSocket"), ("rest", "REST fallback")],
        string="Source",
        default="ws",
    )

    @api.depends("yes_ask", "yes_bid", "no_ask", "no_bid")
    def _compute_spreads(self):
        for rec in self:
            rec.yes_spread = round(rec.yes_ask - rec.yes_bid, 4) if rec.yes_bid else 0.0
            rec.no_spread  = round(rec.no_ask  - rec.no_bid,  4) if rec.no_bid  else 0.0
