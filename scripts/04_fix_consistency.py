#!/usr/bin/env python3
"""
Step 4 - Normalize cross-instance / cross-object attribute
inconsistencies flagged by dcentvfy, so the whole submission passes the
Connectathon consistency check with zero findings.

These are pre-existing IDC artifacts (not introduced by re-identification) and
do NOT affect Patient Name/ID or Study/Series UIDs (those are already
consistent). Two normalizations:

  1. DeviceSerialNumber (Equipment IE) - the htan_hms fluorescence series stored
     a different per-instance GUID on every instance; a single series comes from
     one piece of equipment and should share one value. For each series whose
     instances disagree, all instances are set to one consistent value (the
     lexicographically-first existing value in that series).

  2. OtherClinicalTrialProtocolIDsSequence (Patient IE) - present on the
     tcga_luad annotation (it carries the *annotation dataset's* DOI) but not on
     the image it annotates, so dcentvfy flags a Patient-level mismatch. It does
     not belong on the image, so it is removed from the object(s) that carry it
     within any study where it is not present on every object. (Provenance is
     retained in the annotation's Manufacturer / SoftwareVersions.)

UIDs and pixel data are preserved (edits use dcmtk `dcmodify`, no pixel decode).
Run after 02_modify_dicom.py / 03_fix_wsi.py, on the submission tree:
    .venv/bin/python scripts/04_fix_consistency.py
    .venv/bin/python scripts/04_fix_consistency.py --dry-run
"""
import argparse
import os
import shutil
import subprocess
import sys
from collections import defaultdict

import pydicom

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TREE = os.path.join(ROOT, "data", "submission")
DCMODIFY = shutil.which("dcmodify")

TRIAL_SEQ = "OtherClinicalTrialProtocolIDsSequence"


def find_dcm(root):
    for dp, _, files in os.walk(root):
        for fn in sorted(files):
            if fn.lower().endswith(".dcm"):
                yield os.path.join(dp, fn)


def run_dcmodify(args, path, errors):
    r = subprocess.run([DCMODIFY, "-nb", "-imt", *args, path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        errors.append(f"{path}: dcmodify failed: {r.stderr.strip()}")
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tree", default=TREE)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not DCMODIFY:
        sys.exit("dcmodify (dcmtk) not found on PATH.")
    if not os.path.isdir(args.tree):
        sys.exit(f"Tree not found: {args.tree}")

    # Gather headers.
    by_series = defaultdict(list)   # series_uid -> [(path, device_serial)]
    by_study = defaultdict(list)    # study_uid  -> [(path, has_trial_seq)]
    for f in find_dcm(args.tree):
        ds = pydicom.dcmread(f, stop_before_pixels=True, force=True)
        by_series[str(ds.get("SeriesInstanceUID", ""))].append(
            (f, str(ds.get("DeviceSerialNumber", ""))))
        by_study[str(ds.get("StudyInstanceUID", ""))].append(
            (f, TRIAL_SEQ in ds))

    errors = []
    dsn_fixed = 0
    dsn_series = 0

    # 1) DeviceSerialNumber consistency within each series.
    for series, items in by_series.items():
        distinct = {v for _, v in items if v != ""}
        if len(distinct) <= 1:
            continue
        target = sorted(distinct)[0]
        dsn_series += 1
        print(f"  DeviceSerialNumber: series {series[:32]}.. has {len(distinct)} "
              f"values -> normalizing {len(items)} instances to {target[:32]}..")
        for path, val in items:
            if val == target:
                continue
            if args.dry_run:
                dsn_fixed += 1
                continue
            if run_dcmodify([f"-m", f"DeviceSerialNumber={target}"], path, errors):
                dsn_fixed += 1

    # 2) OtherClinicalTrialProtocolIDsSequence harmonization per study.
    trial_removed = 0
    for study, items in by_study.items():
        haves = [p for p, has in items if has]
        if haves and len(haves) != len(items):   # present on some but not all
            print(f"  {TRIAL_SEQ}: study {study[:32]}.. present on {len(haves)}/"
                  f"{len(items)} objects -> removing from those that have it")
            for p in haves:
                if args.dry_run:
                    trial_removed += 1
                    continue
                if run_dcmodify([f"-e", TRIAL_SEQ], p, errors):
                    trial_removed += 1

    print(f"\nDeviceSerialNumber: normalized {dsn_fixed} instance(s) across {dsn_series} series")
    print(f"{TRIAL_SEQ}: removed from {trial_removed} object(s)")
    if errors:
        print(f"\n{len(errors)} ERROR(S):")
        for e in errors:
            print("  " + e)
        sys.exit(1)
    if args.dry_run:
        print("\n[dry-run] nothing modified.")
    else:
        print("\nDone. Re-validate with scripts/05_validate.sh")


if __name__ == "__main__":
    main()
