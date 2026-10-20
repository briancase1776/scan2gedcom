# Rebuild a scanner PDF that was cut off before its end: keep every
# complete object, add back the last page object if it was lost, then
# write the page tree, catalog, xref table and trailer the file never got.
# For the simple layout these scans use (one image, one content stream
# and one page object per page, page tree as object 4, written last).
# Page images are copied byte for byte; nothing is re-encoded.
#   python3 -I tools/repair_pdf.py <cut-off.pdf> <repaired.pdf>
import sys, re
src, dst = sys.argv[1], sys.argv[2]
b = open(src, "rb").read()
body = b[:b.rfind(b"endobj") + len(b"endobj")] + b"\r"
objs = {}
for m in re.finditer(rb"(?:^|[\r\n])(\d+) 0 obj", body):
    objs[int(m.group(1))] = m.start(1)
def head(n, k=200): return body[objs[n]:objs[n] + k]
pages = sorted(n for n in objs if re.match(rb"\d+ 0 obj\s*<<\s*/Type /Page\b", head(n)))
images = sorted(n for n in objs if b"/Subtype /Image" in head(n))
contents = sorted(n for n in objs if re.match(rb"\d+ 0 obj\s*<< /Length \d+ \s*>>\s*stream\s*q ", head(n)))
assert pages and 4 not in objs, "not the expected layout"
for n in images:   # each image must be a whole JPEG
    m = re.search(rb"/Length (\d+).*?stream\r?\n?", head(n, 400), re.S)
    s = objs[n] + m.end(); data = body[s:s + int(m.group(1))]
    assert data[:2] == b"\xff\xd8" and data.rstrip(b"\r\n")[-2:] == b"\xff\xd9", f"image {n} is cut off"
extra, nxt = [], max(objs) + 1
if len(images) == len(contents) == len(pages) + 1:   # the last page object was lost
    im, ct = images[-1], contents[-1]
    name = re.search(rb"/Name /(\w+)", head(im)).group(1).decode()
    last = head(pages[-1], 400).decode("latin-1")
    box = re.search(r"/MediaBox \[[^\]]*\]", last).group(0)
    rot = re.search(r"/Rotate \d+", last).group(0)
    extra.append((nxt, f"<<\r/Type /Page\r{box}\r/Parent 4 0 R \r{rot} /Resources <<\r/ProcSet [/PDF /ImageC /ImageB /ImageI]\r/XObject <<\r/{name} {im} 0 R\r >>\r >>\r/Contents [ {ct} 0 R\r]\r>>"))
    pages.append(nxt); nxt += 1
extra.append((4, "<<\r/Type /Pages\r/Kids [ " + " ".join(f"{p} 0 R" for p in pages) + f" ]\r/Count {len(pages)}\r>>"))
extra.append((nxt, "<<\r/Type /Catalog\r/Pages 4 0 R  \r>>")); cat = nxt
out = bytearray(body)
for n, d in extra:
    objs[n] = len(out); out += f"{n} 0 obj\r{d}\rendobj\r".encode()
size, x = max(objs) + 1, len(out)
out += f"xref\r\n0 {size}\r\n".encode()
out += b"".join((f"{objs[n]:010d} 00000 n\r\n" if n in objs else "0000000000 65535 f\r\n").encode() for n in range(size))
out += f"trailer\r\n<< /Size {size} /Root {cat} 0 R >>\r\nstartxref\r\n{x}\r\n%%EOF\r\n".encode()
open(dst, "wb").write(out)
print(f"{dst}: {len(pages)} pages, {len(images)} whole images")
