import logging
import re
import requests

logger = logging.getLogger(__name__)

__all__ = ['added_removed', 'build_list']

# -------------- EXTRACT THE PRICE AND FEES INCLUDING PROMOTION ----------------------------------------------------
def getPriceValue(price):
    myPrice = float(price['price'])/100000000
    allPromo = price['promotions']
    if allPromo:
        allPercentPromo = [x for x in allPromo if x['type']=='percentage']
        # take only the first one
        if allPercentPromo:
            myPromo = float(100-allPercentPromo[0]['value'])/100
        else:
            myPromo = 1
    else:
        myPromo = 1
    return myPrice * myPromo

def getPlanPrice(plan, mode):
    try:
        allPlanPrices = [x for x in plan['pricings']
                         if x['phase'] == 1
                         and x['capacities'][0] == 'renew'
                         and x['strategy'] == 'tiered'
                         and x['mode'] == mode]
        return getPriceValue(allPlanPrices[0])
    except (KeyError, IndexError, TypeError):
        return 0

def getPlanFee(plan, mode):
    try:
        allPlanFees = [x for x in plan['pricings']
                       if x['phase'] == 0
                       and x['capacities'][0] == 'installation'
                       and x['strategy'] == 'tiered'
                       and x['mode']  == mode]
        return getPriceValue(allPlanFees[0])
    except (KeyError, IndexError, TypeError):
        return 0

