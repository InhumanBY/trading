from . import models
from . import controllers

from . import version


def post_init_hook(env):
    Summary = env["polymarket_bot.daily_summary"].sudo()
    Summary.recompute_all(paper=True)
    Summary.recompute_all(paper=False)
