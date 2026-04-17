import logging
import re
import sys
import time
from datetime import datetime

# modules
import m.api
import m.availability
import m.catalog
import m.interactive
import m.print

from m.config import configFile

# ----------------- GLOBAL VARIABLES ----------------------------------------------------------

def loadConfigMain(cf):
    global acceptable_dc, filterName, filterDisk, filterMemory, maxPrice, addVAT, APIEndpoint, ovhSubsidiary, \
           showPrompt, showCpu, showFqn, showUnavailable, showUnknown, \
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
    showBandwidth = cf['showBandwidth'] if 'showBandwidth' in cf else showBandwidth
    showCpu = cf['showCpu'] if 'showCpu' in cf else showCpu
    showFee = cf['showFee'] if 'showFee' in cf else showFee
    showFqn = cf['showFqn'] if 'showFqn' in cf else showFqn
    showPrice = cf['showPrice'] if 'showPrice' in cf else showPrice
    showPrompt = cf['showPrompt'] if 'showPrompt' in cf else showPrompt
    showTotalPrice = cf['showTotalPrice'] if 'showTotalPrice' in cf else showTotalPrice
    showUnavailable = cf['showUnavailable'] if 'showUnavailable' in cf else showUnavailable
    showUnknown = cf['showUnknown'] if 'showUnknown' in cf else showUnknown

def loadConfigLogging(cf):
    global logFile, logLevel
    logFile = cf['logFile'] if 'logFile' in cf else logFile
    logLevel = cf['logLevel'] if 'logLevel' in cf else logLevel

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
showBandwidth = True
showCpu = True
showFee = False
showFqn = False
showPrice = True
showPrompt = True
showTotalPrice = False
showUnavailable = True
showUnknown = True
loadConfigMain(configFile)

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

# ----------------- DISPLAY HELP --------------------------------------------------------------
def showHelp():
    logger.info("Showing Help")
    print("")
    print("Colour coding")
    print("-------------")
    m.print.print_help_legend()
    print("")
    print("Interactive mode")
    print("----------------")
    print("The tool starts in interactive mode. Press ':' to drop to the command prompt,")
    print("'q' or Esc to quit, 'r' to refresh the catalog.")
    print("From the command prompt, 'I' re-enters interactive mode and an empty ENTER")
    print("refetches and re-prints the prompt.")
    print("")
    print("Toggles")
    print("-------")
    print(" B  - show Bandwidth and vRack options ON/OFF")
    print(" C  - show CPU type ON/OFF")
    print(" F  - show FQN instead of server details ON/OFF")
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
    print(" I  - enter interactive mode (navigate the list with arrow keys)")
    print(" K  - enter a coupon (buying will fail if coupon is invalid)")
    print(" R  - reload the configuration file")
    print(" Q  - quit")
    print("")
    print("Orders and servers live in manage_ovh.")
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
    print("For example, to deactivate fake buy, buy 2 servers number 6 and get one invoice, re-activate fake buy:")
    print("  > $ !6*2 ?6 $")
    print("")
    dummy=input("Press ENTER.")

# ----------------- BUY SERVER ----------------------------------------------------------------
def buyServer(plan, buyNow):
    strBuyNow = "buy now a " if buyNow else "get an invoice for a "
    strBuy = strBuyNow + plan['model'] + " in " + plan['datacenter'] + "."
    logger.info("Buying: " + strBuy)
    print("Let's " + strBuy)
    try:
        m.api.checkout_cart(m.api.build_cart(plan, ovhSubsidiary, coupon, fakeBuy, months), buyNow, fakeBuy)
    except Exception as e:
        logger.exception("Buying Exception")
        print("Not today.")
        print(e)
        time.sleep(3)

# ------------------ TOOL ---------------------------------------------------------------------
def expandMulti(line):
    pattern = r'(^|\s)([?!]?\d+)\*(\d+)'

    def replacer(match):
        first, word, count = match.groups()
        return first + ' '.join([word] * int(count))

    return re.sub(pattern, replacer, line)

def getCommandValue(strC, current):
    lstC = strC.split("=")
    if len(lstC) == 2:
        strR = lstC[1]
    else:
        print("Current: " + current)
        strR = input("New: ")
    return strR

def formatAge(ts):
    if ts is None:
        return '—'
    secs = int((datetime.now() - ts).total_seconds())
    if secs < 60:
        return f'{secs}s ago'
    if secs < 3600:
        return f'{secs // 60}m ago'
    if secs < 86400:
        return f'{secs // 3600}h ago'
    return f'{secs // 86400}d ago'

# ----------------- MAIN PROGRAM --------------------------------------------------------------

logger.info("-----------")
logger.info("Starting up")
logger.info("-----------")

availabilities = {}
plans = []
displayedPlans = []
fetched_at = None

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
    displayedPlans = [x for x in plans
                      if m.availability.test_availability(x['availability'], showUnavailable, showUnknown)]
    fetched_at = datetime.now()

