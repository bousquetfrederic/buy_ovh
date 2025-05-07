import os
import ovh
import re
import smtplib
import sys
import time
import yaml

from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Global variables ----------------------

unavailableList = ['comingSoon', 'unavailable', 'unknown']

configFile = {}
try:
    configFile = yaml.safe_load(open('conf.yaml', 'r'))
except Exception as e:
    print("Error with config.yaml")
    print(e)
    sys.exit("Bye now.")

acceptable_dc = configFile['datacenters'] if 'datacenters' in configFile else []
filterName = configFile['filterName'] if 'filterName' in configFile else ""
filterDisk = configFile['filterDisk'] if 'filterDisk' in configFile else ""
ovhSubsidiary = configFile['ovhSubsidiary'] if 'ovhSubsidiary' in configFile else "FR"
loop = configFile['loop'] if 'loop' in configFile else False
sleepsecs = configFile['sleepsecs'] if 'sleepsecs' in configFile else 60    
showPrompt = configFile['showPrompt'] if 'showPrompt' in configFile else True
showCpu = configFile['showCpu'] if 'showCpu' in configFile else True
showFqn = configFile['showFqn'] if 'showFqn' in configFile else True
showUnavailable = configFile['showUnavailable'] if 'showUnavailable' in configFile else True
fakeBuy = configFile['fakeBuy'] if 'fakeBuy' in configFile else True
coupon = configFile['coupon'] if 'coupon' in configFile else ''
autoBuyRE = configFile['auto_buy'] if 'auto_buy' in configFile else ""
autoBuyNum = configFile['auto_buy_num'] if 'auto_buy_num' in configFile else 1
autoBuyMaxPrice = configFile['auto_buy_max_price'] if 'auto_buy_max_price' in configFile else 0
autoBuyInvoicesNum = configFile['auto_buy_num_invoices'] if 'auto_buy_num_invoices' in configFile else 0
if autoBuyNum == 0:
    autoBuyRE = ""
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
email_added_removed = configFile['email_added_removed'] if 'email_added_removed' in configFile and email_on else False
email_availability_monitor = configFile['email_availability_monitor'] if 'email_availability_monitor' in configFile and email_on else ""
email_catalog_monitor = configFile['email_catalog_monitor'] if 'email_catalog_monitor' in configFile and email_on else False

# --- Create the API client -----------------
if 'APIEndpoint' not in configFile:
    print("APIEndpoint is mandatory in config file.")
    print("It should look like 'ovh-eu', 'ovh-us', 'ovh-ca'")
    print("See https://github.com/ovh/python-ovh?tab=readme-ov-file#1-create-an-application")
    sys.exit("Bye now.")
else:
    api_endpoint = configFile['APIEndpoint']

if 'APIKey' not in configFile or 'APISecret' not in configFile:
    print("APIKey and APISecret are mandatory in config file.")
    print("You need to create an application key!")
    print("See https://github.com/ovh/python-ovh?tab=readme-ov-file#1-create-an-application")
    print("Once you have the key and secret for your endpoint, fill APIKey and APISecret.")
    sys.exit("Bye now.")
else:
    api_key = configFile['APIKey']
    api_secret = configFile['APISecret']

if 'APIConsumerKey' not in configFile:
    print("You need a consumer key in the config file.")
    print("Let's try to get you one with full access.")
    ck_client = ovh.Client(endpoint=api_endpoint,
                           application_key=api_key,
                           application_secret=api_secret)
    ck = ck_client.new_consumer_key_request()
    ck.add_recursive_rules(ovh.API_READ_WRITE, "/")
    validation = ck.request()
    print("Please visit %s to authenticate" % validation['validationUrl'])
    input("and press Enter to continue...")
    print("Ok", ck_client.get('/me')['firstname'])
    print("Your APIConsumerKey is '%s'" % validation['consumerKey'])
    print("Add it to the config file and try again.")
    sys.exit("Bye now.")        
else:
    api_ck = configFile['APIConsumerKey']

client = ovh.Client(endpoint=api_endpoint,
                    application_key=api_key,
                    application_secret=api_secret,
                    consumer_key=api_ck)

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
               'comingSoon'  : color.BLUE,
               'autobuy'     : color.PURPLE
             }

# -------------- EMAILS ---------------------------------------------------------------------------------------

