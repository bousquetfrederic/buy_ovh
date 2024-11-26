import ovh
import time
import json
import os
import sys
import time

# --- Conf values ------------------------
# if there is a file conf.py with conf values, use it
# otherwise use defaults values below
try:
    from conf import *
except:
    acceptable_dc = ['gra','rbx','sbg','lon','fra','waw',"bhs"]
    filterInvoiceName = ['KS-LE', 'KS-A']
    filterDisk = ['ssd','nvme']
    ovhSubsidiary="FR"
    sleepsecs = 60
    showPrompt = True
    showCpu = True
    showUnavailable = True
    fakeBuy = True
# -------------------------------------------

# --- Global variables ----------------------
client = ovh.Client()

# make a list with autobuys, otherwise empty
autoBuyList = []
# how many auto buys before stopping
autoBuyNum = 0
autoBuyNumInit = 0
autoBuyMaxPrice = 0
if 'auto_buy' in dir():
    autoBuyList = auto_buy
    if 'auto_buy_num' in dir():
        autoBuyNum = auto_buy_num
    if autoBuyNum < 1:
        autoBuyList = []
if 'auto_buy_max_price' in dir():
    autoBuyMaxPrice = auto_buy_max_price
# counters to display how auto buy are doing
autoOK = 0
autoKO = 0
autoFake = 0

# --- Coloring stuff ------------------------
class color:
   PURPLE = '\033[0;35;48m'
   CYAN = '\033[0;36;48m'
   BOLD = '\033[0;37;48m'
   BLUE = '\033[0;34;48m'
   GREEN = '\033[0;32;48m'
   YELLOW = '\033[0;33;48m'
   RED = '\033[0;31;48m'
   BLACK = '\033[0;30;48m'
   UNDERLINE = '\033[0;37;48m'
   END = '\033[0;37;0m'

whichColor = { 'unknown'     : color.CYAN,
               'low'         : color.YELLOW,
               'high'        : color.GREEN,
               'unavailable' : color.RED,
               'autobuy'     : color.PURPLE
             }

# ------------ TOOLS --------------------------------------------------------------------------------------------

# startswith from a list
def startsWithList(st,li):
    for elem in li:
        if st.startswith(elem):
            return True
    return False

# endswith from a list
def endsWithList(st,li):
    for elem in li:
        if st.endswith(elem):
            return True
    return False

# -------------- BUILD LIST OF SERVERS ---------------------------------------------------------------------------
def buildList(showU):
    API_catalog = client.get("/order/catalog/public/eco", ovhSubsidiary=ovhSubsidiary)
    API_availabilities = client.get("/dedicated/server/datacenter/availabilities?datacenters=" + ",".join(acceptable_dc))

    allPlans = API_catalog['plans']
    myPlans = []

    allAddons = API_catalog['addons']

    for plan in allPlans:
        planCode = plan['planCode']
        # only consider plans name starting with the defined filter
        if ( not startsWithList(plan['invoiceName'], filterInvoiceName) ):
            continue

        # find the price
        allPrices = plan['pricings']
        # let's just take the first one for the moment
        if allPrices:
            planPrice = float(allPrices[0]['price'])/100000000
        else:
            planPrice = 0.0

        allStorages = []
        allMemories = []
        allBandwidths = []

        # find mandatory addons
        for family in plan['addonFamilies']:
            if family['name'] == "storage":
                allStorages = family['addons']
            elif family['name'] == "memory":
                allMemories = family['addons']
            elif family['name'] == "bandwidth":
                allBandwidths = family['addons']

        allDatacenters = []

        # same for datacenters
        for config in plan['configurations']:
            if config['name'] == "dedicated_datacenter":
                allDatacenters = config['values']

        # build a list of all possible combinations
        for da in allDatacenters:
            # filter the unacceptable Datacenters according to the defined filter
            if not acceptable_dc or da in acceptable_dc:
                for ba in allBandwidths:
                    for me in allMemories:
                        for st in allStorages:
                            # each config may have a different price within the same plan
                            thisPrice = planPrice
                            # the API adds the name of the plan at the end of the addons, drop it
                            shortme = "-".join(me.split("-")[:-1])
                            shortst = "-".join(st.split("-")[:-1])
                            # filter unwanted disk types
                            if not endsWithList(shortst,filterDisk):
                                continue
                            # build a list of the availabilities for the current plan + addons
                            avail = [x for x in API_availabilities
                                     if (x['fqn'] == planCode + "." + shortme + "." + shortst )]
                            if avail:
                                availability = avail[0]
                                # the list contains the availabilities in each DC
                                availAllDC = availability['datacenters']
                                # find the one for the current DC
                                mydc = [x for x in availAllDC if x['datacenter'] == da]
                                if mydc:
                                    myavailability = mydc[0]['availability']
                                else:
                                    myavailability = 'unknown'
                            else:
                                myavailability = 'unknown'
                            # try to find out the full price
                            try:
                                storagePlan = [x for x in allAddons if (x['planCode'] == st)]
                                thisPrice = thisPrice + float(storagePlan[0]['pricings'][1]['price'])/100000000
                            except Exception as e:
                                print(e)
                            try:
                                memoryPlan = [x for x in allAddons if (x['planCode'] == me)]
                                thisPrice = thisPrice + float(memoryPlan[0]['pricings'][1]['price'])/100000000
                            except Exception as e:
                                print(e)
                            priceStr = "{:.2f}".format(thisPrice)
                            # don't add plan if unavailable and not auto buy (if option selected)
                            myFqn = planCode + "." + shortme + "." + shortst + "." + da
                            myAutoBuy = startsWithList(myFqn,autoBuyList) and (autoBuyMaxPrice == 0 or thisPrice <= autoBuyMaxPrice)
                            if myavailability == 'unavailable' and not myAutoBuy and not showU:
                                continue
                            # Add the plan to the list
                            myPlans.append(
                                { 'planCode' : planCode,
                                  'invoiceName' : plan['invoiceName'],
                                  'datacenter' : da,
                                  'storage' : st,
                                  'memory' : me,
                                  'bandwidth' : ba,
                                  'fqn' : planCode + "." + shortme + "." + shortst + "." + da, # for auto buy
                                  'autobuy' : myAutoBuy,
                                  'price' : priceStr,
                                  'availability' : myavailability
                                })
    return myPlans

