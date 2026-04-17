import logging
import re

import m.availability

__all__ = ['avail_added_removed_Str', 'avail_changed_Str', 'catalog_added_removed_Str']

logger = logging.getLogger(__name__)

# ---------------- TOOL FOR EMAIL ---------------------------------------
# - vibe coded using Copilot
# - compress the list by grouping the datacenters
# - replace [(a.b.c.d), (a.b.c.e)] by a.b.c.(d|e)
def compress_fnq_list(lines):
    groups = {}  # prefix -> list of last segments
    for line in lines:
        parts = line.split(".")
        prefix = tuple(parts[:-1])
        last = parts[-1]
        if prefix not in groups:
            groups[prefix] = []
        groups[prefix].append(last)
    result = []
    for prefix, lasts in groups.items():
        lasts_sorted = sorted(lasts)
        if len(lasts_sorted) == 1:
            last_part = lasts_sorted[0]
        else:
            last_part = "(" + "|".join(lasts_sorted) + ")"

        if prefix:
            result.append(".".join(prefix + (last_part,)))
        else:
            # rare case: only one level
            result.append(last_part)
    return result

# -------------- PRIVATE HELPERS -------------------------------------------------------

def _avail_changed(previousA, newA, regex):
    # look for availability change (unavailable <--> available)
    # for this there is a filter in order to not spam
    # the filter is on the FQN
    availNow = []
    availNotAnymore = []
    if previousA:
        for fqn in newA:
            if bool(re.search(regex, fqn)):
                if (m.availability.test_availability(newA[fqn])):
                    # found an available server that matches the filter
                    if (fqn not in previousA.keys() or not m.availability.test_availability(previousA[fqn])):
                        # its availability went from unavailable to available
                        availNow.append(fqn)
                else:
                    # found an unavailable server that matches the filter
                    if (fqn in previousA.keys() and not m.availability.test_availability(previousA[fqn])):
                        # its availability went from available to unavailable
                        availNotAnymore.append(fqn)
    return (availNow, availNotAnymore)

def _catalog_added_removed(previousP, newP):
    addedFqns = []
    removedFqns = []
    if previousP:
        previousFqns = [x['fqn'] for x in previousP]
        newFqns = [x['fqn'] for x in newP]
        addedFqns = [x for x in newFqns if x not in previousFqns]
        removedFqns = [x for x in previousFqns if x not in newFqns]
    return (addedFqns, removedFqns)

# ---------------- EMAIL MONITOR AVAILAIBILITIES ---------------------------------------
# - detect new servers appearing in availabilities (or leaving)
# - monitor availability of some servers
def avail_added_removed_Str(previousA, newA, preStr="", postStr=""):
    strToSend = ""
    # look for new FQN in availabilities (no filters)
    addedFqns, removedFqns = m.availability.added_removed(previousA, newA)
    addedList = compress_fnq_list(addedFqns)
    removedList = compress_fnq_list(removedFqns)
    if previousA and newA:
        for added in addedList:
            logger.info("a+ " + added)
            strToSend += preStr + "+ " + added + postStr + "\n"
        for removed in removedList:
            logger.info("a- " + removed)
            strToSend += preStr + "- " + removed + postStr + "\n"
    return strToSend

def avail_changed_Str(previousA, newA, regex, preStr="", postStr=""):
    # look for availability change (unavailable <--> available)
    # for this there is a filter in order to not spam
    # the filter is on the FQN
    strToSend = ""
    availNow, availNotAnymore = _avail_changed(previousA, newA, regex)
    for fqn in availNow:
        logger.info("Available now: " + fqn)
        strToSend += preStr + "O " + fqn + postStr + "\n"
    for fqn in availNotAnymore:
        logger.info("Not longer available: " + fqn)
        strToSend += preStr + "X " + fqn + postStr + "\n"
    return strToSend

# ---------------- EMAIL IF SOMETHING APPEARS IN THE CATALOG -----------------------------------
# The catalog is filtered (name and disk), so the new server must pass these filters
def catalog_added_removed_Str(previousP, newP, preStr="", postStr=""):
    strChanged = ""
    addedFqns, removedFqns = _catalog_added_removed(previousP, newP)
    addedList = compress_fnq_list(addedFqns)
    removedList = compress_fnq_list(removedFqns)
    for fqn in addedList:
        logger.info("c+ " + fqn)
        strChanged += preStr + "+ " + fqn + postStr + "\n"
    for fqn in removedList:
        logger.info("c- " + fqn)
        strChanged += preStr + "- " + fqn + postStr + "\n"
    return strChanged
