# Developing gdcfetch

Internals reference for anyone modifying this codebase.

## Setup

```bash
pip install -e ".[dev]"
pytest
```

## Module map

| Module | Role |
|--------|------|
| `client.py` | Core mechanics: search, download, retry, the ranged-GET size trick |
| `browse.py` | Faceted discovery over `client.py`'s search endpoint |
| `presets.py` | Named filters (`Preset` dataclass + `PRESETS` registry) |
| `supplementary.py` | Fixed-UUID datasets not indexed in `/files` (currently: TCGA ATAC-seq) |
| `manifest.py` | `gdc-client` manifest and GDC sample-sheet writers |
| `cli.py` | The `gdcfetch` console command |

## Two kinds of GDC UUID

This distinction caused real confusion during development and is
worth keeping straight:

- **Indexed files** — anything `search_files` returns. `GET
  /files/<uuid>` works for these (returns metadata), and `GET
  /data/<uuid>` downloads the content.
- **Unindexed blobs** — data GDC serves at `/data/<uuid>` but that
  was never processed into the per-file search index (the
  publication-pinned TCGA ATAC-seq tarballs are the only known
  example). `GET /files/<uuid>` 404s for these even when the file
  is completely real — verified against the ATAC-seq UUIDs, which
  do download real ~GB-scale tarballs via `/data/<uuid>` while
  404ing on `/files/<uuid>`. `get_data_size`'s ranged-GET trick is
  the only reliable way to get metadata (size) for this class of
  object; there is no working `/files/<uuid>` fallback for them.

Also note: `HEAD /data/<uuid>` returns 400 for *both* kinds of UUID
— never use it.

## Adding a preset

1. Query the target project's facets to confirm the exact
   `data_type` / `workflow_type` strings and check whether more than
   one workflow exists for the type you want:
   ```python
   from gdcfetch import list_data_types, list_workflow_types
   list_data_types("TCGA-BRCA", data_category="...")
   list_workflow_types("TCGA-BRCA", data_type="...")
   ```
2. Check `access` — most TCGA data is `open`, but some categories
   (structural variants, raw sequencing reads, germline variants)
   are `controlled` and need dbGaP authorization to actually
   download, even though `search_files` will still list them.
3. Add a `Preset` entry to `PRESETS` in `presets.py` with an
   accurate `description` and, if it feeds a specific mutational
   signature class, `signature_classes`.
4. Add a golden test in `tests/test_presets.py`.

## Adding a supplementary dataset

If you find another GDC-served dataset that isn't discoverable
through `search_files` (the same pattern as the TCGA ATAC-seq
tarballs — a publication-pinned per-project archive with a fixed
UUID), add it to `supplementary.py` following the
`TCGA_ATAC_SEQ_UUIDS` pattern: a manually curated `dict[str, str]`
of project code → UUID, each entry verified live with
`client.get_data_size` before being committed (do not trust a
scraped UUID without this check — see the module's own comments for
why).

## Testing

All tests mock HTTP (`requests.Session`-compatible fakes); nothing
in the suite makes network calls by default (`network` marker
deselected in `pyproject.toml`). When adding a scraped or otherwise
externally-sourced value (a UUID, a data-type string), verify it
live once during development, then write the test against a fixed,
recorded response — don't make the test suite itself depend on GDC
being reachable.
