#!/usr/bin/env python3
"""
Step 7 - Submit objects to an archive via DICOMweb STOW-RS (fallback).

Use this when DIMSE ports are blocked by a firewall, or an archive prefers
STOW. Each Part-10 instance is POSTed as its own multipart/related request
(one instance per request is robust for large WSI); the server reads the
transfer syntax from each file's meta header, so the stored encoding is
preserved. Reads endpoints from scripts/archives.json.

Auth (credentials are read from the environment, never stored in the repo):
  - Bearer/OAuth2/JWT archives (e.g. Google, Visage):  export WG26_BEARER_TOKEN=...
  - HTTP Basic archives (e.g. Sectra):  export WG26_STOW_USER=... WG26_STOW_PASSWORD=...
    (obtain both from the archive contact listed in archives.json)
Self-signed TLS at the event: pass --insecure to skip certificate verification.

Usage:
    scripts/07_submit_stow.py proscia
    scripts/07_submit_stow.py sectra --tree data/submission/tcga_luad
    scripts/07_submit_stow.py google --insecure --dry-run
    scripts/07_submit_stow.py --list
"""
import argparse
import json
import os
import sys
import uuid

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARCHIVES = os.path.join(HERE, "archives.json")
TREE = os.path.join(ROOT, "data", "submission")


def find_dcm(root):
    for dp, _, files in os.walk(root):
        for fn in sorted(files):
            if fn.lower().endswith(".dcm"):
                yield os.path.join(dp, fn)


def post_instance(url, path, headers, verify, auth=None):
    boundary = uuid.uuid4().hex
    with open(path, "rb") as fh:
        payload = fh.read()
    body = (
        f"--{boundary}\r\n".encode()
        + b"Content-Type: application/dicom\r\n\r\n"
        + payload
        + f"\r\n--{boundary}--\r\n".encode()
    )
    h = dict(headers)
    h["Content-Type"] = f'multipart/related; type="application/dicom"; boundary={boundary}'
    return requests.post(url, data=body, headers=h, verify=verify, auth=auth, timeout=600)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archive", nargs="?", help="archive key from archives.json")
    ap.add_argument("--tree", default=TREE)
    ap.add_argument("--insecure", action="store_true", help="skip TLS cert verification")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(ARCHIVES) as f:
        cfg = json.load(f)
    archives = cfg["archives"]

    if args.list or not args.archive:
        print("Available archives (DICOMweb STOW-RS):")
        for k, a in archives.items():
            print(f"  {k:<10} {a['name']:<40} "
                  f"{a['stow_url'] or '(no STOW endpoint - use C-STORE)'}"
                  f"{'  [auth: '+a['auth']+']' if a['auth'] != 'none' else ''}")
        return

    if args.archive not in archives:
        sys.exit(f"Unknown archive '{args.archive}'. Use --list.")
    a = archives[args.archive]
    url = a.get("stow_url")
    if not url:
        sys.exit(f"{a['name']} has no STOW endpoint; use 06_submit_cstore.py instead.")

    headers = {"Accept": "application/dicom+json"}
    auth = None
    if a["auth"] == "basic":
        user = os.environ.get("WG26_STOW_USER")
        pw = os.environ.get("WG26_STOW_PASSWORD")
        if not (user and pw):
            sys.exit(f"{a['name']} requires HTTP Basic auth; set WG26_STOW_USER "
                     f"and WG26_STOW_PASSWORD (obtain from {a.get('contact', 'the archive contact')}).")
        from requests.auth import HTTPBasicAuth
        auth = HTTPBasicAuth(user, pw)
    elif a["auth"] != "none":
        tok = os.environ.get("WG26_BEARER_TOKEN")
        if not tok:
            sys.exit(f"{a['name']} requires auth ({a['auth']}); "
                     f"set WG26_BEARER_TOKEN environment variable.")
        headers["Authorization"] = f"Bearer {tok}"

    files = list(find_dcm(args.tree))
    if not files:
        sys.exit(f"No .dcm under {args.tree}")

    print(f"Archive : {a['name']} ({args.archive})")
    print(f"STOW    : {url}")
    print(f"Tree    : {args.tree}  ({len(files)} instances)")
    if args.dry_run:
        for p in files:
            print("  would POST", os.path.relpath(p, args.tree))
        print("\n[dry-run] nothing sent.")
        return

    verify = not args.insecure
    ok = fail = 0
    for p in files:
        rel = os.path.relpath(p, args.tree)
        try:
            resp = post_instance(url, p, headers, verify, auth)
            if resp.status_code in (200, 202):
                ok += 1
                print(f"  {resp.status_code}  {rel}")
            else:
                fail += 1
                print(f"  FAIL {resp.status_code}  {rel}  {resp.text[:200]}")
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"  ERROR {rel}: {e}")

    print(f"\nDone: {ok} stored, {fail} failed.")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
