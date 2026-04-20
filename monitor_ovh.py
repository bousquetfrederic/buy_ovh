import logging
import sys
import time

# modules
import m.api
import m.autobuy
import m.availability
import m.bootstrap
import m.catalog
import m.email
import m.monitor
import m.vps

from m.conf import MonitorConfig
from m.config import configFile, config_path

CFG = MonitorConfig.from_yaml(configFile)

# Logging — stdout fallback so a long-running monitor is observable without a logFile.
m.bootstrap.setup_logging(configFile, 'monitor_ovh', stream_fallback=True)
logger = logging.getLogger(__name__)
logger.info(f"Loaded config from {config_path}")

# ----------------- LOGIN IF AUTOBUY IS ACTIVE -------------------------------------------------
# The public endpoints (availability + catalog) don't need auth; only autobuy does.
if CFG.autoBuy:
    m.bootstrap.login_required(
        configFile, CFG.APIEndpoint,
        "auto_buy is configured but APIKey / APISecret / APIConsumerKey are missing from the config.",
        "auto_buy is configured but login failed.")

# ----------------- BUY SERVER ----------------------------------------------------------------
def buyServer(plan, buyNow, cfg):
    strBuyNow = "buy now a " if buyNow else "get an invoice for a "
    strBuy = strBuyNow + plan['model'] + " in " + plan['datacenter'] + "."
    logger.info("Buying: " + strBuy + "   -Auto Mode-")
    try:
        m.api.checkout_cart(
            m.api.build_cart(plan, cfg.ovhSubsidiary, cfg.fakeBuy, cfg.months),
            buyNow, cfg.fakeBuy)
        if cfg.email_auto_buy:
            m.email.send_auto_buy_email("SUCCESS: " + strBuy)
    except Exception as e:
        logger.exception("Buying Exception")
        if cfg.email_auto_buy:
            m.email.send_auto_buy_email("FAILED: " + strBuy)
        time.sleep(3)

# ----------------- MAIN PROGRAM --------------------------------------------------------------

logger.info("-----------")
logger.info("Starting up")
logger.info("-----------")
if CFG.email_at_startup:
    m.email.send_startup_email()

availabilities = {}
previousAvailabilities = {}
plans = []
previousPlans = []
vpsAvailabilities = {}
previousVpsAvailabilities = {}

logger.debug("Starting the monitor loop")
try:
    while True:
        try:
            if availabilities:
                previousAvailabilities = availabilities
                previousPlans = plans
            if vpsAvailabilities:
                previousVpsAvailabilities = vpsAvailabilities
            availabilities = m.availability.build_availability_dict(
                m.api.api_url(CFG.APIEndpoint), CFG.acceptable_dc)
            plans = m.catalog.build_list(m.api.api_url(CFG.APIEndpoint),
                                         availabilities,
                                         CFG.ovhSubsidiary,
                                         CFG.filterName, CFG.filterDisk, CFG.filterMemory,
                                         CFG.acceptable_dc, CFG.maxPrice,
                                         CFG.addVAT, CFG.months,
                                         CFG.showBandwidth)
            m.autobuy.add_auto_buy(plans, CFG.autoBuy)
            foundAutoBuyServer = False
            if CFG.autoBuy:
                logger.debug("Looking for servers to auto buy")
                for plan in plans:
                    if plan['autobuy']:
                        for auto in CFG.autoBuy:
                            if (m.autobuy.is_auto_buy(plan, auto)
                                and m.availability.test_availability(plan['availability'], False, auto['unknown'])
                            ):
                                logger.info("Found one for regex [" + auto['regex'] + "]: " + plan['fqn'])
                                foundAutoBuyServer = True
                                buyServer(plan, not auto['invoice'], CFG)
                                auto['num'] -= 1
                if not foundAutoBuyServer:
                    logger.debug("Found none.")
            # availability and catalog monitor if configured
            strAvailMonitor = ""
            if CFG.email_added_removed:
                strAvailMonitor = m.monitor.avail_added_removed_Str(previousAvailabilities, availabilities, "", "<br>")
            if CFG.email_availability_monitor:
                strAvailMonitor = strAvailMonitor + \
                                  m.monitor.avail_changed_Str(previousAvailabilities,
                                                              availabilities,
                                                              CFG.email_availability_monitor,
                                                              "", "<br>")
            if strAvailMonitor:
                m.email.send_email("BUY_OVH: availabilities", strAvailMonitor, False)
            if CFG.email_catalog_monitor:
                strCatalogMonitor = m.monitor.catalog_added_removed_Str(previousPlans, plans, "", "<br>")
                if strCatalogMonitor:
                    m.email.send_email("BUY_OVH: catalog", strCatalogMonitor, False)
            if CFG.email_availability_monitor_vps:
                vpsAvailabilities = m.vps.build_vps_availability_dict(
                    m.api.api_url(CFG.APIEndpoint), CFG.ovhSubsidiary)
                strVpsMonitor = m.monitor.avail_changed_Str(previousVpsAvailabilities,
                                                            vpsAvailabilities,
                                                            CFG.email_availability_monitor_vps,
                                                            "", "<br>")
                if strVpsMonitor:
                    m.email.send_email("BUY_OVH: VPS availabilities", strVpsMonitor, False)
            if not foundAutoBuyServer:
                time.sleep(CFG.sleepsecs)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.exception("Exception!")
            if CFG.email_exception:
                m.email.send_email("BUY_OVH: Exception", str(e))
            logger.info("Wait " + str(CFG.sleepsecs) + "s before retry.")
            time.sleep(CFG.sleepsecs)
except KeyboardInterrupt:
    logger.info("User pressed CTRL-C.")
    sys.exit("Bye now.")
