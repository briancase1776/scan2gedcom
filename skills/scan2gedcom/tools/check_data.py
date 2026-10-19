# Check data/*.json against tools/DATA-FORMAT.txt.
# Run from the project root:  python3 -I tools/check_data.py
# Problems make it exit 1. Warnings don't, but look at each one:
#   - a BIRT/DEAT/BURI/RESI whose note sounds like a guess (see "A guess
#     is not a vital event")
#   - the same event given differently in two files, which would show
#     up twice in the tree (see MERGING)
import json, pathlib, re, sys, itertools

FACTS = {"BIRT", "DEAT", "BURI", "MARR", "DIV", "RESI", "OCCU", "RELI", "EVEN"}
VITAL = {"BIRT", "DEAT", "BURI", "RESI"}
MON = "(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)"
DAY = rf"(\d{{1,2}} )?({MON} )?\d{{3,4}}"
DATE = re.compile(rf"^((ABT|BEF|AFT|EST|CAL) )?{DAY}$|^BET {DAY} AND {DAY}$|^FROM {DAY}( TO {DAY})?$|^TO {DAY}$")
ID = re.compile(r"^[a-z]+(-[a-z0-9]+)*$")
PAGE = re.compile(r"^PDF \d{1,4}(-\d{1,4})?$")
GUESS = re.compile(r"\b(possibl[ey]|perhaps|maybe|rumou?r(ed)?|probabl[ey]|likely|might)\b", re.I)

errors, warnings = [], []
def err(f, msg): errors.append(f"{f}: {msg}")
def warn(f, msg): warnings.append(f"warning: {f}: {msg}")

records = {p.stem for p in pathlib.Path("records").glob("*.txt")}
sheets = {p.stem for p in pathlib.Path("families").glob("*.txt")}
people, fams = {}, {}
facts_by_person = {}          # id -> {file: [facts]}

def check_fact(f, where, x, allowed):
    if x.get("type") not in allowed: err(f, f"{where}: bad type {x.get('type')}")
    if "date" in x and not DATE.match(x["date"]): err(f, f"{where}: bad date {x['date']!r}")
    if x.get("kind") not in {"F", "R", "Q", "I"}: err(f, f"{where}: bad kind {x.get('kind')}")
    cite = x.get("cite", [])
    if not isinstance(cite, list): err(f, f"{where}: cite must be a list")
    elif not cite and x.get("kind") != "I": err(f, f"{where}: no pages cited")
    for c in cite if isinstance(cite, list) else []:
        if not PAGE.match(c): err(f, f"{where}: bad page {c!r}")
    if x.get("record") and x["record"] not in records: err(f, f"{where}: no record file {x['record']}")
    if x.get("type") in ("OCCU", "RELI", "EVEN") and not x.get("value"): err(f, f"{where}: {x['type']} needs a value")
    extra = set(x) - {"type", "date", "place", "value", "kind", "cite", "record", "note"}
    if extra: err(f, f"{where}: unknown keys {sorted(extra)}")
    if x.get("type") in VITAL and GUESS.search(x.get("note", "")):
        warn(f, f"{where}: {x['type']} note sounds like a guess; should it be an EVEN \"Possible ...\"?")

for p in sorted(pathlib.Path("data").glob("*.json")):
    try: d = json.loads(p.read_text())
    except Exception as e: err(p.name, f"not JSON: {e}"); continue
    if d.get("sheet") != p.stem: err(p.name, "sheet does not match file name")
    if p.stem not in sheets: err(p.name, "no families/ sheet of that name")
    for i, x in enumerate(d.get("people", [])):
        w = f"person {x.get('id', i)}"
        if not ID.match(str(x.get("id", ""))): err(p.name, f"{w}: bad id")
        if x.get("sex") not in {"M", "F", "U"}: err(p.name, f"{w}: bad sex")
        if x.get("living") not in {"no", "yes", "check"}: err(p.name, f"{w}: bad living")
        for k in ("given", "surname"):
            if not isinstance(x.get(k), str): err(p.name, f"{w}: {k} missing")
        for j, fct in enumerate(x.get("facts", [])): check_fact(p.name, f"{w} fact {j}", fct, FACTS - {"MARR", "DIV"})
        prev = people.get(x.get("id"))
        if prev and (prev["sex"] != x.get("sex") or prev["surname"] != x.get("surname")):
            err(p.name, f"{w}: sex/surname differ from {prev['file']}")
        people.setdefault(x.get("id"), {"sex": x.get("sex"), "surname": x.get("surname"), "file": p.name})
        facts_by_person.setdefault(x.get("id"), {}).setdefault(p.name, []).extend(x.get("facts", []))
    for i, x in enumerate(d.get("families", [])):
        w = f"family {x.get('id', i)}"
        if not ID.match(str(x.get("id", ""))) or not str(x.get("id", "")).startswith("fam-"): err(p.name, f"{w}: bad id")
        fams.setdefault(x.get("id"), []).append((p.name, x))
        for j, fct in enumerate(x.get("facts", [])): check_fact(p.name, f"{w} fact {j}", fct, {"MARR", "DIV"})

for fid, uses in fams.items():
    for fname, x in uses:
        for role in ("husband", "wife"):
            if x.get(role) and x[role] not in people: err(fname, f"family {fid}: {role} {x[role]} not defined")
        for c in x.get("children", []):
            if c not in people: err(fname, f"family {fid}: child {c} not defined")
    if len({(x.get("husband"), x.get("wife")) for _, x in uses}) > 1: err(fid, "defined with different couples")

# Near-duplicates: same person, same type and kind, same date or same
# pages, but not identical, in two different files.
for pid, byfile in facts_by_person.items():
    for (fa, la), (fb, lb) in itertools.combinations(byfile.items(), 2):
        for a in la:
            if a in lb: continue
            for b in lb:
                if b in la or a["type"] != b["type"] or a["kind"] != b["kind"]: continue
                if (a.get("date") and a.get("date") == b.get("date")) or a.get("cite") == b.get("cite"):
                    warn(pid, f"{a['type']} [{a['kind']}] {a.get('date', '')} differs between {fa} and {fb}; "
                              f"make them identical if they are the same event")

for e in errors: print(e)
for w in warnings: print(w)
print(f"{len(people)} people, {len(fams)} families, {len(errors)} problems, {len(warnings)} warnings")
sys.exit(1 if errors else 0)
