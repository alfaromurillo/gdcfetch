# gdcfetch

**Search, browse, and download data from the NCI Genomic Data Commons (GDC)**

## Why this exists

The GDC hosts TCGA and other cancer genomics programs, but the only
official Python-facing tooling is `gdc-client` (download-only, no
search) and a page of example `requests` snippets in the docs — no
library handles pagination, retries, manifest generation, or "what
data actually exists for this project" in one place. `gdcfetch`
fills that gap.

It grew out of a concrete need: downloading every mutation-call file
for a cancer type shouldn't require knowing GDC's exact controlled
vocabulary (`data_type="Masked Somatic Mutation"`,
`workflow_type="Aliquot Ensemble Somatic Variant Merging and
Masking"`) up front. `gdcfetch` ships that vocabulary as named
presets, and a `browse` command for everything it doesn't have a
preset for yet.

## Installation

```bash
pip install gdcfetch
```

or from source:

```bash
git clone https://github.com/alfaromurillo/gdcfetch.git
cd gdcfetch
pip install -e ".[dev]"
```

## Quick start

```bash
gdcfetch presets
gdcfetch browse TCGA-BRCA
gdcfetch download TCGA-BRCA --preset somatic-mutations --dest brca_maf/
```

or from Python:

```python
from gdcfetch import search_files, download_files

hits = search_files("TCGA-BRCA", data_type="Masked Somatic Mutation",
                    workflow_type="Aliquot Ensemble Somatic Variant "
                                  "Merging and Masking")
download_files(hits, "brca_maf/")
```

## The mental model

Three layers, from most to least opinionated:

1. **Presets** (`gdcfetch presets`) — "I know what I want by name"
   (mutation calls, copy number, gene expression, ...). Fastest
   path, no GDC vocabulary required.
2. **Browse** (`gdcfetch browse PROJECT`) — "I don't know what's
   available yet." Lists every data category, data type, and
   experimental strategy GDC has for a project, with file counts,
   so you can discover the exact string to filter on before writing
   a query.
