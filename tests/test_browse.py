"""Browse/facet tests (mocked HTTP)."""

import json

from gdcfetch.browse import (
    describe_project,
    list_data_categories,
    list_data_types,
    list_projects,
    list_workflow_types,
)


class _FacetResponse:
    def __init__(self, aggregations):
        self._aggregations = aggregations

    def raise_for_status(self):
        pass

    def json(self):
        return {"data": {"aggregations": self._aggregations}}


class _FacetSession:
    def __init__(self, aggregations):
        self.aggregations = aggregations
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append(json)
        return _FacetResponse(self.aggregations)


def test_list_data_categories():
    session = _FacetSession(
        {
            "data_category": {
                "buckets": [
                    {
                        "key": "simple nucleotide variation",
                        "doc_count": 10,
                    },
                    {"key": "copy number variation", "doc_count": 5},
                ]
            }
        }
    )
    got = list_data_categories("TCGA-BRCA", session=session)
    assert got == {
        "simple nucleotide variation": 10,
        "copy number variation": 5,
    }


def test_list_data_types_narrows_by_category():
    session = _FacetSession(
        {
            "data_type": {
                "buckets": [
                    {"key": "Copy Number Segment", "doc_count": 3}
                ]
            }
        }
    )
    list_data_types(
        "TCGA-BRCA",
        data_category="copy number variation",
        session=session,
    )
    sent = session.calls[0]["filters"]["content"]
    fields = {c["content"]["field"] for c in sent}
    assert "data_category" in fields


def test_list_workflow_types_narrows_by_data_type():
    session = _FacetSession(
        {
            "analysis.workflow_type": {
                "buckets": [
                    {"key": "DNAcopy", "doc_count": 2229},
                    {"key": "GATK4 CNV", "doc_count": 1027},
                ]
            }
        }
    )
    got = list_workflow_types(
        "TCGA-BRCA", data_type="Copy Number Segment", session=session
    )
    assert got == {"DNAcopy": 2229, "GATK4 CNV": 1027}
    sent = session.calls[0]["filters"]["content"]
    fields = {c["content"]["field"] for c in sent}
    assert "data_type" in fields


def test_describe_project_bundles_three_facets():
    session = _FacetSession(
        {
            "data_category": {"buckets": []},
            "data_type": {"buckets": []},
            "experimental_strategy": {"buckets": []},
        }
    )
    got = describe_project("TCGA-BRCA", session=session)
    assert set(got) == {
        "data_categories",
        "data_types",
        "experimental_strategies",
    }
    assert len(session.calls) == 3


TCGA_BRCA = {
    "project_id": "TCGA-BRCA",
    "name": "Breast Invasive Carcinoma",
    "primary_site": ["Breast"],
    "disease_type": ["Ductal and Lobular Neoplasms"],
    "program": {"name": "TCGA"},
    "summary": {
        "experimental_strategies": [
            {"experimental_strategy": "RNA-Seq"},
            {"experimental_strategy": "ATAC-Seq"},
        ]
    },
}
TCGA_LUAD = {
    "project_id": "TCGA-LUAD",
    "name": "Lung Adenocarcinoma",
    "primary_site": ["Bronchus and lung"],
    "disease_type": ["Adenomas and Adenocarcinomas"],
    "program": {"name": "TCGA"},
    "summary": {
        "experimental_strategies": [
            {"experimental_strategy": "WGS"},
        ]
    },
}
ALCHEMIST = {
    "project_id": "ALCHEMIST-ALCH",
    "name": "Adjuvant Lung Cancer Enrichment Marker "
    "Identification and Sequencing Trial",
    "primary_site": ["Not Reported"],
    "disease_type": ["Not Reported"],
    "program": {"name": "ALCHEMIST"},
    "summary": {
        "experimental_strategies": [
            {"experimental_strategy": "WXS"},
        ]
    },
}


class _ProjectsResponse:
    def __init__(self, hits, total):
        self._hits = hits
        self._total = total

    def raise_for_status(self):
        pass

    def json(self):
        return {
            "data": {
                "hits": self._hits,
                "pagination": {
                    "count": len(self._hits),
                    "total": self._total,
                },
            }
        }


class _ProjectsSession:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        page = self.pages[len(self.calls) - 1]
        return _ProjectsResponse(
            page, sum(len(p) for p in self.pages)
        )


def test_list_projects_paginates_and_sorts():
    session = _ProjectsSession([[ALCHEMIST], [TCGA_BRCA]])
    got = list_projects(session=session, page_size=1)
    assert len(session.calls) == 2
    assert [p["project_id"] for p in got] == [
        "ALCHEMIST-ALCH",
        "TCGA-BRCA",
    ]  # sorted
    assert "filters" not in session.calls[0]


def test_list_projects_filters_by_program():
    session = _ProjectsSession([[TCGA_BRCA]])
    list_projects(program="TCGA", session=session)
    sent = json.loads(session.calls[0]["filters"])
    assert sent == {
        "op": "in",
        "content": {"field": "program.name", "value": ["TCGA"]},
    }


def test_list_projects_filters_by_site():
    session = _ProjectsSession([[TCGA_BRCA, TCGA_LUAD, ALCHEMIST]])
    got = list_projects(site="lung", session=session)
    assert [p["project_id"] for p in got] == ["TCGA-LUAD"]


def test_list_projects_site_is_case_insensitive():
    session = _ProjectsSession([[TCGA_LUAD]])
    got = list_projects(site="LUNG", session=session)
    assert len(got) == 1


def test_list_projects_filters_by_disease_type():
    session = _ProjectsSession([[TCGA_BRCA, TCGA_LUAD]])
    got = list_projects(disease_type="neoplasms", session=session)
    assert [p["project_id"] for p in got] == ["TCGA-BRCA"]


def test_list_projects_disease_type_distinct_from_site():
    # 'neoplasms' should not match on primary_site even though both
    # projects are real cancers -- disease_type and primary_site are
    # different fields
    session = _ProjectsSession([[TCGA_LUAD]])
    got = list_projects(disease_type="neoplasms", session=session)
    assert got == []


def test_list_projects_filters_by_strategy():
    session = _ProjectsSession([[TCGA_BRCA, TCGA_LUAD, ALCHEMIST]])
    got = list_projects(strategy="WGS", session=session)
    assert [p["project_id"] for p in got] == ["TCGA-LUAD"]


def test_list_projects_strategy_substring_match():
    session = _ProjectsSession([[TCGA_BRCA, TCGA_LUAD]])
    got = list_projects(strategy="seq", session=session)
    # RNA-Seq and ATAC-Seq both contain "seq"; WGS does not
    assert [p["project_id"] for p in got] == ["TCGA-BRCA"]


def test_list_projects_filters_combine():
    session = _ProjectsSession([[TCGA_BRCA, TCGA_LUAD, ALCHEMIST]])
    got = list_projects(
        program="TCGA", strategy="atac", session=session
    )
    assert [p["project_id"] for p in got] == ["TCGA-BRCA"]
