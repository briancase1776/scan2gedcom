# Check that the data holds every numbered entry in the book: what
# "all" means. For each line of each transcribed page that starts with
# a generation number ("6. Carol Harlan, b. 1941", "_6_. ..."), the
# name at its start must belong to a person in data/*.json who cites
# that page: in one of their facts, a fact or note of a family they
# married in, or their note. Given name and surname are compared;
# middle names, nicknames in quotes or brackets, titles, Jr./Sr. and
# other spellings in "aka" are allowed for. An entry with no name ("an
# infant son") needs a person with no given name citing the page.
# Also lists every page that no data file cites.
# Run from the project root:  python3 -I tools/check_coverage.py
# Settings, "coverage" in scan2gedcom.json:
#   entry_pattern  where an entry starts; the name follows it
#                  (default "^_?\d{1,2}_?\.\s+")
#   skip_pages     PDF page numbers not checked: pages known to be
#                  missing from the scan, as agreed with the user
# Pages whose Kind is only cover or blank are not checked either.
# Exits 1 while anything is listed.
import json, pathlib, re, sys

cfg = pathlib.Path("scan2gedcom.json")
cov = json.loads(cfg.read_text()).get("coverage", {}) if cfg.exists() else {}
ENTRY = re.compile(cov.get("entry_pattern", r"^_?\d{1,2}_?\.\s+"))
SKIP = set(cov.get("skip_pages", []))
PDF = re.compile(r"PDF (\d{1,4})(?:-(\d{1,4}))?")
ASIDE = re.compile(r"\"[^\"]*\"|“[^”]*”|\([^()]*\)|\[[^\[\]]*\]")       # nicknames, (see page 1), [?]
END = re.compile(r"[,;:]| - | (?:b|d|m|md|mar|bur|dau|s)\.| (?:[Bb]orn|[Dd]ied|[Mm]arried)\b| (?=\d)")   # "M." is an initial, "m." married; a date ends a name
DROP = {"jr", "sr", "ii", "iii", "iv", "dr", "rev", "mr", "mrs", "miss", "capt", "col"}
UNNAMED = {"a", "an", "the", "infant", "baby", "son", "daughter", "dau", "child", "boy", "girl",
           "twin", "twins", "unnamed", "stillborn"}

def words(s):
    return [w for w in re.split(r"[^\w']+", ASIDE.sub(" ", s).replace("_", " ").casefold())
            if w.strip("'") and w not in DROP]

def pages(obj):   # every PDF page an object's text names
    out = set()
    for a, b in PDF.findall(json.dumps(obj, ensure_ascii=False)): out.update(range(int(a), int(b or a) + 1))
    return out

# People: their names and the pages they cite, from every data file.
bad, missing, uncited, n_entries, n_pages, data, cited = [], [], [], 0, 0, [], set()
for p in sorted(pathlib.Path("data").glob("*.json")):
    try: data.append(json.loads(p.read_text()))
    except ValueError: bad.append(f"{p}: not JSON; see check_data.py"); continue
    cited |= pages(p.read_text())
people = {}
for x in (x for d in data for x in d.get("people", [])):
    cur = people.setdefault(x["id"], {"given": words(x.get("given", "")), "surname": words(x.get("surname", "")),
                                      "aka": [], "pages": set()})
    cur["aka"] += [words(a) for a in x.get("aka", []) if len(words(a)) >= 2]
    cur["pages"] |= pages(x)
children = set()
SURNAMES = {v for x in people.values() for v in x["surname"]}
for f in (f for d in data for f in d.get("families", [])):
    children.update(f.get("children", []))
    for role in ("husband", "wife"):
        if f.get(role) in people: people[f[role]]["pages"] |= pages([f.get("facts", []), f.get("note", "")])

def named(pid, w, pg):   # does the entry's name, a list of words, fit this person?
    x, rest = people[pid], [v for v in w if v not in UNNAMED]
    if not x["given"] or all(v in UNNAMED for v in x["given"]):   # no name: an unnamed child
        return pid in children and rest in ([], x["surname"])
    forms = [(x["given"][0], x["surname"])] + [(a[0], a[-1:]) for a in x["aka"]]
    if any(w and w[0] == g and s and all(v in w[1:] for v in s) for g, s in forms): return True
    # an entry giving first names only ("7. Carol Ann, b. 1941", "6. Walt
    # m. 2nd ..."): the person's given names, in order, on a page they cite
    # only when the entry names no surname found in the data ("Ann Lomax" is
    # not Ann Harlan); all the given names, or the first few ("Carol", Carol Ann)
    n = min(len(w), len(x["given"]))
    return pg in x["pages"] and n > 0 and w[:n] == x["given"][:n] and not set(w[1:]) & SURNAMES

for f in sorted(pathlib.Path("transcription").glob("p*.txt")):
    if not re.fullmatch(r"p\d+", f.stem): continue
    pg = int(f.stem[1:])
    head, sep, body = f.read_text().partition("\n" + "-" * 64 + "\n")
    if not sep: bad.append(f"{f}: no 64-dash rule after the header"); continue
    kind = re.search(r"^Kind:\s*(.*)$", head, re.M)
    if pg in SKIP or (kind and set(k.strip() for k in kind.group(1).split("+")) <= {"cover", "blank"}): continue
    n_pages += 1
    if pg not in cited: uncited.append(f"PDF {pg}: no data file cites this page")
    for line in body.split("\n"):
        m = ENTRY.match(line)
        if not m: continue
        n_entries += 1
        rest = ASIDE.sub(" ", line[m.end():])
        w = words(END.split(rest, 1)[0])
        who = [pid for pid, x in people.items() if named(pid, w, pg)]
        if any(pg in people[pid]["pages"] for pid in who): continue
        if who: missing.append(f"PDF {pg}: {line.strip()[:60]}\n    {', '.join(who[:3])} has that name, but cites no PDF {pg}")
        else: missing.append(f"PDF {pg}: {line.strip()[:60]}\n    no person of that name in data/")

for m in bad + missing + uncited: print(m)
print(f"{n_pages} pages, {n_entries} numbered entries, {len(missing)} entries not in the data, "
      f"{len(uncited)} pages not cited" + (f", {len(bad)} files unreadable" if bad else ""))
sys.exit(1 if bad or missing or uncited else 0)
