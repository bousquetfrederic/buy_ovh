import requests

import m.global_variables as GV

# -------------- BUILD AVAILABILITY DICT -------------------------------------------------------------------------
def buildAvailabilityDict():
    myAvail = {}
    response = requests.get("https://eu.api.ovh.com/v1/dedicated/server/datacenter/availabilities?datacenters=" + ",".join(GV.acceptable_dc))
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