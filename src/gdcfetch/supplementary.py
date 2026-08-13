"""Publication-pinned supplementary datasets served by GDC but not
indexed in the files search.

Some datasets that live on ``api.gdc.cancer.gov/data/<uuid>`` are
*not discoverable* through `browse.py` or `client.search_files` --
they were deposited by a publication as a fixed per-project archive
rather than processed through GDC's normal per-file indexing
pipeline. GDC's ATAC-seq bigWig tracks (Corces et al. 2018) are the
leading example: querying ``experimental_strategy=ATAC-Seq`` finds
only the controlled-access raw BAMs, never these open-access
processed signal tracks (verified 2026-08 -- both
``GET /files/<uuid>`` and a files search 404/miss on these UUIDs,
while ``GET /data/<uuid>`` serves the real file).

This module is where such fixed-UUID datasets live: a small,
manually curated table plus a thin download helper, so "I know this
data exists somewhere on GDC but can't find it by searching" has a
documented answer instead of a dead end.
"""

import logging
from pathlib import Path

import requests

from .client import download_by_uuid, get_data_size

logger = logging.getLogger(__name__)

# TCGA ATAC-seq normalized bigWig tarballs, one per cancer type.
# Source: Corces et al. (2018), Science 362:eaav1898,
# https://doi.org/10.1126/science.aav1898
# UUIDs from https://gdc.cancer.gov/about-data/publications/ATACseq-AWG,
# each verified live against GDC (ranged GET, 2026-08) -- see
# TCGA_ATAC_SEQ_SIZES_BYTES below for the confirmed tarball size of
# each, captured at verification time (re-check with `get_data_size`
# if you need the current figure).
TCGA_ATAC_SEQ_UUIDS: dict[str, str] = {
    "ACC": "507afbc0-4283-473a-aad0-0432a2d283f7",
    "BLCA": "6db531a0-293c-433a-ad45-ab709af987b7",
    "BRCA": "f1c06cd3-cf35-41cc-bc75-6db273c94273",
    "CESC": "7f648efd-5737-409e-b6c3-1cd6d027fbfb",
    "CHOL": "78b6baeb-8b9b-486b-ae07-d9094cadaaa2",
    "COAD": "26b96cd9-dce0-4340-b15f-9e0afbb6312c",
    "ESCA": "fa18db6a-00fe-410f-982a-04d14d029812",
    "GBM": "ff11b5c0-5c43-443e-9cc7-dd7be60366f1",
    "HNSC": "82ae6c9d-3e4b-4bbf-a87e-e343265dc95a",
    "KIRC": "f5435391-9f73-4edb-bcda-211f9b9afd16",
    "KIRP": "e0beca12-65a8-421d-a9f2-25e37d2899ac",
    "LGG": "8009b5ee-7910-458c-a334-ee08ebcd1b88",
    "LIHC": "3eb9c64c-5afe-4693-a2d7-cd5ff25928a3",
    "LUAD": "b4fca984-42a6-45fe-9909-2f06cd7e3bcc",
    "LUSC": "5f1e254f-6370-4b60-9041-0009f58f259b",
    "MESO": "165a6103-8d8b-4e1e-afd4-e68fe81f30e6",
    "PCPG": "52c10f2d-1265-4434-8155-35f1fccd8811",
    "PRAD": "4677a65c-a9fb-4fb3-9e56-917715551d4c",
    "SKCM": "9b87d207-8c8e-47da-b56b-333bcf85856d",
    "STAD": "a59a7128-62ff-44f9-8f35-497fda8b0beb",
    "TGCT": "2f27b5c3-73ce-4ddc-9c04-eb6187875788",
    "THCA": "ed21baf7-8aca-404e-827a-a1bea9a89128",
    "UCEC": "e447195b-eeb9-459f-83db-9c748aafe395",
}
"""23 of the 33 TCGA cancer types; the rest have no ATAC-seq profiling
in this release (verified 2026-08 -- not an omission on our end)."""

TCGA_ATAC_SEQ_SIZES_BYTES: dict[str, int] = {
    "ACC": 1_910_000_000,
    "BLCA": 2_170_000_000,
    "BRCA": 15_940_000_000,
    "CESC": 820_000_000,
    "CHOL": 1_210_000_000,
    "COAD": 8_940_000_000,
    "ESCA": 3_880_000_000,
    "GBM": 2_050_000_000,
    "HNSC": 1_880_000_000,
    "KIRC": 3_530_000_000,
    "KIRP": 7_430_000_000,
    "LGG": 2_830_000_000,
    "LIHC": 3_730_000_000,
    "LUAD": 5_060_000_000,
    "LUSC": 3_790_000_000,
    "MESO": 1_510_000_000,
    "PCPG": 2_030_000_000,
    "PRAD": 6_050_000_000,
    "SKCM": 2_600_000_000,
    "STAD": 4_720_000_000,
    "TGCT": 2_060_000_000,
    "THCA": 2_750_000_000,
    "UCEC": 2_690_000_000,
}
"""Approximate tarball size in bytes per project, captured 2026-08 --
for planning disk space before downloading; call `get_data_size` for
the exact current figure."""


def tcga_atac_available(project: str) -> bool:
    """Whether a TCGA project code (e.g. 'BRCA') has an ATAC-seq entry."""
    return project.upper() in TCGA_ATAC_SEQ_UUIDS


def download_tcga_atac(
    project: str,
    dest: str | Path,
    *,
    force: bool = False,
    session: requests.Session | None = None,
) -> Path:
    """Download the TCGA ATAC-seq bigWig tarball for one cancer type.

    ``dest`` is the file path for the tarball itself (extraction is
    left to the caller -- see `sigmutselcovs.download.download_tcga_atac`
    for a worked example that streams and flattens it into per-sample
    bigWigs in one pass).

    Raises ``KeyError`` for TCGA codes without ATAC-seq coverage
    (10 of the 33 types -- e.g. OV) rather than silently returning
    nothing.
    """
    project = project.upper()
    if project not in TCGA_ATAC_SEQ_UUIDS:
        raise KeyError(
            f"No TCGA ATAC-seq data for {project!r}; covered: "
            f"{', '.join(sorted(TCGA_ATAC_SEQ_UUIDS))}"
        )
    uuid = TCGA_ATAC_SEQ_UUIDS[project]
    session = session or requests.Session()
    size = get_data_size(uuid, session=session)
    logger.info(
        "Downloading TCGA-%s ATAC-seq tarball (%s, %.1f GB)",
        project,
        uuid,
        size / 1e9,
    )
    return download_by_uuid(
        uuid, dest, expected_size=size, force=force, session=session
    )
