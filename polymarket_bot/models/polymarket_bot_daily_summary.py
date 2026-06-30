from datetime import datetime, timedelta

from odoo import models, fields, api


class DailySummary(models.Model):
    _name = "polymarket_bot.daily_summary"
    _description = "Daily Trading Summary"
    _order = "date desc"
    _rec_name = "date"
    _sql_constraints = [
        ("date_paper_uniq", "UNIQUE(date, paper)", "One summary per date per mode"),
    ]

    date = fields.Date(
        index=True,
        required=True,
    )
    paper = fields.Boolean(
        default=True,
    )

    net_pnl = fields.Float(digits=(10, 4))
    gross_pnl = fields.Float(digits=(10, 4))
    total_trades = fields.Integer()
    positions_closed = fields.Integer()
    positions_delta_neutral = fields.Integer()
    positions_unhedged = fields.Integer()
    avg_pair_cost = fields.Float(digits=(10, 4))
    win_rate = fields.Float(string="Win rate %", digits=(5, 2))

    @api.model
    def recompute_for_date(self, target_date, paper=True):
        Position = self.env["polymarket_bot.position"]
        date_start = datetime.combine(target_date, datetime.min.time())
        date_end = date_start + timedelta(days=1)

        positions = Position.search([
            ("closed_at", ">=", date_start),
            ("closed_at", "<", date_end),
            ("paper", "=", paper),
        ])

        existing = self.search([("date", "=", target_date), ("paper", "=", paper)], limit=1)

        if not positions:
            existing.unlink()
            return

        net_pnl = sum(positions.mapped("final_pnl"))
        total_trades = sum(len(p.trade_ids) for p in positions)
        delta_neutral_count = len(positions.filtered(
            lambda p: p.state in ("delta_neutral", "closed") and not p.unhedged
        ))
        unhedged_count = len(positions.filtered(
            lambda p: p.unhedged or p.state == "unhedged_expiry"
        ))
        pair_costs = positions.filtered(lambda p: p.pair_cost > 0).mapped("pair_cost")
        avg_pair_cost = sum(pair_costs) / len(pair_costs) if pair_costs else 0.0
        wins = len(positions.filtered(lambda p: p.final_pnl > 0))
        win_rate = (wins / len(positions) * 100) if positions else 0.0

        vals = {
            "date": target_date,
            "paper": paper,
            "net_pnl": net_pnl,
            "gross_pnl": net_pnl,
            "total_trades": total_trades,
            "positions_closed": len(positions),
            "positions_delta_neutral": delta_neutral_count,
            "positions_unhedged": unhedged_count,
            "avg_pair_cost": avg_pair_cost,
            "win_rate": win_rate,
        }
        if existing:
            existing.write(vals)
        else:
            self.create(vals)

    @api.model
    def recompute_today(self, paper=True):
        self.recompute_for_date(fields.Date.context_today(self), paper=paper)

    @api.model
    def recompute_all(self, paper=True):
        Position = self.env["polymarket_bot.position"]
        positions = Position.search([("closed_at", "!=", False), ("paper", "=", paper)])
        dates = set(p.closed_at.date() for p in positions)
        for d in dates:
            self.recompute_for_date(d, paper=paper)
