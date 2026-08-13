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


def test_projects_command_accepts_program_filter():
    args = build_parser().parse_args(
        ["projects", "--program", "TCGA"]
    )
    assert args.program == "TCGA"


def test_projects_command_program_optional():
    args = build_parser().parse_args(["projects"])
    assert args.program is None
    assert args.site is None
    assert args.disease_type is None
    assert args.strategy is None


def test_projects_command_accepts_site_disease_strategy():
    args = build_parser().parse_args(
        [
            "projects",
            "--site",
            "lung",
            "--disease-type",
            "neoplasms",
            "--strategy",
            "WGS",
        ]
    )
    assert args.site == "lung"
    assert args.disease_type == "neoplasms"
    assert args.strategy == "WGS"


def test_download_accepts_token_file():
    args = build_parser().parse_args(
        [
            "download",
            "TCGA-BRCA",
            "--dest",
            "/tmp/x",
            "--token-file",
            "/tmp/token.txt",
        ]
    )
    assert args.token_file == "/tmp/token.txt"
