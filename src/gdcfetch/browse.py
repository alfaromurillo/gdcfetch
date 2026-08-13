"""Explore what data exists before committing to a query.

GDC's controlled vocabulary (project codes, data types, categories,
workflows) isn't obvious up front -- these functions answer "what's
actually available?", either across all of GDC (`list_projects`) or
within one project (the files endpoint's own faceted aggregation),
so you don't have to already know the exact string "TCGA-BRCA" or
"Masked Somatic Mutation" to find it.
"""

import json
import logging

import requests

from .client import GDC_API

logger = logging.getLogger(__name__)

_PROJECT_FIELDS = (
    "project_id",
    "name",
    "primary_site",
    "program.name",
)


def list_projects(
    *,
    program: str | None = None,
    fields: tuple[str, ...] = _PROJECT_FIELDS,
    page_size: int = 100,
    session: requests.Session | None = None,
    timeout: int = 60,
) -> list[dict]:
    """List every GDC project (93 as of 2026-08, across ~30 programs).

    GDC hosts more than TCGA -- TARGET, CPTAC, MMRF, ALCHEMIST, and
    others are all in the same `/projects` index. Pass ``program``
    (e.g. ``"TCGA"``) to narrow the listing to one; leave it unset to
    see everything. Results are sorted by ``project_id``.
    """
    session = session or requests.Session()
    filters = None
    if program is not None:
        filters = {
            "op": "in",
            "content": {"field": "program.name", "value": [program]},
        }
    hits: list[dict] = []
    start = 0
    while True:
        params = {
            "fields": ",".join(fields),
            "size": page_size,
            "from": start,
        }
        if filters is not None:
            params["filters"] = json.dumps(filters)
        response = session.get(
            f"{GDC_API}/projects", params=params, timeout=timeout
        )
        response.raise_for_status()
        data = response.json()["data"]
        hits.extend(data["hits"])
        pagination = data["pagination"]
        start += pagination["count"]
        if start >= pagination["total"] or pagination["count"] == 0:
            break
    hits.sort(key=lambda h: h["project_id"])
    return hits


def _facets(
    project_id: str,
    facets: str,
    *,
    extra_filters: list[dict] | None = None,
    session: requests.Session | None = None,
    timeout: int = 60,
) -> dict[str, dict[str, int]]:
    session = session or requests.Session()
    clauses = [
        {
            "op": "in",
            "content": {
                "field": "cases.project.project_id",
                "value": [project_id],
            },
        }
    ]
    clauses.extend(extra_filters or [])
    payload = {
        "filters": {"op": "and", "content": clauses},
        "facets": facets,
        "size": 0,
    }
    response = session.post(
        f"{GDC_API}/files", json=payload, timeout=timeout
    )
    response.raise_for_status()
    aggregations = response.json()["data"]["aggregations"]
    return {
        field: {b["key"]: b["doc_count"] for b in data["buckets"]}
        for field, data in aggregations.items()
    }


def list_data_categories(project_id: str, **kwargs) -> dict[str, int]:
    """Return ``{data_category: file_count}`` for a project."""
    return _facets(project_id, "data_category", **kwargs)[
        "data_category"
    ]


def list_data_types(
    project_id: str,
    *,
    data_category: str | None = None,
    **kwargs,
) -> dict[str, int]:
    """Return ``{data_type: file_count}`` for a project.

    Pass ``data_category`` (from `list_data_categories`) to narrow
    the listing, e.g. ``list_data_types("TCGA-BRCA",
    data_category="copy number variation")``.
    """
    extra_filters = list(kwargs.pop("extra_filters", None) or [])
    if data_category is not None:
        extra_filters.append(
            {
                "op": "in",
                "content": {
                    "field": "data_category",
                    "value": [data_category],
                },
            }
        )
    return _facets(
        project_id, "data_type", extra_filters=extra_filters, **kwargs
    )["data_type"]


def list_experimental_strategies(
    project_id: str, **kwargs
) -> dict[str, int]:
    """Return ``{experimental_strategy: file_count}`` for a project."""
    return _facets(project_id, "experimental_strategy", **kwargs)[
        "experimental_strategy"
    ]


def list_workflow_types(
    project_id: str,
    *,
    data_type: str | None = None,
    **kwargs,
) -> dict[str, int]:
    """Return ``{workflow_type: file_count}`` for a project.

    Several data types are produced by more than one pipeline (e.g.
    Copy Number Segment has both DNAcopy and GATK4 CNV results for
    TCGA) -- pass ``data_type`` to see which workflows exist for a
    specific type before deciding whether to filter on one.
    """
    extra_filters = list(kwargs.pop("extra_filters", None) or [])
    if data_type is not None:
        extra_filters.append(
            {
                "op": "in",
                "content": {
                    "field": "data_type",
                    "value": [data_type],
                },
            }
        )
    return _facets(
        project_id,
        "analysis.workflow_type",
        extra_filters=extra_filters,
        **kwargs,
    )["analysis.workflow_type"]


def describe_project(project_id: str, **kwargs) -> dict:
    """One-shot overview: data categories, types, and strategies together.

    The natural first call when starting on an unfamiliar project --
    print the result to see what's there before writing a filtered
    `client.search_files` query.
    """
    return {
        "data_categories": list_data_categories(project_id, **kwargs),
        "data_types": list_data_types(project_id, **kwargs),
        "experimental_strategies": list_experimental_strategies(
            project_id, **kwargs
        ),
    }
