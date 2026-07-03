#!/usr/bin/env python3
"""
Step 3 - Remediate pre-existing WSI conformance errors in the
IDC-converted VL Whole Slide Microscopy Image objects so they pass
`dciodvfy -profile WG26SP2025` with zero errors.

These errors exist in the original IDC data (the converter left them); they are
NOT introduced by the re-identification step. Only SM (WSI) objects are touched;
annotations and the presentation state are left unchanged, as are all UIDs and
pixel data (edits use dcmtk `dcmodify`, no pixel decode). Each attribute is only
changed when it is actually wrong, so already-conformant objects (e.g. the
bone-marrow SM) are skipped.

Fixes applied (values mirror what IDC's own conformant bone-marrow slide uses):
  * PositionReferenceIndicator (0020,1040) -> "SLIDE_CORNER"        (if not already)
  * SpecimenTypeCodeSequence in each SpecimenDescriptionSequence item
        -> (1179252003, SCT, "Slide")                              (if missing)
  * SliceThickness (in SharedFunctionalGroupsSequence/PixelMeasuresSequence)
        -> NOMINAL_SLICE_THICKNESS_MM                              (only if 0 / empty)
  * ImagedVolumeDepth (0048,0003)
        -> NOMINAL_SLICE_THICKNESS_MM * 1000 um                    (only if 0)

NOTE: SliceThickness / ImagedVolumeDepth are set to a NOMINAL value because the
IDC source recorded 0 (unknown). They are placeholders, not measured values.
Adjust the constants below or coordinate real values with the data owner.

Run AFTER 02_modify_dicom.py, on the submission tree (edited in place there):
    .venv/bin/python scripts/03_fix_wsi.py
    .venv/bin/python scripts/03_fix_wsi.py --dry-run
"""
import argparse
import os
import shutil
import subprocess
import sys

import pydicom

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TREE = os.path.join(ROOT, "data", "submission")

WSI_SOP_CLASS = "1.2.840.10008.5.1.4.1.1.77.1.6"  # VL Whole Slide Microscopy Image Storage
DCMODIFY = shutil.which("dcmodify")

# Nominal placeholder geometry (IDC source recorded 0 / unknown). 3 um is a
# typical FFPE section; SliceThickness in mm, ImagedVolumeDepth in um, kept consistent.
NOMINAL_SLICE_THICKNESS_MM = 0.003
NOMINAL_IMAGED_VOLUME_DEPTH_UM = NOMINAL_SLICE_THICKNESS_MM * 1000.0

# SpecimenTypeCodeSequence coded value (SNOMED CT "Slide"), as used by the
# conformant IDC bone-marrow WSI.
SPECIMEN_TYPE_CODE = ("1179252003", "SCT", "Slide")


def _is_zero(v):
    try:
        return v is None or float(str(v)) <= 0.0
    except (TypeError, ValueError):
        return True  # empty / unparseable -> treat as needing a value


def plan_fixes(ds):
    """Return a list of dcmodify args for the fixes this dataset needs."""
    args = []
    # PositionReferenceIndicator
    if str(ds.get("PositionReferenceIndicator", "")).strip().upper() != "SLIDE_CORNER":
        args += ["-m", "PositionReferenceIndicator=SLIDE_CORNER"]
    # ImagedVolumeDepth
    if _is_zero(ds.get("ImagedVolumeDepth")):
        args += ["-m", f"ImagedVolumeDepth={NOMINAL_IMAGED_VOLUME_DEPTH_UM}"]
    # SliceThickness inside SharedFunctionalGroupsSequence/PixelMeasuresSequence
    sfgs = ds.get("SharedFunctionalGroupsSequence")
    if sfgs:
        for i, fg in enumerate(sfgs):
            pms = fg.get("PixelMeasuresSequence")
            if pms:
                for j, pm in enumerate(pms):
                    if _is_zero(pm.get("SliceThickness")):
                        args += ["-m", f"SharedFunctionalGroupsSequence[{i}]."
                                        f"PixelMeasuresSequence[{j}]."
                                        f"SliceThickness={NOMINAL_SLICE_THICKNESS_MM}"]
    # SpecimenTypeCodeSequence in each SpecimenDescriptionSequence item
    sds = ds.get("SpecimenDescriptionSequence")
    if sds:
        cv, csd, cm = SPECIMEN_TYPE_CODE
        for k, item in enumerate(sds):
            if "SpecimenTypeCodeSequence" not in item:
                base = f"SpecimenDescriptionSequence[{k}].SpecimenTypeCodeSequence[0]"
                args += ["-i", f"{base}.CodeValue={cv}",
                         "-i", f"{base}.CodingSchemeDesignator={csd}",
                         "-i", f"{base}.CodeMeaning={cm}"]
    return args


def find_dcm(root):
    for dp, _, files in os.walk(root):
        for fn in sorted(files):
            if fn.lower().endswith(".dcm"):
                yield os.path.join(dp, fn)


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

    fixed = skipped_ok = skipped_nonwsi = 0
    errors = []
    for f in find_dcm(args.tree):
        try:
            ds = pydicom.dcmread(f, stop_before_pixels=True, force=True)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{f}: unreadable ({e})")
            continue
        if str(ds.get("SOPClassUID", "")) != WSI_SOP_CLASS:
            skipped_nonwsi += 1
            continue
        fix_args = plan_fixes(ds)
        if not fix_args:
            skipped_ok += 1
            continue
        rel = os.path.relpath(f, args.tree)
        if args.dry_run:
            print(f"  would fix {rel}: {' '.join(fix_args)}")
            fixed += 1
            continue
        r = subprocess.run([DCMODIFY, "-nb", "-imt", *fix_args, f],
                           capture_output=True, text=True)
        if r.returncode != 0:
            errors.append(f"{rel}: dcmodify failed: {r.stderr.strip()}")
            continue
        fixed += 1

    print(f"\nWSI objects fixed:            {fixed}")
    print(f"WSI objects already clean:    {skipped_ok}")
    print(f"Non-WSI objects skipped:      {skipped_nonwsi} (ANN / PR untouched)")
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
