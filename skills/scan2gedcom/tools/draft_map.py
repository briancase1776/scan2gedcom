# Draft the contents map. For each line of contents/pN.txt, find
# the PDF page(s) its book page(s) point to (searching near the page
# for the first person's name, since typed and handwritten page numbers
# differ) and the person in data/ that line names:
#   - a line under another (3.2 under 2.1) names a child of the line
#     above it, so its person is looked for among that person's children;
#   - otherwise, a person of that name who cites one of the pages;
#   - several fits: the one married to the spouse the line names.
# Names are compared loosely, since a typed list has typing slips. Writes <outdir>/draft.txt (one line per contents line:
# ref | number | book pages | PDF pages | id or "-" | text) and
# <outdir>/review.txt (lines it could not settle, with the candidates).
# A first draft only: the map itself is checked by hand.
#   python3 -I tools/draft_map.py . <outdir>
import re, json, pathlib, collections, sys, difflib
R = pathlib.Path(sys.argv[1]); OUT = pathlib.Path(sys.argv[2])
PDFRE = re.compile(r"PDF (\d{1,4})(?:-(\d{1,4}))?")
def pages(o):
    s = set()
    for a, b in PDFRE.findall(json.dumps(o, ensure_ascii=False)): s.update(range(int(a), int(b or a) + 1))
    return s
def norm(s): return re.sub(r"[^a-z]", "", s.casefold())

# transcription: book page labels -> PDF pages, and page bodies
lab = collections.defaultdict(set); body = {}
for f in sorted((R / "transcription").glob("p[0-9]*.txt")):
    pdf = int(f.stem[1:]); h, _, b = f.read_text().partition("\n" + "-" * 64 + "\n")
    body[pdf] = b
    bp = re.search(r"^Book page:\s*(.*)$", h, re.M).group(1)
    for l in re.findall(r"\b(\d{1,3})[A-Za-z]?\b", bp): lab[int(l)].add(pdf)

# people, and who is married to whom and whose child
people, spouses, kids = {}, collections.defaultdict(set), collections.defaultdict(set)
data = [json.loads(p.read_text()) for p in sorted((R / "data").glob("*.json"))]
for x in (x for d in data for x in d.get("people", [])):
    c = people.setdefault(x["id"], {"given": x.get("given", ""), "surname": x.get("surname", ""), "sex": x.get("sex", "U"), "aka": [], "pages": set()})
    c["aka"] += x.get("aka", []); c["pages"] |= pages(x)
for f in (f for d in data for f in d.get("families", [])):
    h, w = f.get("husband"), f.get("wife")
    for a, b in ((h, w), (w, h)):
        if a in people:
            if b: spouses[a].add(b)
            kids[a] |= set(f.get("children", []))
            people[a]["pages"] |= pages([f.get("facts", []), f.get("note", "")])

def forms(pid):   # (first given name, surname) the person goes by
    x = people[pid]
    out = [(norm(x["given"].split(" ")[0]) if x["given"] else "", norm(x["surname"]))]
    for a in x["aka"]:
        w = [v for v in re.split(r"[\s,]+", re.sub(r"\([^)]*\)|\"", " ", a)) if v]
        if len(w) >= 2: out.append((norm(w[0]), norm(w[-1])))
    return out
def like(a, b):
    return a == b or (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a))) \
        or difflib.SequenceMatcher(None, a, b).ratio() >= 0.8
UNNAMED = {"baby", "son", "dau", "daughter", "infant", ""}
def fits(pid, given, sur, sex="U"):
    if given in UNNAMED:   # "Baby son", "3.17?": a person with no name
        return (not people[pid]["given"] or norm(people[pid]["given"]) in ("baby", "infant", "babyboy", "babygirl")) \
            and sex in ("U", people[pid]["sex"])
    return any(g and like(g, given) and (not sur or not s or like(s, sur)) for g, s in forms(pid))
def married_to(pid, words):   # how many of the spouse words fit a spouse on record
    return max([sum(any((g and like(g, w)) or (s and like(s, w)) for g, s in forms(sp)) for w in words)
                for sp in spouses[pid] if sp in people] or [0])

