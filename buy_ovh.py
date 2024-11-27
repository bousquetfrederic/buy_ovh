import ovh
import time
import os
import sys
import time
import yaml
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Global variables ----------------------
client = ovh.Client()

configFile = {}
try:
    configFile = yaml.safe_load(open('conf.yaml', 'r'))
except Exception as e:
    print("Error with config.yaml, using default values")
    print(e)
    time.sleep(3)

acceptable_dc = configFile['datacenters'] if 'datacenters' in configFile else ['gra','rbx','sbg']
filterInvoiceName = configFile['filterName'] if 'filterName' in configFile else ['KS-A']
filterDisk = configFile['filterDisk'] if 'filterDisk' in configFile else ['ssd','nvme','sa']
ovhSubsidiary = configFile['ovhSubsidiary'] if 'ovhSubsidiary' in configFile else "FR"
sleepsecs = configFile['sleepsecs'] if 'sleepsecs' in configFile else 60    
showPrompt = configFile['showPrompt'] if 'showPrompt' in configFile else True
showCpu = configFile['showCpu'] if 'showCpu' in configFile else True
showUnavailable = configFile['showUnavailable'] if 'showUnavailable' in configFile else True
fakeBuy = configFile['fakeBuy'] if 'fakeBuy' in configFile else True
autoBuyList = configFile['auto_buy'] if 'auto_buy' in configFile else []
autoBuyNum = configFile['auto_buy_num'] if 'auto_buy_num' in configFile else 1
autoBuyMaxPrice = configFile['auto_buy_max_price'] if 'auto_buy_max_price' in configFile else 0
if autoBuyNum == 0:
    autoBuyList = []
autoBuyNumInit = autoBuyNum

# counters to display how auto buy are doing
autoOK = 0
autoKO = 0
autoFake = 0

# for sending emails
email_on = configFile['email_on'] if 'email_on' in configFile else False
email_server_port = configFile['email_server_port'] if 'email_server_port' in configFile else 0
email_server_name = configFile['email_server_name'] if 'email_server_name' in configFile else ""
email_server_login = configFile['email_server_login'] if 'email_server_login' in configFile else ""
email_server_password = configFile['email_server_password'] if 'email_server_password' in configFile else ""
email_sender = configFile['email_sender'] if 'email_sender' in configFile else ""
email_receiver = configFile['email_receiver'] if 'email_receiver' in configFile else ""
email_at_startup = configFile['email_at_startup'] if 'email_at_startup' in configFile and email_on else False
email_auto_buy = configFile['email_auto_buy'] if 'email_auto_buy' in configFile and email_on else False

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

# keys present in dict A not in dict B
def inAnotB(A,B):
    return [x for x in A.keys() if x not in B.keys()]

# user input a list
def getListFromUser(prompt):
    a = "a"
    newList = []
    while a:
        a = input(prompt + ". Return to finish : ")
        if a:
            newList.append(a)
    return newList

# -------------- EMAILS ---------------------------------------------------------------------------------------

# send an email
def sendEmail(subject,text):

    html = """\
<html>
  <body>
    <p>
""" + text + """\
    </p>
  </body>
</html>
"""
    try:
        # Create a multipart message and set headers
        message = MIMEMultipart()
        message["From"] = email_sender
        message["To"] = email_receiver
        message["Subject"] = subject

        # Attach the HTML part
        message.attach(MIMEText(html, "html"))

        # Send the email
        with smtplib.SMTP(email_server_name, email_server_port) as server:
            server.starttls()
            server.login(email_server_login, email_server_password)
            server.sendmail(email_sender, email_receiver, message.as_string())
    except Exception as e:
        print("Failed to send an email.")
        print(e)
        time.sleep(2)

def sendStartupEmail():
    sendEmail("BUY_OVH: startup", "BUY_OVH has started")

def sendAutoBuyEmail(string):
    sendEmail("BUY_OVH: autobuy", string)

