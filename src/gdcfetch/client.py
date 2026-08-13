"""Core GDC files-API client: search, download, and raw-blob access.

`search_files` wraps the GDC files POST endpoint with pagination;
`download_files` fetches search results with retry and resume;
`download_by_uuid` and `get_data_size` handle GDC-served blobs that
are *not* indexed in the files search at all (see `supplementary.py`
for the leading example: the TCGA ATAC-seq bigWig tarballs).
"""

import hashlib
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

GDC_API = "https://api.gdc.cancer.gov"

DEFAULT_FIELDS = (
    "file_id",
    "file_name",
    "md5sum",
    "file_size",
    "state",
    "data_category",
    "data_type",
    "data_format",
    "access",
    "analysis.workflow_type",
    "experimental_strategy",
    "cases.project.project_id",
    "cases.submitter_id",
    "cases.samples.submitter_id",
    "cases.samples.tissue_type",
    "cases.samples.tumor_descriptor",
    "cases.samples.specimen_type",
    "cases.samples.preservation_method",
)


def build_filter(
    project_id: str,
    *,
    data_type: str | None = None,
    data_category: str | None = None,
    experimental_strategy: str | None = None,
    workflow_type: str | None = None,
    access: str | None = None,
    extra: list[dict] | None = None,
) -> dict:
    """Build a GDC files-endpoint filter.

    Every field besides ``project_id`` is optional -- omit a field
    to not filter on it (useful for `browse.py`'s exploratory
    queries, or when a data type spans several workflows and you
    want them all).
    """
    clauses = [
        {
            "op": "in",
            "content": {
                "field": "cases.project.project_id",
                "value": [project_id],
            },
        }
    ]
    for field, value in (
        ("data_type", data_type),
        ("data_category", data_category),
        ("experimental_strategy", experimental_strategy),
        ("access", access),
    ):
        if value is not None:
            clauses.append(
                {
                    "op": "in",
                    "content": {"field": field, "value": [value]},
                }
            )
    if workflow_type is not None:
        clauses.append(
            {
                "op": "in",
                "content": {
                    "field": "analysis.workflow_type",
                    "value": [workflow_type],
                },
            }
        )
    clauses.extend(extra or [])
    return {"op": "and", "content": clauses}


def search_files(
    project_id: str,
    *,
    data_type: str | None = None,
    data_category: str | None = None,
    experimental_strategy: str | None = None,
    workflow_type: str | None = None,
    access: str | None = "open",
    fields: tuple[str, ...] = DEFAULT_FIELDS,
    page_size: int = 1000,
    session: requests.Session | None = None,
    timeout: int = 60,
) -> list[dict]:
    """Search the GDC files index and return every matching hit.

    Paginates automatically; results are sorted by ``file_id`` so
    two runs against unchanged data are diffable. Pass
    ``access=None`` to include controlled-access files in the
    listing (you still need dbGaP credentials to actually download
    them -- see `presets.py`'s ``structural-variants`` entry for the
    canonical example).
    """
    session = session or requests.Session()
    filters = build_filter(
        project_id,
        data_type=data_type,
        data_category=data_category,
        experimental_strategy=experimental_strategy,
        workflow_type=workflow_type,
        access=access,
    )
    hits: list[dict] = []
    start = 0
    while True:
        payload = {
            "filters": filters,
            "fields": ",".join(fields),
            "size": page_size,
            "from": start,
        }
        response = session.post(
            f"{GDC_API}/files", json=payload, timeout=timeout
        )
        response.raise_for_status()
        data = response.json()["data"]
        hits.extend(data["hits"])
        pagination = data["pagination"]
        start += pagination["count"]
        if start >= pagination["total"] or pagination["count"] == 0:
            break
    hits.sort(key=lambda h: h["file_id"])
    logger.info("GDC search for %s: %d files", project_id, len(hits))
    return hits


