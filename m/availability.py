import requests

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

# ----------------- LOOK UP AVAILABILITIES ----------------------------------------------------
def lookUpAvail(avail):

    sChoice = 'a'
    while sChoice:
        sChoice = input("FQN starts with: ")
        if sChoice:
            for eachFqn in avail.keys():
                if eachFqn.startswith(sChoice):
                    print(eachFqn + " | " + avail[eachFqn])