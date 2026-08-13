"""Browse/facet tests (mocked HTTP)."""

from gdcfetch.browse import (
    describe_project,
    list_data_categories,
    list_data_types,
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