def get_data_size(
    uuid: str,
    *,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> int:
    """Return the byte size of a ``/data/<uuid>`` blob without downloading it.

    ``HEAD /data/<uuid>`` returns 400 on this endpoint (verified
    2026-08), and files served this way are not always indexed in
    ``/files`` (the TCGA ATAC-seq tarballs, for instance, are not --
    ``GET /files/<uuid>`` 404s for them even though the file is
    real). A 1-byte ranged GET works universally: the server answers
    206 with a ``Content-Range: 0-0/<total>`` header giving the full
    size for the cost of one byte of transfer.
    """
    session = session or requests.Session()
    response = session.get(
        f"{GDC_API}/data/{uuid}",
        headers={"Range": "bytes=0-0"},
        stream=True,
        timeout=timeout,
    )
    try:
        response.raise_for_status()
        content_range = response.headers.get("Content-Range", "")
        if "/" not in content_range:
            raise ValueError(
                f"No Content-Range header for {uuid}; got: "
                f"{dict(response.headers)}"
            )
        return int(content_range.rsplit("/", 1)[-1])
    finally:
        response.close()


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_by_uuid(
    uuid: str,
    dest: str | Path,
    *,
    expected_md5: str | None = None,
    expected_size: int | None = None,
    force: bool = False,
    session: requests.Session | None = None,
    timeout: int = 600,
    retries: int = 3,
) -> Path:
    """Download a single ``/data/<uuid>`` blob to ``dest``, resumable.

    Works for both indexed files (found via `search_files`) and
    unindexed ones (see `get_data_size` and `supplementary.py`).
    Streams to ``<dest>.part`` and renames atomically on success, so
    an interrupted download never leaves a truncated ``dest``.
    """
    dest = Path(dest)
    if (
        dest.exists()
        and not force
        and (
            expected_size is None
            or dest.stat().st_size == expected_size
        )
    ):
        logger.info("Already present, skipping: %s", dest.name)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    session = session or requests.Session()
    part = dest.with_suffix(dest.suffix + ".part")

    last_exc: Exception | None = None
    for attempt in range(retries):
        if attempt:
            time.sleep(2**attempt)
        headers = {}
        mode = "wb"
        if part.exists() and part.stat().st_size > 0:
            headers["Range"] = f"bytes={part.stat().st_size}-"
            mode = "ab"
        try:
            with session.get(
                f"{GDC_API}/data/{uuid}",
                headers=headers,
                stream=True,
                timeout=timeout,
            ) as response:
                if headers and response.status_code == 200:
                    mode = "wb"  # server ignored the Range request
                response.raise_for_status()
                with open(part, mode) as fh:
                    fh.writelines(
                        response.iter_content(chunk_size=1 << 20)
                    )
            if expected_size is not None and (
                part.stat().st_size != expected_size
            ):
                raise OSError(
                    f"size {part.stat().st_size} != expected "
                    f"{expected_size} for {uuid}"
                )
            if (
                expected_md5 is not None
                and _md5(part) != expected_md5
            ):
                raise OSError(f"md5 mismatch for {uuid}")
            os.replace(part, dest)
            return dest
        except (requests.RequestException, OSError) as exc:
            last_exc = exc
            logger.warning(
                "Attempt %d/%d failed for %s: %s",
                attempt + 1,
                retries,
                uuid,
                exc,
            )
    raise last_exc


def download_files(
    hits: list[dict],
    dest: str | Path,
    *,
    workers: int = 6,
    verify_md5: bool = True,
    timeout: int = 600,
    session: requests.Session | None = None,
) -> list[Path]:
    """Download search results into ``<dest>/<file_id>/<file_name>``.

    That layout keeps each file alongside its GDC file ID, which
    many downstream tools (this one's own `manifest.py` included)
    use to recover provenance from the directory name. Already-
    complete files are skipped; the ones that fail are retried a
    few times each (`client.download_by_uuid`'s ``retries``) and,
    if still failing, reported together in a single exception that
    names only the files that never succeeded -- a rerun is always
    safe, since everything already on disk is skipped again.
    """
    dest = Path(dest)
    session = session or requests.Session()

    pending = [
        h
        for h in hits
        if not (
            (dest / h["file_id"] / h["file_name"]).exists()
            and (dest / h["file_id"] / h["file_name"]).stat().st_size
            == h["file_size"]
        )
    ]
    logger.info(
        "Download: %d of %d files to fetch", len(pending), len(hits)
    )
    if not pending:
        return [dest / h["file_id"] / h["file_name"] for h in hits]

    failed: list[tuple[dict, Exception]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_hit = {
            pool.submit(
                download_by_uuid,
                h["file_id"],
                dest / h["file_id"] / h["file_name"],
                expected_md5=h.get("md5sum") if verify_md5 else None,
                expected_size=h.get("file_size"),
                session=session,
                timeout=timeout,
            ): h
            for h in pending
        }
        for future in as_completed(future_to_hit):
            hit = future_to_hit[future]
            try:
                future.result()
            except Exception as exc:  # noqa: BLE001
                failed.append((hit, exc))
    if failed:
        ids = [h["file_id"] for h, _ in failed]
        raise OSError(
            f"{len(failed)} of {len(pending)} downloads failed after "
            f"retries: {ids}. Rerunning is safe."
        )
    return [dest / h["file_id"] / h["file_name"] for h in hits]
