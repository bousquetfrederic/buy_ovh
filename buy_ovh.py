import os
import re
import sys
import time

# modules
import m.global_variables as GV
import m.api
import m.availability
import m.catalog
import m.config
import m.email
import m.monitor
import m.orders
import m.print

# ----------------- CONNECT IF INFO IN CONF FILE ----------------------------------------------
if ('APIEndpoint' in m.config.configFile and
    'APIKey' in m.config.configFile and
    'APISecret' in m.config.configFile):
    # if the customer key is there too, we can connect
    if 'APIConsumerKey' in m.config.configFile:
        m.api.login(m.config.configFile['APIEndpoint'],
                    m.config.configFile['APIKey'],
                    m.config.configFile['APISecret'],
                    m.config.configFile['APIConsumerKey'])

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
    print("When the loop is ON, the script updates the catalog and availabilities every " + str(GV.sleepsecs) + "s.")
    print("You need to press CTRL-C to stop the loop and interact with the script.")
    print("")
    print("Toggles")
    print("-------")
    print(" B - show Bandwidth and vRack options ON/OFF")
    print(" C - show CPU type ON/OFF")
    print(" F - show FQN instead of server details ON/OFF")
    print(" P - show helpful prompt ON/OFF")
    print(" U - show Unavailable servers ON/OFF")
    print(" $ - fake buy ON/OFF")
    print("")
    print("Filters")
    print("-------")
    print(" D - re-enter the Disk filter (sa, nvme, ssd)")
    print(" N - re-enter the Name filter (invoice name or plan code)")
    print("")
    print("Commands")
    print("--------")
    print(" K - enter a coupon (buying will fail if coupon is invalid)")
    print(" L - (re)start the infinite loop, activating monitoring if configured")
    print(" O - show your unpaid orders and a link to pay for one")
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
    if autoMode:
        strAuto = "   -Auto Mode-"
    else:
        strAuto = ""
    if buyNow:
        strBuyNow = "buy now a "
    else:
        strBuyNow = "get an invoice for a "
    strBuy = strBuyNow + plan['invoiceName'] + " in " + plan['datacenter'] + "."
    print("Let's " + strBuy + strAuto)
    try:
        m.api.checkoutCart(m.api.buildCart(plan, GV.ovhSubsidiary, GV.coupon, GV.fakeBuy), buyNow, GV.fakeBuy)
        if autoMode:
            if GV.fakeBuy:
                GV.autoFake += 1
            else:
                GV.autoOK += 1
            if GV.email_auto_buy:
                m.email.sendAutoBuyEmail("SUCCESS: " + strBuy)
    except Exception as e:
        print("Not today.")
        print(e)
        if autoMode:
            GV.autoKO += 1
            if GV.email_auto_buy:
                m.email.sendAutoBuyEmail("FAILED: " + strBuy)
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
if GV.email_at_startup:
    m.email.sendStartupEmail()

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
                availabilities = m.availability.buildAvailabilityDict(GV.acceptable_dc)
                plans = m.catalog.build_list(availabilities,
                                             GV.ovhSubsidiary,
                                             GV.filterName, GV.filterDisk, GV.acceptable_dc,
                                             GV.showBandwidth)
                m.catalog.add_auto_buy(plans, GV.autoBuyRE, GV.autoBuyMaxPrice)
                displayedPlans = [ x for x in plans if (GV.showUnavailable or x['autobuy'] or x['availability'] not in m.availability.unavailableList)]
                m.print.printList(displayedPlans)
                if GV.fakeBuy:
                    print("- Fake Buy ON")
                if not m.api.isLoggedIn():
                    print("- Not logged in")
                foundAutoBuyServer = False
                if GV.autoBuyRE:
                    for plan in plans:
                        if GV.autoBuyNum > 0 and plan['availability'] not in m.availability.unavailableList and plan['autobuy']:
                            # auto buy
                            foundAutoBuyServer = True
                            # The last x are invoices (rather than direct buy) if a number
                            # of invoices is defined in the config file
                            autoBuyInvoice = GV.autoBuyNum <= GV.autoBuyInvoicesNum
                            buyServer(plan, not autoBuyInvoice, True)
                            GV.autoBuyNum -= 1
                            if GV.autoBuyNum < 1:
                                GV.autoBuyRE = ""
                                break
                # availability and catalog monitor if configured
                strAvailMonitor = ""
                if GV.email_added_removed:
                    strAvailMonitor = m.monitor.avail_added_removed_Str(previousAvailabilities, availabilities, "<p>", "</p>")
                if GV.email_availability_monitor:
                    strAvailMonitor = strAvailMonitor + \
                                      m.monitor.avail_changed_Str(previousAvailabilities,
                                                                  availabilities,
                                                                  GV.email_availability_monitor,
                                                                  "<p>", "</p>")
                if strAvailMonitor:
                    m.email.sendEmail("BUY_OVH: availabilities", strAvailMonitor)
                # Don't do the catalog monitoring if the user has just changed the filters
                if not filtersChanged:
                    strCatalogMonitor = m.monitor.catalog_added_removed_Str(previousPlans, plans, "<p>", "</p>")
                    if strCatalogMonitor:
                        m.email.sendEmail("BUY_OVH: catalog", strCatalogMonitor)
                else:
                    filtersChanged = False
                # if the conf says no loop, jump to the menu
                if not GV.loop:
                    m.print.printPrompt()
                    break
                if not foundAutoBuyServer:
                    m.print.printPrompt()
                    m.print.printAndSleep()
            except KeyboardInterrupt:
                raise
            # except Exception as e:
            #     print("Exception!")
            #     print(e)
            #     print("Wait " + str(GV.sleepsecs) + "s before retry.")
            #     time.sleep(GV.sleepsecs)
    except KeyboardInterrupt:
        pass

    print("")
    # stop the infinite loop, the user must press L to restart it
    GV.loop = False
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
                print(displayedPlans[choice]['invoiceName'])
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
        elif sChoice.lower() == 'n':
            print("Current: " + GV.filterName)
            GV.filterName = input("New filter: ")
            filtersChanged = True
        elif sChoice.lower() == 'd':
            print("Current: " + GV.filterDisk)
            GV.filterDisk = input("New filter: ")
            filtersChanged = True
        elif sChoice.lower() == 'k':
            print("Current: " + coupon)
            GV.coupon = input("Enter Coupon: ")
        elif sChoice.lower() == 'u':
            GV.showUnavailable = not GV.showUnavailable
        elif sChoice.lower() == 'p':
            GV.showPrompt = not GV.showPrompt
        elif sChoice.lower() == 'c':
            GV.showCpu = not GV.showCpu
        elif sChoice.lower() == 'f':
            GV.showFqn = not GV.showFqn
        elif sChoice.lower() == 'b':
            GV.showBandwidth = not GV.showBandwidth
            filtersChanged = True
        elif sChoice == '$':
            GV.fakeBuy = not GV.fakeBuy
        elif sChoice.lower() == 'l':
            GV.loop = True
        elif sChoice.lower() == 'o':
            m.orders.unpaidOrders()
        elif sChoice.lower() == 'v':
            m.availability.lookUpAvail(availabilities)
        elif sChoice.lower() == 'h':
            showHelp()
        elif sChoice.lower() == 'q':
            sys.exit("Bye now.")