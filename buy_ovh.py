import ovh
import time
import json
import os
import sys
import datetime


# --- INITIAL VALUES ------------------------
#acceptable_dc = ['gra','rbx']
acceptable_dc = ['gra','rbx','sbg','lon','fra','waw']

filterInvoiceName = ['KS-LE', 'KS-A']

ovhSubsidiary="FR"

sleepsecs = 10

# -------------------------------------------


# --- Coloring stuff ------------------------
class color:
   PURPLE = '\033[1;35;48m'
   CYAN = '\033[1;36;48m'
   BOLD = '\033[1;37;48m'
   BLUE = '\033[1;34;48m'
   GREEN = '\033[1;32;48m'
   YELLOW = '\033[1;33;48m'
   RED = '\033[1;31;48m'
   BLACK = '\033[1;30;48m'
   UNDERLINE = '\033[4;37;48m'
   END = '\033[1;37;0m'

whichColor = { 'unknown'     : color.BLACK,
               'low'         : color.YELLOW,
               'high'        : color.GREEN,
               'unavailable' : color.RED
             }

# ------------ TOOLS --------------------------------------------------------------------------------------------

# startswith from a list
def startsWithList(st,li):
    for elem in li:
        if st.startswith(elem):
            return True
    return False


# -------------- BUILD LIST OF SERVERS ---------------------------------------------------------------------------
def buildList(cli):
    API_catalog = cli.get("/order/catalog/public/eco", ovhSubsidiary=ovhSubsidiary)
    API_availabilities = cli.get("/dedicated/server/datacenter/availabilities?datacenters=" + ",".join(acceptable_dc))

    allPlans = API_catalog['plans']
    myPlans = []

    for plan in allPlans:
        planCode = plan['planCode']
        # only consider plans name starting with the defined filter
        if ( not startsWithList(plan['invoiceName'], filterInvoiceName) ):
            continue

        allStorages = []
        allMemories = []
        allBandwidths = []

        # find mandatory addons
        # TODO: rewrite with list comprehension
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
                            # the API adds the name of the plan at the end of the addons, drop it
                            shortme = "-".join(me.split("-")[:-1])
                            shortst = "-".join(st.split("-")[:-1])
                            # build a list of the availabilities for the current plan + addons
                            avail = [x for x in API_availabilities
                                     if (x['fqn'] == planCode + "." + shortme + "." + shortst )]
                            if len(avail) > 0:
                                availability = avail[0]
                                # the list contains the availabilities in each DC
                                availAllDC = availability['datacenters']
                                # find the one for the current DC
                                mydc = [x for x in availAllDC if x['datacenter'] == da]
                                if len(mydc) > 0:
                                    myavailability = mydc[0]['availability']
                                else:
                                    myavailability = 'unknown'
                            else:
                                myavailability = 'unknown'
                            # Add the plan to the list
                            myPlans.append(
                                { 'planCode' : planCode,
                                  'invoiceName' : plan['invoiceName'],
                                  'datacenter' : da,
                                  'storage' : st,
                                  'memory' : me,
                                  'bandwidth' : ba,
                                  'availability' : myavailability
                                })
    return myPlans


# ----------------- PRINT LIST OF SERVERS -----------------------------------------------------
def printList(plans):
    for plan in plans:
        avail = plan['availability']
        if avail in ['unavailable','unknown']:
            printcolor = whichColor[avail]
        elif avail.endswith("low"):
            printcolor = whichColor['low']
        elif avail.endswith("high"):
            printcolor = whichColor['high']
        else:
            printcolor = whichColor['unknown']
        print(printcolor
              + str(plans.index(plan)).ljust(5) + " | "
              + plan['invoiceName'].ljust(30) + " | "
              + plan['datacenter'] + " | "
              + "-".join(plan['memory'].split("-")[:-1]).ljust(25) + " | "
              + "-".join(plan['storage'].split("-")[:-1]).ljust(25) + " | "
              + plan['availability']
              + color.END)



# ----------------- MAIN PROGRAM --------------------------------------------------------------

client = ovh.Client()

try:
    while True:
        try:
            os.system('cls' if os.name == 'nt' else 'clear')
            plans = buildList(client)
            printList(plans)
            print("- Acceptable DCs : [" + ",".join(acceptable_dc) + "] - Filters : [" + ",".join(filterInvoiceName) + "]- OVH Subsidiary : " + ovhSubsidiary)
            print("- Refresh every " + str(sleepsecs) + "s. CTRL-C to stop and buy/quit.")
            time.sleep(sleepsecs)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print("Exception!")
            print(e)
            print("Wait " + str(sleepsecs) + "s before retry.")
            time.sleep(sleepsecs)
            pass
except KeyboardInterrupt:
    pass

print("")
os.system('cls' if os.name == 'nt' else 'clear')
printList(plans)
sChoice = input("Which one? (Q to quit) ")
if not sChoice.isdigit():
    sys.exit("Bye now.")
choice = int (sChoice)
if choice >= len(plans):
     sys.exit("You had one job.")

myplan = plans[choice]
print("Let's go for " + myplan['invoiceName'] + " in " + myplan['datacenter'] + ".")

# make a cart
cart = client.post("/order/cart", ovhSubsidiary=ovhSubsidiary)
cartId = cart.get("cartId")
client.post("/order/cart/{0}/assign".format(cartId))
# add the server
result = client.post(
                     f'/order/cart/{cart.get("cartId")}/eco',
                     duration = "P1M",
                     planCode = myplan['planCode'],
                     pricingMode = "default",
                     quantity = 1
                    )
itemId = result['itemId']
print("Item ID = " + str(itemId))

# add options
result = client.post(
                     f'/order/cart/{cartId}/eco/options',
                     duration = "P1M",
                     itemId = itemId,
                     planCode = myplan['memory'],
                     pricingMode = "default",
                     quantity = 1
                    )
result = client.post(
                     f'/order/cart/{cartId}/eco/options',
                     itemId = itemId,
                     duration = "P1M",
                     planCode = myplan['storage'],
                     pricingMode = "default",
                     quantity = 1
                    )
result = client.post(
                     f'/order/cart/{cartId}/eco/options',
                     itemId = itemId,
                     duration = "P1M",
                     planCode = myplan['bandwidth'],
                     pricingMode = "default",
                     quantity = 1
                    )

# add configuration
result = client.post(
                     f'/order/cart/{cartId}/item/{itemId}/configuration',
                     label = "dedicated_datacenter",
                     value = myplan['datacenter']
                     )
result = client.post(
                     f'/order/cart/{cartId}/item/{itemId}/configuration',
                     label = "dedicated_os",
                     value = "none_64.en"
                     )
if myplan['datacenter'] == "bhs":
    myregion = "canada"
else:
    myregion = "europe"
result = client.post(
                     f'/order/cart/{cartId}/item/{itemId}/configuration',
                     label = "region",
                     value = myregion
                     )

# checkout!

whattodo = input("Last chance : Make an invoice = I , Buy now = N , other = out :").lower()
if whattodo == 'i':
    mybool = False
elif whattodo == 'n':
    mybool = True
else:
    sys.exit("Keep your money!")

try:
    result = client.post(f'/order/cart/{cartId}/checkout',
                         autoPayWithPreferredPaymentMethod=mybool,
                         waiveRetractationPeriod=mybool
                        )
    print(result)
except ovh.exceptions.BadParametersError as e:
    print("Not today.")
    print(e)