def parse(text):   # first person's (given, surname), and the words naming spouses
    t = re.sub(r"^\d+(\.\d+)*\.?\s*", "", text).replace("I&", "&").replace("&I", "&")
    first, rest = (re.split(r" & | and ", t, maxsplit=1, flags=re.I) + [""])[:2]
    first = re.sub(r"\([^)]*\)|\"[^\"]*\"|\[[^\]]*\]", " ", first)
    w = [norm(v) for v in re.split(r"[\s,]+", first) if v and norm(v) not in ("jr", "sr", "")]
    own = {w[-1]} if len(w) >= 2 else set()   # the first person's surname says nothing about the spouse
    sp = [norm(v) for v in re.split(r"[\s,()\"]+", rest) if len(norm(v)) >= 3
          and norm(v) not in {"nd", "rd", "son", "dau", "of", "and", "acousin", "cousin", "see", "below"} | own]
    given = w[0] if w else ""
    if given == "baby" or not w: given = "baby"
    return given, (w[-1] if len(w) >= 2 else ""), sp

rows = []
for cp in sorted(int(p.stem[1:]) for p in (R / "contents").glob("p[0-9]*.txt")):
    lines = (R / "contents" / f"p{cp}.txt").read_text().split("\n" + "-" * 64 + "\n")[1].split("\n")
    for ln, line in enumerate(lines, 1):
        s = line.strip()
        if not s or s in ("Table of Contents", str(cp)): continue
        m = re.match(r"^(.*?\S)\s{2,}([\d ,.a\-]+)$", s)
        text, pg = (m.group(1), m.group(2)) if m else (s, "")
        num = (re.match(r"^(\d+(?:\.\d+)*\.?)\s", text) or [None, ""])[1]
        rows.append({"ref": f"c{cp}:{ln}", "num": num, "pg": pg, "text": text,
                     "gen": int(num.split(".")[0]) if num else 0})

out, review, stack = [], [], {}
for r in rows:
    if r["text"].startswith("Part "):
        stack = {}; out.append((r["ref"], r["num"], r["pg"], "", "part", r["text"])); continue
    books = [int(x) for x in re.findall(r"\d+", r["pg"])]
    m = re.search(r"(\d+)-(\d)$", r["pg"])
    if m: books.append(int(m.group(1)[:-1] + m.group(2)))   # "328-9"
    given, sur, sp = parse(r["text"])
    sex = "M" if re.search(r"\b(son|boy)\b", r["text"], re.I) else "F" if re.search(r"\b(dau|daughter|girl)\b", r["text"], re.I) else "U"
    cand = set()
    for bk in books:
        for d in (0, -1, 1, -2, 2): cand |= lab.get(bk + d, set())
    near = sorted(p for p in cand if given not in UNNAMED and given in norm(body.get(p, "")))
    pdfs = near or (sorted(lab.get(books[0], set())) if books else [])
    parent = stack.get(r["gen"] - 1)
    pool = [c for c in kids.get(parent, ()) if c in people and fits(c, given, sur, sex)] if parent not in (None, "-") else []
    onpage = [pid for pid in people if fits(pid, given, sur, sex) and people[pid]["pages"] & set(pdfs)]
    pick, why = "-", ""
    for group in ([p for p in pool if p in onpage], pool, onpage):
        if not group: continue
        score = {p: married_to(p, sp) for p in group}
        top = [p for p in group if score[p] == max(score.values())]
        if len(top) == 1 and (not sp or score[top[0]] or not spouses[top[0]]): pick = top[0]
        elif len(top) == 1: why = f"{top[0]} fits, but not the spouse named"
        else: why = f"several: {top[:5]}"
        break
    if pick == "-" and not why: why = "no person of that name" + (f" among {parent}'s children" if parent and parent != "-" else " citing those pages")
    if not near and pick != "-" and people[pick]["pages"] & cand: pdfs = sorted(people[pick]["pages"] & cand)
    r["id"] = pick; stack[r["gen"]] = pick
    for g in [k for k in stack if k > r["gen"]]: del stack[g]
    out.append((r["ref"], r["num"], r["pg"], ",".join(map(str, pdfs)), pick, r["text"]))
    if pick == "-": review.append(f"{r['ref']} {r['text'][:72]} | pdf {pdfs[:4]} | {why}")
OUT.mkdir(exist_ok=True)
(OUT / "draft.txt").write_text("\n".join(" | ".join(x) for x in out) + "\n")
(OUT / "review.txt").write_text("\n".join(review) + "\n")
print(len(out), "lines;", sum(1 for x in out if x[4] not in ("-", "part")), "matched;", len(review), "to review")
