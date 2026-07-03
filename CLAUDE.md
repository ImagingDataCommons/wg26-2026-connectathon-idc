# CLAUDE.md — WG-26 2026 Connectathon IDC Submission (working notes)

Project working memory for preparing the NCI Imaging Data Commons (IDC)
contribution to the **DICOM WG-26 Digital Pathology Connectathon 2026**.
Read this first; it records decisions and conventions not obvious from the code.

## What we are doing
Contributing a curated set of **11 DICOM slide-microscopy objects** from IDC
(v24) — brightfield WSI in four transfer syntaxes, a multiplexed-IF fluorescence
series + its Advanced Blending presentation state, and two bulk-annotation
objects — as reference/test material for the Connectathon. Pipeline:
1. **Download** the selected series from IDC.
2. **Re-identify** them per the Connectathon naming convention.
3. **Validate** (`dciodvfy -profile WG26SP2025`, `dcentvfy`).
4. **Submit** to participating archives via C-STORE (and/or STOW-RS).

## Key decisions (rationale)
- **Role = Evidence Creator, "external images".** IDC is not a scanner or LIS;
  it brings pre-existing public WSI + annotations. Per the Technical
  Requirements this is the reserved `26CN^EXT_...` path.
- **Converted external images.** Every SM was converted to DICOM from a vendor
  format (ModelName e.g. "Aperio converted by com.pixelmed.convert.TIFFToDicom"),
  so the **converted** form of the EXT convention applies:
  **PatientName = `26CN^EXT_IDC_from_<source>_<subject>`**, where `<source>` is
  the original scanner vendor from the metadata. **PatientID = `IDC-EXT-<subject>`**.
  Assigned **per study** (see `data/manifest/wg26_identity_map.csv`); all objects
  of a study (image + its annotation / presentation state) get the **same**
  Patient Name & ID — hard requirement for annotations.
  Subjects/sources: FL01→RareCyte (htan_hms FL), HE01/HE02→Aperio, HE03→LeicaSCN400
  (htan_vanderbilt), MGG01→3DHISTECH (bonemarrow), IHC01/IHC02→Aperio, ISH01→Aperio.
  `<source>` scheme is scanner-vendor (matches the spec example
  `26CN^EXT_BetaConverterCo_from_AcmeScannerCo_ABCD`); edit `STUDY_SOURCE` in
  `00_build_selection.py` to change it.
- **All UIDs and pixel data preserved unchanged.** We only rewrite PatientName
  and PatientID (via `dcmodify`, no decode). This keeps
  image↔annotation↔presentation-state references intact, keeps annotations in
  the same StudyInstanceUID as their image (required), and preserves the
  original transfer syntaxes (the whole point of the selection). Only
  patient-level identity changes.
- **C-STORE (dcmsend) is the primary submission path; STOW-RS is fallback.**
  Reasons: every archive supports C-STORE (DPIA requires it; STOW is optional
  and some endpoints are not ready/require auth); DIMSE handles the large
  multi-instance WSI (esp. the 52 GB FL series) more robustly than large HTTP
  multipart bodies; plaintext DIMSE avoids Google OAuth2 / Visage JWT / TLS
  setup. Use STOW where DIMSE ports are firewalled or an archive prefers it.
- **`dcmsend --decompress-never`** — preserves the stored transfer syntax.
  dcmsend's default (`--decompress-lossless`) would silently decompress the
  JPEG 2000 Lossless series if a peer's accepted context lacks it; `-dn` stores
  as-is or fails visibly. Calling **AE Title = `IDC`**. Per-archive open-vs-
  whitelisting plan: `SUBMISSION_TARGETS.md`.
- **WSI conformance remediation (`03_fix_wsi.py`).** The IDC-converted SM
  objects (all except the Mirax-converted bone-marrow) fail `-profile WG26SP2025`
  with **pre-existing** errors (confirmed on the pristine download): missing
  Type-1 `SpecimenTypeCodeSequence`, `PositionReferenceIndicator` ≠ SLIDE_CORNER,
  and `SliceThickness`/`ImagedVolumeDepth` = 0. `03_fix_wsi.py` fixes only what's
  wrong, only on WSI objects, preserving UIDs/pixels. **Caveat:**
  SliceThickness/ImagedVolumeDepth are set to a **nominal 3 µm placeholder** (the
  source recorded 0 — not a measured value); flag to the data owner / PM. The
  annotations already validate clean; the Advanced Blending **PR is not covered**
  by the WG26SP2025 profile (WSI+ANN only) — fluorescence sub-experiment item.