# -------------- BUILD AVAILABILITY DICT -------------------------------------------------------------------------
def buildAvailabilityDict():
    myAvail = {}
    for avail in client.get("/dedicated/server/datacenter/availabilities?datacenters=" + ",".join(acceptable_dc)):
        myFqn = avail['fqn']
        for da in avail['datacenters']:
            myLongFqn = myFqn + "." + da['datacenter']
            myAvail[myLongFqn] = da['availability']
    return myAvail

# -------------- BUILD LIST OF SERVERS ---------------------------------------------------------------------------
def buildList(avail):
    API_catalog = client.get("/order/catalog/public/eco", ovhSubsidiary=ovhSubsidiary)

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
                            if myFqn in avail:
                                myavailability = avail[myFqn]
                            else:
                                myavailability = 'unknown'
                            myAutoBuy = startsWithList(myFqn,autoBuyList) and (autoBuyMaxPrice == 0 or thisPrice <= autoBuyMaxPrice)
                            if myavailability in ['unavailable','unknown'] and not myAutoBuy and not showUnavailable:
                                continue
                            # Add the plan to the list
                            myPlans.append(
                                { 'planCode' : planCode,
                                  'invoiceName' : plan['invoiceName'],
                                  'datacenter' : da,
                                  'storage' : st,
                                  'memory' : me,
                                  'bandwidth' : ba,
                                  'fqn' : myFqn, # for auto buy
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
def printPrompt():
    if not showPrompt:
        return
    print("- DCs : [" + ",".join(acceptable_dc)
          + "] - Filters : [" + ",".join(filterInvoiceName)
          + "][" + ",".join(filterDisk)
          +"]")

# ----------------- SLEEP x SECONDS -----------------------------------------------------------
def printAndSleep():
    for i in range(sleepsecs,0,-1):
        if showPrompt:
            print(f"- Refresh in {i}s. CTRL-C to stop and buy/quit.", end="\r", flush=True)
        time.sleep(1)

# ----------------- PRINT AVAIL NEW OR REMOVED ------------------------------------------------
def printAddedOrRemoved(oldA, newA):
    for added in inAnotB(newA, oldA):
        print("Added to availabilities: " + added)
    for removed in inAnotB(oldA, newA):
        print("Removed from availabilities: " + removed)

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
    strBuy = strBuyNow + plan['invoiceName'] + " in " + plan['datacenter'] + "."
    print("Let's " + strBuy + strAuto)
    try:
        checkoutCart(buildCart(plan), buyNow, autoMode)
        if autoMode and email_auto_buy:
            sendAutoBuyEmail("SUCCESS: " + strBuy)
    except Exception as e:
        print("Not today.")
        print(e)
        if autoMode and email_auto_buy:
            sendAutoBuyEmail("FAILED: " + strBuy)
        if autoMode:
            autoKO += 1
        time.sleep(3)

# ----------------- MAIN PROGRAM --------------------------------------------------------------

# send email at startup
if email_at_startup:
    sendStartupEmail()

# build an initial list of availabilities so we can see if anything is added during the run
initAvailabilities = buildAvailabilityDict()

# loop until the user wants out
while True:

    try:
        while True:
            try:
                os.system('cls' if os.name == 'nt' else 'clear')
                availabilities = buildAvailabilityDict()
                plans = buildList(availabilities)
                printList(plans)
                if fakeBuy:
                    print("- Fake Buy ON")
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
                    printAddedOrRemoved(initAvailabilities, availabilities)
                    printPrompt()
                    printAndSleep()
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

    sChoice = input("Which one? (Q to quit, Toggles: U/P/C, Filters N/D) ")
    if not sChoice.isdigit():
        if sChoice.lower() == 'n':
            print("Current : " + ",".join(filterInvoiceName))
            filterInvoiceName = getListFromUser("One per line")
        elif sChoice.lower() == 'd':
            print("Current : " + ",".join(filterDisk))
            filterDisk = getListFromUser("One per line (nvme,ssd,sa)")
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

    whattodo = input("Last chance : Make an invoice = I , Buy now = N , other = out : ").lower()
    if whattodo == 'i':
        mybool = False
    elif whattodo == 'n':
        mybool = True
    else:
        continue

    buyServer(plans[choice], mybool, False)
