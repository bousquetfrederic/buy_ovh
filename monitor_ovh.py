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
import m.print

from m.config import configFile

# ----------------- GLOBAL VARIABLES ----------------------------------------------------------

def loadConfigMain(cf):
    global acceptable_dc, filterName, filterDisk, filterMemory, maxPrice, addVAT, APIEndpoint, ovhSubsidiary, \
           printListWhileLooping, sleepsecs, showCpu, showFqn, \
           showBandwidth, fakeBuy, coupon, months, \
           showPrice, showFee, showTotalPrice
    acceptable_dc = cf['datacenters'] if 'datacenters' in cf else acceptable_dc
    addVAT = cf['addVAT'] if 'addVAT' in cf else addVAT
    APIEndpoint = cf['APIEndpoint'] if 'APIEndpoint' in cf else APIEndpoint
    coupon = cf['coupon'] if 'coupon' in cf else coupon
    fakeBuy = cf['fakeBuy'] if 'fakeBuy' in cf else fakeBuy
    filterDisk = cf['filterDisk'] if 'filterDisk' in cf else filterDisk
    filterMemory = cf['filterMemory'] if 'filterMemory' in cf else filterMemory
    filterName = cf['filterName'] if 'filterName' in cf else filterName
    maxPrice = cf['maxPrice'] if 'maxPrice' in cf else maxPrice
    months = cf['months'] if 'months' in cf else months
    ovhSubsidiary = cf['ovhSubsidiary'] if 'ovhSubsidiary' in cf else ovhSubsidiary
    printListWhileLooping = cf['printListWhileLooping'] if 'printListWhileLooping' in cf else printListWhileLooping
    showBandwidth = cf['showBandwidth'] if 'showBandwidth' in cf else showBandwidth
    showCpu = cf['showCpu'] if 'showCpu' in cf else showCpu
    showFee = cf['showFee'] if 'showFee' in cf else showFee
    showFqn = cf['showFqn'] if 'showFqn' in cf else showFqn
    showPrice = cf['showPrice'] if 'showPrice' in cf else showPrice
    showTotalPrice = cf['showTotalPrice'] if 'showTotalPrice' in cf else showTotalPrice
    sleepsecs = cf['sleepsecs'] if 'sleepsecs' in cf else sleepsecs

def loadConfigEmail(cf):
    global email_on, email_at_startup, email_auto_buy, email_added_removed, \
           email_availability_monitor, email_catalog_monitor, email_exception
    email_on = cf['email_on'] if 'email_on' in cf else email_on
    email_at_startup = cf['email_at_startup'] if 'email_at_startup' in cf and email_on else email_at_startup
    email_auto_buy = cf['email_auto_buy'] if 'email_auto_buy' in cf and email_on else email_auto_buy
    email_added_removed = cf['email_added_removed'] if 'email_added_removed' in cf and email_on else email_added_removed
    email_availability_monitor = cf['email_availability_monitor'] if 'email_availability_monitor' in cf and email_on else email_availability_monitor
    email_catalog_monitor = cf['email_catalog_monitor'] if 'email_catalog_monitor' in cf and email_on else email_catalog_monitor
    email_exception = cf['email_exception'] if 'email_exception' in cf and email_on else email_exception

def loadConfigLogging(cf):
    global logFile, logLevel
    logFile = cf['logFile'] if 'logFile' in cf else logFile
    logLevel = cf['logLevel'] if 'logLevel' in cf else logLevel

def loadConfigAutoBuy(cf):
    global autoBuy
    autoBuy = copy.deepcopy(cf['auto_buy']) if 'auto_buy' in cf else autoBuy

acceptable_dc = []
addVAT = False
APIEndpoint = "ovh-eu"
coupon = ''
fakeBuy = True
filterDisk = ""
filterMemory = ""
filterName = ""
maxPrice = 0
months = 1
ovhSubsidiary = "FR"
printListWhileLooping = True
showBandwidth = True
showCpu = True
showFee = False
showFqn = False
showPrice = True
showTotalPrice = False
sleepsecs = 60
loadConfigMain(configFile)

email_on = False
email_at_startup = False
email_auto_buy = False
email_added_removed = False
email_availability_monitor = ""
email_catalog_monitor = False
email_exception = False
loadConfigEmail(configFile)

# Logging
logFile = ""
logLevel = "WARNING"
loadConfigLogging(configFile)
_log_handlers = [logging.FileHandler(logFile, encoding="utf-8")] if logFile \
                else [logging.StreamHandler(sys.stdout)]
logging.basicConfig(level=logging.getLevelNamesMapping()[logLevel.upper()],
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    handlers=_log_handlers)
if logLevel == "ERROR":
    logging.getLogger("urllib3").setLevel(logging.ERROR)
else:
    logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

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
    print("Let's " + strBuy + "   -Auto Mode-")
    try:
        m.api.checkout_cart(m.api.build_cart(plan, ovhSubsidiary, coupon, fakeBuy, months), buyNow, fakeBuy)
        if email_auto_buy:
            m.email.send_auto_buy_email("SUCCESS: " + strBuy)
    except Exception as e:
        logger.exception("Buying Exception")
        print("Not today.")
        print(e)
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
            if printListWhileLooping:
                m.print.clear_screen()
                m.print.print_prompt(acceptable_dc, filterMemory, filterName, filterDisk, maxPrice, coupon, months,
                                     fakeBuy=fakeBuy, loggedIn=m.api.is_logged_in(), loop=True)
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
            if printListWhileLooping:
                displayedPlans = [x for x in plans
                                  if (m.availability.test_availability(x['availability'], True, True)
                                      or x['autobuy'])]
                m.print.print_plan_list(displayedPlans, showCpu, showFqn, showBandwidth,
                                        showPrice, showFee, showTotalPrice)
            foundAutoBuyServer = False
            if autoBuy:
                logger.debug("Looking for servers to auto buy")
                for plan in plans:
                    if plan['autobuy']:
                        for auto in autoBuy:
                            if (m.autobuy.is_auto_buy(plan, auto)
                                and m.availability.test_availability(plan['availability'], False, auto['unknown'])
                            ):
                                logger.debug("Found one for regex [" + auto['regex'] + "]: " + plan['fqn'])
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
                if printListWhileLooping:
                    m.print.print_and_sleep(True, sleepsecs)
                else:
                    time.sleep(sleepsecs)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.exception("Exception!")
            print("Exception!")
            print(e)
            if email_exception:
                m.email.send_email("BUY_OVH: Exception", str(e))
            print("Wait " + str(sleepsecs) + "s before retry.")
            time.sleep(sleepsecs)
except KeyboardInterrupt:
    logger.info("User pressed CTRL-C.")
    sys.exit("Bye now.")