- **Consistency normalization (`04_fix_consistency.py`).** `dcentvfy` found two
  pre-existing artifacts (NOT patient/study identity — that was always consistent):
  (a) per-instance `DeviceSerialNumber` GUIDs within the htan_hms FL and tcga_luad
  SM series → normalized to one value per series; (b) the tcga_luad annotation's
  `OtherClinicalTrialProtocolIDsSequence` (its dataset DOI, absent on the image)
  → removed from the annotation. After steps 03+04, `dciodvfy` (WSI+ANN) and
  `dcentvfy` both report zero findings.

## Repo layout
```
docs/     requirements (technical, logistic), network-config xlsx, selection md
scripts/  00_build_selection.py  -> data/manifest/*  (identity table, source of truth)
          01_download.py         -> data/idc_original/   (pristine)
          02_modify_dicom.py     -> data/submission/     (re-identified copy)
          03_fix_wsi.py          edits data/submission/  (WSI IOD conformance)
          04_fix_consistency.py  edits data/submission/  (dcentvfy consistency)
          05_validate.sh         -> data/validation/     (dciodvfy/dcentvfy logs)
          06_submit_cstore.py    (dcmsend, primary)
          07_submit_stow.py      (STOW-RS, fallback)
          08_verify_submission.py (QIDO-RS: confirm what landed vs the manifest)
          archives.json          (archive STORE endpoints + contacts, parsed from xlsx/docs)
data/     manifest/, idc_original/, submission/, validation/
.venv/    uv-managed (Python 3.12); see requirements.txt
```

## Environment / commands
- **Use `uv`** for the venv (system pip is PEP-668 blocked):
  `uv venv --python 3.12 .venv && uv pip install -r requirements.txt`
- Run scripts with `.venv/bin/python scripts/NN_*.py`.
- CLI tools present: `idc`, `s5cmd`, `dcmsend`/`dcmodify`/`dcmdump` (dcmtk).
  **Validation MUST use `dicom3tools/dciodvfy` (in-repo)** — it has the
  `WG26SP2025WSI`/`WG26SP2025ANN` IOD definitions. The `~/bin/dciodvfy` is older
  and reports a bogus "Information Object Not found" for the WG26 profile. The
  validate script auto-prefers the in-repo build (override via `$DCIODVFY`).
- Typical flow:
  ```
  .venv/bin/python scripts/00_build_selection.py        # (re)build identity table
  .venv/bin/python scripts/01_download.py --full         # all 11 (~55 GB)
  .venv/bin/python scripts/02_modify_dicom.py            # -> data/submission
  .venv/bin/python scripts/03_fix_wsi.py                 # WSI IOD conformance fixes
  .venv/bin/python scripts/04_fix_consistency.py         # dcentvfy consistency fixes
  scripts/05_validate.sh                                 # must be 0 errors
  .venv/bin/python scripts/06_submit_cstore.py <archive> # e.g. proscia
  .venv/bin/python scripts/08_verify_submission.py <archive>  # confirm it landed
  ```
- Download scopes: `--core` (9 objects, ~3.3 GB), `--full` (11, ~55 GB),
  `--uids ...`. The 52 GB fluorescence study is `--full`-only.

## Confirmed with organizers (2026-07-03)
- **Fluorescence in scope** — the multiplexed-IF series + Advanced Blending PR
  are confirmed in scope for 2026; all 11 objects submitted.
- **Participant token `IDC`** and **calling AE Title `IDC`** confirmed.
- **Converted-image naming** applies (SM were converted from vendor formats).

## Open items
- **Whitelisting**: register calling AE Title `IDC` + our source IP with the
  archives that need it (Sectra, AGFA, Visage, Google adapter). Obtain OAuth2
  token (Google STOW) / JWT (Visage) if using their DICOMweb. See
  `SUBMISSION_TARGETS.md`.
- **`<source>` token scheme**: currently scanner-vendor. Confirm acceptable, or
  switch (e.g. collection-based) via `STUDY_SOURCE` in `00_build_selection.py`.
- **UID collision**: archives may already hold the public IDC copy (same
  StudyInstanceUID) — our objects differ only in Patient Name/ID. Flag to PM.

## Timeline (submission-relevant)
- **18 Jul 2026** — all images/annotations submitted for round-1 testing.
- 24 Jul round-1 ends; 3 Aug round-2 begins; **14 Aug** final submission deadline.
- 16–18 Oct — results presented at Pathology Visions (San Diego).
- Contacts: Skip Kennedy <skip.l.kennedy@kp.org>, David Clunie <dclunie@dclunie.com>.
  Announcements via Google Group `wg26-demonstrations`.
- All artifacts released **CC BY 4.0** (predicate for participation).
