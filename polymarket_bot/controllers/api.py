import json
import logging
from datetime import datetime

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PolymarketApi(http.Controller):

    def _get_config(self):
        token = request.httprequest.headers.get("X-Bot-Token", "")
        config = request.env["polymarket_bot.config"].sudo().search([], limit=1)
        if not config or token != config.api_token:
            return None, None
        return config, token

    def _json_response(self, data, status=200):
        return request.make_response(
            json.dumps(data),
            headers=[
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
            ],
            status=status,
        )

    def _error(self, msg, status=400):
        return self._json_response({"error": msg}, status=status)

    def _get_or_create_market(self, condition_id):
        Market = request.env["polymarket_bot.market"].sudo()
        market = Market.search([("condition_id", "=", condition_id)], limit=1)
        if not market:
            market = Market.create({"condition_id": condition_id})
        return market

    @http.route("/polymarket/api/config", type="http", auth="public", methods=["POST"], csrf=False)
    def get_config(self, **kwargs):
        config, _ = self._get_config()
        if not config:
            return self._error("unauthorized", 401)
        return self._json_response(config.get_config_for_bot())

    @http.route("/polymarket/api/heartbeat", type="http", auth="public", methods=["POST"], csrf=False)
    def heartbeat(self, **kwargs):
        config, _ = self._get_config()
        if not config:
            return self._error("unauthorized", 401)
        body = json.loads(request.httprequest.get_data(as_text=True))
        config.write({
            "last_heartbeat": datetime.utcnow(),
            "bot_pid": body.get("pid", 0),
        })
        return self._json_response({"ok": True})

    @http.route("/polymarket/api/market", type="http", auth="public", methods=["POST"], csrf=False)
    def upsert_market(self, **kwargs):
        config, _ = self._get_config()
        if not config:
            return self._error("unauthorized", 401)
        try:
            body = json.loads(request.httprequest.get_data(as_text=True))
        except Exception:
            return self._error("invalid json")

        condition_id = body.get("condition_id", "").strip()
        if not condition_id:
            return self._error("condition_id required")

        Market = request.env["polymarket_bot.market"].sudo()
        market = Market.search([("condition_id", "=", condition_id)], limit=1)

        vals = {}
        if body.get("question"):
            vals["question"] = body["question"]
        if body.get("market_slug"):
            vals["market_slug"] = body["market_slug"]
        if body.get("end_time"):
            vals["end_time"] = body["end_time"]
        if body.get("state"):
            vals["state"] = body["state"]

        if market:
            if vals:
                market.write(vals)
        else:
            vals["condition_id"] = condition_id
            market = Market.create(vals)

        return self._json_response({"id": market.id})

    @http.route("/polymarket/api/price", type="http", auth="public", methods=["POST"], csrf=False)
    def create_price(self, **kwargs):
        config, _ = self._get_config()
        if not config:
            return self._error("unauthorized", 401)
        try:
            body = json.loads(request.httprequest.get_data(as_text=True))
        except Exception:
            return self._error("invalid json")

        condition_id = body.get("market_id", "").strip()
        if not condition_id:
            return self._error("market_id required")

        market = self._get_or_create_market(condition_id)
        try:
            record = request.env["polymarket_bot.market_price"].sudo().create({
                "market_id": market.id,
                "yes_ask": body.get("yes_ask", 0),
                "no_ask": body.get("no_ask", 0),
            })
        except Exception as e:
            _logger.exception("price create error")
            return self._error(str(e))
        return self._json_response({"id": record.id})

    @http.route("/polymarket/api/signal", type="http", auth="public", methods=["POST"], csrf=False)
    def create_signal(self, **kwargs):
        config, _ = self._get_config()
        if not config:
            return self._error("unauthorized", 401)
        try:
            body = json.loads(request.httprequest.get_data(as_text=True))
        except Exception:
            return self._error("invalid json")

        market = self._get_or_create_market(body.get("market_id", ""))
        try:
            record = request.env["polymarket_bot.arb_signal"].sudo().create({
                "market_id": market.id,
                "signal_type": body.get("signal_type"),
                "yes_ask": body.get("yes_ask", 0),
                "no_ask": body.get("no_ask", 0),
                "avg_yes_position": body.get("avg_yes_position", 0),
                "avg_no_position": body.get("avg_no_position", 0),
                "projected_pair_cost": body.get("projected_pair_cost", 0),
                "position_state_before": body.get("position_state_before", ""),
                "acted_on": body.get("acted_on", False),
                "skip_reason": body.get("skip_reason", ""),
                "signal_time": body.get("signal_time"),
            })
        except Exception as e:
            _logger.exception("signal create error")
            return self._error(str(e))
        return self._json_response({"id": record.id})

    @http.route("/polymarket/api/trade", type="http", auth="public", methods=["POST"], csrf=False)
    def create_trade(self, **kwargs):
        config, _ = self._get_config()
        if not config:
            return self._error("unauthorized", 401)
        try:
            body = json.loads(request.httprequest.get_data(as_text=True))
        except Exception:
            return self._error("invalid json")

        market = self._get_or_create_market(body.get("market_id", ""))
        position = request.env["polymarket_bot.position"].sudo().search(
            [("market_id", "=", market.id), ("state", "!=", "closed")], limit=1
        )
        try:
            record = request.env["polymarket_bot.trade"].sudo().create({
                "market_id": market.id,
                "side": body.get("side"),
                "qty": body.get("qty", 0),
                "price": body.get("price", 0),
                "cost": body.get("cost", 0),
                "order_id": body.get("order_id", ""),
                "trade_type": body.get("trade_type"),
                "status": body.get("status", "filled"),
                "paper": body.get("paper", True),
                "trade_time": body.get("trade_time"),
                "position_id": position.id if position else False,
            })
        except Exception as e:
            _logger.exception("trade create error")
            return self._error(str(e))
        return self._json_response({"id": record.id})

    @http.route("/polymarket/api/position", type="http", auth="public", methods=["POST"], csrf=False)
    def upsert_position(self, **kwargs):
        config, _ = self._get_config()
        if not config:
            return self._error("unauthorized", 401)
        try:
            body = json.loads(request.httprequest.get_data(as_text=True))
        except Exception:
            return self._error("invalid json")

        market = self._get_or_create_market(body.get("market_id", ""))
        state = body.get("state", "empty")

        vals = {
            "market_id": market.id,
            "state": state,
            "qty_yes": body.get("qty_yes", 0),
            "qty_no": body.get("qty_no", 0),
            "cost_yes": body.get("cost_yes", 0),
            "cost_no": body.get("cost_no", 0),
            "paper": body.get("paper", True),
            "state_log": body.get("state_log", ""),
            "final_pnl": body.get("final_pnl", 0),
            "unhedged": body.get("unhedged", False),
        }
        if body.get("market_end_time"):
            vals["market_end_time"] = body["market_end_time"]
        if body.get("hedged_at"):
            vals["hedged_at"] = body["hedged_at"]
        if body.get("delta_neutral_at"):
            vals["delta_neutral_at"] = body["delta_neutral_at"]
        if body.get("closed_at"):
            vals["closed_at"] = body["closed_at"]

        Position = request.env["polymarket_bot.position"].sudo()
        existing = Position.search(
            [("market_id", "=", market.id), ("state", "!=", "closed")], limit=1
        )
        if existing:
            existing.write(vals)
            record = existing
        else:
            record = Position.create(vals)

        return self._json_response({"id": record.id})

    @http.route("/polymarket/api/daily_summary", type="http", auth="public", methods=["POST"], csrf=False)
    def upsert_daily_summary(self, **kwargs):
        config, _ = self._get_config()
        if not config:
            return self._error("unauthorized", 401)
        try:
            body = json.loads(request.httprequest.get_data(as_text=True))
        except Exception:
            return self._error("invalid json")

        date = body.get("date")
        paper = body.get("paper", True)
        vals = {
            "date": date,
            "paper": paper,
            "total_signals": body.get("total_signals", 0),
            "entry_signals": body.get("entry_signals", 0),
            "hedge_signals": body.get("hedge_signals", 0),
            "total_trades": body.get("total_trades", 0),
            "positions_delta_neutral": body.get("positions_delta_neutral", 0),
            "positions_hedged": body.get("positions_hedged", 0),
            "positions_unhedged": body.get("positions_unhedged", 0),
            "gross_pnl": body.get("gross_pnl", 0),
            "net_pnl": body.get("net_pnl", 0),
            "avg_pair_cost": body.get("avg_pair_cost", 0),
        }
        Summary = request.env["polymarket_bot.daily_summary"].sudo()
        existing = Summary.search([("date", "=", date), ("paper", "=", paper)], limit=1)
        if existing:
            existing.write(vals)
            record = existing
        else:
            record = Summary.create(vals)

        return self._json_response({"id": record.id})

    @http.route("/polymarket/api/positions/open", type="http", auth="public", methods=["POST"], csrf=False)
    def get_open_positions(self, **kwargs):
        config, _ = self._get_config()
        if not config:
            return self._error("unauthorized", 401)
        positions = request.env["polymarket_bot.position"].sudo().search([
            ("state", "not in", ["closed", "unhedged_expiry"])
        ])
        return self._json_response([{
            "market_id": p.market_id.condition_id if p.market_id else "",
            "state": p.state,
            "qty_yes": p.qty_yes,
            "qty_no": p.qty_no,
            "cost_yes": p.cost_yes,
            "cost_no": p.cost_no,
        } for p in positions])
