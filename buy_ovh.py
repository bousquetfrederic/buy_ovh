import os
import re
import sys
import time

# modules
import m.api
import m.availability
import m.catalog
import m.email
import m.monitor
import m.orders
import m.print
import m.servers

from m.config import configFile

# ----------------- GLOBAL VARIABLES ----------------------------------------------------------

def loadConfigMain(cf):
    global acceptable_dc, filterName, filterDisk, filterMemory, maxPrice, addVAT, APIEndpoint, ovhSubsidiary, \
           loop, sleepsecs, showPrompt, showCpu, showFqn, showUnavailable, showUnknown, \
           showBandwidth, fakeBuy, coupon
    acceptable_dc = cf['datacenters'] if 'datacenters' in cf else acceptable_dc
    filterName = cf['filterName'] if 'filterName' in cf else filterName
    filterDisk = cf['filterDisk'] if 'filterDisk' in cf else filterDisk
    filterMemory = cf['filterMemory'] if 'filterMemory' in cf else filterMemory
    maxPrice = cf['maxPrice'] if 'maxPrice' in cf else maxPrice
    addVAT = cf['addVAT'] if 'addVAT' in cf else addVAT
    ovhSubsidiary = cf['ovhSubsidiary'] if 'ovhSubsidiary' in cf else ovhSubsidiary
    APIEndpoint = cf['APIEndpoint'] if 'APIEndpoint' in cf else APIEndpoint
    loop = cf['loop'] if 'loop' in cf else loop
    sleepsecs = cf['sleepsecs'] if 'sleepsecs' in cf else sleepsecs    
    showPrompt = cf['showPrompt'] if 'showPrompt' in cf else showPrompt
    showCpu = cf['showCpu'] if 'showCpu' in cf else showCpu
    showFqn = cf['showFqn'] if 'showFqn' in cf else showFqn
    showUnavailable = cf['showUnavailable'] if 'showUnavailable' in cf else showUnavailable
    showUnknown = cf['showUnknown'] if 'showUnknown' in cf else showUnknown
    showBandwidth = cf['showBandwidth'] if 'showBandwidth' in cf else showBandwidth
    fakeBuy = cf['fakeBuy'] if 'fakeBuy' in cf else fakeBuy
    coupon = cf['coupon'] if 'coupon' in cf else coupon

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

def loadConfigAutoBuy(cf):
    global autoBuyRE, autoBuyNum, autoBuyMaxPrice, autoBuyInvoicesNum, autoBuyUnknown, \
           autoBuyNumInit, autoOK, autoKO, autoFake
    autoBuyRE = cf['auto_buy'] if 'auto_buy' in cf else autoBuyRE
    autoBuyNum = cf['auto_buy_num'] if 'auto_buy_num' in cf else autoBuyNum
    autoBuyMaxPrice = cf['auto_buy_max_price'] if 'auto_buy_max_price' in cf else autoBuyMaxPrice
    autoBuyInvoicesNum = cf['auto_buy_num_invoices'] if 'auto_buy_num_invoices' in cf else autoBuyInvoicesNum
    autoBuyUnknown = cf['auto_buy_unknown'] if 'auto_buy_unknown' in cf else autoBuyUnknown
    if autoBuyNum == 0:
        autoBuyRE = ""
    autoBuyNumInit = autoBuyNum
    autoOK = 0
    autoKO = 0
    autoFake = 0

acceptable_dc = []
filterName = ""
filterDisk = ""
filterMemory = ""
maxPrice = 0
addVAT = False
ovhSubsidiary = "FR"
APIEndpoint = "ovh-eu"
loop = False
sleepsecs = 60    
showPrompt = True
showCpu = True
showFqn = False
showUnavailable = True
showUnknown = True
showBandwidth = True
fakeBuy = True
coupon = ''

loadConfigMain(configFile)

email_on = False
email_at_startup = False
email_auto_buy = False
email_added_removed = False
email_availability_monitor = ""
email_catalog_monitor = False
email_exception = False
loadConfigEmail(configFile)

# Auto Buy
autoBuyRE = ""
autoBuyNum = 1
autoBuyMaxPrice = 0
autoBuyInvoicesNum = 0
autoBuyNumInit = 0
autoBuyUnknown = False
# counters to display how auto buy are doing
autoOK = 0
autoKO = 0
autoFake = 0
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
            print("Failed to get a consumer key, did you authenticate?")
        input("Press Enter to continue...")

