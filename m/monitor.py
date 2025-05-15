import re

import m.availability

__all__ = ['avail_added_removed_Str', 'avail_changed_Str', 'catalog_added_removed_Str']

# ---------------- EMAIL MONITOR AVAILAIBILITIES ---------------------------------------
# - detect new servers appearing in availabilities (or leaving)
# - monitor availability of some servers
def avail_added_removed_Str(previousA, newA, preStr="", postStr=""):
    strToSend = ""
    # look for new FQN in availabilities (no filters)
    addedFqns, removedFqns = m.availability.added_removed(previousA, newA)
    if previousA:
        for added in addedFqns:
            strToSend += preStr + "Added to availabilities: " + added + postStr + "\n"
        for removed in removedFqns:
            strToSend += preStr + "Removed from availabilities: " + removed + postStr + "\n"
    return strToSend

def avail_changed_Str(previousA, newA, regex, preStr="", postStr=""):
    # look for availability change (unavailable <--> available)
    # for this there is a filter in order to not spam
    # the filter is on the FQN
    strToSend = ""
    availNow, availNotAnymore = m.availability.changed(previousA, newA, regex)
    for fqn in availNow:
        strToSend += preStr + "Available now: " + fqn + postStr + "\n"
    for fqn in availNotAnymore:
        strToSend += preStr + "No longer available: " + fqn + postStr + "\n"
    return strToSend

# ---------------- EMAIL IF SOMETHING APPEARS IN THE CATALOG -----------------------------------
# The catalog is filtered (name and disk), so the new server must pass these filters
def catalog_added_removed_Str(previousP, newP, preStr="", postStr=""):
    strChanged = ""
    addedFqns, removedFqns = m.catalog.added_removed(previousP, newP)
    for fqn in addedFqns:
        strChanged += preStr + "New to the catalog: " + fqn + postStr + "\n"
    for fqn in removedFqns:
        strChanged += preStr + "No longer in the catalog: " + fqn + postStr + "\n"
    return strChanged