# ----------------- PRINT LIST OF SERVERS -----------------------------------------------------
def printList(plans):
    if not plans:
        print(whichColor['unavailable'] + "No availability." + color.END)
    for plan in plans:
        avail = plan['availability']
        if avail in ['unavailable','unknown']:
            printcolor = whichColor[avail]
        elif avail.endswith("low") or avail.endswith('H'):
            printcolor = whichColor['low']
        elif avail.endswith("high"):
            printcolor = whichColor['high']
        else:
            printcolor = whichColor['unknown']
        invoiceNameSplit = plan['invoiceName'].split('|')
        model = invoiceNameSplit[0]
        if len(invoiceNameSplit) > 1:
            cpu = invoiceNameSplit[1][1:]
        else:
            cpu = "unknown"
        if showCpu:
            modelStr = model.ljust(10) + "| " + cpu.ljust(20)
        else:
            modelStr = model.ljust(10)
        # special colour for autobuy
        if plan['autobuy']:
            codeStr = whichColor['autobuy'] + plan['planCode'].ljust(11) + printcolor
        else:
            codeStr = plan['planCode'].ljust(11)
        print(printcolor
              + str(plans.index(plan)).ljust(4) + "| "
              + codeStr  + "| "
              + modelStr + "| "
              + plan['datacenter'] + " | "
              + "-".join(plan['memory'].split("-")[1:-1]).ljust(17) + "| "
              + "-".join(plan['storage'].split("-")[1:-1]).ljust(11) + "| "
              + plan['price'].ljust(6) + "| "
              #+ plan['availability']
              + color.END)
    # if there has been at least one auto buy, show counters
    if autoBuyNumInit > 0 and autoBuyNum < autoBuyNumInit:
        print("Auto buy left: " + str(autoBuyNum) + "/" + str(autoBuyNumInit)
              + " - OK: " + str(autoOK) + ", NOK: " + str(autoKO) + ", Fake: " + str(autoFake))


# ----------------- PRINT PROMPT --------------------------------------------------------------
def printPrompt(showP):
    if not showP:
        return
    print("- DCs : [" + ",".join(acceptable_dc)
          + "] - Filters : [" + ",".join(filterInvoiceName)
          + "][" + ",".join(filterDisk)
          +"] - OVH Subsidiary : " + ovhSubsidiary)

# ----------------- SLEEP x SECONDS -----------------------------------------------------------
def printAndSleep(showP):
    for i in range(sleepsecs,0,-1):
        if showP:
            print(f"- Refresh in {i}s. CTRL-C to stop and buy/quit.", end="\r", flush=True)
        time.sleep(1)