# ----------------- DISPLAY HELP --------------------------------------------------------------
def showHelp():
    print("")
    print("Colour coding")
    print("-------------")
    print(m.print.whichColor['high'] + "Available HIGH")
    print(m.print.whichColor['low'] + "Available LOW")
    print(m.print.whichColor['unavailable'] + "Unavailable")
    print(m.print.whichColor['comingSoon'] + "Coming Soon")
    print(m.print.whichColor['unknown'] + "Availability unknown" + m.print.color.END)
    print("")
    print("Infinite Loop")
    print("-------------")
    print("When the loop is ON, the script updates the catalog and availabilities every " + str(sleepsecs) + "s.")
    print("You need to press CTRL-C to stop the loop and interact with the script.")
    print("")
    print("Toggles")
    print("-------")
    print(" B - show Bandwidth and vRack options ON/OFF")
    print(" C - show CPU type ON/OFF")
    print(" F - show FQN instead of server details ON/OFF")
    print(" P - show helpful prompt ON/OFF")
    print(" U - show Unavailable servers ON/OFF")
    print(" UK - show servers with Unknown availability ON/OFF")
    print(" T - add Tax (VAT) to the price ON/OFF")
    print(" $ - fake buy ON/OFF")
    print("")
    print("Filters")
    print("-------")
    print(" FD - re-enter the Disk filter (sa, nvme, ssd)")
    print(" FM - re-enter the Memory filter (ex: 32g)")
    print(" FN - re-enter the Name filter (invoice name or plan code)")
    print(" FP - set maximum price")
    print("")
    print("Commands")
    print("--------")
    print(" D - show your undelivered orders and a link to see your bill for one")
    print(" K - enter a coupon (buying will fail if coupon is invalid)")
    print(" L - (re)start the infinite loop, activating monitoring if configured")
    print(" O - show your unpaid orders and a link to pay for one")
    print(" R - reload the configuration file")
    print(" S - print a list of your servers with some specs")
    print(" V - look up availabilities for a specific FQN")
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
    global autoFake, autoOK, autoKO
    if autoMode:
        strAuto = "   -Auto Mode-"
    else:
        strAuto = ""
    if buyNow:
        strBuyNow = "buy now a "
    else:
        strBuyNow = "get an invoice for a "
    strBuy = strBuyNow + plan['model'] + " in " + plan['datacenter'] + "."
    print("Let's " + strBuy + strAuto)
    try:
        m.api.checkout_cart(m.api.build_cart(plan, ovhSubsidiary, coupon, fakeBuy), buyNow, fakeBuy)
        if autoMode:
            if fakeBuy:
                autoFake += 1
            else:
                autoOK += 1
            if email_auto_buy and loop:
                m.email.send_auto_buy_email("SUCCESS: " + strBuy)
    except Exception as e:
        print("Not today.")
        print(e)
        if autoMode:
            autoKO += 1
            if email_auto_buy  and loop:
                m.email.send_auto_buy_email("FAILED: " + strBuy)
        time.sleep(3)

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
# ----------------- MAIN PROGRAM --------------------------------------------------------------

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
while True:

    try:
        while True:
            try:
                os.system('cls' if os.name == 'nt' else 'clear')
                if availabilities:
                    previousAvailabilities = availabilities
                    previousPlans = plans
                availabilities = m.availability.build_availability_dict(m.api.api_url(APIEndpoint),acceptable_dc)
                plans = m.catalog.build_list(m.api.api_url(APIEndpoint),
                                             availabilities,
                                             ovhSubsidiary,
                                             filterName, filterDisk, filterMemory, acceptable_dc, maxPrice,
                                             addVAT,
                                             showBandwidth)
                m.catalog.add_auto_buy(plans, autoBuyRE, autoBuyMaxPrice)
                displayedPlans = [ x for x in plans \
                                   if (x['availability'] not in m.availability.unavailableAndUnknownList or
                                       (x['availability'] in m.availability.unavailableList and showUnavailable) or
                                       (x['availability'] == 'unknown' and showUnknown) or
                                       x['autobuy'])]
                m.print.print_plan_list(displayedPlans, showCpu, showFqn, showBandwidth)
                if fakeBuy:
                    print("- Fake Buy ON")
                if not m.api.is_logged_in():
                    print("- Not logged in")
                foundAutoBuyServer = False
                if autoBuyRE:
                    for plan in plans:
                        if (plan['autobuy'] and
                            autoBuyNum > 0 and
                            (plan['availability'] not in m.availability.unavailableAndUnknownList or
                             (plan['availability'] == 'unknown' and autoBuyUnknown))
                        ):
                            # auto buy
                            foundAutoBuyServer = True
                            # The last x are invoices (rather than direct buy) if a number
                            # of invoices is defined in the config file
                            autoBuyInvoice = autoBuyNum <= autoBuyInvoicesNum
                            buyServer(plan, not autoBuyInvoice, True)
                            autoBuyNum -= 1
                            if autoBuyNum < 1:
                                autoBuyRE = ""
                                break
                # availability and catalog monitor if configured
                strAvailMonitor = ""
                if email_added_removed:
                    strAvailMonitor = m.monitor.avail_added_removed_Str(previousAvailabilities, availabilities, "<p>", "</p>")
                if email_availability_monitor:
                    strAvailMonitor = strAvailMonitor + \
                                      m.monitor.avail_changed_Str(previousAvailabilities,
                                                                  availabilities,
                                                                  email_availability_monitor,
                                                                  "<p>", "</p>")
                if strAvailMonitor:
                    m.email.send_email("BUY_OVH: availabilities", strAvailMonitor, not loop)
                # Don't do the catalog monitoring if the user has just changed the filters
                if not filtersChanged:
                    strCatalogMonitor = m.monitor.catalog_added_removed_Str(previousPlans, plans, "<p>", "</p>")
                    if strCatalogMonitor:
                        m.email.send_email("BUY_OVH: catalog", strCatalogMonitor, not loop)
                else:
                    filtersChanged = False
                # if the conf says no loop, jump to the menu
                if not loop:
                    if showPrompt:
                        m.print.print_prompt(acceptable_dc, filterMemory, filterName, filterDisk, maxPrice, coupon)
                        # if there has been at least one auto buy, show counters
                        if autoBuyNumInit > 0 and autoBuyNum < autoBuyNumInit:
                            m.print.print_auto_buy(autoBuyNum, autoBuyNumInit,
                                                   autoOK, autoKO, autoFake)
                    break
                if not foundAutoBuyServer:
                    if showPrompt:
                        m.print.print_prompt(acceptable_dc, filterMemory, filterName, filterDisk, maxPrice, coupon)
                        if autoBuyNumInit > 0 and autoBuyNum < autoBuyNumInit:
                            m.print.print_auto_buy(autoBuyNum, autoBuyNumInit,
                                                   autoOK, autoKO, autoFake)
                    m.print.print_and_sleep(showPrompt, sleepsecs)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print("Exception!")
                print(e)
                if loop and email_exception:
                    m.email.send_email("BUY_OVH: Exception",str(e))
                print("Wait " + str(sleepsecs) + "s before retry.")
                time.sleep(sleepsecs)
    except KeyboardInterrupt:
        pass

    print("")
    # stop the infinite loop, the user must press L to restart it
    loop = False
    allChoices = input("(H for Help)> ")
    # The user can specify to buy a server multiple times
    # "2*5" means buy server 2, 5 times
    # "2" and "2*1" mean the same thing
    # "!2*3 ?2*10" works too (see below for ! and ?)
    allChoicesExpanded = expandMulti(allChoices)
    listChoices = allChoicesExpanded.split(' ')
    for sChoice in listChoices:
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
                sys.exit("You had one job.")
            if whattodo == 'a':
                print(displayedPlans[choice]['model'])
                whattodo = input("Last chance : Make an invoice = I , Buy now = N , other = out : ").lower()
            if whattodo == 'i':
                mybool = False
            elif whattodo == 'n':
                mybool = True
            else:
                continue
            buyServer(displayedPlans[choice], mybool, False)
        # not a number means command
        # the '?', '!', and '*' have no effect here 
        elif sChoice.lower() == 'fd':
            print("Current: " + filterDisk)
            filterDisk = input("New filter: ")
            filtersChanged = True
        elif sChoice.lower() == 'fm':
            print("Current: " + filterMemory)
            filterMemory = input("New filter: ")
            filtersChanged = True
        elif sChoice.lower() == 'fn':
            print("Current: " + filterName)
            filterName = input("New filter: ")
            filtersChanged = True
        elif sChoice.lower() == 'fp':
            if maxPrice > 0:
                print("Current:" + str(maxPrice))
            else:
                print("Current: None")
            tmpMaxPrice = input("New Max Price: ")
            if tmpMaxPrice == "":
                maxPrice = 0
            else:
                maxPrice = float(tmpMaxPrice)
            filtersChanged = True
        elif sChoice.lower() == 'k':
            print("Current: " + coupon)
            coupon = input("Enter Coupon: ")
        elif sChoice.lower() == 'uk':
            showUnknown = not showUnknown
        elif sChoice.lower() == 'u':
            showUnavailable = not showUnavailable
        elif sChoice.lower() == 'p':
            showPrompt = not showPrompt
        elif sChoice.lower() == 'c':
            showCpu = not showCpu
        elif sChoice.lower() == 'f':
            showFqn = not showFqn
        elif sChoice.lower() == 'b':
            showBandwidth = not showBandwidth
            filtersChanged = True
        elif sChoice == '$':
            fakeBuy = not fakeBuy
        elif sChoice.lower() == 'l':
            loop = True
        elif sChoice.lower() == 'o':
            m.orders.unpaid_orders(True)
        elif sChoice.lower() == 'd':
            m.orders.undelivered_orders(True)
        elif sChoice.lower() == 'r':
            # reload conf
            loadConfigMain(configFile)
            filtersChanged = True
        elif sChoice.lower() == 'rr':
            # reload conf including autobuy
            loadConfigMain(configFile)
            loadConfigAutoBuy(configFile)
            filtersChanged = True
        elif sChoice.lower() == 's':
            m.servers.servers_specs(True)
        elif sChoice.lower() == 't':
            addVAT = not addVAT
            # VAT increases the price which could no longer pass the max price filter
            # so a server could "disappear" or "appear" in the catalog
            # triggering the catalog monitor
            filtersChanged = True
        elif sChoice.lower() == 'v':
            m.availability.look_up_avail(availabilities)
        elif sChoice.lower() == 'h':
            showHelp()
        elif sChoice.lower() == 'q':
            sys.exit("Bye now.")
