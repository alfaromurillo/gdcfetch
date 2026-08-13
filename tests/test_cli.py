"""CLI smoke tests (no network)."""

import pytest

from gdcfetch.cli import build_parser, main


def test_presets_command_lists_all(capsys):
    assert main(["presets"]) == 0
    out = capsys.readouterr().out
    assert "somatic-mutations" in out
    assert "SBS, DBS, ID" in out
    assert "structural-variants" in out


def test_search_requires_project():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["search"])


def test_download_requires_dest():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["download", "TCGA-BRCA"])


def test_atac_command_unknown_project(capsys):
    with pytest.raises(KeyError):
        main(["atac", "OV", "--dest", "/tmp/wont-be-used.tgz"])


def test_command_required():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])