# send an email
def sendEmail(subject,text):

    html = """\
<html>
  <body>
""" + text + """\
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

        # if not in infinite loop, warn the user
        if not loop:
            print("Sending an email --> " + subject)
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
    sendEmail("BUY_OVH: startup", "<p>BUY_OVH has started</p>")

def sendAutoBuyEmail(string):
    sendEmail("BUY_OVH: autobuy", "<p>" + string + "</p>")

# ---------------- EMAIL MONITOR AVAILAIBILITIES ---------------------------------------
# - detect new servers appearing in availabilities (or leaving)
# - monitor availability of some servers
def availabilityMonitor(previousA, newA):
    strToSend = ""
    # look for new FQN in availabilities (no filters)
    if previousA and email_added_removed:
        for added in [x for x in newA.keys() if x not in previousA.keys()]:
            strToSend += "<p>Added to availabilities: " + added + "</p>\n"
        for removed in [x for x in previousA.keys() if x not in newA.keys()]:
            strToSend += "<p>Removed from availabilities: " + removed + "</p>\n"
    # look for availability change (unavailable <--> available)
    # for this there is a filter in order to not spam
    # the filter is on the FQN
    if previousA and email_availability_monitor:
        availNow = []
        availNotAnymore = []
        for fqn in newA:
            if bool(re.search(email_availability_monitor, fqn)):
                if (newA[fqn] not in unavailableList):
                    # found an available server that matches the filter
                    if (fqn not in previousA.keys()
                        or previousA[fqn] in unavailableList):
                        # its availability went from unavailable to available
                        availNow.append(fqn)
                else:
                    # found an unavailable server that matches the filter
                    if (fqn in previousA.keys()
                        and previousA[fqn] not in unavailableList):
                        # its availability went from available to unavailable
                        availNotAnymore.append(fqn)
        for fqn in availNow:
            strToSend += "<p>Available now: " + fqn + "</p>\n"
        for fqn in availNotAnymore:
            strToSend += "<p>No longer available: " + fqn + "</p>\n"
    if strToSend:
        sendEmail("BUY_OVH: availability monitor", strToSend)

# ---------------- EMAIL IF SOMETHING APPEARS IN THE CATALOG -----------------------------------
# The catalog is filtered (name and disk), so the new server must pass these filters
def catalogMonitor(previousP, newP):
    if previousP and email_catalog_monitor:
        previousFqns = [x['fqn'] for x in previousP]
        newFqns = [x['fqn'] for x in newP]
        addedFqns = [ x for x in newFqns if x not in previousFqns]
        removedFqns = [ x for x in previousFqns if x not in newFqns]
        if addedFqns or removedFqns:
            strChanged = ""
            for fqn in addedFqns:
                strChanged += "<p>New to the catalog: " + fqn + "</p>\n"
            for fqn in removedFqns:
                strChanged += "<p>No longer in the catalog: " + fqn + "</p>\n"
            sendEmail("BUY_OVH: catalog monitor", strChanged)

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
# Here we fix errors in the catalog to match the FQN listed in the availabilities
def fixMem(mem):
    fixedMem = mem
    # For 25rises011 and 021, OVH add "-rise-s" instead of the plancode at the end of the RAM
    # and in the availabilities there is an extra "-on-die-ecc-5200"
    if mem.endswith("-rise"):
        fixedMem = mem.removesuffix("-rise") + "-on-die-ecc-5200"
    return fixedMem

def fixSto(sto):
    fixedSto = sto
    # For SYS-01 with hybrid disks, the availabilities have 500nvme instead of 512nvme 
    if sto.endswith("4000sa-2x512nvme") or sto.endswith("4000sa-1x512nvme"):
        fixedSto = sto.replace("512", "500")
    return fixedSto

def buildList(avail):
    API_catalog = client.get("/order/catalog/public/eco", ovhSubsidiary=ovhSubsidiary)

    allPlans = API_catalog['plans']
    myPlans = []

    allAddons = API_catalog['addons']

    for plan in allPlans:
        planCode = plan['planCode']
        # only consider plans passing the name filter, which is a regular expression
        # Either invoice name of plan code must match
        if not (bool(re.search(filterName, plan['invoiceName']))
                or bool(re.search(filterName, plan['planCode']))):
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
                for me in allMemories:
                    for st in allStorages:
                        for ba in allBandwidths:
                            # each config may have a different price within the same plan
                            thisPrice = planPrice
                            # the API adds the name of the plan at the end of the addons, drop it
                            # (only for building the FQN)
                            # Also there are sometimes differences between catalog and availabilities
                            # fix these errors (only for building the FQN)
                            shortme = fixMem("-".join(me.split("-")[:-1]))
                            shortst = fixSto("-".join(st.split("-")[:-1]))
                            # filter unwanted disk types
                            # if the disk filter is set
                            # OVH seems to add sata now, like in "ssd-sata"
                            if not bool(re.search(filterDisk,shortst)):
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
                            try:
                                bandwidthPlan = [x for x in allAddons if (x['planCode'] == ba)]
                                thisPrice = thisPrice + float(bandwidthPlan[0]['pricings'][1]['price'])/100000000
                            except Exception as e:
                                print(e)
                            priceStr = "{:.2f}".format(thisPrice)
                            # don't add plan if unavailable and not auto buy (if option selected)
                            myFqn = planCode + "." + shortme + "." + shortst + "." + da
                            if myFqn in avail:
                                myavailability = avail[myFqn]
                            else:
                                myavailability = 'unknown'
                            myAutoBuy = (autoBuyRE and
                                         (bool(re.search(autoBuyRE, myFqn)) or bool(re.search(autoBuyRE, plan['invoiceName'])))
                                         and (autoBuyMaxPrice == 0 or thisPrice <= autoBuyMaxPrice))
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
        if avail in unavailableList:
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
            planColor = whichColor['autobuy']
        else:
            planColor = printcolor
        if showFqn:
            fqnStr = planColor + plan['fqn'] + printcolor
        else:
            codeStr = planColor + plan['planCode'].ljust(11) + printcolor
            fqnStr = codeStr  + "| " + modelStr + "| " + plan['datacenter'] + " | " \
                     + plan['memory'].split("-")[1].rjust(4) + " | " \
                     + "-".join(plan['storage'].split("-")[1:-1]).ljust(11)
        print(printcolor
              + str(plans.index(plan)).ljust(4) + "| "
              + fqnStr + " | "
              + plan['bandwidth'].split("-")[1].rjust(4) + " | "
              + plan['price'].rjust(6) + " |"
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
          + "] - Filters : [" + filterName
          + "][" + filterDisk
          +"] - Coupon : [" + coupon + "]")

# ----------------- SLEEP x SECONDS -----------------------------------------------------------
def printAndSleep():
    for i in range(sleepsecs,0,-1):
        if showPrompt:
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

    # add coupon
    if coupon:
        result = client.post(f'/order/cart/{cartId}/coupon',
                             label = "coupon",
                             value = coupon)

    return cartId

# ---------------- CHECKOUT THE CART ---------------------------------------------------------
def checkoutCart(cartId, buyNow, autoMode):
    # 'global' because the function may change these global variables
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
    # 'global' because the function may change this global variable
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

# ----------------- SHOW UNPAID ORDERS --------------------------------------------------------
def unpaidOrders():
    # Get today's date
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    # Calculate the date 14 days ago
    date_14_days_ago = today - timedelta(days=14)

    params = {}
    params['date.from'] = date_14_days_ago.strftime('%Y-%m-%d')
    params['date.to'] = tomorrow.strftime('%Y-%m-%d')

    API_orders = client.get("/me/order/", **params)

    orderList = []

    print("Building list of unpaid orders. Please wait.")

    for orderId in API_orders:
        orderStatus = client.get("/me/order/{0}/status/".format(orderId))
        if orderStatus == 'notPaid':
            details = client.get("/me/order/{0}/details/".format(orderId))
            for detailId in details:
                orderDetail = client.get("/me/order/{0}/details/{1}".format(orderId, detailId))
                if orderDetail['domain'] == '*001' and orderDetail['detailType'] == "DURATION":
                    description = orderDetail['description'].split('|')[0].split(' ')[0]
                    location = orderDetail['description'].split('-')[-2][-4:]
                    theOrder = client.get("/me/order/{0}/".format(orderId))
                    orderURL = theOrder['url']
                    orderDate = theOrder['expirationDate'].split('T')[0]
                    orderList.append({
                                    'orderId' : orderId,
                                    'description' : description,
                                    'location' : location,
                                    'url' : orderURL,
                                    'date' : orderDate})

    for order in orderList:
        print (str(orderList.index(order)).ljust(4) + "| "
            + order['description'].ljust(10) + "| "
            + order['location']  + "| "
            + order['date'])

    continueLoop = True
    while continueLoop:
        sChoice = input("Which one? ")
        if sChoice.isdigit():
            choice = int (sChoice)
            if choice >= len(orderList):
                continueLoop = False
            else:
                print ("URL: " + orderList[choice]['url'])
        else:
            continueLoop = False

# ----------------- LOOK UP AVAILABILITIES ----------------------------------------------------
def lookUpAvail(avail):

    sChoice = 'a'
    while sChoice:
        sChoice = input("FQN starts with: ")
        if sChoice:
            for eachFqn in avail.keys():
                if eachFqn.startswith(sChoice):
                    print(eachFqn + " | " + avail[eachFqn])

# ----------------- DISPLAY HELP --------------------------------------------------------------
def showHelp():
    print("")
    print("Colour coding")
    print("-------------")
    print(whichColor['high'] + "Available HIGH")
    print(whichColor['low'] + "Available LOW")
    print(whichColor['unavailable'] + "Unavailable")
    print(whichColor['comingSoon'] + "Coming Soon")
    print(whichColor['unknown'] + "Availability unknown" + color.END)
    print("")
    print("Infinite Loop")
    print("-------------")
    print("When the loop is ON, the script updates the catalog and availabilities every " + str(sleepsecs) + "s.")
    print("You need to press CTRL-C to stop the loop and interact with the script.")
    print("")
    print("Toggles")
    print("-------")
    print(" U - show Unavailable servers ON/OFF")
    print(" P - show helpful prompt ON/OFF")
    print(" C - show CPU type ON/OFF")
    print(" F - show FQN instead of server details ON/OFF")
    print(" $ - fake buy ON/OFF")
    print("")
    print("Filters")
    print("-------")
    print(" N - re-enter the Name filter (invoice name or plan code)")
    print(" D - re-enter the Disk filter (sa, nvme, ssd)")
    print("")
    print("Commands")
    print("--------")
    print(" L - (re)start the infinite loop, activating monitoring if configured")
    print(" O - show your unpaid orders and a link to pay for one")
    print(" K - enter a coupon (buying will fail if coupon is invalid)")
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
    sendStartupEmail()

# previous list of availabilities so we can send email if something pops up
previousAvailabilities = {}

# previous plans
previousPlans = []

availabilities = {}
# Plans which pass the filters (name + disk)
plans = []
# Unavailable servers can be hidden (see conf file),
# so we need a list of non hidden plans for display and order
displayedPlans = []

# loop until the user wants out
while True:

    try:
        while True:
            try:
                os.system('cls' if os.name == 'nt' else 'clear')
                if availabilities:
                    previousAvailabilities = availabilities
                    previousPlans = plans
                availabilities = buildAvailabilityDict()
                plans = buildList(availabilities)
                displayedPlans = [ x for x in plans if (showUnavailable or x['autobuy'] or x['availability'] not in unavailableList)]
                printList(displayedPlans)
                if fakeBuy:
                    print("- Fake Buy ON")
                foundAutoBuyServer = False
                if autoBuyRE:
                    for plan in plans:
                        if autoBuyNum > 0 and plan['availability'] not in unavailableList and plan['autobuy']:
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
                availabilityMonitor(previousAvailabilities, availabilities)
                catalogMonitor(previousPlans, plans)
                # if the conf says no loop, jump to the menu
                if not loop:
                    printPrompt()
                    break
                if not foundAutoBuyServer:
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
            print("Current: " + filterName)
            filterName = input("New filter: ")
        elif sChoice.lower() == 'd':
            print("Current: " + filterDisk)
            filterDisk = input("New filter: ")
        elif sChoice.lower() == 'k':
            print("Current: " + coupon)
            coupon = input("Enter Coupon: ")
        elif sChoice.lower() == 'u':
            showUnavailable = not showUnavailable
        elif sChoice.lower() == 'p':
            showPrompt = not showPrompt
        elif sChoice.lower() == 'c':
            showCpu = not showCpu
        elif sChoice.lower() == 'f':
            showFqn = not showFqn
        elif sChoice == '$':
            fakeBuy = not fakeBuy
        elif sChoice.lower() == 'l':
            loop = True
        elif sChoice.lower() == 'o':
            unpaidOrders()
        elif sChoice.lower() == 'v':
            lookUpAvail(availabilities)
        elif sChoice.lower() == 'h':
            showHelp()
        elif sChoice.lower() == 'q':
            sys.exit("Bye now.")