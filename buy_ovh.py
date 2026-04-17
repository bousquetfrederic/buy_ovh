import copy
import logging
import re
import sys
import time

# modules
import m.api
import m.availability
import m.catalog
import m.email
import m.interactive
import m.monitor
import m.orders
import m.print
import m.servers

from m.config import configFile

# ----------------- GLOBAL VARIABLES ----------------------------------------------------------

def loadConfigMain(cf):
    global acceptable_dc, filterName, filterDisk, filterMemory, maxPrice, addVAT, APIEndpoint, ovhSubsidiary, \
           loop, printListWhileLooping, sleepsecs, showPrompt, showCpu, showFqn, showUnavailable, showUnknown, \
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
    loop = cf['loop'] if 'loop' in cf else loop
    maxPrice = cf['maxPrice'] if 'maxPrice' in cf else maxPrice
    months = cf['months'] if 'months' in cf else months
    ovhSubsidiary = cf['ovhSubsidiary'] if 'ovhSubsidiary' in cf else ovhSubsidiary
    printListWhileLooping = cf['printListWhileLooping'] if 'printListWhileLooping' in cf else printListWhileLooping
    showBandwidth = cf['showBandwidth'] if 'showBandwidth' in cf else showBandwidth
    showCpu = cf['showCpu'] if 'showCpu' in cf else showCpu
    showFee = cf['showFee'] if 'showFee' in cf else showFee
    showFqn = cf['showFqn'] if 'showFqn' in cf else showFqn
    showPrice = cf['showPrice'] if 'showPrice' in cf else showPrice
    showPrompt = cf['showPrompt'] if 'showPrompt' in cf else showPrompt
    showTotalPrice = cf['showTotalPrice'] if 'showTotalPrice' in cf else showTotalPrice
    showUnavailable = cf['showUnavailable'] if 'showUnavailable' in cf else showUnavailable
    showUnknown = cf['showUnknown'] if 'showUnknown' in cf else showUnknown
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
loop = False
maxPrice = 0
months = 1
ovhSubsidiary = "FR"
printListWhileLooping = True
showBandwidth = True
showCpu = True
showFee = False
showFqn = False
showPrice = True
showPrompt = True
showTotalPrice = False
showUnavailable = True
showUnknown = True
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
if logFile:
    logging.basicConfig(level=logging.getLevelNamesMapping()[logLevel.upper()],
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                        handlers=[logging.FileHandler(logFile, encoding="utf-8")]
                       )
if logLevel == "ERROR":
    logging.getLogger("urllib3").setLevel(logging.ERROR)
else:
    logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
# below in case there is no logfile
logger.addHandler(logging.NullHandler())

# Auto Buy
autoBuy = []
loadConfigAutoBuy(configFile)

# ----------------- CONNECT IF INFO IN CONF FILE ----------------------------------------------
if ('APIKey' in m.config.configFile and
    'APISecret' in m.config.configFile):
    # if the customer key is there too, we can connect
    if 'APIConsumerKey' in m.config.configFile:
        m.api.login(APIEndpoint,
                    m.config.configFile['APIKey'],
                    m.config.configFile['APISecret'],
                    m.config.configFile['APIConsumerKey'])
    else:
        ck = m.api.get_consumer_key(APIEndpoint,
                                    m.config.configFile['APIKey'],
                                    m.config.configFile['APISecret'])
        if ck != "nokey":
            print("To add the generated consumer key to your conf.yaml file:")
            print("APIConsumerKey: " + ck)
        else:
            logger.error("Failed to get a consumer key")
            print("Failed to get a consumer key, did you authenticate?")
        input("Press Enter to continue...")

