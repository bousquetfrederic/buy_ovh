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
    return fixedMem

def fixSto(sto):
    fixedSto = sto
    # For SYS-01 with hybrid disks, the availabilities have 500nvme instead of 512nvme 
    if sto.endswith("4000sa-2x512nvme") or sto.endswith("4000sa-1x512nvme"):
        fixedSto = sto.replace("512", "500")
    return fixedSto

# -------------- BUILD LIST OF SERVERS ---------------------------------------------------------------------------
def build_list(url,
               avail, ovhSubsidiary,
               filterName, filterDisk, filterMemory, acceptable_dc, maxPrice,
               addVAT,
               bandwidthAndVRack):
    response = requests.get(url + "order/catalog/public/eco?ovhSubsidiary=" + ovhSubsidiary)
    API_catalog = response.json()

    allPlans = API_catalog['plans']
    myPlans = []

    allAddons = API_catalog['addons']

    try:
        vatRate = 1 + (API_catalog['locale']['taxRate']) / 100
    except:
        if addVAT:
            print("Could not read VAT from the catalog")
        vatRate = 1

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
        # first pricing is the setup fee, second is the monthly price
        # (1 month commitment)
        if allPrices:
            planFee = float(allPrices[0]['price'])/100000000
            planPrice = float(allPrices[1]['price'])/100000000
        else:
            planFee = 0.0
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
                # the API adds the name of the plan at the end of the addons, drop it
                # (only for building the FQN)
                # for KS-LE-* they also add the v1 at the end which needs to go
                # Also there are sometimes differences between catalog and availabilities
                # fix these errors (only for building the FQN)
                if me.split("-")[-1] == "v1":
                    shortme = fixMem("-".join(me.split("-")[:-2]))
                else:
                    shortme = fixMem("-".join(me.split("-")[:-1]))
                # apply the memory filter
                if not bool(re.search(filterMemory,shortme)):
                    continue
                for st in allStorages:
                    if st.split("-")[-1] == "v1":
                        shortst = fixSto("-".join(st.split("-")[:-2]))
                    else:
                        shortst = fixSto("-".join(st.split("-")[:-1]))
                    # apply the disk filter
                    if not bool(re.search(filterDisk,shortst)):
                        continue
                    for ba in allBandwidths:
                        for vr in allVRack:
                            # each config may have a different price within the same plan
                            thisPrice = planPrice
                            thisFee = planFee
                            # try to find out the full price
                            try:
                                storagePlan = [x for x in allAddons if (x['planCode'] == st)]
                                thisFee = thisFee + float(storagePlan[0]['pricings'][0]['price'])/100000000
                                thisPrice = thisPrice + float(storagePlan[0]['pricings'][1]['price'])/100000000
                            except Exception as e:
                                print(e)
                            try:
                                memoryPlan = [x for x in allAddons if (x['planCode'] == me)]
                                thisFee = thisFee + float(memoryPlan[0]['pricings'][0]['price'])/100000000
                                thisPrice = thisPrice + float(memoryPlan[0]['pricings'][1]['price'])/100000000
                            except Exception as e:
                                print(e)
                            try:
                                bandwidthPlan = [x for x in allAddons if (x['planCode'] == ba)]
                                bandwidthPrice = float(bandwidthPlan[0]['pricings'][1]['price'])/100000000
                                # if showBandwidth is false, drop the plans with a bandwidth that costs money
                                if not bandwidthAndVRack and bandwidthPrice > 0.0:
                                    continue
                                # not sure if there is setup fee for the bandwidth?
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
                                    # not sure if there is setup fee for the vRack?
                                    thisPrice = thisPrice + vRackPrice
                                except Exception as e:
                                    print(e)
                            if addVAT:
                                # apply the VAT to the price
                                thisFee = round(thisFee * vatRate, 2)
                                thisPrice = round(thisPrice * vatRate, 2)
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
                                'fee' : thisFee,
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
