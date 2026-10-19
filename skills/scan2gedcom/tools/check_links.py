# Check the rendered sheets and records.
# Run from the project root:  python3 -I tools/check_links.py
#   - every families/<id>.txt and records/<id>.txt a file names exists
#   - each file's "Id:" line matches its file name
#   - each sheet's parents' sheet names it back
#   - each lineage file (families/line-<sheet id>.txt) names its root
#     sheet on a "Root sheet:" line, and the root sheet names it back
#   - no rendered file is older than its template (render again)
#   - no @@QUOTE / @@PAGE line is left unrendered
# and warns (without failing) when a sheet or lineage file cites a
# record, in its text or its data file, but is not on the record's
# "Used on:" line.
import json, pathlib, re, sys

LINK = re.compile(r"\b(families|records)/([a-z0-9-]+)\.txt")
errors, warnings = [], []
files = sorted(pathlib.Path("families").glob("*.txt")) + sorted(pathlib.Path("records").glob("*.txt"))
text = {p: p.read_text() for p in files}

for p, s in text.items():
    m = re.search(r"^Id:\s*(\S+)", s, re.M)
    if not m: errors.append(f"{p}: no Id: line")
    elif m.group(1) != p.stem: errors.append(f"{p}: Id {m.group(1)} does not match the file name")
    for kind, rid in set(LINK.findall(s)):
        if not pathlib.Path(kind, rid + ".txt").exists(): errors.append(f"{p}: names {kind}/{rid}.txt, which does not exist")
    if re.search(r"^@@(QUOTE|PAGE) ", s, re.M): errors.append(f"{p}: unrendered @@ line")
    t = pathlib.Path("tools/templates") / p
    if not t.exists(): errors.append(f"{p}: no template {t}")
    elif t.stat().st_mtime > p.stat().st_mtime: errors.append(f"{p}: older than its template; render again")

for p, s in text.items():
    if p.parts[0] != "families": continue
    m = re.search(r"^Parents:\s*families/([a-z0-9-]+)\.txt", s, re.M)
    if m:
        parent = pathlib.Path("families", m.group(1) + ".txt")
        if parent in text and f"families/{p.stem}.txt" not in text[parent]:
            errors.append(f"{parent}: does not link to its child's sheet families/{p.stem}.txt")
    if p.stem.startswith("line-"):
        m = re.search(r"^Root sheet:\s*families/([a-z0-9-]+)\.txt", s, re.M)
        root = pathlib.Path("families", p.stem[5:] + ".txt")
        if not m or m.group(1) != p.stem[5:]: errors.append(f"{p}: needs a line \"Root sheet: {root}\"")
        elif root in text and f"families/{p.stem}.txt" not in text[root]:
            errors.append(f"{root}: does not link to its lineage file families/{p.stem}.txt")

# Records each sheet or lineage file cites, from its text and its data.
cites = {}
for p, s in text.items():
    if p.parts[0] == "families":
        for kind, rid in LINK.findall(s):
            if kind == "records": cites.setdefault(rid, set()).add(p.stem)
for p in sorted(pathlib.Path("data").glob("*.json")):
    try: d = json.loads(p.read_text())
    except ValueError: continue          # check_data.py reports it
    for x in d.get("people", []) + d.get("families", []):
        for f in x.get("facts", []):
            if f.get("record"): cites.setdefault(f["record"], set()).add(p.stem)
for rid, users in sorted(cites.items()):
    r = pathlib.Path("records", rid + ".txt")
    if r not in text: continue
    m = re.search(r"^Used on:.*(?:\n[ \t]+\S.*)*", text[r], re.M)
    listed = set(re.findall(r"families/([a-z0-9-]+)\.txt", m.group(0))) if m else set()
    for u in sorted(users - listed):
        warnings.append(f"warning: {r}: cited by families/{u}.txt, which is not on its Used on: line")

for e in errors: print(e)
for w in warnings: print(w)
print(f"{len(files)} files, {len(errors)} problems, {len(warnings)} warnings")
sys.exit(1 if errors else 0)
