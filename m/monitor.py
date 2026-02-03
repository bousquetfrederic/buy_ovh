from collections import defaultdict

import m.availability
import m.catalog

__all__ = ['avail_added_removed_Str', 'avail_changed_Str', 'catalog_added_removed_Str']

# ---------------- TOOL FOR EMAIL ---------------------------------------
# - vibe coded using Copilot
# - replace [(a.b.c.d), (a.b.c.e)] by a.b.c.(d|e) for shorter emails
def compress_fnq_list(lines):
    # Parse into lists of segments
    parsed = [tuple(line.split(".")) for line in lines]
    # Group by length: different lengths cannot be merged
    length_groups = defaultdict(list)
    for p in parsed:
        length_groups[len(p)].append(p)
    output = []
    for length, group in length_groups.items():
        # For each length, recursively factor
        output.extend(factor_level(group, 0))
    return [".".join(parts) for parts in output]

def factor_level(group, level):
    if len(group) == 1:
        return [group[0]]
    if level >= len(group[0]):
        return group
    # Group by the value at this level
    buckets = defaultdict(list)
    for g in group:
        buckets[g[level]].append(g)
    # If only one bucket, go deeper
    if len(buckets) == 1:
        key = next(iter(buckets))
        sub = factor_level(buckets[key], level + 1)
        return sub
    # Try to factor deeper levels inside each bucket
    factored = []
    for key, items in buckets.items():
        factored.append((key, factor_level(items, level + 1)))
    # Check if all subgroups share identical suffix patterns
    suffixes = [tuple(x[1] for x in f[1]) for f in factored]
    if all(s == suffixes[0] for s in suffixes):
        # We can merge keys at this level
        merged_keys = sorted(f[0] for f in factored)
        merged_suffix = suffixes[0][0]
        merged = [None] * len(merged_suffix)
        merged[level] = "(" + "|".join(merged_keys) + ")"
        for i in range(level + 1, len(merged_suffix)):
            merged[i] = merged_suffix[i]
        return [tuple(merged)]
    # Otherwise, return each subgroup separately
    result = []
    for key, sub in factored:
        for s in sub:
            new = list(s)
            new[level] = key
            result.append(tuple(new))
    return result

# ---------------- EMAIL MONITOR AVAILAIBILITIES ---------------------------------------
# - detect new servers appearing in availabilities (or leaving)
# - monitor availability of some servers
def avail_added_removed_Str(previousA, newA, preStr="", postStr=""):
    strToSend = ""
    # look for new FQN in availabilities (no filters)
    addedFqns, removedFqns = m.availability.added_removed(previousA, newA)
    try:
        addedList = compress_fnq_list(addedFqns)
        removedList = compress_fnq_list(removedFqns)
    except:
        addedList = addedFqns
        removedList = removedFqns
    if previousA and newA:
        for added in addedList:
            strToSend += preStr + "Added to availabilities: " + added + postStr + "\n"
        for removed in removedList:
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
    try:
        addedList = compress_fnq_list(addedFqns)
        removedList = compress_fnq_list(removedFqns)
    except:
        addedList = addedFqns
        removedList = removedFqns
    for fqn in addedList:
        strChanged += preStr + "New to the catalog: " + fqn + postStr + "\n"
    for fqn in removedList:
        strChanged += preStr + "No longer in the catalog: " + fqn + postStr + "\n"
    return strChanged