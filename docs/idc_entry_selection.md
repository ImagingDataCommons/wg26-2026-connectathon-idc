# DICOM WG-26 Connectathon 2026 — Slide Microscopy Test Dataset (from NCI Imaging Data Commons)

This document describes a small, curated set of DICOM slide microscopy images, a presentation state, and bulk annotations selected from the NCI Imaging Data Commons (IDC) for submission to the [DICOM WG-26 Digital Pathology Connectathon 2026](https://dicom-wg26-connectathons.github.io/2026/). It records *what* was selected, *why*, and *how to retrieve it*.

## *1\. Summary*

- **Objects:** 11 DICOM series (slide microscopy images, one Advanced Blending presentation state, and bulk annotation objects)  
- **Total size:** \~55.3 GB  
- **Source:** NCI Imaging Data Commons, data release **v24** (queried via the `idc-index` Python package / DuckDB index)  
- **License:** every object is **CC BY 4.0**, which satisfies the Connectathon requirement that all submitted artifacts be shareable under CC-BY  
- **Selection principle:** for each requirement, the *smallest representative series* in IDC that still clearly exemplifies the target feature, to keep the dataset lightweight

## *2\. Selection methodology*

The dataset was assembled to cover four orthogonal requirements. All counts and sizes were obtained by querying the IDC v24 index (`sm_index`, `sm_instance_index`, `ann_index`, `ann_group_index`, and the main `index`).

### **2.1 Coverage of DICOM transfer syntaxes**

IDC slide microscopy uses four transfer syntaxes for the VOLUME (pyramid) frames. The dataset includes a brightfield example of each, choosing the smallest qualifying series:

- **JPEG Baseline** (`1.2.840.10008.1.2.4.50`) — the dominant brightfield encoding in IDC  
- **JPEG 2000 lossy** (`1.2.840.10008.1.2.4.91`)  
- **JPEG 2000 Lossless** (`1.2.840.10008.1.2.4.90`) — the rarest; the smallest such series in IDC is still \~736 MB, so this is unavoidably the largest brightfield item  
- **Explicit VR Little Endian, uncompressed** (`1.2.840.10008.1.2.1`) — supplied by the fluorescence series, which stores its channels uncompressed; it therefore does double duty

### **2.2 Fluorescence image with a presentation state**

Epifluorescence imaging exists in four HTAN collections. A multiplexed immunofluorescence series from **htan\_hms** was selected together with its **Advanced Blending Presentation State** (SOP Class `1.2.840.10008.5.1.4.1.1.11.8`, ContentLabel `MULTIPLEXED_IF`), which defines how the marker channels are pseudo-colored and blended for display. The presentation state was inspected to confirm it references this image series and blends its channels (markers DNA / CD20 / CD68). htan\_hms stores each image as a single large multi-channel series, so this is the largest item in the dataset; an alternative with much smaller per-channel series (\~6 MB) exists in htan\_wustl if size becomes a concern.

### **2.3 Variety of bulk annotations**

IDC bulk annotations (ANN modality, *Microscopy Bulk Simple Annotations*, all 2D) span two distinct styles, both included:

- **Automatic POLYGON** nuclei segmentation (Pan-Cancer-Nuclei-Seg) carrying per-object **Area** measurements (µm²) — dense, algorithm-generated  
- **Manual RECTANGLE** cell-typing from a pediatric-leukemia bone-marrow slide — 35 distinct hematology cell-type / quality classes in a single compact object

Each annotation is accompanied by its source image so a viewer can render the overlay. (Note: IDC bulk annotations use only POLYGON and RECTANGLE graphic types and 2D coordinates; POINT, POLYLINE, and ELLIPSE are not present natively and would have to be derived.)

### **2.4 Non-H\&E brightfield stains**

Because the Connectathon places no restriction on stain type, three non-H\&E brightfield stains were added to broaden visual variety, again choosing small representatives:

- **Immunohistochemistry, nuclear** (TTF-1)  
- **Immunohistochemistry, membranous** (CD20)  
- **Chromogenic in-situ hybridization** (EBER probe) — a non-antibody stain class

Combined with the H\&E and Giemsa material already present, the set spans H\&E, two IHC patterns, ISH, a Romanowsky/Giemsa hematology stain, and fluorescence.

## *3\. Complete sample inventory*

| \# | Role | Object | Collection | Stain / Illumination | Transfer syntax | Size |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| 1 | Fluorescence sample; also exemplifies uncompressed transfer syntax | SM | htan\_hms | Epifluorescence — multiplexed IF (\~24-marker panel) | Explicit VR Little Endian — uncompressed | 52.0 GB |
| 2 | Advanced Blending presentation state for the fluorescence series | PR | htan\_hms | — (presentation state) | Explicit VR Little Endian — uncompressed | 0.2 MB |
| 3 | Transfer syntax: JPEG Baseline | SM | hcmi\_cmdc | Brightfield — H\&E | JPEG Baseline (Process 1\) — lossy 8-bit | 3.8 MB |
| 4 | Transfer syntax: JPEG 2000 lossy; source slide for the polygon nuclei annotation | SM | tcga\_luad | Brightfield — H\&E | JPEG 2000 — lossy | 14.1 MB |
| 5 | Transfer syntax: JPEG 2000 Lossless | SM | htan\_vanderbilt | Brightfield — H\&E | JPEG 2000 Lossless | 736.4 MB |
| 6 | Bulk annotation: POLYGON, automatic, with per-object Area measurements (5,682 nuclei) | ANN | tcga\_luad | — (annotation) | Explicit VR Little Endian — uncompressed | 1.0 MB |
| 7 | Bulk annotation: RECTANGLE, manual, 35 cell-type classes (782 boxes) | ANN | bonemarrowwsi\_pediatricleukemia | — (annotation) | Explicit VR Little Endian — uncompressed | 0.1 MB |
| 8 | Source slide for the rectangle annotation; also a non-H\&E hematology stain | SM | bonemarrowwsi\_pediatricleukemia | Brightfield — May-Grünwald Giemsa | JPEG Baseline (Process 1\) — lossy 8-bit | 2.5 GB |
| 9 | Non-H\&E brightfield stain (IHC, nuclear pattern) | SM | cgci\_htmcp\_lc | Brightfield — IHC (TTF-1, nuclear) | JPEG 2000 — lossy | 6.8 MB |
| 10 | Non-H\&E brightfield stain (IHC, membranous pattern) | SM | cgci\_blgsp | Brightfield — IHC (CD20, membranous) | JPEG 2000 — lossy | 21.3 MB |
| 11 | Non-H\&E brightfield stain (in-situ hybridization) | SM | cgci\_htmcp\_dlbcl | Brightfield — ISH (EBER probe) | JPEG 2000 — lossy | 69.3 MB |

## *4\. Identifiers and preview links*

Each entry lists the `SeriesInstanceUID` (stable IDC identifier) and a Slim viewer link. Annotation and presentation-state links open within their source-image study, so they render in context.

1. **htan\_hms / SM** — `1.3.6.1.4.1.5962.99.1.2351537988.1691156399.1655913979716.4.0`  
   [Preview in Slim viewer](https://viewer.imaging.datacommons.cancer.gov/slim/studies/2.25.254901417575324832540235892437527774975/series/1.3.6.1.4.1.5962.99.1.2351537988.1691156399.1655913979716.4.0)  
2. **htan\_hms / PR** — `1.2.826.0.1.3680043.10.511.3.32217822852247924170142261734082901`  
   [Preview in Slim viewer](https://viewer.imaging.datacommons.cancer.gov/slim/studies/2.25.254901417575324832540235892437527774975/series/1.2.826.0.1.3680043.10.511.3.32217822852247924170142261734082901)  
3. **hcmi\_cmdc / SM** — `1.3.6.1.4.1.5962.99.1.3052275118.437477262.1772578833838.4.0`  
   [Preview in Slim viewer](https://viewer.imaging.datacommons.cancer.gov/slim/studies/2.25.326831351899246997718579660054873448065/series/1.3.6.1.4.1.5962.99.1.3052275118.437477262.1772578833838.4.0)  
4. **tcga\_luad / SM** — `1.3.6.1.4.1.5962.99.1.1048952951.469777563.1637431525495.2.0`  
   [Preview in Slim viewer](https://viewer.imaging.datacommons.cancer.gov/slim/studies/2.25.113910498547580375599321634216516970390/series/1.3.6.1.4.1.5962.99.1.1048952951.469777563.1637431525495.2.0)  
5. **htan\_vanderbilt / SM** — `1.3.6.1.4.1.5962.99.1.2027811345.1425031706.1655590253073.4.0`  
   [Preview in Slim viewer](https://viewer.imaging.datacommons.cancer.gov/slim/studies/2.25.215244595345296939373838636406158345745/series/1.3.6.1.4.1.5962.99.1.2027811345.1425031706.1655590253073.4.0)  
6. **tcga\_luad / ANN** — `1.2.826.0.1.3680043.10.511.3.66626547635466777954373480481638649`  
   [Preview in Slim viewer](https://viewer.imaging.datacommons.cancer.gov/slim/studies/2.25.113910498547580375599321634216516970390/series/1.2.826.0.1.3680043.10.511.3.66626547635466777954373480481638649)  
7. **bonemarrowwsi\_pediatricleukemia / ANN** — `1.2.826.0.1.3680043.10.511.3.75156072263858645925658754886035975`  
   [Preview in Slim viewer](https://viewer.imaging.datacommons.cancer.gov/slim/studies/1.2.826.0.1.3680043.8.498.37689962845386577627578641862732406672/series/1.2.826.0.1.3680043.10.511.3.75156072263858645925658754886035975)  
8. **bonemarrowwsi\_pediatricleukemia / SM** — `1.2.826.0.1.3680043.8.498.19212570839483117674134243789833677578`  
   [Preview in Slim viewer](https://viewer.imaging.datacommons.cancer.gov/slim/studies/1.2.826.0.1.3680043.8.498.37689962845386577627578641862732406672/series/1.2.826.0.1.3680043.8.498.19212570839483117674134243789833677578)  
9. **cgci\_htmcp\_lc / SM** — `1.3.6.1.4.1.5962.99.1.3836604227.2006969735.1773363162947.4.0`  
   [Preview in Slim viewer](https://viewer.imaging.datacommons.cancer.gov/slim/studies/2.25.62097431654635660667506156467264852146/series/1.3.6.1.4.1.5962.99.1.3836604227.2006969735.1773363162947.4.0)  
10. **cgci\_blgsp / SM** — `1.3.6.1.4.1.5962.99.1.3888926996.1445722942.1773415485716.4.0`  
    [Preview in Slim viewer](https://viewer.imaging.datacommons.cancer.gov/slim/studies/2.25.35449169900502839636017945370968954585/series/1.3.6.1.4.1.5962.99.1.3888926996.1445722942.1773415485716.4.0)  
11. **cgci\_htmcp\_dlbcl / SM** — `1.3.6.1.4.1.5962.99.1.2962403854.296721353.1772488962574.4.0`  
    [Preview in Slim viewer](https://viewer.imaging.datacommons.cancer.gov/slim/studies/2.25.336444473395720978044870396873829787454/series/1.3.6.1.4.1.5962.99.1.2962403854.296721353.1772488962574.4.0)

## *5\. Connectathon compliance notes*

- **Validation gate.** Every image and annotation object is validated by the project manager with `dciodvfy -profile WG26SP2025`; self-supplied data must report **zero errors**. Validate each series locally before submission.

- **Brightfield WSI restrictions.** The brightfield items (H\&E, IHC, ISH, Giemsa) are single-optical-path RGB images and are expected to fit the brightfield-oriented profile; confirm `TILED_FULL`, single optical path, and single focal plane via `dciodvfy`.

- **Fluorescence caveat.** The multiplexed-IF series and its Advanced Blending presentation state fall outside the brightfield-oriented profile (multiple optical paths, non-RGB, and a distinct SOP class). Confirm with the organizers that fluorescence and presentation-state objects are in scope for 2026 before relying on these two items. If excluded, also replace the uncompressed transfer-syntax exemplar, since the fluorescence series was covering it.

- **Annotation conformance.** Annotations conform to the *Microscopy Bulk Simple Annotations* SOP Class, use 2D coordinates, and are stored under the same `StudyInstanceUID` as their source image in a separate series — matching the Connectathon's annotation requirements.

- **Submission mechanism.** Objects are stored into participating archives via C-STORE / STOW-RS (or handed to the project manager as Part 10 files); notify the project manager by email describing each submission.

## *6\. How to download*

All series can be retrieved with the `idc-index` command-line tool using the companion manifest (`wg26_idc_manifest.s5cmd`):

pip install idc-index

idc download-from-manifest \--manifest-file wg26\_idc\_manifest.s5cmd \--download-dir ./wg26\_data

Files are organized as `collection_id/PatientID/StudyInstanceUID/Modality_SeriesInstanceUID`. To download everything *except* the large fluorescence and bone-marrow slides, remove their two `cp` lines from the manifest first.

## *7\. Licensing*

All selected objects are released under the Creative Commons Attribution 4.0 International (CC BY 4.0) license in IDC. Attribution should credit the NCI Imaging Data Commons and the originating collections (HTAN, TCGA, HCMI, CGCI, and the pediatric-leukemia bone-marrow WSI collection).

