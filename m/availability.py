import logging
import requests

logger = logging.getLogger(__name__)

__all__ = ['added_removed', 'build_availability_dict', 'test_availability']

# -------------- TEST AVAILABILITY AGAINST LISTS -----------------------------------------------------------------
def test_availability(avail, allow_unavailable=False, allow_unknown=False):
    if avail == "unknown":
        return allow_unknown
    if avail in ("comingSoon", "unavailable"):
        return allow_unavailable
    return True

# -------------- BUILD AVAILABILITY DICT -------------------------------------------------------------------------
def build_availability_dict(url, datacenters=[]):
    logger.debug("Building Availability list")
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


