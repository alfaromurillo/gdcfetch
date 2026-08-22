"""gdcfetch: search, browse, and download data from the NCI Genomic Data Commons.

Three layers:

- `client`: general-purpose search/download against any GDC project
  and file type (`search_files`, `download_files`,
  `download_by_uuid`, `get_data_size`).
- `browse`: answer "what's available?" before writing a filtered
  query -- `list_projects` across all of GDC, or `list_data_types` /
  `describe_project` / ... within one project.
- `presets`: named, ready-to-use filters for the file types cancer
  researchers actually reach for -- somatic mutations (SBS/DBS/ID),
  copy number (CN), structural variants (SV), and gene expression.

`supplementary` covers datasets GDC serves but doesn't index in
search at all (currently: the TCGA ATAC-seq bigWig tarballs).

`tcga_barcode` covers what a downloaded file's ``Tumor_Sample_Barcode``
means and what GDC's clinical data says about the case it came from
(sample-type code, per-sample collection day, prior-treatment status)
-- none of the presets above filter or deduplicate by this, so it is
left to the caller.
"""

try:
    from importlib.metadata import version

    __version__ = version("gdcfetch")
except Exception:  # noqa: BLE001 - version is informational only
    __version__ = "unknown"

from .auth import authenticated_session, load_token
from .browse import (
    describe_project,
    list_data_categories,
    list_data_types,
    list_experimental_strategies,
    list_projects,
    list_workflow_types,
)
from .client import (
    build_filter,
    download_by_uuid,
    download_files,
    get_data_size,
    search_files,
)
from .manifest import write_manifest, write_sample_sheet
from .presets import Preset, get_preset, list_presets
from .supplementary import (
    TCGA_ATAC_SEQ_UUIDS,
    download_tcga_atac,
    tcga_atac_available,
)
from .tcga_barcode import (
    SAMPLE_TYPE_CODES,
    TcgaBarcodeInfo,
    fetch_case_metadata,
    parse_tcga_barcode,
)

__all__ = [
    "SAMPLE_TYPE_CODES",
    "TCGA_ATAC_SEQ_UUIDS",
    "Preset",
    "TcgaBarcodeInfo",
    "__version__",
    "authenticated_session",
    "build_filter",
    "describe_project",
    "download_by_uuid",
    "download_files",
    "download_tcga_atac",
    "fetch_case_metadata",
    "get_data_size",
    "get_preset",
    "list_data_categories",
    "list_data_types",
    "list_experimental_strategies",
    "list_presets",
    "list_projects",
    "list_workflow_types",
    "load_token",
    "parse_tcga_barcode",
    "search_files",
    "tcga_atac_available",
    "write_manifest",
    "write_sample_sheet",
]