# ----------------- DISPLAY HELP --------------------------------------------------------------
def showHelp():
    logger.info("Showing Help")
    print("")
    print("Colour coding")
    print("-------------")
    m.print.print_help_legend()
    print("")
    print("Infinite Loop")
    print("-------------")
    print("When the loop is ON, the script updates the catalog and availabilities every " + str(sleepsecs) + "s.")
    print("You need to press CTRL-C to stop the loop and interact with the script.")
    print("")
    print("Toggles")
    print("-------")
    print(" B  - show Bandwidth and vRack options ON/OFF")
    print(" C  - show CPU type ON/OFF")
    print(" F  - show FQN instead of server details ON/OFF")
    print(" LP - show the server list while looping ON/OFF")
    print(" P  - show helpful prompt ON/OFF")
    print(" PP - show the monthly price ON/OFF")
    print(" PF - show the installation fee ON/OFF")
    print(" PT - show the total price ON/OFF")
    print(" U  - show Unavailable servers ON/OFF")
    print(" UK - show servers with Unknown availability ON/OFF")
    print(" T  - add Tax (VAT) to the price ON/OFF")
    print(" $  - fake buy ON/OFF")
    print("")
    print("Filters")
    print("-------")
    print(" FD - re-enter the Disk filter (sa, nvme, ssd)")
    print(" FM - re-enter the Memory filter (ex: 32g)")
    print(" FN - re-enter the Name filter (invoice name or plan code)")
    print(" FP - set maximum price")
    print("")
    print(" [filtername]=[value] is also supported, for example:")
    print(" fp=20 fm=32g")
    print("")
    print("Months upfront")
    print("--------------")
    print(" M1  - show prices and buy with 1 month commitment")
    print(" M12 - show prices and buy with 12 months commitment paid upfront")
    print(" M24 - show prices and buy with 24 months commitment paid upfront")
    print("")
    print("Commands")
    print("--------")
    print(" D  - show your undelivered orders and a link to see your bill for one")
    print(" I  - enter interactive mode (navigate the list with arrow keys)")
    print(" K  - enter a coupon (buying will fail if coupon is invalid)")
    print(" L  - (re)start the infinite loop, activating monitoring if configured")
    print(" O  - show your unpaid orders and a link to pay for one")
    print(" R  - reload the configuration file")
    print(" S  - print a list of your servers with some specs")
    print(" V  - look up availabilities for a specific FQN")
    print("")
    print("Buying")
    print("------")
    print("Enter the server number in the list to either get an invoice or buy it straight away.")
    print("  Example :> 0")
    print("Start with ! to buy it now, ? for invoice.")
    print("  Example :> ?1")
    print("Add * followed by a number to buy multiple time")
    print("(this creates as many orders, each of them for one server)")
    print("  Example :> !3*4")
    print("")
    print("It is possible to enter more than one command at a time.")
    print("For example, to deactivate fake buy, buy 2 servers number 6 and get one invoice, re-activate fake buy and then restart the loop:")
    print("  > $ !6*2 ?6 $ l")
    print("")
    dummy=input("Press ENTER.") 

# ----------------- BUY SERVER ----------------------------------------------------------------
def buyServer(plan, buyNow, autoMode):
    if autoMode:
        strAuto = "   -Auto Mode-"
    else:
        strAuto = ""
    if buyNow:
        strBuyNow = "buy now a "
    else:
        strBuyNow = "get an invoice for a "
    strBuy = strBuyNow + plan['model'] + " in " + plan['datacenter'] + "."
    logger.info("Buying: " + strBuy + strAuto)
    print("Let's " + strBuy + strAuto)
    try:
        m.api.checkout_cart(m.api.build_cart(plan, ovhSubsidiary, coupon, fakeBuy, months), buyNow, fakeBuy)
        if autoMode and email_auto_buy and loop:
            m.email.send_auto_buy_email("SUCCESS: " + strBuy)
    except Exception as e:
        logger.exception("Buying Exception")
        print("Not today.")
        print(e)
        if autoMode and email_auto_buy and loop:
            m.email.send_auto_buy_email("FAILED: " + strBuy)
        time.sleep(3)

# -------------- AUTO BUY TOOLS ----------------------------------------------------------------
def is_auto_buy(plan, auto):
    return (auto['num'] > 0
            and (bool(re.search(auto['regex'], plan['fqn'])) or bool(re.search(auto['regex'], plan['model'])))
            and (auto['max_price'] == 0 or plan['price'] <= auto['max_price']))

def add_auto_buy(plans):
    logger.debug("Adding Auto Buy info")
    for plan in plans:
        plan['autobuy'] = False
        for auto in autoBuy:
            if is_auto_buy(plan, auto):
                plan['autobuy'] = True
                break

