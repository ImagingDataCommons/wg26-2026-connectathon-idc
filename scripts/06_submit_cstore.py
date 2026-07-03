#!/usr/bin/env python3
"""
Step 6 - Submit objects to an archive via DICOM C-STORE (DIMSE), using dcmsend.

C-STORE is the recommended primary submission path (see README): it is
supported by every archive, handles the large multi-instance WSI series
robustly, preserves the stored transfer syntax through presentation-context
negotiation (no recompression), and uses plaintext DIMSE - avoiding the
TLS/OAuth/JWT setup some DICOMweb endpoints require.

Reads endpoints from scripts/archives.json. Recurses the submission tree and
sends every *.dcm.

Usage:
    scripts/06_submit_cstore.py sectra                 # send whole submission tree
    scripts/06_submit_cstore.py google --tree data/submission/tcga_luad
    scripts/06_submit_cstore.py proscia --aet IDC_WG26 --dry-run
    scripts/06_submit_cstore.py --list                 # list archive keys
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARCHIVES = os.path.join(HERE, "archives.json")
TREE = os.path.join(ROOT, "data", "submission")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archive", nargs="?", help="archive key from archives.json")
    ap.add_argument("--tree", default=TREE, help=f"tree/dir to send (default {TREE})")
    ap.add_argument("--aet", help="our calling AE title (default from archives.json)")
    ap.add_argument("--list", action="store_true", help="list archive keys and exit")
    ap.add_argument("--dry-run", action="store_true", help="print the dcmsend command only")
    args = ap.parse_args()

    with open(ARCHIVES) as f:
        cfg = json.load(f)
    archives = cfg["archives"]

    if args.list or not args.archive:
        print("Available archives (DIMSE C-STORE SCP):")
        for k, a in archives.items():
            s = a["store_scp"]
            print(f"  {k:<10} {a['name']:<40} {s['host']}:{s['port']} AEC={s['aet']}")
        return

    if args.archive not in archives:
        sys.exit(f"Unknown archive '{args.archive}'. Use --list.")
    a = archives[args.archive]
    scp = a["store_scp"]
    calling = args.aet or cfg.get("calling_aet_default", "IDC_WG26")

    dcmsend = shutil.which("dcmsend")
    if not dcmsend:
        sys.exit("dcmsend (dcmtk) not found on PATH.")
    if not os.path.isdir(args.tree):
        sys.exit(f"Tree not found: {args.tree}")

    # --decompress-never: preserve the stored transfer syntax. dcmsend's default
    # (--decompress-lossless) would silently decompress lossless-compressed
    # objects (e.g. our JPEG 2000 Lossless series) if the peer's accepted
    # presentation context lacks that syntax. With --decompress-never the
    # object is stored as-is, or the store fails visibly (never transcoded).
    cmd = [dcmsend, str(scp["host"]), str(scp["port"]),
           "--scan-directories", "--recurse", "--scan-pattern", "*.dcm",
           "--decompress-never",
           "--aetitle", calling, "--call", scp["aet"],
           "--no-halt", "-v", args.tree]

    print(f"Archive : {a['name']} ({args.archive})")
    print(f"Target  : {scp['host']}:{scp['port']}  AEC={scp['aet']}  AET={calling}")
    print(f"Tree    : {args.tree}")
    if a.get("notes"):
        print(f"Notes   : {a['notes']}")
    print("Command : " + " ".join(cmd))
    if args.dry_run:
        print("\n[dry-run] not sent.")
        return

    print()
    r = subprocess.run(cmd)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
