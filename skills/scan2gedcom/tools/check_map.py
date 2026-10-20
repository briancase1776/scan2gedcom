# Check contents/map.txt against the contents list and the data, the way
# a directory index is checked against its directory.
# Blocking:
#   NOENTRY   a line of the contents list has no line in the map
#   ORPHAN    a map line names a contents line that isn't there, or its
#             text differs from it
#   NOID      an id that is not a person in data/
#   NOPAGE    a PDF page with no transcription/pNNN.txt
# Warnings (worth a look, not always wrong):
#   NOTCITED  the person cites none of the line's PDF pages
#   NOTCHILD  the person is not a child of the person on the line above
#   NOTWED    the line names a spouse, and none of the person's spouses
#             in the data has a name the line gives
# Then a summary: lines mapped, "-" lines (people not in the data yet),
# and which mapped people have a family sheet.
#   python3 -I tools/check_map.py [--todo]   (--todo lists the "-" lines)
import re, json, pathlib, sys
RULE = "\n" + "-" * 64 + "\n"
if not pathlib.Path("contents/map.txt").exists():
    print("no contents/map.txt: this book has no contents list mapped"); sys.exit(0)
contents = {}
for p in sorted(pathlib.Path("contents").glob("p[0-9]*.txt"), key=lambda p: int(p.stem[1:])):
    for i, line in enumerate(p.read_text().split(RULE, 1)[1].split("\n"), 1):
        s = line.strip()
        if s and s not in ("Table of Contents", p.stem[1:]):
            contents[f"c{p.stem[1:]}:{i}"] = re.sub(r"\s{2,}[\d ,.a\-]+$", "", s)
people, spouses, kids = {}, {}, {}
for p in sorted(pathlib.Path("data").glob("*.json")):
    d = json.loads(p.read_text())
    for x in d.get("people", []):
        people.setdefault(x["id"], set()).update(int(a) for a, b in re.findall(r"PDF (\d+)(?:-(\d+))?", json.dumps(x)))
    for f in d.get("families", []):
        h, w = f.get("husband"), f.get("wife")
        for a, b in ((h, w), (w, h)):
            if a:
                spouses.setdefault(a, set()).add(b)
                kids.setdefault(a, set()).update(f.get("children", []))
                people.setdefault(a, set()).update(int(x) for x in re.findall(r"PDF (\d+)", json.dumps([f.get("facts", []), f.get("note", "")])))
names, surnames = {}, {}
for p in sorted(pathlib.Path("data").glob("*.json")):
    for x in json.loads(p.read_text()).get("people", []):
        surnames[x["id"]] = {w.casefold() for w in re.findall(r"[A-Za-z]{3,}", x.get("surname", ""))}
        names.setdefault(x["id"], set()).update(w.casefold() for n in [x.get("given", ""), x.get("surname", "")] + x.get("aka", []) for w in re.findall(r"[A-Za-z]{3,}", n))
pdfs = {int(p.stem[1:]) for p in pathlib.Path("transcription").glob("p[0-9]*.txt")}
block, warn, seen, rows = [], [], set(), []
for n, line in enumerate(pathlib.Path("contents/map.txt").read_text().split("\n"), 1):
    if not line.strip() or line.startswith(("#", "MAP ")): continue
    f = line.split(" | ")
    if len(f) != 6: block.append(f"BADLINE   map line {n}: needs 6 fields"); continue
    ref, num, book, pdf, pid, text = f
    seen.add(ref)
    if contents.get(ref) != text: block.append(f"ORPHAN    {ref}: \"{text[:50]}\" is not that line of the contents ({contents.get(ref, 'no such line')[:50]!r})")
    pages = [int(x) for x in pdf.split(",")] if pdf != "-" else []
    for x in pages:
        if x not in pdfs: block.append(f"NOPAGE    {ref}: PDF {x}")
    if pid not in ("-", "(group)", "(part)") and pid not in people: block.append(f"NOID      {ref}: {pid}")
    rows.append((ref, num, pages, pid, text))
for ref in contents:
    if ref not in seen: block.append(f"NOENTRY   {ref}: {contents[ref][:60]}")
stack = {}
for ref, num, pages, pid, text in rows:
    if pid == "(part)": stack = {}; continue
    gen = int(num.split(".")[0]) if num != "-" else 0
    up = stack.get(gen - 1)
    if pid in people:
        if pages and not people[pid] & set(pages): warn.append(f"NOTCITED  {ref}: {pid} cites none of PDF {','.join(map(str, pages))}")
        if up in people and pid not in kids.get(up, ()): warn.append(f"NOTCHILD  {ref}: {pid} is not a child of {up} in the data")
        said = {w.casefold() for w in re.findall(r"[A-Za-z]{3,}", re.split(r"&|\band\b", text.replace("I&", "&").replace("&I", "&"), maxsplit=1, flags=re.I)[-1])} - {"son", "dau", "and", "see", "below", "cousin"} - surnames.get(pid, set())
        if "&" in text or " and " in text.casefold():
            wed = [s for s in spouses.get(pid, ()) if s]
            if not any(names.get(s, set()) & said for s in wed): warn.append(f"NOTWED    {ref}: no spouse of {pid} in the data is named on the line")
    stack[gen] = pid
    for g in [k for k in stack if k > gen]: del stack[g]
todo = [r for r in rows if r[3] == "-"]
sheets = {p.stem for p in pathlib.Path("families").glob("*.txt")}
mapped = [r for r in rows if r[3] in people]
for m in block + warn: print(m)
print(f"{len(rows)} lines: {len(mapped)} people in the data ({sum(r[3] in sheets for r in mapped)} with their own sheet), "
      f"{len(todo)} not in the data yet; {len(block)} problems, {len(warn)} warnings")
if "--todo" in sys.argv:
    for ref, num, pages, pid, text in todo: print(f"  {ref:7} {text[:75]}")
sys.exit(1 if block else 0)
