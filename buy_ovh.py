import argparse
import dataclasses
import logging
import sys
import time
from datetime import datetime

# modules
import m.api
import m.availability
import m.bootstrap
import m.cache
import m.catalog
import m.interactive
import m.print
import m.state

from m.conf import BuyOvhConfig
from m.config import configFile, config_path


def _parse_args():
    parser = argparse.ArgumentParser(
        prog='buy_ovh',
        description='Browse and order OVH dedicated servers.')
    parser.add_argument('--conf', '-c', default='conf.yaml',
                        help='Path to the YAML config file (default: conf.yaml).')
    sub = parser.add_subparsers(dest='cmd')
    sub.add_parser('list',
                   help='Print the filtered plan list and exit.')
    buy_p = sub.add_parser(
        'buy',
        help='Run a buy-command grammar (e.g. "!3 ?5x2") and exit.')
    buy_p.add_argument('tokens', nargs=argparse.REMAINDER,
                       help='Buy tokens, space-separated: !N, ?N, !NxM, !N*M.')
    return parser.parse_args()


ARGS = _parse_args()

# ----------------- CONFIG ----------------------------------------------------

# Build the typed config once, overlay the persisted UI state from the
# last interactive session, then hand the whole thing around. The `R`
# key in interactive builds a fresh config without re-applying the
# overlay — that's the "reset to conf" escape hatch.
CFG = BuyOvhConfig.from_yaml(configFile)
CFG.apply_state_overlay(m.state.load())

m.bootstrap.setup_logging(configFile, 'buy_ovh')
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.info(f"Loaded config from {config_path}")

m.bootstrap.login_if_credentials(configFile, CFG.APIEndpoint)

# ----------------- BUY SERVER ------------------------------------------------

def buyServer(plan, buyNow, cfg):
    strBuyNow = "buy now a " if buyNow else "get an invoice for a "
    strBuy = strBuyNow + plan['model'] + " in " + plan['datacenter'] + "."
    logger.info("Buying: " + strBuy)
    print("Let's " + strBuy)
    try:
        m.api.checkout_cart(
            m.api.build_cart(plan, cfg.ovhSubsidiary, cfg.fakeBuy, cfg.months),
            buyNow, cfg.fakeBuy)
    except Exception as e:
        logger.exception("Buying Exception")
        print("Not today.")
        print(e)
        time.sleep(3)

# ----------------- MAIN PROGRAM ---------------------------------------------

logger.info("-----------")
logger.info("Starting up")
logger.info("-----------")

availabilities = {}
plans = []
displayedPlans = []
fetched_at = None


def _filter_displayed(all_plans, cfg):
    """Apply availability toggles plus per-column regex filters."""
    avail_filtered = [p for p in all_plans
                      if m.availability.test_availability(p['availability'],
                                                          cfg.showUnavailable,
                                                          cfg.showUnknown)]
    return m.catalog.apply_column_filters(avail_filtered, cfg.columnFilters)


def refetch(cfg):
    """Rebuild availabilities, plans, displayedPlans, and fetched_at."""
    global availabilities, plans, displayedPlans, fetched_at
    fName = '' if cfg.quickLook else cfg.filterName
    fDisk = '' if cfg.quickLook else cfg.filterDisk
    fMem = '' if cfg.quickLook else cfg.filterMemory
    mPrice = 0 if cfg.quickLook else cfg.maxPrice
    availabilities = m.availability.build_availability_dict(
        m.api.api_url(cfg.APIEndpoint), cfg.acceptable_dc)
    plans = m.catalog.build_list(m.api.api_url(cfg.APIEndpoint),
                                 availabilities,
                                 cfg.ovhSubsidiary,
                                 fName, fDisk, fMem, cfg.acceptable_dc, mPrice,
                                 cfg.addVAT, cfg.months,
                                 cfg.showBandwidth)
    for p in plans:
        p['autobuy'] = False
    displayedPlans = _filter_displayed(plans, cfg)
    fetched_at = datetime.now()


def runInteractive():
    """Run the interactive navigator; returns when the user quits."""
    # quickLook is a manual, session-only override — never persisted and
    # never loaded from conf, so it always enters interactive mode off.
    CFG.quickLook = False

    def intRefilter():
        return _filter_displayed(plans, CFG)

    def intBuy(plan, buyNow):
        buyServer(plan, buyNow, CFG)

    def intRefresh():
        refetch(CFG)
        return intRefilter(), fetched_at

    def intReload():
        logger.info('User reloaded the configuration')
        # Rebuild from conf alone — the persisted overlay is intentionally
        # not re-applied here, so R acts as a clean reset to conf baseline.
        # columnFilters survive the reload because the interactive UI owns
        # them in place.
        saved_filters = CFG.columnFilters
        fresh = BuyOvhConfig.from_yaml(configFile)
        for f in dataclasses.fields(CFG):
            if f.name != 'columnFilters':
                setattr(CFG, f.name, getattr(fresh, f.name))
        CFG.columnFilters = saved_filters
        refetch(CFG)
        return intRefilter(), fetched_at

    m.interactive.run(displayedPlans, CFG, intBuy, intRefilter,
                      refresh_fn=intRefresh, reload_fn=intReload,
                      fetched_at=fetched_at)
    m.state.save(CFG.mirrored_state())


def runList():
    """Print the plan list once, cache it, and exit — `buy_ovh.py list`."""
    m.interactive.render_list(displayedPlans, CFG)
    m.cache.save_list(displayedPlans, fetched_at)


def runBuy(tokens):
    """Execute a buy-command grammar and exit — `buy_ovh.py buy ...`.
    Operates against the cached list written by `list`, so indices line up
    with what was last printed."""
    line = ' '.join(tokens)
    ops, errors = m.interactive.parse_command(line)
    for e in errors:
        print(e)
    if not ops:
        if not errors:
            print('No buy tokens. Example: buy_ovh.py buy "!3 ?5x2"')
        return
    print(f'Using cached list from {fetched_at:%Y-%m-%d %H:%M} '
          f'({m.print.format_age(fetched_at)}). '
          f"Run 'buy_ovh.py list' to refresh.")
    for buyNow, n, times in ops:
        if n < 0 or n >= len(displayedPlans):
            print(f'index {n} out of range (0-{len(displayedPlans) - 1})')
            continue
        plan = displayedPlans[n]
        for _ in range(times):
            buyServer(plan, buyNow, CFG)


# initial fetch — `buy` reuses the cache written by `list` so indices stay
# stable between the two invocations; everything else fetches fresh.
if ARGS.cmd == 'buy':
    cached_plans, cached_at = m.cache.load_list()
    if cached_plans is None:
        sys.exit("No cached list found. Run 'buy_ovh.py list' first.")
    for p in cached_plans:
        p.setdefault('autobuy', False)
    displayedPlans = cached_plans
    fetched_at = cached_at
else:
    try:
        refetch(CFG)
    except Exception as e:
        logger.exception("Startup fetch exception")
        print("Startup fetch failed:")
        print(e)

try:
    if ARGS.cmd == 'list':
        runList()
    elif ARGS.cmd == 'buy':
        runBuy(ARGS.tokens)
    else:
        runInteractive()
except KeyboardInterrupt:
    logger.info("User pressed CTRL-C.")
logger.info("Bye.")
if ARGS.cmd is None:
    sys.exit("Bye now.")
