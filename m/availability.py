import re
import requests

__all__ = ['unavailableList', 'added_removed', 'buildAvailabilityDict', 'changed', 'lookUpAvail']

unavailableList = ['comingSoon', 'unavailable', 'unknown']

# -------------- BUILD AVAILABILITY DICT -------------------------------------------------------------------------
def buildAvailabilityDict(datacenters=[]):
    myAvail = {}
    if datacenters:
        response = requests.get("https://eu.api.ovh.com/v1/dedicated/server/datacenter/availabilities?datacenters=" + ",".join(datacenters))
    else:
        response = requests.get("https://eu.api.ovh.com/v1/dedicated/server/datacenter/availabilities")
    for avail in response.json():
        myFqn = avail['fqn']
        for da in avail['datacenters']:
            myLongFqn = myFqn + "." + da['datacenter']
            myAvail[myLongFqn] = da['availability']
    return myAvail

# -------------- CHECK IF FQNS HAVE BEEN ADDED OR REMOVED -------------------------------------
def added_removed(previousA, newA):
    if previousA:
        return ([x for x in newA.keys() if x not in previousA.keys()],
                [x for x in previousA.keys() if x not in newA.keys()])
    else:
        return ([],[])

# -------------- CHECK IF AVAILABILITY OF FQN HAS CHANGED -------------------------------------
def changed(previousA, newA, regex):
    # look for availability change (unavailable <--> available)
    # for this there is a filter in order to not spam
    # the filter is on the FQN
    availNow = []
    availNotAnymore = []
    if previousA:
        for fqn in newA:
            if bool(re.search(regex, fqn)):
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
    return (availNow, availNotAnymore)

# ----------------- LOOK UP AVAILABILITIES ----------------------------------------------------
def lookUpAvail(avail):

    sChoice = 'a'
    while sChoice:
        sChoice = input("FQN starts with: ")
        if sChoice:
            for eachFqn in avail.keys():
                if eachFqn.startswith(sChoice):
                    print(eachFqn + " | " + avail[eachFqn])