# Build one GEDCOM 5.5.1 file from data/*.json (see tools/DATA-FORMAT.txt),
# sheets and lineage files alike. A person's or a family's "note"
# becomes a NOTE; a family's "adopted" children get PEDI adopted on
# their FAMC link, its "step" children a NOTE there naming the
# step-parent, and its "inferred" children a NOTE saying the placement
# was worked out or only guessed at.
# Under the FAM's CHIL line, step and adopted children also get the
# per-parent tags Ancestry and Family Tree Maker read (_FREL, _MREL).
# Run from the project root:  python3 -I tools/build_gedcom.py
# Settings come from scan2gedcom.json in the project root:
#   title, author, author_short (optional, e.g. "Ada"), source_note,
#   project (a short name), gedcom (output path)
import json, pathlib, re

cfg = json.loads(pathlib.Path("scan2gedcom.json").read_text())
AUTHOR = cfg.get("author_short") or "the author"
POSS = f"{AUTHOR}'s"
KIND = {"F": f"[F] {AUTHOR} says it",
        "R": f"[R] a record {AUTHOR} copied or abstracted",
        "Q": f"[Q] someone {AUTHOR} quotes",
        "I": "[I] worked out on the sheet, not stated in the book"}
LIVING_RANK = {"no": 0, "check": 1, "yes": 2}
REFN_TYPE = re.sub(r"[^a-z0-9]+", "-", cfg["project"].lower()).strip("-") + "-sheets"

people, families = {}, {}
for p in sorted(pathlib.Path("data").glob("*.json")):
    d = json.loads(p.read_text())
    for x in d["people"]:
        cur = people.setdefault(x["id"], {**x, "facts": [], "aka": [], "notes": []})
        for a in x.get("aka", []):
            if a not in cur["aka"]: cur["aka"].append(a)
        for f in x.get("facts", []):
            if f not in cur["facts"]: cur["facts"].append(f)
        if x.get("note") and x["note"] not in cur["notes"]: cur["notes"].append(x["note"])
        if LIVING_RANK[x["living"]] > LIVING_RANK[cur["living"]]: cur["living"] = x["living"]
    for x in d["families"]:
        cur = families.setdefault(x["id"], {**x, "children": [], "facts": [], "adopted": [], "inferred": [], "step": {},
                                            "notes": []})
        if x.get("note") and x["note"] not in cur["notes"]: cur["notes"].append(x["note"])
        for k in ("children", "adopted", "inferred"):
            for c in x.get(k, []):
                if c not in cur[k]: cur[k].append(c)
        cur["step"].update(x.get("step", {}))
        for f in x.get("facts", []):
            if f not in cur["facts"]: cur["facts"].append(f)

def record_info(rid):
    lines = pathlib.Path("records", rid + ".txt").read_text().split("\n")
    title = []
    for l in lines[1:]:
        if re.match(r"^[A-Z][a-z]+( [a-z]+)?:", l): break
        title.append(l.strip())
    inbook = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("In book:")), "")
    return " ".join(t for t in title if t), inbook

recs = sorted({f["record"] for x in list(people.values()) + list(families.values())
               for f in x["facts"] if f.get("record")})
src = {"book": "@S1@"}
for n, r in enumerate(recs, 2): src[r] = f"@S{n}@"
ind = {pid: f"@I{n}@" for n, pid in enumerate(sorted(people), 1)}
fam = {fid: f"@F{n}@" for n, fid in enumerate(sorted(families), 1)}

out = []
def line(level, tag, value=""):
    value = str(value)
    parts = value.split("\n")
    for k, part in enumerate(parts):
        chunks = [part[i:i + 200] for i in range(0, len(part), 200)] or [""]
        for m, chunk in enumerate(chunks):
            if k == 0 and m == 0: out.append(f"{level} {tag} {chunk}".rstrip())
            else: out.append(f"{level + 1} {'CONC' if m else 'CONT'} {chunk}".rstrip())

