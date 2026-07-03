#!/usr/bin/env python3
"""
Step 2 - Apply the Connectathon "external image" identity to every object.

For each downloaded DICOM file, sets:
    PatientName  ->  26CN^EXT_IDC_from_<source>_<subject>  (converted external images)
    PatientID    ->  IDC-EXT-<subject>
consistently for all objects of a study, so an annotation / presentation state
carries the same Patient Name and ID (and the same StudyInstanceUID) as the
image it references. All UIDs and pixel data are preserved unchanged, so
image<->annotation<->presentation-state references and the original transfer
syntaxes stay intact.

Editing is done in place with dcmtk `dcmodify` (no pixel-data decode/re-encode).
By default the pristine download is copied into data/submission/ (reorganized
under the new PatientID) and edited there, leaving data/idc_original/ untouched.

Usage:
    .venv/bin/python scripts/02_modify_dicom.py            # copy -> edit submission tree
    .venv/bin/python scripts/02_modify_dicom.py --in-place # edit the download in place
    .venv/bin/python scripts/02_modify_dicom.py --dry-run
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

import pydicom

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SELECTION = os.path.join(ROOT, "data", "manifest", "wg26_selection.json")
SRC = os.path.join(ROOT, "data", "idc_original")
DST = os.path.join(ROOT, "data", "submission")

DCMODIFY = shutil.which("dcmodify")


def load_maps():
    with open(SELECTION) as f:
        sel = json.load(f)
    by_series, by_study = {}, {}
    for o in sel["objects"]:
        by_series[o["SeriesInstanceUID"]] = o
        by_study[o["StudyInstanceUID"]] = (o["new_PatientName"], o["new_PatientID"])
    return sel, by_series, by_study


def find_dcm(root):
    for dp, _, files in os.walk(root):
        for fn in files:
            if fn.lower().endswith(".dcm"):
                yield os.path.join(dp, fn)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--dst", default=DST)
    ap.add_argument("--in-place", action="store_true",
                    help="edit files in --src directly (no copy)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not DCMODIFY:
        sys.exit("dcmodify (dcmtk) not found on PATH.")
    if not os.path.isdir(args.src):
        sys.exit(f"Source tree not found: {args.src}. Run 01_download.py first.")

    sel, by_series, by_study = load_maps()
    files = sorted(find_dcm(args.src))
    if not files:
        sys.exit(f"No .dcm files under {args.src}")

    print(f"Found {len(files)} DICOM files under {args.src}")
    if args.in_place:
        print("Mode: IN-PLACE edit")
    else:
        print(f"Mode: copy -> {args.dst} (reorganized under new PatientID), then edit")

    per_study = {}
    errors = []
    for src_path in files:
        try:
            ds = pydicom.dcmread(src_path, stop_before_pixels=True, force=True)
            series_uid = str(ds.SeriesInstanceUID)
            study_uid = str(ds.StudyInstanceUID)
            sop_uid = str(ds.SOPInstanceUID)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{src_path}: unreadable ({e})")
            continue

        info = by_series.get(series_uid)
        if info is None or study_uid not in by_study:
            errors.append(f"{src_path}: series/study not in selection "
                          f"(series={series_uid[:30]}..)")
            continue
        name, pid = by_study[study_uid]

        if args.in_place:
            target = src_path
        else:
            rel = f"{info['collection_id']}/{pid}/{study_uid}/{info['Modality']}_{series_uid}"
            out_dir = os.path.join(args.dst, rel)
            target = os.path.join(out_dir, sop_uid + ".dcm")
            if not args.dry_run:
                os.makedirs(out_dir, exist_ok=True)
                shutil.copy2(src_path, target)

        per_study.setdefault(info["subject"], {"name": name, "pid": pid, "n": 0})
        per_study[info["subject"]]["n"] += 1

        if args.dry_run:
            continue

        cmd = [DCMODIFY, "-nb",
               "-m", f"PatientName={name}",
               "-m", f"PatientID={pid}", target]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            errors.append(f"{target}: dcmodify failed: {r.stderr.strip()}")
            continue
        # verify readback
        chk = pydicom.dcmread(target, stop_before_pixels=True, force=True)
        if str(chk.PatientName) != name or str(chk.PatientID) != pid:
            errors.append(f"{target}: readback mismatch "
                          f"(name={chk.PatientName}, id={chk.PatientID})")

    print("\nPer-subject summary:")
    for subj in sorted(per_study):
        d = per_study[subj]
        print(f"  {subj:<6} {d['name']:<20} {d['pid']:<16} {d['n']:>3} files")

    if errors:
        print(f"\n{len(errors)} ERROR(S):")
        for e in errors:
            print("  " + e)
        sys.exit(1)
    if args.dry_run:
        print("\n[dry-run] no files modified.")
    else:
        out = args.src if args.in_place else args.dst
        print(f"\nDone. Modified tree at: {out}")
        print("Next: scripts/05_validate.sh")


if __name__ == "__main__":
    main()