# -------------- BUILD LIST OF SERVERS ---------------------------------------------------------------------------
def build_list(url,
               avail, ovhSubsidiary,
               filterName, filterDisk, filterMemory, acceptable_dc, maxPrice,
               addVAT, months,
               bandwidthAndVRack):
    logger.debug("Building Server list")
    response = requests.get(url + "order/catalog/public/eco?ovhSubsidiary=" + ovhSubsidiary)
    API_catalog = response.json()

    allPlans = API_catalog['plans']
    myPlans = []

    if months == 12:
        pricingMode = 'upfront12'
    elif months == 24:
        pricingMode = 'upfront24'
    else:
        pricingMode = 'default'

    allAddonsDict = {}
    for addon in API_catalog['addons']:
        planCode = addon["planCode"]
        allAddonsDict[planCode] = {k: v for k, v in addon.items() if k != "planCode"}

    try:
        vatRate = 1 + (API_catalog['locale']['taxRate']) / 100
    except (KeyError, TypeError):
        logger.exception("Could not read VAT from the catalog")
        if addVAT:
            print("Could not read VAT from the catalog")
        vatRate = 1
    logger.debug("VAT Rate=" + str(vatRate))

    for plan in allPlans:
        planCode = plan['planCode']
        invoiceNameSplit = plan['invoiceName'].split('|')
        model = invoiceNameSplit[0]
        if len(invoiceNameSplit) > 1:
            cpu = invoiceNameSplit[1][1:]
            # remove extra space at the end of the model name
            model = model[:-1]
        else:
            cpu = "unknown"
        # only consider plans passing the name filter, which is a regular expression
        # Either model (from invoice name) of plan code must match
        if not (bool(re.search(filterName, model))
                or bool(re.search(filterName, plan['planCode']))):
            continue

        # find the price and fee
        planFee = getPlanFee(plan, pricingMode)
        planPrice = getPlanPrice(plan, pricingMode)

        allStorages = []
        allMemories = []
        allBandwidths = []
        allVRack = []

        # find mandatory addons
        for family in plan['addonFamilies']:
            if family['name'] == "storage":
                allStorages = family['addons']
            elif family['name'] == "memory":
                allMemories = family['addons']
            elif family['name'] == "bandwidth":
                allBandwidths = family['addons']
            elif family['name'] == "vrack":
                allVRack = family['addons']

        # vRack is not always present
        if not allVRack:
            allVRack = ['none']

        allDatacenters = []

        # same for datacenters
        for config in plan['configurations']:
            if config['name'] == "dedicated_datacenter":
                allDatacenters = config['values']
                # filter and sort datacenters per acceptable_dc
                if acceptable_dc:
                    filteredDatacenters = [x for x in allDatacenters if x in acceptable_dc]
                    sortedDatacenters = sorted(filteredDatacenters, key=lambda x: acceptable_dc.index(x))
                else:
                    sortedDatacenters = allDatacenters

        # build a list of all possible combinations
        for da in sortedDatacenters:
            for me in allMemories:
                memoryPlan = allAddonsDict[me]
                # apply the memory filter
                if not bool(re.search(filterMemory,memoryPlan['product'])):
                    continue
                memoryFee = getPlanFee(memoryPlan, pricingMode)
                memoryPrice = getPlanPrice(memoryPlan, pricingMode)
                for st in allStorages:
                    storagePlan = allAddonsDict[st]
                    # apply the disk filter
                    if not bool(re.search(filterDisk,storagePlan['product'])):
                        continue
                    storageFee = getPlanFee(storagePlan, pricingMode)
                    storagePrice = getPlanPrice(storagePlan, pricingMode)
                    for ba in allBandwidths:
                        bandwidthPlan = allAddonsDict[ba]
                        bandwidthPrice = getPlanPrice(bandwidthPlan, pricingMode)
                        for vr in allVRack:
                            # each config may have a different price within the same plan
                            thisPrice = planPrice + memoryPrice + storagePrice
                            thisFee = planFee + memoryFee + storageFee
                            # try to find out the full price
                            thisFee = thisFee + getPlanFee(storagePlan, pricingMode)
                            thisPrice = thisPrice + getPlanPrice(storagePlan, pricingMode)
                            memoryPlan = allAddonsDict[me]
                            thisFee = thisFee + getPlanFee(memoryPlan, pricingMode)
                            thisPrice = thisPrice + getPlanPrice(memoryPlan, pricingMode)
                            bandwidthPlan = allAddonsDict[ba]
                            bandwidthPrice = getPlanPrice(bandwidthPlan, pricingMode)
                            # if showBandwidth is false, drop the plans with a bandwidth that costs money
                            if not bandwidthAndVRack and bandwidthPrice > 0.0:
                                continue
                            # not sure if there is setup fee for the bandwidth?
                            thisPrice = thisPrice + bandwidthPrice
                            if vr != 'none':
                                vRackPlan = allAddonsDict[vr]
                                vRackPrice = getPlanPrice(vRackPlan, pricingMode)
                                # if showBandwidth is false, drop the plans with a vRack that costs money
                                if not bandwidthAndVRack and vRackPrice > 0.0:
                                    continue
                                # not sure if there is setup fee for the vRack?
                                thisPrice = thisPrice + vRackPrice
                            if addVAT:
                                # apply the VAT to the price
                                thisFee = round(thisFee * vatRate, 2)
                                thisPrice = round(thisPrice * vatRate, 2)
                            # apply the max price filter if different from 0
                            if maxPrice > 0 and thisPrice > maxPrice:
                                continue
                            myFqn = planCode + "." + memoryPlan['product'] + "." + storagePlan['product'] + "." + da
                            if myFqn in avail:
                                myavailability = avail[myFqn]
                            else:
                                myavailability = 'unknown'
                            # Add the plan to the list
                            myPlans.append(
                                { 'planCode' : planCode,
                                'model' : model,
                                'cpu' : cpu,
                                'datacenter' : da,
                                'storage' : st,
                                'memory' : me,
                                'bandwidth' : ba,
                                'vrack' : vr,
                                'fqn' : myFqn, # for auto buy
                                'price' : thisPrice,
                                'fee' : thisFee,
                                'availability' : myavailability
                                })
    return sorted(myPlans, key=lambda x: x['planCode'])

# -------------- CHECK IF A SERVER WAS ADDED OR REMOVED -------------------------------------
def added_removed(previousP, newP):
    addedFqns = []
    removedFqns = []
    if previousP:
        previousFqns = [x['fqn'] for x in previousP]
        newFqns = [x['fqn'] for x in newP]
        addedFqns = [ x for x in newFqns if x not in previousFqns]
        removedFqns = [ x for x in previousFqns if x not in newFqns]
    return (addedFqns, removedFqns)
