import re

import m.global_variables as GV

# ---------------- EMAIL MONITOR AVAILAIBILITIES ---------------------------------------
# - detect new servers appearing in availabilities (or leaving)
# - monitor availability of some servers
def avail_added_removed(previousA, newA):
    strToSend = ""
    # look for new FQN in availabilities (no filters)
    if previousA:
        for added in [x for x in newA.keys() if x not in previousA.keys()]:
            strToSend += "<p>Added to availabilities: " + added + "</p>\n"
        for removed in [x for x in previousA.keys() if x not in newA.keys()]:
            strToSend += "<p>Removed from availabilities: " + removed + "</p>\n"
    return strToSend

def avail_changed(previousA, newA, regex):
    # look for availability change (unavailable <--> available)
    # for this there is a filter in order to not spam
    # the filter is on the FQN
    strToSend = ""
    if previousA:
        availNow = []
        availNotAnymore = []
        for fqn in newA:
            if bool(re.search(regex, fqn)):
                if (newA[fqn] not in GV.unavailableList):
                    # found an available server that matches the filter
                    if (fqn not in previousA.keys()
                        or previousA[fqn] in GV.unavailableList):
                        # its availability went from unavailable to available
                        availNow.append(fqn)
                else:
                    # found an unavailable server that matches the filter
                    if (fqn in previousA.keys()
                        and previousA[fqn] not in GV.unavailableList):
                        # its availability went from available to unavailable
                        availNotAnymore.append(fqn)
        for fqn in availNow:
            strToSend += "<p>Available now: " + fqn + "</p>\n"
        for fqn in availNotAnymore:
            strToSend += "<p>No longer available: " + fqn + "</p>\n"
    return strToSend

# ---------------- EMAIL IF SOMETHING APPEARS IN THE CATALOG -----------------------------------
# The catalog is filtered (name and disk), so the new server must pass these filters
def catalog_added_removed(previousP, newP):
    strChanged = ""
    if previousP:
        previousFqns = [x['fqn'] for x in previousP]
        newFqns = [x['fqn'] for x in newP]
        addedFqns = [ x for x in newFqns if x not in previousFqns]
        removedFqns = [ x for x in previousFqns if x not in newFqns]
        for fqn in addedFqns:
            strChanged += "<p>New to the catalog: " + fqn + "</p>\n"
        for fqn in removedFqns:
            strChanged += "<p>No longer in the catalog: " + fqn + "</p>\n"
    return strChanged