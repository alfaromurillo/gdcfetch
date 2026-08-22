"""Tests for tcga_barcode (mocked HTTP, no network)."""

import pytest

from gdcfetch.tcga_barcode import (
    fetch_case_metadata,
    parse_tcga_barcode,
)


def test_parse_tcga_barcode_full():
    info = parse_tcga_barcode("TCGA-AA-3971-01A-01W-0995-10")
    assert info.case_id == "TCGA-AA-3971"
    assert info.sample_id == "TCGA-AA-3971-01A"
    assert info.sample_type_code == "01"
    assert info.sample_type_name == "Primary Solid Tumor"
    assert info.vial == "A"
    assert info.portion_analyte == "01W"
    assert info.plate == "0995"
    assert info.center == "10"


def test_parse_tcga_barcode_metastatic():
    info = parse_tcga_barcode("TCGA-ER-A19T-06A-11D-A19A-08")
    assert info.sample_type_code == "06"
    assert info.sample_type_name == "Metastatic"


def test_parse_tcga_barcode_minimal_length():
    info = parse_tcga_barcode("TCGA-AA-3971-01A")
    assert info.case_id == "TCGA-AA-3971"
    assert info.portion_analyte is None


def test_parse_tcga_barcode_invalid_raises():
    with pytest.raises(ValueError, match="Not a valid TCGA"):
        parse_tcga_barcode("not-a-barcode")


class _CasesResponse:
    def __init__(self, hits):
        self._hits = hits

    def raise_for_status(self):
        pass

    def json(self):
        return {"data": {"hits": self._hits}}


class _CasesSession:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append(json)
        return _CasesResponse(self.hits)


def test_fetch_case_metadata_parses_response():
    hits = [
        {
            "submitter_id": "TCGA-BL-A0C8",
            "diagnoses": [{"prior_treatment": "No"}],
            "samples": [
                {
                    "submitter_id": "TCGA-BL-A0C8-01A",
                    "days_to_collection": 213,
                },
                {
                    "submitter_id": "TCGA-BL-A0C8-01B",
                    "days_to_collection": 806,
                },
            ],
        }
    ]
    session = _CasesSession(hits)

    metadata = fetch_case_metadata(["TCGA-BL-A0C8"], session=session)

    assert metadata["TCGA-BL-A0C8"]["prior_treatment"] == "No"
    assert metadata["TCGA-BL-A0C8"]["sample_days_to_collection"] == {
        "TCGA-BL-A0C8-01A": 213,
        "TCGA-BL-A0C8-01B": 806,
    }
    assert len(session.calls) == 1


def test_fetch_case_metadata_missing_days_and_treatment():
    hits = [
        {
            "submitter_id": "TCGA-AA-0001",
            "diagnoses": [],
            "samples": [
                {"submitter_id": "TCGA-AA-0001-01A"},
            ],
        }
    ]
    session = _CasesSession(hits)

    metadata = fetch_case_metadata(["TCGA-AA-0001"], session=session)

    assert metadata["TCGA-AA-0001"]["prior_treatment"] is None
    assert metadata["TCGA-AA-0001"]["sample_days_to_collection"] == {
        "TCGA-AA-0001-01A": None
    }


def test_fetch_case_metadata_empty_input_skips_network():
    class _FailSession:
        def post(self, *args, **kwargs):
            raise AssertionError("should not make a network call")

    assert fetch_case_metadata([], session=_FailSession()) == {}


def test_fetch_case_metadata_warns_on_missing_case(caplog):
    session = _CasesSession([])
    with caplog.at_level("WARNING"):
        metadata = fetch_case_metadata(
            ["TCGA-ZZ-9999"], session=session
        )
    assert metadata == {}
    assert "no record" in caplog.text
