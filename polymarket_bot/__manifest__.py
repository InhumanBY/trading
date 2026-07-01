{
    "name": "Polymarket Bot",
    "version": "19.0.1.1.0",
    "category": "Finance",
    "summary": "Polymarket BTC 15-min arbitrage bot — admin panel, signals, positions, dashboard",
    "author": "",
    "depends": [
        "base",
        "mail",
        "web",
    ],
    "post_init_hook": "post_init_hook",
    "data": [
        "data/bot_config_data.xml",
        "data/cron.xml",

        "security/ir.model.access.csv",

        "views/polymarket_bot_market_views.xml",
        "views/polymarket_bot_bot_config_views.xml",
        "views/polymarket_bot_position_views.xml",
        "views/polymarket_bot_arb_signal_views.xml",
        "views/polymarket_bot_trade_views.xml",
        "views/polymarket_bot_daily_summary_views.xml",
        "views/polymarket_bot_dashboard_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "polymarket_bot/static/src/widgets/**/*",
        ],
    },
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