def enterInteractive():
    """Spin up the interactive navigator and sync state back on return."""
    global showCpu, showFqn, showBandwidth, showPrice, showFee, showTotalPrice, \
           showUnavailable, showUnknown, fakeBuy, displayedPlans, fetched_at
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
                if m.availability.test_availability(x['availability'],
                                                    intState['showUnavailable'],
                                                    intState['showUnknown'])]

    def intBuy(plan, buyNow):
        # buyServer reads the fakeBuy global, so push the interactive toggle
        # through before each buy
        global fakeBuy
        fakeBuy = intState['fakeBuy']
        buyServer(plan, buyNow)

    def intRefresh():
        refetch()
        return ([x for x in plans
                 if m.availability.test_availability(x['availability'],
                                                     intState['showUnavailable'],
                                                     intState['showUnknown'])],
                fetched_at)

    reason = m.interactive.run(displayedPlans, intState, intBuy, intRefilter,
                               refresh_fn=intRefresh, fetched_at=fetched_at)
    showCpu = intState['showCpu']
    showFqn = intState['showFqn']
    showBandwidth = intState['showBandwidth']
    showPrice = intState['showPrice']
    showFee = intState['showFee']
    showTotalPrice = intState['showTotalPrice']
    showUnavailable = intState['showUnavailable']
    showUnknown = intState['showUnknown']
    fakeBuy = intState['fakeBuy']
    displayedPlans = intRefilter()
    return reason

# initial fetch
try:
    refetch()
except Exception as e:
    logger.exception("Startup fetch exception")
    print("Startup fetch failed:")
    print(e)

# Start in interactive mode; the user toggles between interactive and the
# command prompt. 'quit' ends the program.
mode = 'interactive'
try:
    while True:
        if mode == 'interactive':
            reason = enterInteractive()
            if reason == 'quit':
                logger.info("User quitted from interactive.")
                sys.exit("Bye now.")
            mode = 'prompt'
            continue

        # ---------------- COMMAND PROMPT ----------------
        print("")
        if showPrompt:
            m.print.print_prompt(acceptable_dc, filterMemory, filterName, filterDisk, maxPrice, coupon, months,
                                 fakeBuy=fakeBuy, loggedIn=m.api.is_logged_in(), loop=False)
            m.print.console.print(f'[bright_black]fetched {formatAge(fetched_at)}[/]')
            m.print.print_plan_list(displayedPlans, showCpu, showFqn, showBandwidth,
                                    showPrice, showFee, showTotalPrice)
        if fakeBuy:
            m.print.console.print('[black on yellow] FAKE BUY [/]')
        allChoices = input("(H for Help, I for interactive, empty ENTER to refresh)> ")
        logger.info("User Choice: " + allChoices)

        # empty input: refetch and loop back to interactive? No — the user said
        # pressing Enter on the prompt refreshes and re-displays the prompt.
        if allChoices.strip() == '':
            try:
                refetch()
            except Exception as e:
                logger.exception("Refetch exception")
                print("Refetch failed:")
                print(e)
            continue

        allChoicesExpanded = expandMulti(allChoices)
        logger.debug("User Choice expanded: " + allChoicesExpanded)
        listChoices = allChoicesExpanded.split(' ')
        for sChoice in listChoices:
            logger.debug("Processing Choice: " + sChoice)
            if sChoice.startswith('?'):
                whattodo = 'i'
                sChoice = sChoice[1:]
            elif sChoice.startswith('!'):
                whattodo = 'n'
                sChoice = sChoice[1:]
            else:
                whattodo = 'a'
            if sChoice.isdigit():
                choice = int(sChoice)
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
                buyServer(displayedPlans[choice], mybool)
            elif sChoice.lower().startswith('fd'):
                filterDisk = getCommandValue(sChoice, filterDisk)
                logger.info("New filterDisk=" + filterDisk)
            elif sChoice.lower().startswith('fm'):
                filterMemory = getCommandValue(sChoice, filterMemory)
                logger.info("New filterMemory=" + filterMemory)
            elif sChoice.lower().startswith('fn'):
                filterName = getCommandValue(sChoice, filterName)
                logger.info("New filterName=" + filterName)
            elif sChoice.lower().startswith('fp'):
                tmpMaxPrice = getCommandValue(sChoice, str(maxPrice))
                if tmpMaxPrice == "":
                    maxPrice = 0
                else:
                    maxPrice = float(tmpMaxPrice)
                logger.info("New maxPrice=" + tmpMaxPrice)
            elif sChoice.lower() == 'm1':
                months = 1
                logger.info("New contract duration 1 month")
            elif sChoice.lower() == 'm12':
                months = 12
                logger.info("New contract duration 12 months")
            elif sChoice.lower() == 'm24':
                months = 24
                logger.info("New contract duration 24 months")
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
            elif sChoice == '$':
                fakeBuy = not fakeBuy
                logger.info("Fake Buy=" + str(fakeBuy))
            elif sChoice.lower() == 'i':
                logger.info("User switched to interactive mode")
                mode = 'interactive'
            elif sChoice.lower() == 'r':
                logger.info("User reloaded the configuration")
                loadConfigMain(configFile)
            elif sChoice.lower() == 't':
                addVAT = not addVAT
                logger.info("Apply VAT=" + str(addVAT))
            elif sChoice.lower() == 'h':
                showHelp()
            elif sChoice.lower() == 'q':
                logger.info("User quitted.")
                sys.exit("Bye now.")

        # refetch after each dispatched line so the next view is fresh
        try:
            refetch()
        except Exception as e:
            logger.exception("Refetch exception")
            print("Refetch failed:")
            print(e)
except KeyboardInterrupt:
    logger.info("User pressed CTRL-C at the prompt.")
    sys.exit("Bye now.")
