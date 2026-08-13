"""Write search results as a manifest or sample sheet.

`write_manifest` reproduces the exact 5-column format the official
``gdc-client`` download tool expects, so results from `search_files`
can feed either this package's own `download_files` or the official
downloader interchangeably. `write_sample_sheet` reproduces the
11-column format the GDC Data Portal's own "Sample Sheet" download
uses, for interop with tools that expect that layout.
"""

from datetime import date
from pathlib import Path

import pandas as pd

SAMPLE_SHEET_COLUMNS = [
    "File ID",
    "File Name",
    "Data Category",
    "Data Type",
    "Project ID",
    "Case ID",
    "Sample ID",
    "Tissue Type",
    "Tumor Descriptor",
    "Specimen Type",
    "Preservation Method",
]


def write_manifest(hits: list[dict], path: str | Path) -> Path:
    """Write a ``gdc-client``-compatible manifest (id filename md5 size state)."""
    path = Path(path)
    rows = [
        (
            h["file_id"],
            h["file_name"],
            h.get("md5sum", ""),
            str(h.get("file_size", "")),
            h.get("state", "released"),
        )
        for h in hits
    ]
    lines = ["\t".join(("id", "filename", "md5", "size", "state"))]
    lines += ["\t".join(r) for r in rows]
    path.write_text("\n".join(lines) + "\n")
    return path


def _joined(values: list[str]) -> str:
    return ", ".join(dict.fromkeys(v for v in values if v))


def _sample_sheet_row(hit: dict) -> list[str]:
    cases = hit.get("cases", [])
    samples = [s for c in cases for s in c.get("samples", [])]

    def sample_field(name: str) -> str:
        return _joined([s.get(name) or "Unknown" for s in samples])

    return [
        hit["file_id"],
        hit["file_name"],
        hit.get("data_category", ""),
        hit.get("data_type", ""),
        _joined(
            [
                c.get("project", {}).get("project_id", "")
                for c in cases
            ]
        ),
        _joined([c.get("submitter_id", "") for c in cases]),
        _joined([s.get("submitter_id", "") for s in samples]),
        sample_field("tissue_type"),
        sample_field("tumor_descriptor"),
        sample_field("specimen_type"),
        sample_field("preservation_method"),
    ]


def write_sample_sheet(
    hits: list[dict],
    path: str | Path | None = None,
    *,
    directory: str | Path | None = None,
) -> Path:
    """Write a GDC Data Portal-style sample sheet.

    Either give an explicit ``path`` or a ``directory``, in which
    case the file is named ``gdc_sample_sheet.<YYYY-MM-DD>.tsv``.
    """
    if path is None:
        if directory is None:
            raise ValueError("Give either path or directory")
        path = (
            Path(directory)
            / f"gdc_sample_sheet.{date.today().isoformat()}.tsv"
        )
    path = Path(path)
    frame = pd.DataFrame(
        [_sample_sheet_row(h) for h in hits],
        columns=SAMPLE_SHEET_COLUMNS,
    )
    frame.to_csv(path, sep="\t", index=False)
    return path
