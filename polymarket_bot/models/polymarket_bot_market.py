import pytz
from datetime import datetime

from odoo import models, fields, api


def _name_from_slug(slug):
    try:
        ts = int(slug.split("-")[-1])
        if ts > 1_000_000_000:
            et = pytz.timezone("America/New_York")
            start = datetime.fromtimestamp(ts, tz=et)
            end = datetime.fromtimestamp(ts + 900, tz=et)
            return (
                f"Bitcoin Up or Down – "
                f"{start.strftime('%b %-d')}, "
                f"{start.strftime('%-I:%M')}–{end.strftime('%-I:%M %p')} ET"
            )
    except Exception:
        pass
    return None


class Market(models.Model):
    _name = "polymarket_bot.market"
    _description = "Polymarket Market"
    _order = "id desc"
    _rec_name = "name"
    _condition_id_uniq = models.Constraint(
        "UNIQUE(condition_id)",
        "condition_id must be unique",
    )

    condition_id = fields.Char(
        required=True,
        index=True,
        string="Condition ID",
    )
    name = fields.Char(
        compute="_compute_name",
        store=True,
        string="Name",
    )
    question = fields.Char(
        string="Question",
    )
    market_slug = fields.Char(
        string="Slug",
    )
    url = fields.Char(
        compute="_compute_url",
        store=True,
        string="URL",
    )
    end_time = fields.Datetime(
        string="End Time",
    )
    state = fields.Selection(
        selection=[
            ("active", "Active"),
            ("expired", "Expired"),
        ],
        default="active",
        required=True,
        string="State",
    )

    position_ids = fields.One2many(
        "polymarket_bot.position",
        "market_id",
        string="Positions",
    )
    trade_ids = fields.One2many(
        "polymarket_bot.trade",
        "market_id",
        string="Trades",
    )
    signal_ids = fields.One2many(
        "polymarket_bot.arb_signal",
        "market_id",
        string="Signals",
    )
    price_ids = fields.One2many(
        "polymarket_bot.market_price",
        "market_id",
        string="Price History",
    )

    position_count = fields.Integer(
        compute="_compute_counts",
    )
    trade_count = fields.Integer(
        compute="_compute_counts",
    )
    signal_count = fields.Integer(
        compute="_compute_counts",
    )
    price_count = fields.Integer(
        compute="_compute_counts",
    )

    @api.depends("market_slug", "question", "condition_id")
    def _compute_name(self):
        for rec in self:
            name = None
            if rec.market_slug:
                name = _name_from_slug(rec.market_slug)
            if not name:
                name = rec.question or (rec.condition_id[:8] if rec.condition_id else "")
            rec.name = name

    @api.depends("market_slug")
    def _compute_url(self):
        for rec in self:
            if rec.market_slug:
                rec.url = f"https://polymarket.com/event/{rec.market_slug}"
            else:
                rec.url = ""

    @api.depends("position_ids", "trade_ids", "signal_ids")
    def _compute_counts(self):
        for rec in self:
            rec.position_count = len(rec.position_ids)
            rec.trade_count = len(rec.trade_ids)
            rec.signal_count = len(rec.signal_ids)
            rec.price_count = len(rec.price_ids)

    def action_view_positions(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Positions",
            "res_model": "polymarket_bot.position",
            "view_mode": "list,form",
            "domain": [("market_id", "=", self.id)],
        }

    def action_view_trades(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Trades",
            "res_model": "polymarket_bot.trade",
            "view_mode": "list",
            "domain": [("market_id", "=", self.id)],
        }

    def action_view_signals(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Signals",
            "res_model": "polymarket_bot.arb_signal",
            "view_mode": "list",
            "domain": [("market_id", "=", self.id)],
        }

    def get_price_chart_data(self):
        self.ensure_one()
        ticks = self.env["polymarket_bot.market_price"].search(
            [("market_id", "=", self.id)],
            order="tick_time asc",
            limit=5000,
        )
        return {
            "labels": [t.tick_time.isoformat() for t in ticks],
            "yes_ask": [t.yes_ask for t in ticks],
            "no_ask": [t.no_ask for t in ticks],
        }
