"""Core client tests (mocked HTTP, no network)."""

import hashlib

import pytest

from gdcfetch.client import (
    build_filter,
    download_by_uuid,
    download_files,
    get_data_size,
    search_files,
)


def test_build_filter_minimal():
    got = build_filter("TCGA-BRCA")
    assert got == {
        "op": "and",
        "content": [
            {
                "op": "in",
                "content": {
                    "field": "cases.project.project_id",
                    "value": ["TCGA-BRCA"],
                },
            }
        ],
    }


def test_build_filter_all_fields():
    got = build_filter(
        "TCGA-BRCA",
        data_type="Copy Number Segment",
        data_category="copy number variation",
        experimental_strategy="WGS",
        workflow_type="DNAcopy",
        access="open",
    )
    fields = {c["content"]["field"] for c in got["content"]}
    assert fields == {
        "cases.project.project_id",
        "data_type",
        "data_category",
        "experimental_strategy",
        "access",
        "analysis.workflow_type",
    }


HIT_A = {"file_id": "id-b", "file_name": "b.txt", "file_size": 2}
HIT_B = {"file_id": "id-a", "file_name": "a.txt", "file_size": 1}


class _SearchResponse:
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


class _SearchSession:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append(json)
        page = self.pages[len(self.calls) - 1]
        return _SearchResponse(page, sum(len(p) for p in self.pages))


def test_search_files_paginates_and_sorts():
    session = _SearchSession([[HIT_A], [HIT_B]])
    hits = search_files("TCGA-BRCA", session=session, page_size=1)
    assert len(session.calls) == 2
    assert [h["file_id"] for h in hits] == ["id-a", "id-b"]  # sorted


def test_search_files_default_access_open():
    session = _SearchSession([[]])
    search_files("TCGA-BRCA", session=session)
    sent = session.calls[0]["filters"]["content"]
    access_clause = [
        c for c in sent if c["content"]["field"] == "access"
    ]
    assert access_clause[0]["content"]["value"] == ["open"]


class _RangeResponse:
    def __init__(self, content_range, status=206):
        self.headers = (
            {"Content-Range": content_range} if content_range else {}
        )
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise OSError(f"HTTP {self.status_code}")

    def close(self):
        pass


class _RangeSession:
    def __init__(self, content_range):
        self.content_range = content_range

    def get(self, url, headers=None, stream=True, timeout=None):
        return _RangeResponse(self.content_range)


def test_get_data_size_from_content_range():
    session = _RangeSession("0-0/8939070313")
    assert get_data_size("some-uuid", session=session) == 8939070313


def test_get_data_size_missing_header_raises():
    session = _RangeSession(None)
    with pytest.raises(ValueError, match="Content-Range"):
        get_data_size("some-uuid", session=session)


class _DataResponse:
    def __init__(self, content, status_code=200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise OSError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _DataSession:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def get(self, url, headers=None, stream=True, timeout=None):
        self.requests.append(headers or {})
        return _DataResponse(self.payload)


def test_download_by_uuid_verifies_and_writes(tmp_path):
    payload = b"hello world"
    session = _DataSession(payload)
    dest = tmp_path / "out.bin"
    got = download_by_uuid(
        "uuid-1",
        dest,
        expected_md5=hashlib.md5(payload).hexdigest(),
        expected_size=len(payload),
        session=session,
    )
    assert got == dest
    assert dest.read_bytes() == payload
    assert not dest.with_suffix(".bin.part").exists()


def test_download_by_uuid_skips_when_present(tmp_path):
    dest = tmp_path / "out.bin"
    dest.write_bytes(b"already here")
    session = _DataSession(b"unused")
    download_by_uuid(
        "uuid-1",
        dest,
        expected_size=len(b"already here"),
        session=session,
    )
    assert session.requests == []


def test_download_files_skips_and_reports_partial_failure(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("gdcfetch.client.time.sleep", lambda s: None)
    hits = [
        {
            "file_id": "ok",
            "file_name": "ok.txt",
            "file_size": 2,
            "md5sum": hashlib.md5(b"ok").hexdigest(),
        },
        {
            "file_id": "bad",
            "file_name": "bad.txt",
            "file_size": 999,
            "md5sum": "0" * 32,
        },
    ]

    class _MixedSession:
        def get(self, url, headers=None, stream=True, timeout=None):
            if "ok" in url:
                return _DataResponse(b"ok")
            return _DataResponse(b"", status_code=500)

    with pytest.raises(OSError, match="bad"):
        download_files(
            hits, tmp_path, session=_MixedSession(), workers=2
        )
    assert (tmp_path / "ok" / "ok.txt").read_bytes() == b"ok"
