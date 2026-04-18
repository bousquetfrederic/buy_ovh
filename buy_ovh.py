import argparse
import logging
import sys
import time
from datetime import datetime

# modules
import m.api
import m.availability
import m.cache
import m.catalog
import m.interactive
import m.print
import m.state

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

# ----------------- GLOBAL VARIABLES ----------------------------------------------------------

MAIN_DEFAULTS = {
    'acceptable_dc': ([], 'datacenters'),
    'addVAT': False,
    'APIEndpoint': 'ovh-eu',
    'fakeBuy': True,
    'filterDisk': '',
    'filterMemory': '',
    'filterName': '',
    'maxPrice': 0,
    'months': 1,
    'ovhSubsidiary': 'FR',
    'showBandwidth': True,
    'showCpu': True,
    'showFee': False,
    'showFqn': False,
    'showPrice': True,
    'showTotalPrice': False,
    'showUnavailable': True,
    'showUnknown': True,
}

LOGGING_DEFAULTS = {
    'logFile': '',
    'logLevel': 'WARNING',
}

def loadConfigMain(cf):
    for name, spec in MAIN_DEFAULTS.items():
        if isinstance(spec, tuple):
            default, yaml_key = spec
        else:
            default, yaml_key = spec, name
        globals()[name] = cf.get(yaml_key, globals().get(name, default))

def loadConfigLogging(cf):
    for name, spec in LOGGING_DEFAULTS.items():
        if isinstance(spec, tuple):
            default, yaml_key = spec
        else:
            default, yaml_key = spec, name
        globals()[name] = cf.get(yaml_key, globals().get(name, default))

loadConfigMain(configFile)

# Overlay the last-saved interactive state on top of conf defaults.
# Applied only once at startup; the `R` key re-runs loadConfigMain
# without re-applying state, so R stays a clean "reset to conf".
for _k, _v in m.state.load().items():
    globals()[_k] = _v

# Logging
loadConfigLogging(configFile)
if logFile:
    logging.basicConfig(level=logging.getLevelNamesMapping()[logLevel.upper()],
                        format="%(asctime)s [buy_ovh] [%(levelname)s] %(name)s: %(message)s",
                        handlers=[logging.FileHandler(logFile, encoding="utf-8")]
                       )
if logLevel == "ERROR":
    logging.getLogger("urllib3").setLevel(logging.ERROR)
else:
    logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
# below in case there is no logfile
logger.addHandler(logging.NullHandler())
logger.info(f"Loaded config from {config_path}")

# ----------------- CONNECT IF INFO IN CONF FILE ----------------------------------------------
if ('APIKey' in configFile and 'APISecret' in configFile):
    if 'APIConsumerKey' in configFile:
        m.api.login(APIEndpoint,
                    configFile['APIKey'],
                    configFile['APISecret'],
                    configFile['APIConsumerKey'])
    else:
        ck = m.api.get_consumer_key(APIEndpoint,
                                    configFile['APIKey'],
                                    configFile['APISecret'])
        if ck != "nokey":
            print("To add the generated consumer key to your conf.yaml file:")
            print("APIConsumerKey: " + ck)
        else:
            logger.error("Failed to get a consumer key")
            print("Failed to get a consumer key, did you authenticate?")
        input("Press Enter to continue...")

# ----------------- BUY SERVER ----------------------------------------------------------------
def buyServer(plan, buyNow):
    strBuyNow = "buy now a " if buyNow else "get an invoice for a "
    strBuy = strBuyNow + plan['model'] + " in " + plan['datacenter'] + "."
    logger.info("Buying: " + strBuy)
    print("Let's " + strBuy)
    try:
        m.api.checkout_cart(m.api.build_cart(plan, ovhSubsidiary, fakeBuy, months), buyNow, fakeBuy)
    except Exception as e:
        logger.exception("Buying Exception")
        print("Not today.")
        print(e)
        time.sleep(3)

# ----------------- MAIN PROGRAM --------------------------------------------------------------

logger.info("-----------")
logger.info("Starting up")
logger.info("-----------")

availabilities = {}
plans = []
displayedPlans = []
fetched_at = None
# Per-column regex filters driven by the interactive UI. Empty at startup;
# mutated in place by the interactive run loop. The config-level filters
# (filterName, filterDisk, filterMemory, maxPrice) still narrow the catalog
# at build_list time; column filters narrow the on-screen list on top of that.
columnFilters = {}


def _filter_displayed(all_plans):
    """Apply availability toggles plus per-column regex filters."""
    avail_filtered = [p for p in all_plans
                      if m.availability.test_availability(p['availability'],
                                                          showUnavailable,
                                                          showUnknown)]
    return m.catalog.apply_column_filters(avail_filtered, columnFilters)


def refetch():
    """Rebuild availabilities, plans, displayedPlans, and fetched_at."""
    global availabilities, plans, displayedPlans, fetched_at
    availabilities = m.availability.build_availability_dict(m.api.api_url(APIEndpoint), acceptable_dc)
    plans = m.catalog.build_list(m.api.api_url(APIEndpoint),
                                 availabilities,
                                 ovhSubsidiary,
                                 filterName, filterDisk, filterMemory, acceptable_dc, maxPrice,
                                 addVAT, months,
                                 showBandwidth)
    for p in plans:
        p['autobuy'] = False
    displayedPlans = _filter_displayed(plans)
    fetched_at = datetime.now()

# State keys mirrored between the module globals and the interactive state
# dict. `refresh_fn` / `reload_fn` copy in both directions so whichever side
# mutates (interactive key, or config reload) both agree on what to fetch.
# Sourced from m.state so the persisted-state overlay and the interactive
# mirror stay in lockstep.
_MIRRORED_STATE = m.state.MIRRORED_KEYS


def _stateFromGlobals():
    return {k: globals()[k] for k in _MIRRORED_STATE}


def _applyStateToGlobals(state):
    for k in _MIRRORED_STATE:
        globals()[k] = state[k]


def runInteractive():
    """Run the interactive navigator; returns when the user quits."""
    intState = _stateFromGlobals()
    # Shared mutable dict: interactive mutates column filters in place so
    # they survive across a config reload.
    intState['filters'] = columnFilters

    def intRefilter():
        avail = [x for x in plans
                 if m.availability.test_availability(x['availability'],
                                                     intState['showUnavailable'],
                                                     intState['showUnknown'])]
        return m.catalog.apply_column_filters(avail, columnFilters)

    def intBuy(plan, buyNow):
        # Push the interactive fakeBuy toggle into the global buyServer reads.
        _applyStateToGlobals(intState)
        buyServer(plan, buyNow)

    def intRefresh():
        _applyStateToGlobals(intState)
        refetch()
        return intRefilter(), fetched_at

    def intReload():
        logger.info('User reloaded the configuration')
        loadConfigMain(configFile)
        for k in _MIRRORED_STATE:
            intState[k] = globals()[k]
        refetch()
        return intRefilter(), fetched_at

    m.interactive.run(displayedPlans, intState, intBuy, intRefilter,
                      refresh_fn=intRefresh, reload_fn=intReload,
                      fetched_at=fetched_at)
    _applyStateToGlobals(intState)
    m.state.save(intState)


def runList():
    """Print the plan list once, cache it, and exit — `buy_ovh.py list`."""
    m.interactive.render_list(displayedPlans, _stateFromGlobals())
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
            buyServer(plan, buyNow)


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
        refetch()
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
