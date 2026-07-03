#!/usr/bin/env bash
# Step 5 - Validate the submission objects.
#
#   1. dciodvfy -profile WG26SP2025  on every object  (must report 0 errors)
#   2. dcentvfy                      per study         (patient/study/series
#                                                       attribute consistency
#                                                       across image + annotation)
#
# Per-object logs are written under data/validation/. A summary is printed and
# the script exits non-zero if any object has validation errors.
#
# Usage:  scripts/05_validate.sh [TREE]
#         (TREE defaults to data/submission)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TREE="${1:-$ROOT/data/submission}"
LOGDIR="$ROOT/data/validation"
PROFILE="WG26SP2025"

# Use the dicom3tools build shipped in the repo (it defines the WG26SP2025
# WSI/ANN IODs the profile needs); fall back to PATH. Override with $DCIODVFY.
DCIODVFY="${DCIODVFY:-$ROOT/dicom3tools/dciodvfy}"
DCENTVFY="${DCENTVFY:-$ROOT/dicom3tools/dcentvfy}"
[ -x "$DCIODVFY" ] || DCIODVFY="$(command -v dciodvfy || true)"
[ -x "$DCENTVFY" ] || DCENTVFY="$(command -v dcentvfy || true)"
[ -n "$DCIODVFY" ] && [ -x "$DCIODVFY" ] || { echo "dciodvfy not found (set \$DCIODVFY)"; exit 2; }
echo "dciodvfy: $DCIODVFY"
HAVE_DCENTVFY=0
[ -n "$DCENTVFY" ] && [ -x "$DCENTVFY" ] && HAVE_DCENTVFY=1
[ -d "$TREE" ] || { echo "Tree not found: $TREE (run 01_download.py / 02_modify_dicom.py first)"; exit 2; }

mkdir -p "$LOGDIR"
echo "Validating objects under: $TREE"
echo "Profile: -profile $PROFILE"
echo

total=0; failed=0; na=0
declare -a FAILED_FILES

# 1) Per-object IOD validation
while IFS= read -r -d '' f; do
    total=$((total+1))
    rel="${f#"$TREE"/}"
    log="$LOGDIR/${rel//\//__}.dciodvfy.txt"
    "$DCIODVFY" -profile "$PROFILE" "$f" > "$log" 2>&1
    # dciodvfy reports problems as lines beginning with "Error"
    nerr=$(grep -c '^Error' "$log" 2>/dev/null || true)
    nwarn=$(grep -c '^Warning' "$log" 2>/dev/null || true)
    # "Information Object Not found" as the ONLY error means the SOP class is not
    # covered by this profile (e.g. the Advanced Blending Presentation State -
    # WG26SP2025 defines only WSI + ANN IODs). That is out-of-scope, not a defect.
    niob=$(grep -c '^Error - Information Object Not found' "$log" 2>/dev/null || true)
    if [ "${nerr:-0}" -gt 0 ] && [ "${nerr:-0}" -eq "${niob:-0}" ]; then
        na=$((na+1))
        printf "  N/A   %-70s (SOP class not in %s profile)\n" "$rel" "$PROFILE"
    elif [ "${nerr:-0}" -gt 0 ]; then
        failed=$((failed+1))
        FAILED_FILES+=("$rel ($nerr errors, $nwarn warnings)")
        printf "  FAIL  %-70s %s err %s warn\n" "$rel" "$nerr" "$nwarn"
    else
        printf "  ok    %-70s %s warn\n" "$rel" "${nwarn:-0}"
    fi
done < <(find "$TREE" -type f -name '*.dcm' -print0 | sort -z)

echo
echo "IOD validation: $((total-failed-na))/$((total-na)) in-scope objects passed; $na N/A (not in profile); logs in $LOGDIR"

# 2) Cross-object consistency per study
if [ "$HAVE_DCENTVFY" -eq 1 ]; then
    echo
    echo "Entity-consistency check (dcentvfy), per study:"
    # study dirs are 3 levels below TREE: collection/PatientID/StudyInstanceUID
    while IFS= read -r -d '' study_dir; do
        sfiles=()   # bash 3.2 compatible (macOS /bin/bash lacks mapfile)
        while IFS= read -r sf; do sfiles+=("$sf"); done \
            < <(find "$study_dir" -type f -name '*.dcm')
        [ "${#sfiles[@]}" -ge 1 ] || continue
        study="$(basename "$study_dir")"
        clog="$LOGDIR/study_${study}.dcentvfy.txt"
        "$DCENTVFY" "${sfiles[@]}" > "$clog" 2>&1
        if [ -s "$clog" ]; then
            printf "  ISSUES  study %-50s (%d files) -> %s\n" "$study" "${#sfiles[@]}" "$clog"
        else
            printf "  ok      study %-50s (%d files)\n" "$study" "${#sfiles[@]}"
        fi
    done < <(find "$TREE" -mindepth 3 -maxdepth 3 -type d -print0)
else
    echo
    echo "(dcentvfy not found; skipped cross-object consistency check)"
fi

echo
if [ "$failed" -gt 0 ]; then
    echo "RESULT: $failed object(s) FAILED IOD validation:"
    for x in "${FAILED_FILES[@]}"; do echo "  - $x"; done
    exit 1
fi
echo "RESULT: all $((total-na)) in-scope objects passed IOD validation ($na out-of-profile N/A)."
