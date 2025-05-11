import time

import m.global_variables as GV

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

# ----------------- PRINT LIST OF SERVERS -----------------------------------------------------
def printList(plans):
    if not plans:
        print(whichColor['unavailable'] + "No availability." + color.END)
    sizeOfCol = {
        'index' : 0,
        'planCode' : 0,
        'datacenter' : 0,
        'model' : 0,
        'cpu' : 0,
        'fqn' : 0,
        'memory' : 0,
        'storage' : 0,
        'bandwidth' : 0,
        'vrack' : 0,
        'price' : 0
    }
    plansForDisplay = []
    # determine what to print
    for plan in plans:
        invoiceNameSplit = plan['invoiceName'].split('|')
        model = invoiceNameSplit[0]
        if len(invoiceNameSplit) > 1:
            cpu = invoiceNameSplit[1][1:]
            # remove extra space at the end of model name
            model = model[:-1]
        else:
            cpu = "unknown"
        if plan['vrack'] == 'none':
            vrack = 'none'
        else:
            vrack = plan['vrack'].split("-")[2]
        myPlanD = {
            'index':        str(plans.index(plan)),
            'planCode':     plan['planCode'],
            'datacenter':   plan['datacenter'],
            'fqn':          plan['fqn'],
            'memory':       plan['memory'].split("-")[1],
            'storage':      "-".join(plan['storage'].split("-")[1:-1]),
            'bandwidth':    plan['bandwidth'].split("-")[1],
            'vrack':        vrack,
            'autobuy':      plan['autobuy'],
            'availability': plan['availability'],
            'model':        model,
            'cpu':          cpu,
            'price':        plan['price']
            }
        plansForDisplay.append(myPlanD)
        # update the max width of each column if needed
        for col in myPlanD.keys():
            if col not in ['autobuy', 'availability']:
                sizeOfCol[col]=max(sizeOfCol[col], len(myPlanD[col]))

    # print the list
    for planD in plansForDisplay:
        # what colour?
        avail = planD['availability']
        if avail in GV.unavailableList:
            printcolor = whichColor[avail]
        elif avail.endswith("low") or avail.endswith('H'):
            printcolor = whichColor['low']
        elif avail.endswith("high"):
            printcolor = whichColor['high']
        else:
            printcolor = whichColor['unknown']
        # special colour for autobuy
        if planD['autobuy']:
            planColor = whichColor['autobuy']
        else:
            planColor = printcolor
        # show CPU or not?
        if GV.showCpu:
            modelStr = planD['model'].ljust(sizeOfCol['model']) + " | " + planD['cpu'].ljust(sizeOfCol['cpu'])
        else:
            modelStr = planD['model'].ljust(sizeOfCol['model'])
        # show FQN or split info into different columns?
        if GV.showFqn:
            fqnStr = planColor + planD['fqn'].ljust(sizeOfCol['fqn']) + printcolor
        else:
            codeStr = planColor + planD['planCode'].ljust(sizeOfCol['planCode']) + printcolor
            fqnStr = codeStr  + " | " + modelStr + " | " + \
                     planD['datacenter'].ljust(sizeOfCol['datacenter']) + " | " + \
                     planD['memory'].rjust(sizeOfCol['memory']) + " | " + \
                     planD['storage'].ljust(sizeOfCol['storage'])
        # show bandwidth and vrack?
        if GV.showBandwidth:
            if planD['vrack'] == 'none':
                vRackStr = 'none'
            else:
                vRackStr = planD['vrack'].rjust(sizeOfCol['vrack'])
            bandwidthStr = planD['bandwidth'].rjust(sizeOfCol['bandwidth']) + " | " + vRackStr + " | "
        else:
            bandwidthStr = ""

        colStr = printcolor + planD['index'].rjust(sizeOfCol['index']) + " | " + \
                 fqnStr + " | " + bandwidthStr + \
                 planD['price'].rjust(sizeOfCol['price']) + " |" + color.END
        print(colStr)

    # if there has been at least one auto buy, show counters
    if GV.autoBuyNumInit > 0 and GV.autoBuyNum < GV.autoBuyNumInit:
        print("Auto buy left: " + str(GV.autoBuyNum) + "/" + str(GV.autoBuyNumInit)
              + " - OK: " + str(GV.autoOK) + ", NOK: " + str(GV.autoKO) + ", Fake: " + str(GV.autoFake))


# ----------------- PRINT PROMPT --------------------------------------------------------------
def printPrompt():
    if not GV.showPrompt:
        return
    print("- DCs : [" + ",".join(GV.acceptable_dc)
          + "] - Filters : [" + GV.filterName
          + "][" + GV.filterDisk
          +"] - Coupon : [" + GV.coupon + "]")

# ----------------- SLEEP x SECONDS -----------------------------------------------------------
def printAndSleep():
    for i in range(GV.sleepsecs,0,-1):
        if GV.showPrompt:
            print(f"- Refresh in {i}s. CTRL-C to stop and buy/quit.", end="\r", flush=True)
        time.sleep(1)

# ----------------- PRINT LIST OF ORDERS -------------------------------------------------------
def printOrders(orderList):
    for order in orderList:
        print (str(orderList.index(order)).ljust(4) + "| "
            + order['description'].ljust(10) + "| "
            + order['location']  + "| "
            + order['date'])