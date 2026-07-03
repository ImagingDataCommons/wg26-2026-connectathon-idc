#!/usr/bin/env python3
"""
Step 8 - Verify a submission at an archive via DICOMweb QIDO-RS.

Independently confirms that what we submitted actually landed. For every study
in the identity manifest (data/manifest/wg26_identity_map.csv - the source of
truth) it queries the archive and checks:
  - the study is present,
  - PatientName and PatientID match the re-identified values,
  - the number of series matches, and each expected series is present,
  - each series' Modality and instance count match what we submitted.

The QIDO-RS base is derived from the archive's `stow_url` in archives.json (the
DICOMweb root, with a trailing `/studies` stripped), or set explicitly with
`qido_url` in archives.json / the --qido-url flag. Auth and TLS options mirror
07_submit_stow.py (env vars WG26_STOW_USER/PASSWORD or WG26_BEARER_TOKEN;
--insecure to skip cert verification at the event).

Exit status is 0 only if every checked study matches; non-zero otherwise, so it
can gate a submission in CI or a shell pipeline.

Usage:
    scripts/08_verify_submission.py proscia                     # verify all manifest studies
    scripts/08_verify_submission.py proscia --study 2.25.1139...  # just one study
    scripts/08_verify_submission.py sectra --insecure
    scripts/08_verify_submission.py agfa --qido-url https://ei-service.med.agfa.be/qido-rs/v1
    scripts/08_verify_submission.py --list
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARCHIVES = os.path.join(HERE, "archives.json")
MANIFEST = os.path.join(ROOT, "data", "manifest", "wg26_identity_map.csv")

# DICOM tags used in QIDO includefield / responses
PN, PID = "00100010", "00100020"
NUM_STUDY_SERIES, NUM_STUDY_INST = "00201206", "00201208"
MODALITY, SERIES_UID, NUM_SERIES_INST = "00080060", "0020000E", "00201209"


def first(ds, tag, default=None):
    """First value of a DICOM-JSON element, unwrapping PersonName dicts."""
    vals = ds.get(tag, {}).get("Value")
    if not vals:
        return default
    v = vals[0]
    if isinstance(v, dict):  # PN VR -> {"Alphabetic": "..."}
        return v.get("Alphabetic", default)
    return v


def load_manifest(path):
    """Aggregate the identity map into {StudyInstanceUID: {...}} (one study may
    have several series rows, e.g. image + annotation + presentation state)."""
    studies = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            suid = row["StudyInstanceUID"]
            st = studies.setdefault(suid, {
                "patient_name": row["new_PatientName"],
                "patient_id": row["new_PatientID"],
                "collection": row["collection"],
                "series": {},
            })
            st["series"][row["SeriesInstanceUID"]] = {
                "modality": row["modality"],
                "instances": int(row["instances"]),
            }
    return studies


def qido_base(a, override):
    if override:
        return override.rstrip("/")
    url = a.get("qido_url") or a.get("stow_url")
    if not url:
        return None
    url = url.rstrip("/")
    if url.lower().endswith("/studies"):
        url = url[: -len("/studies")]
    return url


def auth_for(a):
    headers = {"Accept": "application/dicom+json"}
    auth = None
    if a["auth"] == "basic":
        user = os.environ.get("WG26_STOW_USER")
        pw = os.environ.get("WG26_STOW_PASSWORD")
        if not (user and pw):
            sys.exit(f"{a['name']} needs HTTP Basic auth; set WG26_STOW_USER and "
                     f"WG26_STOW_PASSWORD (obtain from {a.get('contact', 'the archive contact')}).")
        from requests.auth import HTTPBasicAuth
        auth = HTTPBasicAuth(user, pw)
    elif a["auth"] != "none":
        tok = os.environ.get("WG26_BEARER_TOKEN")
        if not tok:
            sys.exit(f"{a['name']} needs auth ({a['auth']}); set WG26_BEARER_TOKEN.")
        headers["Authorization"] = f"Bearer {tok}"
    return headers, auth


def get_json(url, headers, auth, verify):
    r = requests.get(url, headers=headers, auth=auth, verify=verify, timeout=90)
    if r.status_code == 204:  # QIDO: no matches
        return []
    r.raise_for_status()
    return r.json() if r.content else []


def series_instance_count(base, suid, sruid, ctx):
    """Reliable per-series instance count: prefer NumberOfSeriesRelatedInstances,
    else count the instances resource."""
    inst = get_json(f"{base}/studies/{suid}/series/{sruid}/instances", *ctx)
    return len(inst)


def verify_study(base, suid, expect, ctx):
    """Return (ok: bool, lines: list[str]) for one study."""
    lines = []
    coll = expect["collection"]
    studies = get_json(
        f"{base}/studies?StudyInstanceUID={suid}"
        f"&includefield={PN}&includefield={PID}"
        f"&includefield={NUM_STUDY_SERIES}&includefield={NUM_STUDY_INST}", *ctx)
    if not studies:
        return False, [f"  MISSING  {coll:<32} study not found: {suid}"]

    ds = studies[0]
    got_name = first(ds, PN)
    got_id = first(ds, PID)
    exp_series = expect["series"]
    exp_inst_total = sum(s["instances"] for s in exp_series.values())

    problems = []
    if got_name != expect["patient_name"]:
        problems.append(f"PatientName {got_name!r} != {expect['patient_name']!r}")
    if got_id != expect["patient_id"]:
        problems.append(f"PatientID {got_id!r} != {expect['patient_id']!r}")

    # Per-series ground truth
    series = get_json(f"{base}/studies/{suid}/series"
                      f"?includefield={MODALITY}&includefield={NUM_SERIES_INST}", *ctx)
    got_series = {}
    for s in series:
        sruid = first(s, SERIES_UID)
        n = first(s, NUM_SERIES_INST)
        got_series[sruid] = {
            "modality": first(s, MODALITY),
            "instances": int(n) if n is not None else None,
        }

    got_inst_total = 0
    for sruid, exp in exp_series.items():
        if sruid not in got_series:
            problems.append(f"series {exp['modality']} missing ({sruid})")
            continue
        g = got_series[sruid]
        n = g["instances"]
        if n is None:  # server didn't populate the count -> count explicitly
            n = series_instance_count(base, suid, sruid, ctx)
        got_inst_total += n
        if n != exp["instances"]:
            problems.append(f"series {exp['modality']} instances {n} != {exp['instances']}")
        if g["modality"] and g["modality"] != exp["modality"]:
            problems.append(f"series modality {g['modality']} != {exp['modality']}")

    extra = set(got_series) - set(exp_series)
    n_series_got = len(got_series)
    n_series_exp = len(exp_series)

    if problems:
        head = (f"  FAIL     {coll:<32} series {n_series_got}/{n_series_exp}  "
                f"inst {got_inst_total}/{exp_inst_total}")
        return False, [head] + [f"             - {p}" for p in problems] + (
            [f"             - {len(extra)} unexpected extra series present"] if extra else [])

    line = (f"  ok       {coll:<32} series {n_series_got}/{n_series_exp}  "
            f"inst {got_inst_total}/{exp_inst_total}  {expect['patient_id']}")
    if extra:
        line += f"  (+{len(extra)} extra series present)"
    return True, [line]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archive", nargs="?", help="archive key from archives.json")
    ap.add_argument("--study", help="verify only this StudyInstanceUID")
    ap.add_argument("--qido-url", help="override QIDO-RS base (else derived from stow_url)")
    ap.add_argument("--manifest", default=MANIFEST, help=f"identity CSV (default {MANIFEST})")
    ap.add_argument("--insecure", action="store_true", help="skip TLS cert verification")
    ap.add_argument("--list", action="store_true", help="list archive keys and exit")
    args = ap.parse_args()

    with open(ARCHIVES) as f:
        cfg = json.load(f)
    archives = cfg["archives"]

    if args.list or not args.archive:
        print("Available archives (QIDO-RS base derived from stow_url unless qido_url set):")
        for k, a in archives.items():
            print(f"  {k:<10} {a['name']:<40} {qido_base(a, None) or '(no DICOMweb - use --qido-url)'}")
        return

    if args.archive not in archives:
        sys.exit(f"Unknown archive '{args.archive}'. Use --list.")
    a = archives[args.archive]
    base = qido_base(a, args.qido_url)
    if not base:
        sys.exit(f"{a['name']} has no DICOMweb base; pass --qido-url.")

    studies = load_manifest(args.manifest)
    if args.study:
        if args.study not in studies:
            sys.exit(f"StudyInstanceUID {args.study} not in manifest.")
        studies = {args.study: studies[args.study]}

    headers, auth = auth_for(a)
    verify = not args.insecure
    ctx = (headers, auth, verify)

    print(f"Archive : {a['name']} ({args.archive})")
    print(f"QIDO    : {base}")
    print(f"Manifest: {len(studies)} study(ies), "
          f"{sum(len(s['series']) for s in studies.values())} series, "
          f"{sum(i['instances'] for s in studies.values() for i in s['series'].values())} instances expected")
    print()

    passed = failed = 0
    for suid, expect in sorted(studies.items(), key=lambda kv: kv[1]["patient_id"]):
        try:
            ok, lines = verify_study(base, suid, expect, ctx)
        except requests.RequestException as e:
            ok, lines = False, [f"  ERROR    {expect['collection']:<32} {e}"]
        print("\n".join(lines))
        passed += ok
        failed += not ok

    print()
    total = passed + failed
    if failed:
        print(f"RESULT: {failed}/{total} study(ies) FAILED verification at {a['name']}.")
        sys.exit(1)
    print(f"RESULT: all {total} study(ies) verified at {a['name']} "
          f"(present, correct identity, series/instance counts match).")


if __name__ == "__main__":
    main()
