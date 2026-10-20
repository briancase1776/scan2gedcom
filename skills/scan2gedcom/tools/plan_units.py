# Check the work plan (work/units.txt) against the book. For each unit:
# how many numbered entries its pages hold, how many of those are not
# yet in the data (tools/check_coverage.py's list), and which marriages
# the contents map names whose spouse is not yet in the data
# (tools/check_map.py's NOTWED lines) fall on its pages. Then the gaps
# in the plan: pages with entries not in the data that no unit covers,
# and pages two units share. Totals by wave.
#   python3 -I tools/plan_units.py [--gaps]   (--gaps lists each entry)
import re, pathlib, subprocess, sys, collections
def rng(s):
    out = set()
    for part in s.split(","):
        a, _, b = part.strip().partition("-"); out.update(range(int(a), int(b or a) + 1))
    return out
if not pathlib.Path("work/units.txt").exists():
    print("no work/units.txt: no plan to check"); sys.exit(0)
units = []
for line in pathlib.Path("work/units.txt").read_text().split("\n"):
    if line.count(" | ") == 4 and not line.startswith("#"):
        u, wave, pages, root, what = line.split(" | ")
        units.append((u, wave, rng(pages), root, what))
cov = subprocess.run([sys.executable, "-I", "tools/check_coverage.py"], capture_output=True, text=True).stdout
missing = collections.defaultdict(list)
for m in re.finditer(r"^PDF (\d+): (\S.*)\n    (.*)$", cov, re.M):
    missing[int(m.group(1))].append(m.group(2))
mp = subprocess.run([sys.executable, "-I", "tools/check_map.py"], capture_output=True, text=True).stdout
ref_pdf = {}
for line in pathlib.Path("contents/map.txt").read_text().split("\n"):
    f = line.split(" | ")
    if len(f) == 6 and f[3] != "-": ref_pdf[f[0]] = {int(x) for x in f[3].split(",")}
notwed = [(m.group(1), m.group(2)) for m in re.finditer(r"^NOTWED\s+(c\d:\d+): no spouse of (\S+)", mp, re.M)]
entries = collections.Counter()
for f in pathlib.Path("transcription").glob("p[0-9]*.txt"):
    b = f.read_text().partition("\n" + "-" * 64 + "\n")[2]
    entries[int(f.stem[1:])] = sum(1 for l in b.split("\n") if re.match(r"^_?\d{1,2}_?\.\s", l))
owner = collections.defaultdict(list)
for u, wave, pages, root, what in units:
    for p in pages: owner[p].append(u)
waves = collections.defaultdict(lambda: [0, 0, 0])
print(f"{'unit':18} wave  entries  missing  spouses")
for u, wave, pages, root, what in units:
    e = sum(entries[p] for p in pages); m = sum(len(missing[p]) for p in pages)
    s = [pid for ref, pid in notwed if ref_pdf.get(ref, set()) & pages]
    waves[wave][0] += e; waves[wave][1] += m; waves[wave][2] += len(s)
    print(f"{u:18} {wave:4} {e:8} {m:8} {len(s):8}")
print("wave totals (entries / missing / spouses): " + "; ".join(f"{w} {v[0]}/{v[1]}/{v[2]}" for w, v in sorted(waves.items())))
gaps = sorted(p for p in missing if p not in owner)
shared = sorted(p for p, us in owner.items() if len(us) > 1)
lost = [(ref, pid) for ref, pid in notwed if not any(ref_pdf.get(ref, set()) & u[2] for u in units)]
print(f"pages with entries not in the data that no unit covers: {len(gaps)} pages, {sum(len(missing[p]) for p in gaps)} entries")
print("  " + ", ".join(map(str, gaps)))
print(f"pages two units share: {', '.join(f'{p} ({'+'.join(owner[p])})' for p in shared) or 'none'}")
print(f"spouse gaps no unit covers: {len(lost)}" + "".join(f"\n  {ref} {pid}" for ref, pid in lost))
if "--gaps" in sys.argv:
    for p in gaps:
        for e in missing[p]: print(f"  PDF {p}: {e}")
