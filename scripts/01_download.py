#!/usr/bin/env python3
"""
Step 1 - Download the selected series from NCI Imaging Data Commons (IDC v24).

Reads the selection produced by 00_build_selection.py and downloads via
idc-index into a pristine tree (data/idc_original/). Files land in the IDC
default layout:  collection_id/PatientID/StudyInstanceUID/Modality_SeriesInstanceUID/

Scope options:
    --core   download the 9 brightfield/annotation objects (~3.3 GB), excluding
             the ~52 GB fluorescence study whose Connectathon scope is pending
             organizer confirmation (default).
    --full   download all 11 objects (~55 GB).
    --uids U1 U2 ...   download only the given SeriesInstanceUIDs.
    --dry-run          report sizes only, download nothing.

Usage:
    .venv/bin/python scripts/01_download.py --core
    .venv/bin/python scripts/01_download.py --full
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SELECTION = os.path.join(ROOT, "data", "manifest", "wg26_selection.json")
DEST = os.path.join(ROOT, "data", "idc_original")


def load_selection():
    if not os.path.exists(SELECTION):
        sys.exit(f"Missing {SELECTION}; run 00_build_selection.py first.")
    with open(SELECTION) as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--core", action="store_true",
                   help="download everything except the ~52 GB fluorescence study (default)")
    g.add_argument("--full", action="store_true", help="download all 11 objects (~55 GB)")
    g.add_argument("--uids", nargs="+", help="download only these SeriesInstanceUIDs")
    ap.add_argument("--dry-run", action="store_true", help="report sizes only")
    ap.add_argument("--dest", default=DEST, help=f"download directory (default {DEST})")
    args = ap.parse_args()

    sel = load_selection()
    objs = sel["objects"]

    if args.uids:
        wanted = set(args.uids)
        chosen = [o for o in objs if o["SeriesInstanceUID"] in wanted]
    elif args.full:
        chosen = objs
    else:  # default = core
        chosen = [o for o in objs if not o["is_fluorescence_study"]]

    if not chosen:
        sys.exit("No series selected for download.")

    total_gb = sum(o["series_size_MB"] for o in chosen) / 1024
    print(f"IDC data version: {sel['idc_data_version']}")
    print(f"Selected {len(chosen)} objects, {total_gb:.2f} GB:")
    for o in chosen:
        print(f"  #{o['index']:>2} {o['collection_id']:<32} {o['Modality']:<3} "
              f"{o['subject']:<6} {o['series_size_MB']/1024:8.3f} GB  "
              f"{o['instanceCount']:>3} inst  {o['SeriesInstanceUID']}")

    if args.dry_run:
        print("\n[dry-run] nothing downloaded.")
        return

    if total_gb > 10:
        print(f"\nWARNING: this will download {total_gb:.1f} GB. Ctrl-C within 8 s to abort.")
        try:
            import time
            time.sleep(8)
        except KeyboardInterrupt:
            sys.exit("\nAborted.")

    from idc_index import index
    c = index.IDCClient()
    os.makedirs(args.dest, exist_ok=True)
    uids = [o["SeriesInstanceUID"] for o in chosen]
    print(f"\nDownloading to {args.dest} ...")
    c.download_from_selection(downloadDir=args.dest, seriesInstanceUID=uids,
                              quiet=False, show_progress_bar=True)
    print("Download complete.")


if __name__ == "__main__":
    main()
