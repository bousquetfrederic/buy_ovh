import logging
import re

__all__ = ['is_auto_buy', 'add_auto_buy']

logger = logging.getLogger(__name__)


def is_auto_buy(plan, auto):
    return (auto['num'] > 0
            and (bool(re.search(auto['regex'], plan['fqn'])) or bool(re.search(auto['regex'], plan['model'])))
            and (auto['max_price'] == 0 or plan['price'] <= auto['max_price']))


def add_auto_buy(plans, autoBuy):
    logger.debug("Adding Auto Buy info")
    for plan in plans:
        plan['autobuy'] = False
        for auto in autoBuy:
            if is_auto_buy(plan, auto):
                plan['autobuy'] = True
                break
