import re
import requests

__all__ = ['added_removed', 'build_list']

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

# -------------- BUILD LIST OF SERVERS ---------------------------------------------------------------------------
def build_list(avail, ovhSubsidiary,
               filterName, filterDisk, acceptable_dc,
               bandwidthAndVRack):

    response = requests.get("https://eu.api.ovh.com/v1/order/catalog/public/eco?ovhSubsidiary=" + ovhSubsidiary)
    API_catalog = response.json()

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

        # build a list of all possible combinations
        for da in allDatacenters:
            # filter the unacceptable Datacenters according to the defined filter
            if not acceptable_dc or da in acceptable_dc:
                for me in allMemories:
                    for st in allStorages:
                        for ba in allBandwidths:
                            for vr in allVRack:
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
                                    bandwidthPrice = float(bandwidthPlan[0]['pricings'][1]['price'])/100000000
                                    # if showBandwidth is false, drop the plans with a bandwidth that costs money
                                    if not bandwidthAndVRack and bandwidthPrice > 0.0:
                                        continue
                                    thisPrice = thisPrice + bandwidthPrice
                                except Exception as e:
                                    print(e)
                                if vr != 'none':
                                    try:
                                        vRackPlan = [x for x in allAddons if (x['planCode'] == vr)]
                                        vRackPrice = float(vRackPlan[0]['pricings'][2]['price'])/100000000
                                        # if showBandwidth is false, drop the plans with a vRack that costs money
                                        if bandwidthAndVRack and vRackPrice > 0.0:
                                            continue
                                        thisPrice = thisPrice + vRackPrice
                                    except Exception as e:
                                        print(e)
                                myFqn = planCode + "." + shortme + "." + shortst + "." + da
                                if myFqn in avail:
                                    myavailability = avail[myFqn]
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
                                    'vrack' : vr,
                                    'fqn' : myFqn, # for auto buy
                                    'price' : thisPrice,
                                    'availability' : myavailability
                                    })
    return sorted(myPlans, key=lambda x: x['planCode'])

# -------------- ADD AUTO BUY INFO TO PLAN LIST ---------------------------------------------
def add_auto_buy(plans, autoBuyRE, autoBuyMaxPrice):
    for plan in plans:
        plan['autobuy'] = (autoBuyRE and
                           (bool(re.search(autoBuyRE, plan['fqn'])) or bool(re.search(autoBuyRE, plan['invoiceName'])))
                            and (autoBuyMaxPrice == 0 or plan['price'] <= autoBuyMaxPrice))        

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