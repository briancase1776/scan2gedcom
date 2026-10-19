# Render group-sheet and record templates, pulling every quotation
# verbatim from the transcription files.
#   @@QUOTE pNNN | first-line-start | last-line-start
#   @@PAGE pNNN            (whole page body)
# Run from the project root:
#   python3 -I tools/render.py transcription tools/templates \
#       tools/templates/families/*.txt tools/templates/records/*.txt
# Output goes to families/ and records/; edit the templates, not those.
import sys, pathlib, re
tx = pathlib.Path(sys.argv[1])
def body(p):
    s = (tx / f"{p}.txt").read_text()
    head, sep, b = s.partition("\n" + "-" * 64 + "\n")
    if not sep: sys.exit(f"{p}: no 64-dash rule after the header")
    bp = re.search(r"^Book page:\s*(.*)$", head, re.M).group(1).strip()
    return bp, b.rstrip("\n").split("\n")
def label(p, bp):
    n = int(p[1:])
    return f"PDF {n}" + (f", book page {bp}" if bp != "none" else "")
def quote(p, a, z):
    bp, lines = body(p)
    i = [k for k, l in enumerate(lines) if l.startswith(a)]
    if len(i) != 1: sys.exit(f"{p}: start {a!r} matched {len(i)} lines")
    j = [k for k, l in enumerate(lines) if l.startswith(z) and k >= i[0]]
    if not j: sys.exit(f"{p}: end {z!r} not found")
    return [f"  [{label(p, bp)}]"] + ["    " + l if l else "" for l in lines[i[0]:j[0] + 1]]
def render(src, dst):
    out = []
    for n, line in enumerate(pathlib.Path(src).read_text().split("\n"), 1):
        if line.startswith("@@QUOTE "):
            parts = [x.strip() for x in line[8:].split("|")]
            if len(parts) != 3: sys.exit(f"{src}:{n}: @@QUOTE needs page | start | end, "
                                         f"and neither string may contain '|'")
            out += quote(*parts)
        elif line.startswith("@@PAGE "):
            p = line[7:].strip(); bp, lines = body(p)
            out += [f"  [{label(p, bp)}]"] + ["    " + l if l else "" for l in lines]
        else:
            out.append(line)
    pathlib.Path(dst).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(dst).write_text("\n".join(out).rstrip("\n") + "\n")
for src in sys.argv[3:]:
    rel = pathlib.Path(src).relative_to(sys.argv[2])
    render(src, pathlib.Path(sys.argv[1]).parent / rel)
    print("wrote", rel)
