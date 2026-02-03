from collections import defaultdict

import m.availability
import m.catalog

__all__ = ['avail_added_removed_Str', 'avail_changed_Str', 'catalog_added_removed_Str']

# ---------------- TOOL FOR EMAIL ---------------------------------------
# - vibe coded using Copilot
# - replace [(a.b.c.d), (a.b.c.e)] by a.b.c.(d|e) for shorter emails
def compress_fnq_list(lines):
    fqns_4 = []
    passthrough = []
    for line in lines:
        parts = line.split(".")
        if len(parts) == 4:
            fqns_4.append(tuple(parts))
        else:
            passthrough.append(line)
    # Group by a
    groups_a = defaultdict(list)
    for a, b, c, d in fqns_4:
        groups_a[a].append((b, c, d))
    result = []
    for a, bcd_list in groups_a.items():
        # Group by b
        groups_b = defaultdict(list)
        for b, c, d in bcd_list:
            groups_b[b].append((c, d))
        # Pour chaque b, on construit sa structure c/d avec Option B
        b_struct = {}  # b -> list of (c_group_tuple, dset_tuple)
        for b, cd_list in groups_b.items():
            c_to_ds = defaultdict(set)
            for c, d in cd_list:
                c_to_ds[c].add(d)
            # Option B sur c/d : regrouper les c qui ont le même set de d
            dset_to_cs = defaultdict(list)
            for c, dset in c_to_ds.items():
                dset_to_cs[frozenset(dset)].append(c)
            struct = []
            for dset, cs in dset_to_cs.items():
                cs_sorted = tuple(sorted(cs))
                ds_sorted = tuple(sorted(dset))
                struct.append((cs_sorted, ds_sorted))
            struct.sort()
            b_struct[b] = struct
        # Maintenant, on regroupe les b qui ont la même structure c/d
        struct_to_bs = defaultdict(list)
        for b, struct in b_struct.items():
            key = tuple(struct)  # hashable
            struct_to_bs[key].append(b)
        # On produit les lignes
        for struct, bs in struct_to_bs.items():
            bs_sorted = sorted(bs)
            if len(bs_sorted) == 1:
                b_part = bs_sorted[0]
            else:
                b_part = "(" + "|".join(bs_sorted) + ")"
            for c_group, dset in struct:
                if len(c_group) == 1:
                    c_part = c_group[0]
                else:
                    c_part = "(" + "|".join(c_group) + ")"

                if len(dset) == 1:
                    d_part = dset[0]
                else:
                    d_part = "(" + "|".join(dset) + ")"
                result.append(".".join([a, b_part, c_part, d_part]))
    # On rajoute les lignes non compressées (≠ 4 niveaux)
    result.extend(passthrough)
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