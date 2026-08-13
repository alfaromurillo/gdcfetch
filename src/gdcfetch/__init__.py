"""gdcfetch: search, browse, and download data from the NCI Genomic Data Commons.

Three layers:

- `client`: general-purpose search/download against any GDC project
  and file type (`search_files`, `download_files`,
  `download_by_uuid`, `get_data_size`).
- `browse`: answer "what's available for this project?" before
  writing a filtered query (`list_data_types`, `describe_project`,
  ...).
- `presets`: named, ready-to-use filters for the file types cancer
  researchers actually reach for -- somatic mutations (SBS/DBS/ID),
  copy number (CN), structural variants (SV), and gene expression.

`supplementary` covers datasets GDC serves but doesn't index in
search at all (currently: the TCGA ATAC-seq bigWig tarballs).
"""

try:
    from importlib.metadata import version

    __version__ = version("gdcfetch")
except Exception:  # noqa: BLE001 - version is informational only
    __version__ = "unknown"

from .browse import (
    describe_project,
    list_data_categories,
    list_data_types,
    list_experimental_strategies,
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

__all__ = [
    "__version__",
    "build_filter",
    "search_files",
    "download_files",
    "download_by_uuid",
    "get_data_size",
    "describe_project",
    "list_data_categories",
    "list_data_types",
    "list_experimental_strategies",
    "list_workflow_types",
    "Preset",
    "list_presets",
    "get_preset",
    "write_manifest",
    "write_sample_sheet",
    "TCGA_ATAC_SEQ_UUIDS",
    "tcga_atac_available",
    "download_tcga_atac",
]