# ------------------ TOOL ---------------------------------------------------------------------
# when ordering servers, the user can type something like "!0*3"
# "*3" means repeat 3 times
# this function expand these, so "!2*3" becomes "!2 !2 !2"
# if no multiplier is specified, it means 1
def expandMulti(line):
    pattern = r'(^|\s)([?!]?\d+)\*(\d+)'

    def replacer(match):
        first, word, count = match.groups()
        return first + ' '.join([word] * int(count))

    return re.sub(pattern, replacer, line)

# Some input can take the form command=value
# extract the value
def getCommandValue(strC, current):
    lstC = strC.split("=")
    if len(lstC) == 2:
        strR = lstC[1]
    else:
        print("Current: " + current)
        strR = input("New: ")
    return strR

# ----------------- MAIN PROGRAM --------------------------------------------------------------

logger.info("-----------")
logger.info("Starting up")
logger.info("-----------")
# send email at startup
if email_at_startup:
    m.email.send_startup_email()

availabilities = {}
# previous list of availabilities so we can send email if something pops up
previousAvailabilities = {}

# Plans which pass the filters (name + disk)
plans = []
# previous plans
previousPlans = []
# Unavailable servers can be hidden (see conf file),
# so we need a list of non hidden plans for display and order
displayedPlans = []

# do the catalog monitoring only if filters have not changed
filtersChanged = False

