# scan2gedcom

A Claude Code skill for turning a scanned family-history book into a
family tree you can trust, one checked stage at a time:

1. **Transcription:** one text file per PDF page, read from the page
   images, word for word, with marks for handwriting, uncertain
   readings and scan problems.
2. **Family group sheets and records:** one text sheet per family, every
   fact tagged with where it comes from (the author, a record, someone
   quoted, or worked out) and the PDF page; one file per record the book
   copies; the book's own words pulled in verbatim by a script.
3. **Structured data:** one JSON file per sheet, checked by a script.
4. **GEDCOM 5.5.1:** one file for Ancestry, DNATools or any tree
   program, with page citations on every event and conflicting readings
   kept side by side.

The book is the only source. Nothing is corrected silently, guesses
never become facts, and living people stay private.

## Install

In Claude Code:

    /plugin marketplace add briancase1776/scan2gedcom
    /plugin install scan2gedcom@scan2gedcom

Then ask Claude to transcribe a scanned family book, or run
`/scan2gedcom`.

Needs `pdftoppm`, `pdfinfo` and `pdftotext` (poppler-utils) and
Python 3. `check_gedcom.py` needs `ged4py` (`pip install ged4py`).

## What's here

    skills/scan2gedcom/SKILL.md        the method, stage by stage
    skills/scan2gedcom/reference/      transcription rules, sheet and
                                       record layout, data format,
                                       briefs for helper agents
    skills/scan2gedcom/tools/          render.py, check_links.py,
                                       check_data.py, build_gedcom.py,
                                       check_gedcom.py
    examples/demo/                     an invented four-page book taken
                                       through every stage

To see the tools work, from `examples/demo`:

    T=../../skills/scan2gedcom/tools
    python3 -I $T/render.py transcription tools/templates \
        tools/templates/families/*.txt tools/templates/records/*.txt
    python3 -I $T/check_links.py
    python3 -I $T/check_data.py
    python3 -I $T/build_gedcom.py
    python3 -I $T/check_gedcom.py gedcom/harlan-family.ged

The demo's family, book and places are made up.

## License

MIT
