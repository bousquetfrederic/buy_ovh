import copy
import logging
import sys
import time

# modules
import m.api
import m.autobuy
import m.availability
import m.catalog
import m.email
import m.monitor

from m.config import configFile, config_path

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
    'sleepsecs': 60,
}

EMAIL_DEFAULTS = {
    'email_on': False,
    'email_at_startup': False,
    'email_auto_buy': False,
    'email_added_removed': False,
    'email_availability_monitor': '',
    'email_catalog_monitor': False,
    'email_exception': False,
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

def loadConfigEmail(cf):
    # email_on must be resolved first so the gating below is correct
    email_on_val = cf.get('email_on', globals().get('email_on', EMAIL_DEFAULTS['email_on']))
    globals()['email_on'] = email_on_val
    for name, spec in EMAIL_DEFAULTS.items():
        if name == 'email_on':
            continue  # already handled
        if isinstance(spec, tuple):
            default, yaml_key = spec
        else:
            default, yaml_key = spec, name
        if yaml_key in cf and email_on_val:
            globals()[name] = cf[yaml_key]
        else:
            globals()[name] = globals().get(name, default)

def loadConfigLogging(cf):
    for name, spec in LOGGING_DEFAULTS.items():
        if isinstance(spec, tuple):
            default, yaml_key = spec
        else:
            default, yaml_key = spec, name
        globals()[name] = cf.get(yaml_key, globals().get(name, default))

def loadConfigAutoBuy(cf):
    global autoBuy
    autoBuy = copy.deepcopy(cf['auto_buy']) if 'auto_buy' in cf else autoBuy

loadConfigMain(configFile)

loadConfigEmail(configFile)

# Logging
loadConfigLogging(configFile)
_log_handlers = [logging.FileHandler(logFile, encoding="utf-8")] if logFile \
                else [logging.StreamHandler(sys.stdout)]
logging.basicConfig(level=logging.getLevelNamesMapping()[logLevel.upper()],
                    format="%(asctime)s [monitor_ovh] [%(levelname)s] %(name)s: %(message)s",
                    handlers=_log_handlers)
if logLevel == "ERROR":
    logging.getLogger("urllib3").setLevel(logging.ERROR)
else:
    logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.info(f"Loaded config from {config_path}")

# Auto Buy
autoBuy = []
loadConfigAutoBuy(configFile)

# ----------------- LOGIN IF AUTOBUY IS ACTIVE -------------------------------------------------
# The public endpoints (availability + catalog) don't need auth; only autobuy does.
if autoBuy:
    if not ('APIKey' in configFile
            and 'APISecret' in configFile
            and 'APIConsumerKey' in configFile):
        sys.exit("auto_buy is configured but APIKey / APISecret / APIConsumerKey are missing from the config.")
    if not m.api.login(APIEndpoint,
                       configFile['APIKey'],
                       configFile['APISecret'],
                       configFile['APIConsumerKey']):
        sys.exit("auto_buy is configured but login failed.")

# ----------------- BUY SERVER ----------------------------------------------------------------
def buyServer(plan, buyNow):
    strBuyNow = "buy now a " if buyNow else "get an invoice for a "
    strBuy = strBuyNow + plan['model'] + " in " + plan['datacenter'] + "."
    logger.info("Buying: " + strBuy + "   -Auto Mode-")
    try:
        m.api.checkout_cart(m.api.build_cart(plan, ovhSubsidiary, fakeBuy, months), buyNow, fakeBuy)
        if email_auto_buy:
            m.email.send_auto_buy_email("SUCCESS: " + strBuy)
    except Exception as e:
        logger.exception("Buying Exception")
        if email_auto_buy:
            m.email.send_auto_buy_email("FAILED: " + strBuy)
        time.sleep(3)

# ----------------- MAIN PROGRAM --------------------------------------------------------------

logger.info("-----------")
logger.info("Starting up")
logger.info("-----------")
if email_at_startup:
    m.email.send_startup_email()

availabilities = {}
previousAvailabilities = {}
plans = []
previousPlans = []

logger.debug("Starting the monitor loop")
try:
    while True:
        try:
            if availabilities:
                previousAvailabilities = availabilities
                previousPlans = plans
            availabilities = m.availability.build_availability_dict(m.api.api_url(APIEndpoint), acceptable_dc)
            plans = m.catalog.build_list(m.api.api_url(APIEndpoint),
                                         availabilities,
                                         ovhSubsidiary,
                                         filterName, filterDisk, filterMemory, acceptable_dc, maxPrice,
                                         addVAT, months,
                                         showBandwidth)
            m.autobuy.add_auto_buy(plans, autoBuy)
            foundAutoBuyServer = False
            if autoBuy:
                logger.debug("Looking for servers to auto buy")
                for plan in plans:
                    if plan['autobuy']:
                        for auto in autoBuy:
                            if (m.autobuy.is_auto_buy(plan, auto)
                                and m.availability.test_availability(plan['availability'], False, auto['unknown'])
                            ):
                                logger.info("Found one for regex [" + auto['regex'] + "]: " + plan['fqn'])
                                foundAutoBuyServer = True
                                buyServer(plan, not auto['invoice'])
                                auto['num'] -= 1
                if not foundAutoBuyServer:
                    logger.debug("Found none.")
            # availability and catalog monitor if configured
            strAvailMonitor = ""
            if email_added_removed:
                strAvailMonitor = m.monitor.avail_added_removed_Str(previousAvailabilities, availabilities, "", "<br>")
            if email_availability_monitor:
                strAvailMonitor = strAvailMonitor + \
                                  m.monitor.avail_changed_Str(previousAvailabilities,
                                                              availabilities,
                                                              email_availability_monitor,
                                                              "", "<br>")
            if strAvailMonitor:
                m.email.send_email("BUY_OVH: availabilities", strAvailMonitor, False)
            if email_catalog_monitor:
                strCatalogMonitor = m.monitor.catalog_added_removed_Str(previousPlans, plans, "", "<br>")
                if strCatalogMonitor:
                    m.email.send_email("BUY_OVH: catalog", strCatalogMonitor, False)
            if not foundAutoBuyServer:
                time.sleep(sleepsecs)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.exception("Exception!")
            if email_exception:
                m.email.send_email("BUY_OVH: Exception", str(e))
            logger.info("Wait " + str(sleepsecs) + "s before retry.")
            time.sleep(sleepsecs)
except KeyboardInterrupt:
    logger.info("User pressed CTRL-C.")
    sys.exit("Bye now.")