3. **Search** (`gdcfetch search PROJECT --data-type "..."`) — full
   control once you know (from a preset, from browsing, or from the
   [GDC data dictionary](https://docs.gdc.cancer.gov/Data_Dictionary/viewer/))
   exactly what you're after.

A fourth, separate concept — **supplementary datasets**
(`gdcfetch atac PROJECT`) — covers data GDC serves but doesn't index
in search at all (see below).

## Getting mutation calls for signature analysis

This is the workflow the tool was built around. Somatic point
mutations, double-substitutions, and short indels — the raw material
for COSMIC's SBS, DBS, and ID signature classes — all live in the
**same MAF file** per aliquot, distinguished only by the
`Variant_Type` column (`SNP`/`DNP`/`TNP` vs. `INS`/`DEL`). There is
no separate GDC data type to look for per signature class:

```bash
gdcfetch download TCGA-BRCA --preset somatic-mutations --dest brca_maf/
```

Copy number (CN) and structural variant (SV) signatures need
different, genuinely separate data:

| Signature class | Preset | Data type | Access |
|---|---|---|---|
| SBS, DBS, ID | `somatic-mutations` | Masked Somatic Mutation | open |
| CN | `masked-copy-number-segments` | Masked Copy Number Segment | open |
| CN (per-gene) | `gene-level-copy-number` | Gene Level Copy Number | open |
| CN (allele-specific) | `allele-specific-copy-number` | Allele-specific Copy Number Segment | open |
| SV | `structural-variants` | Structural Rearrangement | **controlled** |

**Structural variants are the one case where `download_files` won't
just work without extra setup** — `Structural Rearrangement` calls
(Manta/SvABA) are controlled-access on GDC. `search_files` lists
them with no authorization needed, but downloading the bytes
requires a dbGaP data-access authorization and a GDC token:

```bash
# after getting dbGaP access and downloading your token from
# https://portal.gdc.cancer.gov (user icon -> Download Token)
gdcfetch download TCGA-BRCA --preset structural-variants \
    --dest brca_sv/ --token-file gdc-user-token.txt
```

```python
from gdcfetch import authenticated_session, download_files, load_token, search_files

session = authenticated_session(load_token("gdc-user-token.txt"))
hits = search_files("TCGA-BRCA", data_type="Structural Rearrangement",
                    access="controlled")
download_files(hits, "brca_sv/", session=session)
```

The token only proves to GDC that *you* have an approved dbGaP
authorization — `gdcfetch` doesn't grant access to anything on its
own.

Run `gdcfetch presets` any time to see this table with descriptions
kept next to the code (and re-verify a preset still matches reality
with `gdcfetch browse PROJECT --data-category "..."`, since GDC
occasionally reprocesses data through new pipeline versions).

## Getting the two TCGA covariates

If you're here from
[sigmutselcovs](https://github.com/alfaromurillo/sigmutselcovs) —
these are the two TCGA-sourced covariates it builds, and both are
reachable through this tool:

**Gene expression** — a normal, searchable preset:

```bash
gdcfetch download TCGA-BRCA --preset gene-expression --dest brca_gexp/
gdcfetch manifest TCGA-BRCA --preset gene-expression -o brca_gexp_manifest.txt
```

**ATAC-seq (chromatin accessibility)** — this is the interesting
case, and the reason `supplementary.py` exists. Querying GDC's
normal search index for `experimental_strategy=ATAC-Seq` only turns
up controlled-access raw BAMs. The open-access, analysis-ready
signal tracks (Corces et al. 2018) were deposited as one fixed
tarball per cancer type, tied to the publication rather than indexed
as a searchable dataset — `browse`/`search` genuinely cannot find
them, no matter how you phrase the filter. `gdcfetch` ships the
verified UUID for each of the 23 TCGA types that have this data
(confirmed live against the GDC API, 2026-08):

```bash
gdcfetch atac BRCA --dest brca_atac.tgz
```

```python
from gdcfetch import tcga_atac_available, download_tcga_atac

if tcga_atac_available("OV"):
    download_tcga_atac("OV", "ov_atac.tgz")
else:
    print("no ATAC-seq for this type")  # true for OV and 9 others
```

## Finding a project

GDC hosts more than TCGA — TARGET, CPTAC, MMRF, ALCHEMIST, and about
two dozen other programs, 93 projects in total. If you don't already
know the project code:

```bash
gdcfetch projects              # all 93
gdcfetch projects --program TCGA   # just the 33 TCGA cancer types
gdcfetch projects --site lung             # substring match on primary_site
gdcfetch projects --disease-type neoplasms
gdcfetch projects --strategy WGS --program TCGA
```

`--site` and `--disease-type` look like they'd overlap but don't —
`primary_site` is *where* the disease is (e.g. "Bronchus and lung"),
`disease_type` is *what* it is (e.g. "Adenomas and Adenocarcinomas").
`--strategy` matches against the project's available experimental
strategies (RNA-Seq, WGS, ATAC-Seq, ...). All three are
case-insensitive substring matches, applied client-side, and combine
with each other and with `--program`.

```python
from gdcfetch import list_projects

tcga = list_projects(program="TCGA")
lung = list_projects(site="lung")
wgs_tcga = list_projects(program="TCGA", strategy="WGS")
```

## Exploring an unfamiliar project

```bash
$ gdcfetch browse TCGA-STAD
data_categories:
  simple nucleotide variation: 18432
  copy number variation: 9812
  ...
data_types:
  Masked Somatic Mutation: 812
  Copy Number Segment: 2104
  ...
experimental_strategies:
  WXS: 14203
  ATAC-Seq: 40
  ...
```

Narrow to one category before deciding what to filter on:

```bash
gdcfetch browse TCGA-STAD --data-category "structural variation"
```

From Python, `describe_project` returns the same three dictionaries
for programmatic use.

## CLI reference

| Command | Purpose |
|---|---|
| `gdcfetch presets` | List named presets with descriptions |
| `gdcfetch projects [--program NAME] [--site TEXT] [--disease-type TEXT] [--strategy TEXT]` | List all GDC projects, optionally filtered |
| `gdcfetch browse PROJECT [--data-category ...]` | List available data categories/types/strategies |
| `gdcfetch search PROJECT [--preset NAME \| --data-type ...]` | List matching files |
| `gdcfetch download PROJECT [...] --dest DIR` | Download matching files |
| `gdcfetch manifest PROJECT [...] -o FILE` | Write a `gdc-client`-compatible manifest |
| `gdcfetch atac PROJECT --dest FILE` | Download the TCGA ATAC-seq tarball for one cancer type |

`search`/`download`/`manifest` all accept the same filter flags:
`--preset`, or any combination of `--data-type`, `--data-category`,
`--experimental-strategy`, `--workflow-type`, `--access`.

## Python API reference

| Function | Purpose |
|---|---|
| `search_files(project, **filters)` | Paginated search; returns a list of file-metadata dicts |
| `download_files(hits, dest)` | Parallel, resumable download of search results into `<dest>/<file_id>/<file_name>` |
| `download_by_uuid(uuid, dest)` | Download any single `/data/<uuid>` blob directly |
| `get_data_size(uuid)` | Byte size of a blob via a 1-byte ranged GET, without downloading it |
| `list_projects(program=None)` | List all GDC projects, or just one program |
| `describe_project(project)` / `list_data_types(project)` / ... | Faceted browsing within a project |
| `list_presets()` / `get_preset(name)` | Inspect the preset registry |
| `write_manifest(hits, path)` | `gdc-client`-format manifest |
| `write_sample_sheet(hits, path)` | GDC Data Portal-format sample sheet |
| `tcga_atac_available(project)` / `download_tcga_atac(project, dest)` | The ATAC-seq shortcut above |
| `load_token(path)` / `authenticated_session(token)` | Controlled-access downloads (see above) |

All of `search_files`, `download_files`, `download_by_uuid`, and
`get_data_size` accept an optional `session: requests.Session` for
testing or connection reuse across many calls.

## Design notes

- **Idempotent, resumable downloads.** Every download streams to a
  `.part` file and renames atomically on success, so an interrupted
  transfer never leaves a truncated file at the destination; a
  rerun only refetches what's missing or incomplete.
- **Retries survive transient failures without losing a whole
  batch.** GDC occasionally 500s on an individual file in an
  otherwise healthy download; each file gets its own retry with
  backoff, and `download_files` reports only the files that never
  succeeded after retries — the rest of a large batch isn't held
  hostage by one bad file.
- **`HEAD /data/<uuid>` returns 400.** Use a 1-byte ranged `GET`
  instead (`get_data_size` does this) — it returns the true size via
  `Content-Range` for the cost of one byte, and works even for blobs
  that aren't indexed in `/files` at all.

## Related packages

- [sigmutsel](https://github.com/alfaromurillo/sigmutsel) — mutation
  rate estimation and selection inference; its MAF downloader is a
  natural future consumer of this package.
- [sigmutselcovs](https://github.com/alfaromurillo/sigmutselcovs) —
  tissue-specific covariate matrices for sigmutsel; the project this
  client was extracted from.

## License

MIT License — see LICENSE file for details.

## Contributing

```bash
pip install -e ".[dev]"
pytest
black src/ tests/
ruff check src/ tests/ --fix
```

Network-marked tests are deselected by default; most of the suite
runs against mocked HTTP with no external calls. Please use the
GitHub issue tracker for bugs or feature requests.