def fact(f, level=1):
    t = f["type"]
    if t in ("OCCU", "RELI"): line(level, t, f.get("value", ""))
    else: line(level, t)
    if t == "EVEN": line(level + 1, "TYPE", f.get("value", "")[:90])
    if f.get("date"): line(level + 1, "DATE", f["date"])
    if f.get("place"): line(level + 1, "PLAC", f["place"])
    if f.get("note"): line(level + 1, "NOTE", f["note"])
    if f.get("cite"):
        line(level + 1, "SOUR", src["book"])
        line(level + 2, "PAGE", ", ".join(f["cite"]))
        line(level + 2, "NOTE", KIND[f["kind"]])
    if f.get("record"):
        line(level + 1, "SOUR", src[f["record"]])
        line(level + 2, "PAGE", record_info(f["record"])[1])

line(0, "HEAD")
line(1, "SOUR", "SCAN2GEDCOM")
line(2, "NAME", f"{cfg['project']} family group sheets")
line(1, "GEDC"); line(2, "VERS", "5.5.1"); line(2, "FORM", "LINEAGE-LINKED")
line(1, "CHAR", "UTF-8")
line(1, "SUBM", "@U1@")
line(1, "NOTE", f"Built from the family group sheets and lineage files drawn from \"{cfg['title']}\" by "
     f"{cfg['author']}. Each person's REFN is the id used on the sheets. Where the book "
     "disagrees with itself, each reading is a separate event with its own page citation. "
     "People marked RESN privacy may be living.")
line(0, "@U1@ SUBM"); line(1, "NAME", f"{cfg['project']} transcription project")

for pid in sorted(people):
    x = people[pid]
    line(0, f"{ind[pid]} INDI")
    line(1, "NAME", f"{x['given']} /{x['surname']}/".strip())
    if x["given"]: line(2, "GIVN", x["given"])
    if x["surname"]: line(2, "SURN", x["surname"])
    for a in x["aka"]:
        line(1, "NAME", a); line(2, "TYPE", "aka")
    line(1, "SEX", x["sex"])
    if x["living"] != "no": line(1, "RESN", "privacy")
    line(1, "REFN", pid); line(2, "TYPE", REFN_TYPE)
    for n in x["notes"]: line(1, "NOTE", n)
    for f in x["facts"]: fact(f)
    for fid in sorted(families):
        if pid in families[fid]["children"]:
            line(1, "FAMC", fam[fid])
            if pid in families[fid]["adopted"]: line(2, "PEDI", "adopted")
            if pid in families[fid]["step"]:
                line(2, "NOTE", f"Step-child of the {families[fid]['step'][pid]} in this family; "
                                "the child of the other parent")
            if pid in families[fid]["inferred"]:
                line(2, "NOTE", "Placement in this family worked out [I] or only guessed at in the book "
                                "(one or both parents); see the sheet")
    for fid in sorted(families):
        if pid in (families[fid].get("husband"), families[fid].get("wife")): line(1, "FAMS", fam[fid])

for fid in sorted(families):
    x = families[fid]
    line(0, f"{fam[fid]} FAM")
    if x.get("husband"): line(1, "HUSB", ind[x["husband"]])
    if x.get("wife"): line(1, "WIFE", ind[x["wife"]])
    for c in x["children"]:
        line(1, "CHIL", ind[c])
        # Ancestry / Family Tree Maker: the link to each parent the family has
        if c in x["step"]:
            if x.get("husband"): line(2, "_FREL", "Step" if x["step"][c] == "husband" else "Natural")
            if x.get("wife"): line(2, "_MREL", "Step" if x["step"][c] == "wife" else "Natural")
        elif c in x["adopted"]:
            if x.get("husband"): line(2, "_FREL", "Adopted")
            if x.get("wife"): line(2, "_MREL", "Adopted")
    for f in x["facts"]: fact(f)
    for n in x["notes"]: line(1, "NOTE", n)
    line(1, "REFN", fid)

line(0, f"{src['book']} SOUR")
line(1, "TITL", cfg["title"])
line(1, "AUTH", cfg["author"])
line(1, "NOTE", cfg.get("source_note", "Scanned book. Pages are cited by PDF page of the scan, "
     "as in the transcription."))
for r in recs:
    title, inbook = record_info(r)
    line(0, f"{src[r]} SOUR")
    line(1, "TITL", title)
    line(1, "NOTE", f"Known only from {POSS} copy or abstract in the book ({inbook}). "
         f"Record file: records/{r}.txt")
line(0, "TRLR")

dst = pathlib.Path(cfg["gedcom"])
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"{dst}: {len(people)} people, {len(families)} families, "
      f"{len(recs) + 1} sources, {len(out)} lines")
