# DICOM WG-26 Connectathon 2026 — IDC Slide-Microscopy Submission

Toolkit and working area for contributing a curated [**NCI Imaging Data Commons
(IDC)**](https://imaging.datacommons.cancer.gov) slide-microscopy dataset to the
[DICOM WG-26 Digital Pathology Connectathon 2026](https://dicom-wg26-connectathons.github.io/2026/).

This repository downloads a small set of public DICOM whole-slide-imaging (WSI)
objects from IDC, re-identifies them to the Connectathon naming convention,
validates them against the Connectathon profile, and submits them to the
participating image archives.

> ### 🧩 Built with the IDC skill
> The data discovery, selection, and download that made this work possible were
> driven by the **[NCI Imaging Data Commons skill for AI agents](https://github.com/ImagingDataCommons/imaging-data-commons-skill)**
> — an agent-ready interface to IDC (`idc-index` + IDC MCP server) that lets an
> assistant query the 100+ TB public archive, filter to exactly the series
> needed, and pull them down. It was instrumental in curating this dataset; see
> [§8 How this repository was developed](#8-how-this-repository-was-developed).

---

## 1. What is being submitted

**11 DICOM series — 250 SOP instances across 8 studies, ~55 GB** — from IDC data
release **v24**, all licensed **CC BY 4.0** (satisfies the Connectathon
requirement that artifacts be shareable under CC-BY). The set was chosen to
exercise interoperability across transfer syntaxes, an advanced presentation
state, two annotation styles, and several stains. See
[docs/idc_entry_selection.md](docs/idc_entry_selection.md) for the full
selection rationale.

| # | Role in the set | Modality | Collection | Subject | Transfer syntax | Size |
|--:|-----------------|:--------:|------------|:-------:|-----------------|-----:|
| 1 | Fluorescence (multiplexed IF); uncompressed exemplar | SM | htan_hms | FL01 | Explicit VR LE (uncompressed) | 52.0 GB |
| 2 | Advanced Blending presentation state for #1 | PR | htan_hms | FL01 | Explicit VR LE | 0.2 MB |
| 3 | Transfer syntax: JPEG Baseline (H&E) | SM | hcmi_cmdc | HE01 | JPEG Baseline | 3.8 MB |
| 4 | Transfer syntax: JPEG 2000 lossy (H&E); source of #6 | SM | tcga_luad | HE02 | JPEG 2000 lossy | 14.1 MB |
| 5 | Transfer syntax: JPEG 2000 Lossless (H&E) | SM | htan_vanderbilt | HE03 | JPEG 2000 Lossless | 736.4 MB |
| 6 | Bulk annotation: POLYGON, automatic (5,682 nuclei) | ANN | tcga_luad | HE02 | Explicit VR LE | 1.0 MB |
| 7 | Bulk annotation: RECTANGLE, manual (35 classes) | ANN | bonemarrowwsi_pediatricleukemia | MGG01 | Explicit VR LE | 0.1 MB |
| 8 | Source slide for #7; Giemsa hematology stain | SM | bonemarrowwsi_pediatricleukemia | MGG01 | JPEG Baseline | 2.5 GB |
| 9 | Non-H&E: IHC nuclear (TTF-1) | SM | cgci_htmcp_lc | IHC01 | JPEG 2000 lossy | 6.8 MB |
| 10 | Non-H&E: IHC membranous (CD20) | SM | cgci_blgsp | IHC02 | JPEG 2000 lossy | 21.3 MB |
| 11 | Non-H&E: ISH (EBER probe) | SM | cgci_htmcp_dlbcl | ISH01 | JPEG 2000 lossy | 69.3 MB |

The **~52 GB fluorescence pair (#1, #2)** dominates the total; the other **9
series total ~3.3 GB**. Fluorescence is **confirmed in scope for 2026** by the
organizers, so all 11 series are submitted.

Each numbered row above is one DICOM **series** (a series may hold many SOP
instances — e.g. row #1 is 216 instances of the fluorescence WSI pyramid);
together the 11 series comprise **250 SOP instances**. Where this repo says "11
objects" it means these 11 series.

The authoritative machine-readable table (with the exact identity assignments)
is generated to `data/manifest/wg26_selection.json` /
`wg26_identity_map.csv`.

---

## 2. How the objects are prepared

**Role.** IDC participates as an **Evidence Creator supplying "external
images"** — pre-existing public WSI plus annotations. This maps to the reserved
`26CN^EXT_...` naming convention in the Technical Requirements.

Every SM image was **converted to DICOM from a proprietary vendor format**
(the ModelName reads e.g. *"Aperio converted by com.pixelmed.convert.TIFFToDicom"*),
so the **converted external-image** naming convention applies.

**Re-identification (only change made to the data):**
- `PatientName` → `26CN^EXT_IDC_from_<source>_<subject>`
  (e.g. `26CN^EXT_IDC_from_Aperio_HE02`), where `<source>` is the original
  scanner vendor recorded in the metadata (Aperio, LeicaSCN400, RareCyte,
  3DHISTECH).
- `PatientID` → `IDC-EXT-<subject>`
- Assigned **per study**, so every object of a study — the image and its
  annotation or presentation state — shares the same Patient Name and ID.
  This satisfies the requirement that annotations carry the same Patient
  Name/ID (and StudyInstanceUID) as the image they reference.

**Everything else is preserved byte-for-byte:** all UIDs (Study/Series/SOP),
cross-object references, and the original encoded pixel data / transfer
syntaxes. Editing is done in place (in the submission copy) with `dcmodify`
(no pixel decode). This is why the image↔annotation↔presentation-state links
and the transfer-syntax coverage stay intact.

**WSI conformance remediation (`03_fix_wsi.py`).** Validation revealed that the
IDC-converted SM objects (all except the Mirax-converted bone-marrow slide,
which is already clean) carry **pre-existing** `-profile WG26SP2025` errors —
missing Type-1 `SpecimenTypeCodeSequence`, `PositionReferenceIndicator` ≠
`SLIDE_CORNER`, and zero `SliceThickness`/`ImagedVolumeDepth`. These are in the
original IDC data (not introduced by re-identification). `03_fix_wsi.py` repairs
only the wrong attributes on WSI objects (annotations untouched, UIDs/pixels
preserved). ⚠️ `SliceThickness`/`ImagedVolumeDepth` are set to a **nominal 3 µm
placeholder** (the source recorded 0, not a measured value) — flag to the data
owner. The **presentation state is not covered** by the WG26SP2025 profile
(WSI + ANN IODs only) and is a fluorescence sub-experiment coordination item.

**Consistency normalization (`04_fix_consistency.py`).** The `dcentvfy`
entity-consistency check (which the project manager runs across all images and
annotations) surfaced two further **pre-existing** IDC artifacts — neither
affecting Patient/Study identity, which was consistent throughout:

- **`DeviceSerialNumber` (Equipment IE):** the `htan_hms` fluorescence and
  `tcga_luad` SM series each stored a *different per-instance GUID* (217 instances
  across the two series). A series comes from one device, so all instances are
  normalized to a single value per series.
- **`OtherClinicalTrialProtocolIDsSequence` (Patient IE):** present on the
  `tcga_luad` annotation (it carried the *annotation dataset's* DOI,
  `doi:10.5281/zenodo.11099005`) but absent on the image it annotates. Because it
  does not belong on the image, it is **removed from the annotation** (adding it
  to the image would misattribute provenance). The DOI remains recoverable from
  the annotation's `Manufacturer` / `SoftwareVersions`.

After this step `dcentvfy` reports **zero findings across all 8 studies**.

---

## 3. Submission networking: C-STORE vs DICOMweb

**Recommendation: use C-STORE (DIMSE) as the primary path; keep STOW-RS as a
fallback.** For this dataset specifically:

| Factor | C-STORE (dcmsend) | STOW-RS (DICOMweb) |
|---|---|---|
| Archive support | **All** archives (DPIA requires C-STORE) | Optional; some endpoints not ready / auth-gated |
| Large multi-instance WSI (52 GB FL series) | Streams per instance in one association — robust | Large HTTP multipart bodies more fragile |
| Transfer-syntax preservation | Preserved via presentation-context negotiation | Preserved (server reads file-meta), if conformant |
| Auth / TLS setup | Plaintext DIMSE — none needed | Google OAuth2, Visage JWT, TLS certs for several |
| Firewall friendliness | Needs outbound to per-archive DIMSE ports | HTTPS/HTTP, generally friendlier |

Every archive in the network config exposes a **C-STORE SCP**; only a subset
expose a ready **STOW-RS** endpoint (AGFA and Visage have none published).
Use STOW-RS when DIMSE ports are blocked or an archive prefers it.

**Transfer-syntax fidelity:** `dcmsend` is invoked with **`--decompress-never`**
so a compressed object (notably the JPEG 2000 Lossless series) is stored exactly
as encoded, or the store fails visibly — never silently transcoded (dcmsend's
default would decompress lossless data if the peer's context lacks that syntax).

Endpoints are parsed into [scripts/archives.json](scripts/archives.json), and
the per-archive plan (open vs whitelisting-required) is in
[SUBMISSION_TARGETS.md](SUBMISSION_TARGETS.md) — **verify against the live
spreadsheet before each submission**, as endpoints change during the event.
Our calling AE Title is **`IDC`**.

---

## 4. Quickstart

```bash
# 0. Environment (uv-managed venv)
uv venv --python 3.12 .venv
uv pip install -r requirements.txt

# 1. (Re)build the identity table  ->  data/manifest/
.venv/bin/python scripts/00_build_selection.py

# 2. Download from IDC              ->  data/idc_original/
.venv/bin/python scripts/01_download.py --core      # 9 objects, ~3.3 GB
#   or  --full  (all 11, ~55 GB)  /  --dry-run  to preview

# 3. Re-identify                    ->  data/submission/
.venv/bin/python scripts/02_modify_dicom.py

# 3b. Fix pre-existing WSI conformance errors in the IDC-converted SM objects
.venv/bin/python scripts/03_fix_wsi.py

# 3c. Normalize pre-existing cross-instance consistency (dcentvfy) findings
.venv/bin/python scripts/04_fix_consistency.py

# 4. Validate (must report 0 errors). Uses the in-repo dicom3tools/dciodvfy,
#    which has the WG26SP2025 WSI/ANN IOD definitions.
scripts/05_validate.sh

# 5. Submit to an archive (C-STORE primary; --list to see keys)
.venv/bin/python scripts/06_submit_cstore.py sectra
#   fallback:
.venv/bin/python scripts/07_submit_stow.py proscia

# 6. Verify what actually landed (QIDO-RS vs the manifest; exit 0 only if all match)
.venv/bin/python scripts/08_verify_submission.py proscia
```

After a successful submission, **email the project manager** describing what
was uploaded (required of Evidence Creators).

---

## 5. Compliance checklist
- [x] All objects CC BY 4.0.
- [x] Annotations use *Microscopy Bulk Simple Annotations* SOP Class, 2D coords,
      same Study as their image.
- [x] Annotation Patient Name/ID == source image Patient Name/ID (enforced by
      per-study identity assignment).
- [x] `dciodvfy -profile WG26SP2025` reports **0 errors** for every WSI + ANN
      object after `03_fix_wsi.py` (run `scripts/05_validate.sh`; uses the
      in-repo `dicom3tools/dciodvfy`). PR is out of profile scope.
- [x] `dcentvfy` reports **0 consistency issues** across all 8 studies after
      `04_fix_consistency.py` (patient/study/series/equipment attributes agree).
- [x] Fluorescence (#1/#2) confirmed in scope for 2026.
- [x] Participant token `IDC` and calling AE Title `IDC` confirmed.
- [ ] Register calling AE Title `IDC` + our source IP with the whitelisting
      archives (see [SUBMISSION_TARGETS.md](SUBMISSION_TARGETS.md)).

See [CLAUDE.md](CLAUDE.md) for decisions, open items, and the event timeline
(key dates: **round-1 submission by 18 Jul 2026**, final by 14 Aug 2026).

---

## 6. Licensing & attribution
Two licenses apply, by content type:

- **This toolkit** (the scripts, docs, and manifests in this repository) is
  licensed **Apache-2.0** — see [LICENSE](LICENSE).
- **The DICOM data objects** downloaded from IDC and re-identified for
  submission are **CC BY 4.0** (not the code license). Per the Logistic
  Requirements, all Connectathon artifacts are shared publicly under CC-BY.

### Acknowledging IDC
Any reuse of these objects should acknowledge the NCI Imaging Data Commons:

> Fedorov, A., Longabaugh, W. J. R., Pot, D., Clunie, D. A., Pieper, S. D.,
> Gibbs, D. L., Bridge, C., Herrmann, M. D., Homeyer, A., Lewis, R., Aerts,
> H. J. W. L., Krishnaswamy, D., Thiriveedhi, V. K., Ciausu, C., Schacherer,
> D. P., Bontempi, D., Pihl, T., Wagner, U., Farahani, K., et al. (2023).
> National Cancer Institute Imaging Data Commons: Toward Transparency,
> Reproducibility, and Scalability in Imaging Artificial Intelligence.
> *RadioGraphics*, 43(12). https://doi.org/10.1148/rg.230180

### Source dataset citations
Cite the dataset each object derives from (ordered to match the table in §1).
All are CC BY 4.0. DOIs resolve to the IDC-hosted Zenodo records (the DICOM
conversions actually distributed via IDC), with the original collection given
where distinct.

- **#1–2 · FL01 · `htan_hms`** — Clunie, D., Herrmann, M. D., Clifford, W.,
  Pot, D., Wagner, U., Farahani, K., Kim, E., & Fedorov, A. (2024). *DICOM
  converted Slide Microscopy images for the HTAN-HMS collection* [Dataset].
  Zenodo. https://doi.org/10.5281/zenodo.12666872
- **#3 · HE01 · `hcmi_cmdc`** — Clunie, D., Clifford, W., & Fedorov, A. (2026).
  *HCMI-CMDC: DICOM converted whole slide images from the Human Cancer Models
  Initiative (HCMI) Cancer Model Development Center (CMDC)* [Dataset]. Zenodo.
  https://doi.org/10.5281/zenodo.17381441
- **#4 · HE02 · `tcga_luad` (WSI)** — Clunie, D., Clifford, W., Pot, D.,
  Wagner, U., Farahani, K., Kim, E., & Fedorov, A. (2024). *DICOM converted
  Slide Microscopy images for the TCGA-LUAD collection* [Dataset]. Zenodo.
  https://doi.org/10.5281/zenodo.12689915
  Original collection: Albertina, B., Watson, M., Holback, C., Jarosz, R.,
  Kirk, S., Lee, Y., Rieger-Christ, K., & Lemmerman, J. (2016). *The Cancer
  Genome Atlas Lung Adenocarcinoma Collection (TCGA-LUAD)* (Version 4)
  [Dataset]. The Cancer Imaging Archive.
  https://doi.org/10.7937/K9/TCIA.2016.JGNIHEP5
- **#5 · HE03 · `htan_vanderbilt`** — Clunie, D., Clifford, W., Pot, D.,
  Wagner, U., Farahani, K., Kim, E., & Fedorov, A. (2024). *DICOM converted
  Slide Microscopy images for the HTAN-VANDERBILT collection* [Dataset].
  Zenodo. https://doi.org/10.5281/zenodo.12690006
- **#6 · HE02 · `tcga_luad` (nuclei annotation)** — Bridge, C., Herrmann, M.,
  Clunie, D., & Fedorov, A. (2024). *Pan-Cancer-Nuclei-Seg-DICOM: DICOM
  converted Dataset of Segmented Nuclei in Hematoxylin and Eosin Stained
  Histopathology Images* [Dataset]. Zenodo.
  https://doi.org/10.5281/zenodo.11099004
- **#7–8 · MGG01 · `bonemarrowwsi_pediatricleukemia`** — Höfener, H., Kock, F.,
  Pontones, M. A., Ghete, T., Pfrang, D., Dickel, N., Kunz, M., Schacherer, D.,
  Clunie, D. A., Fedorov, A., Westphal, M., & Metzler, M. (2025).
  *BoneMarrowWSI-PediatricLeukemia: A Comprehensive Dataset of Bone Marrow
  Aspirate Smear Whole Slide Images with Expert Annotations and Clinical Data
  in Pediatric Leukemia* [Dataset]. Zenodo.
  https://doi.org/10.5281/zenodo.14933087
- **#9 · IHC01 · `cgci_htmcp_lc`** — Clunie, D., Clifford, W., & Fedorov, A.
  (2026). *CGCI-HTMCP-LC: DICOM converted whole slide images from the Cancer
  Genome Characterization Initiative (CGCI) HIV+ Tumor Molecular
  Characterization Project (HTMCP) - Lung Cancer* [Dataset]. Zenodo.
  https://doi.org/10.5281/zenodo.17381428
- **#10 · IHC02 · `cgci_blgsp`** — Clunie, D., Clifford, W., & Fedorov, A.
  (2026). *CGCI-BLGSP: DICOM converted whole slide images from the Cancer
  Genome Characterization Initiative (CGCI) - Burkitt Lymphoma Genome
  Sequencing Project (BLGSP)* [Dataset]. Zenodo.
  https://doi.org/10.5281/zenodo.17381396
- **#11 · ISH01 · `cgci_htmcp_dlbcl`** — Clunie, D., Clifford, W., & Fedorov,
  A. (2026). *CGCI-HTMCP-DLBCL: DICOM converted whole slide images from the
  Cancer Genome Characterization Initiative (CGCI) HIV+ Tumor Molecular
  Characterization Project (HTMCP) - Diffuse Large B-Cell Lymphoma* [Dataset].
  Zenodo. https://doi.org/10.5281/zenodo.17381412

Citations retrieved via the IDC citation service (`get_citations`, APA),
scoped to the 11 submitted `SeriesInstanceUID`s (not by collection, which would
also pull in unrelated derived datasets that merely share a collection, e.g.
TCGA-SBU-TIL-Maps and the BAMF AIMI segmentations). The original TCGA-LUAD TCIA
collection is added as upstream provenance — the series-scoped query returns
only the DICOM-converted record that IDC actually distributes.

## 7. Repository layout
```
docs/     The IDC selection rationale (idc_entry_selection.md). The Connectathon
          requirements, network-config spreadsheet, and per-vendor archive docs
          are NOT here — they are third-party and contain shared credentials;
          see the private companion repo (below).
scripts/  Numbered pipeline (00 build → 01 download → 02 modify → 03 fix-wsi
          → 04 fix-consistency → 05 validate → 06/07 submit → 08 verify) plus
          archives.json.
dicom3tools/  Local dciodvfy/dcentvfy build with the WG26SP2025 IOD profiles
          (git-ignored; re-obtainable — see .gitignore).
data/     manifest/ (identity table, tracked), idc_original/ (pristine download),
          submission/ (re-identified), validation/ (logs).  [git-ignored bulk]
```

### Companion repositories
This **public** repository — the toolkit, manifests, and documentation — is at
[`ImagingDataCommons/wg26-2026-connectathon-idc`](https://github.com/ImagingDataCommons/wg26-2026-connectathon-idc).

Third-party connectathon source documents and the shared run-time credentials
are archived separately, in a **private** repository:
[`imagingdatacommons/wg26-2026-connectathon-idc-private`](https://github.com/imagingdatacommons/wg26-2026-connectathon-idc-private).
This public repo hardcodes no secrets; the submission scripts read them from
`WG26_STOW_USER` / `WG26_STOW_PASSWORD` / `WG26_BEARER_TOKEN` at run time (values
recorded in the private repo's `CREDENTIALS.md`).

---

## 8. How this repository was developed

This toolkit was built through an **AI-assisted, agentic workflow**: the IDC team
directed the work and made every domain decision, while Claude Code (Anthropic's
agentic coding CLI) performed the exploration, scripting, and iterative debugging
under that direction. It is shared in that spirit — the numbered pipeline and the
decision log are meant to make the whole process inspectable and reproducible.

The work proceeded roughly as:

1. **Data discovery & selection.** Candidate series were found by querying IDC
   programmatically through the **[IDC skill](https://github.com/ImagingDataCommons/imaging-data-commons-skill)**
   (`idc-index` + the IDC MCP server), then curated to cover the interoperability
   dimensions the Connectathon needs — four transfer syntaxes, two annotation
   styles, an advanced presentation state, and a range of stains. The rationale
   is written up in [docs/idc_entry_selection.md](docs/idc_entry_selection.md).
2. **Pipeline authoring.** The `00`–`07` scripts were written and refined
   incrementally; each step does one narrow, reversible thing and preserves
   UIDs and pixel data.
3. **Validation-driven remediation.** Running the WG26SP2025 validators on the
   *pristine* IDC download surfaced the pre-existing conformance and consistency
   issues (see §2); each was diagnosed, confirmed as pre-existing (not introduced
   by re-identification), and repaired with the smallest possible change
   (`03_fix_wsi.py`, `04_fix_consistency.py`).
4. **Submission & verification.** Objects are stored to each archive (C-STORE /
   STOW-RS) and then independently confirmed via QIDO-RS; progress is tracked in
   [SUBMISSION_STATUS.md](SUBMISSION_STATUS.md).

Human domain experts reviewed and authorized all substantive choices — the
naming convention, the remediation approach (including the flagged nominal
`SliceThickness` placeholder), and every archive submission. **[CLAUDE.md](CLAUDE.md)**
is the running decision log (what was decided and *why*); together with the git
history and the numbered scripts it forms the reproducible record of how the
dataset was produced.
