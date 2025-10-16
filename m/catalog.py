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
    elif mem.endswith("-16g"):
    # For KS-STOR and SYS-STOR they don't have the ECC part at the end of the mem in the catalog
        fixedMem = mem + "-ecc-2133"
    elif mem.endswith("-32g"):
        fixedMem = mem + "-ecc-2933"
    return fixedMem

def fixSto(sto):
    fixedSto = sto
    # For SYS-01 with hybrid disks, the availabilities have 500nvme instead of 512nvme 
    if sto.endswith("4000sa-2x512nvme") or sto.endswith("4000sa-1x512nvme"):
        fixedSto = sto.replace("512", "500")
    return fixedSto

# -------------- BUILD LIST OF SERVERS ---------------------------------------------------------------------------
def build_list(avail, ovhSubsidiary,
               filterName, filterDisk, acceptable_dc, maxPrice,
               percentVAT,
               bandwidthAndVRack):

    response = requests.get("https://eu.api.ovh.com/v1/order/catalog/public/eco?ovhSubsidiary=" + ovhSubsidiary)
    API_catalog = response.json()

    allPlans = API_catalog['plans']
    myPlans = []

    allAddons = API_catalog['addons']

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

        # find the price
        allPrices = plan['pricings']
        # let's just take the first one for the moment
        if allPrices:
            planPrice = float(allPrices[1]['price'])/100000000
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
                # filter and sort datacenters per acceptable_dc
                if acceptable_dc:
                    filteredDatacenters = [x for x in allDatacenters if x in acceptable_dc]
                    sortedDatacenters = sorted(filteredDatacenters, key=lambda x: acceptable_dc.index(x))
                else:
                    sortedDatacenters = allDatacenters

        # build a list of all possible combinations
        for da in sortedDatacenters:
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
                            # apply the VAT to the price
                            thisPrice = thisPrice * round(1+percentVAT/100, 2)
                            # apply the max price filter if different from 0
                            if maxPrice > 0 and thisPrice > maxPrice:
                                continue
                            myFqn = planCode + "." + shortme + "." + shortst + "." + da
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
                                'availability' : myavailability
                                })
    return sorted(myPlans, key=lambda x: x['planCode'])

# -------------- ADD AUTO BUY INFO TO PLAN LIST ---------------------------------------------
def add_auto_buy(plans, autoBuyRE, autoBuyMaxPrice):
    for plan in plans:
        plan['autobuy'] = (autoBuyRE and
                           (bool(re.search(autoBuyRE, plan['fqn'])) or bool(re.search(autoBuyRE, plan['model'])))
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
