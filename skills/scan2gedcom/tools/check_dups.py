# Look for one person under two ids: people in data/ with the same first
# given name and surname (or aka) and the same birth year, or the same
# names and the same spouse. Lists each group with its ids and the files
# that define them, for a person to judge: twins, a father and son, or a
# family's repeated names can be legitimate. With --new FILE..., lists
# only groups that include a person defined in those files.
#   python3 -I tools/check_dups.py [--new data/line-x.json ...]
import re, json, pathlib, sys, collections
new = set(sys.argv[sys.argv.index("--new") + 1:]) if "--new" in sys.argv else None
def norm(s): return re.sub(r"[^a-z]", "", s.casefold())
people, where, spouses = {}, collections.defaultdict(set), collections.defaultdict(set)
for p in sorted(pathlib.Path("data").glob("*.json")):
    d = json.loads(p.read_text())
    for x in d.get("people", []):
        people.setdefault(x["id"], x); where[x["id"]].add(str(p))
    for f in d.get("families", []):
        h, w = f.get("husband"), f.get("wife")
        if h and w: spouses[h].add(w); spouses[w].add(h)
def names(x):
    out = {(norm(x.get("given", "").split(" ")[0]) if x.get("given") else "", norm(x.get("surname", "")))}
    for a in x.get("aka", []):
        w = [v for v in re.split(r"[\s,]+", re.sub(r"\([^)]*\)|\"", " ", a)) if v]
        if len(w) >= 2: out.add((norm(w[0]), norm(w[-1])))
    return {n for n in out if n[0] and n[1]}
def born(x):
    for f in x.get("facts", []):
        m = re.search(r"\b(\d{4})\b", f.get("date", "")) if f["type"] == "BIRT" else None
        if m: return m.group(1)
groups = collections.defaultdict(set)
for pid, x in people.items():
    b = born(x)
    for n in names(x):
        if b: groups[("born", n, b)].add(pid)
        for sp in spouses[pid]:
            if sp in people:
                for sn in names(people[sp]): groups[("wed", n, sn)].add(pid)
seen, out = set(), []
for key, ids in sorted(groups.items(), key=lambda kv: str(kv[0])):
    ids = frozenset(ids)
    if len(ids) < 2 or ids in seen: continue
    if new is not None and not any(where[i] & new for i in ids): continue
    seen.add(ids)
    what = f"born {key[2]}" if key[0] == "born" else f"married a {key[2][0].title()} {key[2][1].title()}"
    out.append(f"{key[1][0].title()} {key[1][1].title()}, {what}: " + ", ".join(f"{i} ({'+'.join(sorted(pathlib.Path(w).stem for w in where[i]))})" for i in sorted(ids)))
for o in out: print(o)
print(f"{len(out)} groups to judge")