# loop until the user wants out
logger.debug("Starting the main loop")
while True:

    try:
        logger.debug("Starting a new update cycle")
        while True:
            try:
                m.print.clear_screen()
                # Render the header panel first so toggles (fake buy, filters,
                # etc.) show up immediately, before the slow catalog fetch.
                if showPrompt:
                    m.print.print_prompt(acceptable_dc, filterMemory, filterName, filterDisk, maxPrice, coupon, months,
                                         fakeBuy=fakeBuy, loggedIn=m.api.is_logged_in(), loop=loop)
                if availabilities:
                    previousAvailabilities = availabilities
                    previousPlans = plans
                availabilities = m.availability.build_availability_dict(m.api.api_url(APIEndpoint),acceptable_dc)
                plans = m.catalog.build_list(m.api.api_url(APIEndpoint),
                                             availabilities,
                                             ovhSubsidiary,
                                             filterName, filterDisk, filterMemory, acceptable_dc, maxPrice,
                                             addVAT, months,
                                             showBandwidth)
                add_auto_buy(plans)
                if printListWhileLooping or not loop:
                    displayedPlans = [ x for x in plans \
                                    if (m.availability.test_availability(x['availability'], showUnavailable, showUnknown)
                                        or x['autobuy'])]
                    m.print.print_plan_list(displayedPlans, showCpu, showFqn, showBandwidth,
                                            showPrice, showFee, showTotalPrice)
                foundAutoBuyServer = False
                if autoBuy:
                    logger.debug("Looking for servers to auto buy")
                    for plan in plans:
                        if plan['autobuy']:
                            for auto in autoBuy:
                                if (is_auto_buy(plan, auto)
                                    and m.availability.test_availability(plan['availability'], False, auto['unknown'])
                                ):
                                    # auto buy
                                    logger.debug("Found one for regex [" + auto['regex'] + "]: " + plan['fqn'])
                                    foundAutoBuyServer = True
                                    buyServer(plan, not auto['invoice'], True)
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
                    m.email.send_email("BUY_OVH: availabilities", strAvailMonitor, not loop)
                # Don't do the catalog monitoring if the user has just changed the filters
                if not filtersChanged:
                    strCatalogMonitor = m.monitor.catalog_added_removed_Str(previousPlans, plans, "", "<br>")
                    if strCatalogMonitor:
                        m.email.send_email("BUY_OVH: catalog", strCatalogMonitor, not loop)
                else:
                    filtersChanged = False
                # if the conf says no loop, jump to the menu
                if not loop:
                    break
                if not foundAutoBuyServer:
                    m.print.print_and_sleep(showPrompt, sleepsecs)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.exception("Exception!")
                print("Exception!")
                print(e)
                if loop and email_exception:
                    m.email.send_email("BUY_OVH: Exception",str(e))
                print("Wait " + str(sleepsecs) + "s before retry.")
                time.sleep(sleepsecs)
    except KeyboardInterrupt:
        logger.info("User pressed CTRL-C.")
        pass

    print("")
    # stop the infinite loop, the user must press L to restart it
    loop = False
    # surface FAKE BUY right above the prompt regardless of showPrompt;
    # absence of the badge is sufficient signal that buys would be real
    if fakeBuy:
        m.print.console.print('[black on yellow] FAKE BUY [/]')
    allChoices = input("(H for Help)> ")
    logger.info("User Choice: " + allChoices)
    # The user can specify to buy a server multiple times
    # "2*5" means buy server 2, 5 times
    # "2" and "2*1" mean the same thing
    # "!2*3 ?2*10" works too (see below for ! and ?)
    allChoicesExpanded = expandMulti(allChoices)
    logger.debug("User Choice expanded: " + allChoicesExpanded)
    listChoices = allChoicesExpanded.split(' ')
    for sChoice in listChoices:
        logger.debug("Processing Choice: " + sChoice)
        # when buying, the user can specify if they want an invoice or buy now, by starting with ? or !
        # example: ?2 means an invoice for server two
        #          !4 means buy server 4 now
        #          3  means I want server 3 but ask me if I want an invoice or to buy now
        if sChoice.startswith('?'):
            # invoice, no need to ask
            whattodo = 'i'
            sChoice = sChoice[1:]
        elif sChoice.startswith('!'):
            # buy now, no need to ask
            whattodo = 'n'
            sChoice = sChoice[1:]
        else:
            # if it's a server number, we'll ask if use wants an invoice or buy now
            whattodo = 'a'
        # if the user entered a number, it's a server number so let's buy it or get an invoice
        if sChoice.isdigit():
            choice = int (sChoice)
            if choice >= len(displayedPlans):
                logger.error("User had one job.")
                sys.exit("You had one job.")
            if whattodo == 'a':
                logger.debug("Model selected: " + displayedPlans[choice]['model'])
                print(displayedPlans[choice]['model'])
                whattodo = input("Last chance : Make an invoice = I , Buy now = N , other = out : ").lower()
                logger.debug("User chose to: " + whattodo)
            if whattodo == 'i':
                mybool = False
            elif whattodo == 'n':
                mybool = True
            else:
                continue
            buyServer(displayedPlans[choice], mybool, False)
        # not a number means command
        # the '?', '!', and '*' have no effect here
        # Filters can either be changed via [filtername]=[value]
        # or buy just [filtername] then inputing the value when asked
        elif sChoice.lower().startswith('fd'):
            filterDisk = getCommandValue(sChoice, filterDisk)
            logger.info("New filterDisk=" + filterDisk)
            filtersChanged = True
        elif sChoice.lower().startswith('fm'):
            filterMemory = getCommandValue(sChoice, filterMemory)
            logger.info("New filterMemory=" + filterMemory)
            filtersChanged = True
        elif sChoice.lower().startswith('fn'):
            filterName = getCommandValue(sChoice, filterName)
            logger.info("New filterName=" + filterName)
            filtersChanged = True
        elif sChoice.lower().startswith('fp'):
            tmpMaxPrice=getCommandValue(sChoice, str(maxPrice))
            if tmpMaxPrice == "":
                maxPrice = 0
            else:
                maxPrice = float(tmpMaxPrice)
            logger.info("New maxPrice=" + tmpMaxPrice)
            filtersChanged = True
        elif sChoice.lower() == 'm1':
            months = 1
            logger.info("New contract duration 1 month")
            filtersChanged = True
        elif sChoice.lower() == 'm12':
            months = 12
            logger.info("New contract duration 12 months")
            filtersChanged = True
        elif sChoice.lower() == 'm24':
            months = 24
            logger.info("New contract duration 24 months")
            filtersChanged = True
        elif sChoice.lower() == 'k':
            print("Current: " + coupon)
            coupon = input("Enter Coupon: ")
            logger.info("New coupon=" + coupon)
        elif sChoice.lower() == 'uk':
            showUnknown = not showUnknown
            logger.debug("Show unknown=" + str(showUnknown))
        elif sChoice.lower() == 'u':
            showUnavailable = not showUnavailable
            logger.debug("Show unavailable=" + str(showUnavailable))
        elif sChoice.lower() == 'p':
            showPrompt = not showPrompt
            logger.debug("Show prompt=" + str(showPrompt))
        elif sChoice.lower() == 'pp':
            showPrice = not showPrice
            logger.debug("Show price=" + str(showPrice))
        elif sChoice.lower() == 'pf':
            showFee = not showFee
            logger.debug("Show fee=" + str(showFee))
        elif sChoice.lower() == 'pt':
            showTotalPrice = not showTotalPrice
            logger.debug("Show total price=" + str(showTotalPrice))
        elif sChoice.lower() == 'c':
            showCpu = not showCpu
            logger.debug("Show CPU=" + str(showCpu))
        elif sChoice.lower() == 'f':
            showFqn = not showFqn
            logger.debug("Show FQN=" + str(showFqn))
        elif sChoice.lower() == 'b':
            showBandwidth = not showBandwidth
            logger.debug("Show bandwidth=" + str(showBandwidth))
            filtersChanged = True
        elif sChoice == '$':
            fakeBuy = not fakeBuy
            logger.info("Fake Buy=" + str(fakeBuy))
        elif sChoice.lower() == 'i':
            logger.info("User entered interactive mode")
            intState = {
                'showCpu': showCpu, 'showFqn': showFqn,
                'showBandwidth': showBandwidth,
                'showPrice': showPrice, 'showFee': showFee,
                'showTotalPrice': showTotalPrice,
                'showUnavailable': showUnavailable,
                'showUnknown': showUnknown,
                'fakeBuy': fakeBuy,
            }
            def intRefilter():
                return [x for x in plans
                        if (m.availability.test_availability(x['availability'],
                                                             intState['showUnavailable'],
                                                             intState['showUnknown'])
                            or x['autobuy'])]
            def intBuy(plan, buyNow):
                # buyServer reads the fakeBuy global, so push the interactive
                # toggle through before each buy
                global fakeBuy
                fakeBuy = intState['fakeBuy']
                buyServer(plan, buyNow, False)
            displayedPlans = intRefilter()
            m.interactive.run(displayedPlans, intState, intBuy, intRefilter)
            showCpu = intState['showCpu']
            showFqn = intState['showFqn']
            showBandwidth = intState['showBandwidth']
            showPrice = intState['showPrice']
            showFee = intState['showFee']
            showTotalPrice = intState['showTotalPrice']
            showUnavailable = intState['showUnavailable']
            showUnknown = intState['showUnknown']
            fakeBuy = intState['fakeBuy']
        elif sChoice.lower() == 'l':
            logger.info("User started the infinite loop")
            loop = True
        elif sChoice.lower() == 'lp':
            printListWhileLooping = not printListWhileLooping
            logger.debug("Print List while looping=" + str(printListWhileLooping))
        elif sChoice.lower() == 'o':
            m.orders.unpaid_orders(True)
        elif sChoice.lower() == 'd':
            m.orders.undelivered_orders(True)
        elif sChoice.lower() == 'r':
            # reload conf
            logger.info("User reloaded the configuration")
            loadConfigMain(configFile)
            filtersChanged = True
        elif sChoice.lower() == 'rr':
            logger.info("User reloaded the configuration")
            # reload conf including autobuy
            loadConfigMain(configFile)
            loadConfigAutoBuy(configFile)
            filtersChanged = True
        elif sChoice.lower() == 's':
            m.servers.servers_specs(True)
        elif sChoice.lower() == 't':
            addVAT = not addVAT
            logger.info("Apply VAT=" + str(addVAT))
            # VAT increases the price which could no longer pass the max price filter
            # so a server could "disappear" or "appear" in the catalog
            # triggering the catalog monitor
            filtersChanged = True
        elif sChoice.lower() == 'v':
            m.availability.look_up_avail(availabilities)
        elif sChoice.lower() == 'h':
            showHelp()
        elif sChoice.lower() == 'q':
            logger.info("User quitted.")
            sys.exit("Bye now.")
