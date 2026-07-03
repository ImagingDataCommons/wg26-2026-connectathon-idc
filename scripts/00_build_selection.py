#!/usr/bin/env python3
"""
Build the authoritative selection + identity table for the WG-26 2026 submission.

Reads the 11 selected SeriesInstanceUIDs from the local idc-index (IDC data
release v24), groups them by StudyInstanceUID, and assigns each study a
Connectathon "external image" identity per the WG-26 Technical Requirements:

    PatientName = "26CN^EXT_<PARTICIPANT>_<subject>"
    (Evidence-Creator "external images" naming convention)

Annotations and the presentation state inherit the identity of the image
study they belong to, satisfying the requirement that annotations carry the
same Patient Name / ID (and Study Instance UID) as the images they annotate.

Outputs (under data/manifest/):
    wg26_selection.json   - one record per object (source of truth for all scripts)
    wg26_series.txt       - 11 SeriesInstanceUIDs (full set)
    wg26_series_core.txt  - 9 UIDs excluding the ~52 GB fluorescence study
    wg26_identity_map.csv  - human-readable identity assignment table

Re-run only if the selection changes; downstream scripts read the JSON, not IDC.
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "manifest")

# Participant token used in the "26CN^EXT_<participant>_<subject>" name.
PARTICIPANT = "IDC"

# The 11 selected series (see docs/idc_entry_selection.md).
SERIES_UIDS = [
    "1.3.6.1.4.1.5962.99.1.2351537988.1691156399.1655913979716.4.0",          # 1 htan_hms SM (fluorescence)
    "1.2.826.0.1.3680043.10.511.3.32217822852247924170142261734082901",       # 2 htan_hms PR (adv. blending)
    "1.3.6.1.4.1.5962.99.1.3052275118.437477262.1772578833838.4.0",           # 3 hcmi_cmdc SM (H&E, JPEG baseline)
    "1.3.6.1.4.1.5962.99.1.1048952951.469777563.1637431525495.2.0",           # 4 tcga_luad SM (H&E, J2K lossy)
    "1.3.6.1.4.1.5962.99.1.2027811345.1425031706.1655590253073.4.0",          # 5 htan_vanderbilt SM (H&E, J2K lossless)
    "1.2.826.0.1.3680043.10.511.3.66626547635466777954373480481638649",       # 6 tcga_luad ANN (polygon nuclei)
    "1.2.826.0.1.3680043.10.511.3.75156072263858645925658754886035975",       # 7 bonemarrow ANN (rectangle cell-type)
    "1.2.826.0.1.3680043.8.498.19212570839483117674134243789833677578",       # 8 bonemarrow SM (May-Grunwald Giemsa)
    "1.3.6.1.4.1.5962.99.1.3836604227.2006969735.1773363162947.4.0",          # 9 cgci_htmcp_lc SM (IHC TTF-1)
    "1.3.6.1.4.1.5962.99.1.3888926996.1445722942.1773415485716.4.0",          # 10 cgci_blgsp SM (IHC CD20)
    "1.3.6.1.4.1.5962.99.1.2962403854.296721353.1772488962574.4.0",           # 11 cgci_htmcp_dlbcl SM (ISH EBER)
]

# Assigned subject code per StudyInstanceUID. Short, human-readable at the
# Connectathon; stain/illumination encoded so slides are recognizable.
STUDY_SUBJECT = {
    "2.25.254901417575324832540235892437527774975": "FL01",   # htan_hms  epifluorescence + PR
    "2.25.326831351899246997718579660054873448065": "HE01",   # hcmi_cmdc H&E (JPEG baseline)
    "2.25.113910498547580375599321634216516970390": "HE02",   # tcga_luad H&E (J2K lossy) + polygon ANN
    "2.25.215244595345296939373838636406158345745": "HE03",   # htan_vanderbilt H&E (J2K lossless)
    "1.2.826.0.1.3680043.8.498.37689962845386577627578641862732406672": "MGG01",  # bonemarrow Giemsa + rect ANN
    "2.25.62097431654635660667506156467264852146":  "IHC01",  # cgci_htmcp_lc IHC TTF-1
    "2.25.35449169900502839636017945370968954585":  "IHC02",  # cgci_blgsp IHC CD20
    "2.25.336444473395720978044870396873829787454": "ISH01",  # cgci_htmcp_dlbcl ISH EBER
}

# Every SM image was converted to DICOM from a proprietary vendor format
# (via PixelMed TIFFToDicom / IDC's mirax converter), so the "converted image"
# naming applies:  PatientName -> "26CN^EXT_IDC_from_<source>_<subject>".
# <source> is the ORIGINAL SCANNER VENDOR, taken from ManufacturerModelName
# (matches the spec example 26CN^EXT_BetaConverterCo_from_AcmeScannerCo_ABCD).
# Annotation / presentation-state objects share their study's identity.
# PatientID (not governed by the naming convention) -> "IDC-EXT-<subject>".
STUDY_SOURCE = {
    "2.25.254901417575324832540235892437527774975": "RareCyte",     # htan_hms - RareCyte CyteFinder
    "2.25.326831351899246997718579660054873448065": "Aperio",       # hcmi_cmdc - Leica Aperio
    "2.25.113910498547580375599321634216516970390": "Aperio",       # tcga_luad - Leica Aperio
    "2.25.215244595345296939373838636406158345745": "LeicaSCN400",  # htan_vanderbilt - Leica SCN400
    "1.2.826.0.1.3680043.8.498.37689962845386577627578641862732406672": "3DHISTECH",  # bonemarrow - Pannoramic 250 / Mirax
    "2.25.62097431654635660667506156467264852146":  "Aperio",       # cgci_htmcp_lc - Leica Aperio
    "2.25.35449169900502839636017945370968954585":  "Aperio",       # cgci_blgsp - Leica Aperio
    "2.25.336444473395720978044870396873829787454": "Aperio",       # cgci_htmcp_dlbcl - Leica Aperio
}

# Study containing the large (~52 GB) fluorescence series, excluded from the
# "core" download subset (its Connectathon scope is pending organizer confirmation).
FLUORESCENCE_STUDY = "2.25.254901417575324832540235892437527774975"


def main():
    try:
        from idc_index import index
    except ImportError:
        sys.exit("idc-index not installed: pip install idc-index")

    c = index.IDCClient()
    print(f"IDC data version: {getattr(c, 'idc_version', '?')}")

    df = c.index
    sub = df[df.SeriesInstanceUID.isin(SERIES_UIDS)].copy()
    if len(sub) != len(SERIES_UIDS):
        found = set(sub.SeriesInstanceUID)
        missing = [u for u in SERIES_UIDS if u not in found]
        sys.exit(f"ERROR: {len(missing)} series not found in index: {missing}")

    order = {u: i for i, u in enumerate(SERIES_UIDS)}
    sub["__order"] = sub.SeriesInstanceUID.map(order)
    sub = sub.sort_values("__order")

    records = []
    for _, r in sub.iterrows():
        study = r.StudyInstanceUID
        subject = STUDY_SUBJECT.get(study)
        source = STUDY_SOURCE.get(study)
        if subject is None or source is None:
            sys.exit(f"ERROR: no subject/source assigned for study {study}")
        new_name = f"26CN^EXT_{PARTICIPANT}_from_{source}_{subject}"
        records.append({
            "index": int(r.__order) + 1,
            "collection_id": r.collection_id,
            "Modality": r.Modality,
            "sop_class_name": r.get("sop_class_name", ""),
            "SOPClassUID": r.get("SOPClassUID", ""),
            "transfer_syntax_name": r.get("transfer_syntax_name", ""),
            "TransferSyntaxUID": r.get("TransferSyntaxUID", ""),
            "SeriesDescription": r.get("SeriesDescription", ""),
            "instanceCount": int(r.instanceCount),
            "series_size_MB": round(float(r.series_size_MB), 3),
            "SeriesInstanceUID": r.SeriesInstanceUID,
            "StudyInstanceUID": study,
            "original_PatientID": r.PatientID,
            "subject": subject,
            "source_scanner": source,
            "new_PatientName": new_name,
            "new_PatientID": f"{PARTICIPANT}-EXT-{subject}",
            "is_fluorescence_study": study == FLUORESCENCE_STUDY,
            "license": r.get("license_short_name", ""),
        })

    os.makedirs(OUT, exist_ok=True)

    meta = {
        "idc_data_version": getattr(c, "idc_version", "?"),
        "participant": PARTICIPANT,
        "naming_convention": "26CN^EXT_<participant>_from_<source>_<subject> (converted external images)",
        "role": "Evidence Creator (external images + annotations, converted from vendor formats to DICOM)",
        "n_objects": len(records),
        "total_size_MB": round(sum(x["series_size_MB"] for x in records), 3),
        "objects": records,
    }
    with open(os.path.join(OUT, "wg26_selection.json"), "w") as f:
        json.dump(meta, f, indent=2)

    with open(os.path.join(OUT, "wg26_series.txt"), "w") as f:
        for u in SERIES_UIDS:
            f.write(u + "\n")

    with open(os.path.join(OUT, "wg26_series_core.txt"), "w") as f:
        for x in records:
            if not x["is_fluorescence_study"]:
                f.write(x["SeriesInstanceUID"] + "\n")

    with open(os.path.join(OUT, "wg26_identity_map.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["idx", "collection", "modality", "subject", "source_scanner",
                    "new_PatientName", "new_PatientID",
                    "StudyInstanceUID", "SeriesInstanceUID",
                    "size_MB", "instances", "transfer_syntax"])
        for x in records:
            w.writerow([x["index"], x["collection_id"], x["Modality"], x["subject"],
                        x["source_scanner"], x["new_PatientName"], x["new_PatientID"],
                        x["StudyInstanceUID"], x["SeriesInstanceUID"],
                        x["series_size_MB"], x["instanceCount"], x["transfer_syntax_name"]])

    print(f"Wrote {len(records)} objects to {OUT}/wg26_selection.json")
    print(f"Total size: {meta['total_size_MB']/1024:.2f} GB "
          f"(core subset excludes {FLUORESCENCE_STUDY[:24]}... fluorescence study)")


if __name__ == "__main__":
    main()
