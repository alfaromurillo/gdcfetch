"""Supplementary-dataset tests (mocked HTTP for the download path)."""

import pytest

from gdcfetch.supplementary import (
    TCGA_ATAC_SEQ_SIZES_BYTES,
    TCGA_ATAC_SEQ_UUIDS,
    download_tcga_atac,
    tcga_atac_available,
)


def test_23_of_33_tcga_types_covered():
    assert len(TCGA_ATAC_SEQ_UUIDS) == 23
    assert set(TCGA_ATAC_SEQ_UUIDS) == set(TCGA_ATAC_SEQ_SIZES_BYTES)


def test_known_uuids_well_formed():
    for code, uuid in TCGA_ATAC_SEQ_UUIDS.items():
        assert code == code.upper()
        assert len(uuid) == 36 and uuid.count("-") == 4


def test_tcga_atac_available():
    assert tcga_atac_available("BRCA")
    assert tcga_atac_available("brca")  # case-insensitive
    assert not tcga_atac_available(
        "OV"
    )  # known gap, Corces didn't profile it


class _RangeResponse:
    def __init__(self, size):
        self.headers = {"Content-Range": f"0-0/{size}"}
        self.status_code = 206

    def raise_for_status(self):
        pass

    def close(self):
        pass


class _DataResponse:
    def __init__(self, content):
        self.content = content
        self.status_code = 200

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Session:
    def __init__(self, payload):
        self.payload = payload

    def get(self, url, headers=None, stream=True, timeout=None):
        if headers and "Range" in headers and len(self.payload) > 1:
            return _RangeResponse(len(self.payload))
        return _DataResponse(self.payload)


def test_download_tcga_atac(tmp_path):
    session = _Session(b"fake tarball bytes")
    dest = tmp_path / "brca.tgz"
    got = download_tcga_atac("BRCA", dest, session=session)
    assert got == dest
    assert dest.read_bytes() == b"fake tarball bytes"


def test_download_tcga_atac_unknown_project_raises():
    with pytest.raises(KeyError, match="OV"):
        download_tcga_atac("OV", "/tmp/wont-be-used.tgz")
