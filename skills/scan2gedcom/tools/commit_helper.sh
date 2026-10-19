#!/bin/bash
# Check one helper's files on their own, on top of HEAD, and commit
# exactly those files only if they pass.
#
# usage, from the project root, once the helper has finished:
#   tools/commit_helper.sh [-p] <message file> <file> ...
#     <file> ...  every file the helper wrote or deleted: templates,
#                 rendered sheets and records, data files
#     -p          push the branch after committing
#
# Helpers share one working tree, so a check of the whole tree can pass
# only because of another helper's half-written files, or fail because
# of them. This copies just the named files into a temporary git
# worktree of HEAD, renders every template there, and requires that
# every rendered file is current and named (none stale, none left out),
# then that check_links.py and check_data.py report no problems. Only
# then does it commit the named files, and nothing else you may have
# staged. Your working tree is not touched.
set -uo pipefail
shopt -s nullglob
push=; if [ "${1:-}" = -p ]; then push=1; shift; fi
if [ $# -lt 2 ] || [ ! -f "$1" ]; then sed -n '5,9p' "$0"; exit 2; fi
msg=$1; shift
wt=$(mktemp -d "${TMPDIR:-/tmp}/commit-helper-XXXXXX")
trap 'git worktree remove --force "$wt" >/dev/null 2>&1; rm -rf "$wt"' EXIT
git worktree add -q --detach "$wt" HEAD || exit 1
for f in "$@"; do
    if [ -e "$f" ]; then mkdir -p "$wt/$(dirname "$f")" && cp "$f" "$wt/$f" || exit 1
    else rm -f "$wt/$f"; fi
done

run() {   # a check: its last line if it passes, all of it if not
    local out rc; out=$("$@" 2>&1); rc=$?
    if [ $rc = 0 ]; then printf '%s\n' "$out" | tail -1; else printf '%s\n' "$out"; fi
    return $rc
}
check() (
    cd "$wt" || exit 1
    git add -A -- "$@" || exit 1                   # the worktree's own index
    python3 -I tools/render.py transcription tools/templates \
        tools/templates/families/*.txt tools/templates/records/*.txt >/dev/null || exit 1
    odd=$(git diff --name-only; git ls-files --others --exclude-standard)
    if [ -n "$odd" ]; then
        echo "not what the templates render (render again, or name these files):"
        printf '%s\n' "$odd"; exit 1
    fi
    run python3 -I tools/check_links.py && run python3 -I tools/check_data.py
)
if ! check "$@"; then echo "NOT committed"; exit 1; fi
git add -A -- "$@" && git commit -q -F "$msg" --only -- "$@" || exit 1
git log --oneline -1
if [ -n "$push" ]; then git push -q origin HEAD || exit 1; fi