# ---------------- BUILD THE CART --------------------------------------------------------------
def buildCart(plan):
    if fakeBuy:
        print("Fake cart!")
        time.sleep(1)
        return 0

    # make a cart
    cart = client.post("/order/cart", ovhSubsidiary=ovhSubsidiary)
    cartId = cart.get("cartId")
    client.post("/order/cart/{0}/assign".format(cartId))
    # add the server
    result = client.post(
                         f'/order/cart/{cart.get("cartId")}/eco',
                         duration = "P1M",
                         planCode = plan['planCode'],
                         pricingMode = "default",
                         quantity = 1
                        )
    itemId = result['itemId']

    # add options
    result = client.post(
                         f'/order/cart/{cartId}/eco/options',
                         duration = "P1M",
                         itemId = itemId,
                         planCode = plan['memory'],
                         pricingMode = "default",
                         quantity = 1
                        )
    result = client.post(
                         f'/order/cart/{cartId}/eco/options',
                         itemId = itemId,
                         duration = "P1M",
                         planCode = plan['storage'],
                         pricingMode = "default",
                         quantity = 1
                        )
    result = client.post(
                         f'/order/cart/{cartId}/eco/options',
                         itemId = itemId,
                         duration = "P1M",
                         planCode = plan['bandwidth'],
                         pricingMode = "default",
                         quantity = 1
                        )

    # add configuration
    result = client.post(
                         f'/order/cart/{cartId}/item/{itemId}/configuration',
                         label = "dedicated_datacenter",
                         value = plan['datacenter']
                         )
    result = client.post(
                         f'/order/cart/{cartId}/item/{itemId}/configuration',
                         label = "dedicated_os",
                         value = "none_64.en"
                         )
    if plan['datacenter'] == "bhs":
        myregion = "canada"
    else:
        myregion = "europe"
    result = client.post(
                         f'/order/cart/{cartId}/item/{itemId}/configuration',
                         label = "region",
                         value = myregion
                         )
    return cartId

# ---------------- CHECKOUT THE CART ---------------------------------------------------------
def checkoutCart(cartId, buyNow, autoMode):
    global autoFake, autoOK
    if fakeBuy:
        print("Fake buy! Now: " + str(buyNow) + ", Auto: " + str(autoMode))
        time.sleep(2)
        if autoMode:
            autoFake += 1
        return

    # this is it, we checkout the cart!
    result = client.post(f'/order/cart/{cartId}/checkout',
                         autoPayWithPreferredPaymentMethod=buyNow,
                         waiveRetractationPeriod=buyNow
                        )
    if autoMode:
        autoOK += 1

# ----------------- BUY SERVER ----------------------------------------------------------------
def buyServer(plan, buyNow, autoMode):
    global autoKO
    if autoMode:
        strAuto = "   -Auto Mode-"
    else:
        strAuto = ""
    if buyNow:
        strBuyNow = "buy now a "
    else:
        strBuyNow = "get an invoice for a "
    print("Let's " + strBuyNow + plan['invoiceName'] + " in " + plan['datacenter'] + "." + strAuto)
    try:
        checkoutCart(buildCart(plan), buyNow, autoMode)
    except Exception as e:
        print("Not today.")
        print(e)
        if autoMode:
            autoKO += 1
        time.sleep(3)

# ----------------- MAIN PROGRAM --------------------------------------------------------------

# loop until the user wants out
while True:

    try:
        while True:
            try:
                os.system('cls' if os.name == 'nt' else 'clear')
                plans = buildList(showUnavailable)
                printList(plans)
                foundAutoBuyServer = False
                if autoBuyList:
                    for plan in plans:
                        if autoBuyNum > 0 and plan['availability'] not in ['unknown','unavailable'] and plan['autobuy']:
                            # auto buy
                            foundAutoBuyServer = True
                            buyServer(plan, True, True)
                            autoBuyNum -= 1
                            if autoBuyNum < 1:
                                autoBuyList = []
                                break
                if not foundAutoBuyServer:
                    printPrompt(showPrompt)
                    printAndSleep(showPrompt)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print("Exception!")
                print(e)
                print("Wait " + str(sleepsecs) + "s before retry.")
                time.sleep(sleepsecs)
    except KeyboardInterrupt:
        pass

    print("")

    sChoice = input("Which one? (Q to quit, Toggles: U/P/C) ")
    if not sChoice.isdigit():
        if sChoice.lower() == 'u':
            showUnavailable = not showUnavailable
        elif sChoice.lower() == 'p':
            showPrompt = not showPrompt
        elif sChoice.lower() == 'c':
            showCpu = not showCpu
        elif sChoice.lower() == 'q':
            sys.exit("Bye now.")
        continue
    choice = int (sChoice)
    if choice >= len(plans):
         sys.exit("You had one job.")

    whattodo = input("Last chance : Make an invoice = I , Buy now = N , other = out :").lower()
    if whattodo == 'i':
        mybool = False
    elif whattodo == 'n':
        mybool = True
    else:
        continue

    buyServer(plans[choice], mybool, False)
