import uuid
from odoo import models, fields, api


class BotConfig(models.Model):
    _name = "polymarket_bot.config"
    _description = "Polymarket Bot Configuration"
    _inherit = ["mail.thread"]

    name = fields.Char(default="Polymarket Bot Config", required=True)
    bot_status = fields.Selection(
        [("stopped", "Stopped"), ("running", "Running"), ("paused", "Paused")],
        default="stopped",
        readonly=True,
        tracking=True,
    )
    paper_trading = fields.Boolean(default=True, tracking=True)

    # Strategy
    entry_threshold = fields.Float(default=0.50, digits=(10, 4))
    target_pair_cost = fields.Float(default=0.975, digits=(10, 4))
    delta_neutral_threshold = fields.Float(default=10.0)
    position_size_usd = fields.Float(default=20.0)
    stop_entry_minutes = fields.Float(default=2.0)
    stop_hedge_minutes = fields.Float(default=1.0)

    # Risk limits
    max_position_per_market_usd = fields.Float(default=200.0)
    max_total_exposure_usd = fields.Float(default=500.0)
    daily_loss_limit_usd = fields.Float(default=-30.0)

    # Connections
    polymarket_api_key = fields.Char()
    polymarket_secret = fields.Char(password=True)
    polymarket_passphrase = fields.Char(password=True)
    wallet_private_key = fields.Char(password=True)
    telegram_bot_token = fields.Char(password=True)
    telegram_chat_id = fields.Char()
    api_token = fields.Char(readonly=True)

    # Bot state (updated by bot via API)
    last_heartbeat = fields.Datetime(readonly=True)
    bot_pid = fields.Integer(readonly=True)

    # Dashboard computed
    open_positions_count = fields.Integer(compute="_compute_dashboard")
    one_side_positions_count = fields.Integer(compute="_compute_dashboard")
    today_net_pnl = fields.Float(compute="_compute_dashboard", digits=(10, 4))
    today_positions_delta_neutral = fields.Integer(compute="_compute_dashboard")
    today_positions_unhedged = fields.Integer(compute="_compute_dashboard")
    today_avg_pair_cost = fields.Float(compute="_compute_dashboard", digits=(10, 4))

    @classmethod
    def ensure_singleton(cls, env):
        config = env["polymarket_bot.config"].search([], limit=1)
        if not config:
            config = env["polymarket_bot.config"].create({"name": "Polymarket Bot Config"})
        return config

    @api.depends()
    def _compute_dashboard(self):
        today = fields.Date.today()
        for rec in self:
            positions = self.env["polymarket_bot.position"].search(
                [("state", "not in", ["closed"])]
            )
            rec.open_positions_count = len(positions)
            rec.one_side_positions_count = len(
                positions.filtered(lambda p: p.state in ("one_side_yes", "one_side_no"))
            )
            summary = self.env["polymarket_bot.daily_summary"].search(
                [("date", "=", today)], limit=1
            )
            if summary:
                rec.today_net_pnl = summary.net_pnl
                rec.today_positions_delta_neutral = summary.positions_delta_neutral
                rec.today_positions_unhedged = summary.positions_unhedged
                rec.today_avg_pair_cost = summary.avg_pair_cost
            else:
                rec.today_net_pnl = 0.0
                rec.today_positions_delta_neutral = 0
                rec.today_positions_unhedged = 0
                rec.today_avg_pair_cost = 0.0

    def get_config_for_bot(self):
        self.ensure_one()
        return {
            "bot_status": self.bot_status,
            "paper_trading": self.paper_trading,
            "entry_threshold": self.entry_threshold,
            "target_pair_cost": self.target_pair_cost,
            "delta_neutral_threshold": self.delta_neutral_threshold,
            "position_size_usd": self.position_size_usd,
            "stop_entry_minutes": self.stop_entry_minutes,
            "stop_hedge_minutes": self.stop_hedge_minutes,
            "max_position_per_market_usd": self.max_position_per_market_usd,
            "max_total_exposure_usd": self.max_total_exposure_usd,
            "daily_loss_limit_usd": self.daily_loss_limit_usd,
            "telegram_bot_token": self.telegram_bot_token or "",
            "telegram_chat_id": self.telegram_chat_id or "",
        }

    def action_start(self):
        self.ensure_one()
        self.sudo().write({"bot_status": "running"})

    def action_stop(self):
        self.ensure_one()
        self.sudo().write({"bot_status": "stopped"})

    def action_pause(self):
        self.ensure_one()
        self.sudo().write({"bot_status": "paused"})

    def action_regenerate_token(self):
        self.ensure_one()
        self.sudo().write({"api_token": str(uuid.uuid4()).replace("-", "")})

    def action_view_positions(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Open Positions",
            "res_model": "polymarket_bot.position",
            "view_mode": "list,form",
            "domain": [("state", "not in", ["closed"])],
        }

    def action_view_signals(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Recent Signals",
            "res_model": "polymarket_bot.arb_signal",
            "view_mode": "list,form",
        }
