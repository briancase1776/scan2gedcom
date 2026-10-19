# Read a GEDCOM file back with an independent parser (ged4py) and check
# that every link resolves both ways, that each PEDI on a FAMC link is a
# GEDCOM 5.5.1 value, and that each _FREL / _MREL under a CHIL (the
# per-parent link Ancestry reads) has a value the builder writes and a
# parent to apply to.
#   python3 -m venv <scratch>/gv && <scratch>/gv/bin/pip install ged4py
#   <scratch>/gv/bin/python3 -I tools/check_gedcom.py gedcom/<name>.ged
import sys
from ged4py.parser import GedcomReader

errors = []
with GedcomReader(sys.argv[1]) as g:
    indi = {r.xref_id: r for r in g.records0("INDI")}
    fam = {r.xref_id: r for r in g.records0("FAM")}
    sour = {r.xref_id: r for r in g.records0("SOUR")}

    def ptr(rec, tag):
        return [s.value for s in rec.sub_records if s.tag == tag]

    for x, r in indi.items():
        for f in ptr(r, "FAMC"):
            if f not in fam or x not in ptr(fam[f], "CHIL"): errors.append(f"{x}: FAMC {f} not matched by CHIL")
        for f in ptr(r, "FAMS"):
            if f not in fam or x not in ptr(fam[f], "HUSB") + ptr(fam[f], "WIFE"):
                errors.append(f"{x}: FAMS {f} not matched by HUSB/WIFE")
        for ev in r.sub_records:
            for s in ev.sub_records:
                if s.tag == "SOUR" and s.value not in sour: errors.append(f"{x}: {ev.tag} cites missing {s.value}")
                if ev.tag == "FAMC" and s.tag == "PEDI" and s.value not in ("adopted", "birth", "foster", "sealing"):
                    errors.append(f"{x}: FAMC {ev.value} has PEDI {s.value!r}")
    for x, r in fam.items():
        for c in ptr(r, "CHIL"):
            if c not in indi or x not in ptr(indi[c], "FAMC"): errors.append(f"{x}: CHIL {c} not matched by FAMC")
        for s in r.sub_records:
            for t in s.sub_records if s.tag == "CHIL" else []:
                parent = {"_FREL": "HUSB", "_MREL": "WIFE"}.get(t.tag)
                if not parent: continue
                if t.value not in ("Natural", "Step", "Adopted"): errors.append(f"{x}: CHIL {s.value} {t.tag} {t.value!r}")
                if t.value != "Natural" and not ptr(r, parent):
                    errors.append(f"{x}: CHIL {s.value} {t.tag} {t.value} but no {parent}")
        for t in ("HUSB", "WIFE"):
            for s in ptr(r, t):
                if s not in indi or x not in ptr(indi[s], "FAMS"): errors.append(f"{x}: {t} {s} not matched by FAMS")

    private = sum(1 for r in indi.values() if r.sub_tag("RESN"))
    links = [s for r in indi.values() for s in r.sub_records if s.tag == "FAMC"]
    adopted = sum(1 for s in links if any(t.tag == "PEDI" and t.value == "adopted" for t in s.sub_records))
    noted = sum(1 for s in links if any(t.tag == "NOTE" for t in s.sub_records))
    step = sum(1 for r in fam.values() for s in r.sub_records if s.tag == "CHIL"
               for t in s.sub_records if t.tag in ("_FREL", "_MREL") and t.value == "Step")
    for e in errors: print(e)
    print(f"{len(indi)} INDI, {len(fam)} FAM, {len(sour)} SOUR, {private} marked RESN privacy, "
          f"{adopted} adopted, {step} step and {noted} noted child links, {len(errors)} problems")
sys.exit(1 if errors else 0)
