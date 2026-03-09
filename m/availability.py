import logging
import re
import requests

logger = logging.getLogger(__name__)

__all__ = ['added_removed', 'build_availability_dict', 'changed', 'look_up_avail', 'test_availability']

# -------------- TEST AVAILABILITY AGAINST LISTS -----------------------------------------------------------------
def test_availability(avail, allow_unavailable=False, allow_unknown=False):
    if avail == "unknown":
        return allow_unknown
    if avail in ("comingSoon", "unavailable"):
        return allow_unavailable
    return True

# -------------- BUILD AVAILABILITY DICT -------------------------------------------------------------------------
def build_availability_dict(url, datacenters=[]):
    logger.info("Building Availability list")
    myAvail = {}
    if datacenters:
        response = requests.get(url + "dedicated/server/datacenter/availabilities?datacenters=" + ",".join(datacenters))
    else:
        response = requests.get(url + "dedicated/server/datacenter/availabilities")
    for avail in response.json():
        if 'fqn' in avail:
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
                if (test_availability(newA[fqn])):
                    # found an available server that matches the filter
                    if (fqn not in previousA.keys() or not test_availability(previousA[fqn])):
                        # its availability went from unavailable to available
                        availNow.append(fqn)
                else:
                    # found an unavailable server that matches the filter
                    if (fqn in previousA.keys() and not test_availability(previousA[fqn])):
                        # its availability went from available to unavailable
                        availNotAnymore.append(fqn)
    return (availNow, availNotAnymore)

# ----------------- LOOK UP AVAILABILITIES ----------------------------------------------------
def look_up_avail(avail):

    sChoice = 'a'
    while sChoice:
        sChoice = input("FQN starts with: ")
        if sChoice:
            fqnsToShow = []
            # size of column
            sizeCol = 0
            for eachFqn in avail.keys():
                if eachFqn.startswith(sChoice):
                    fqnsToShow.append(eachFqn)
                    sizeCol = max(sizeCol, len(eachFqn))
            for eachFqn in fqnsToShow:
                if eachFqn.startswith(sChoice):
                    print(eachFqn.ljust(sizeCol) + " | " + avail[eachFqn])