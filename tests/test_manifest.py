"""Manifest / sample sheet format tests (golden rows)."""

from gdcfetch.manifest import write_manifest, write_sample_sheet

HIT = {
    "file_id": "2c73d8ac-84b9-4094-9f5e-fbd6c2e8eabf",
    "file_name": (
        "c8c7600d-2c13-4df1-b058-2d02432bd49e"
        ".rna_seq.augmented_star_gene_counts.tsv"
    ),
    "md5sum": "4f9639a7ecab8b0dab8db9b17f145a2c",
    "file_size": 4216302,
    "state": "released",
    "data_category": "Transcriptome Profiling",
    "data_type": "Gene Expression Quantification",
    "cases": [
        {
            "project": {"project_id": "TCGA-COAD"},
            "submitter_id": "TCGA-AA-3688",
            "samples": [
                {
                    "submitter_id": "TCGA-AA-3688-01A",
                    "tissue_type": "Tumor",
                    "tumor_descriptor": "Primary",
                    "specimen_type": None,
                    "preservation_method": None,
                }
            ],
        }
    ],
}


def test_manifest_matches_gdc_client_format(tmp_path):
    path = write_manifest([HIT], tmp_path / "manifest.txt")
    lines = path.read_text().splitlines()
    assert lines[0] == "id\tfilename\tmd5\tsize\tstate"
    assert lines[1] == (
        "2c73d8ac-84b9-4094-9f5e-fbd6c2e8eabf\t"
        "c8c7600d-2c13-4df1-b058-2d02432bd49e"
        ".rna_seq.augmented_star_gene_counts.tsv\t"
        "4f9639a7ecab8b0dab8db9b17f145a2c\t4216302\treleased"
    )


def test_sample_sheet_golden_row(tmp_path):
    path = write_sample_sheet([HIT], tmp_path / "sheet.tsv")
    lines = path.read_text().splitlines()
    assert lines[0] == (
        "File ID\tFile Name\tData Category\tData Type\t"
        "Project ID\tCase ID\tSample ID\tTissue Type\t"
        "Tumor Descriptor\tSpecimen Type\tPreservation Method"
    )
    assert lines[1] == (
        "2c73d8ac-84b9-4094-9f5e-fbd6c2e8eabf\t"
        "c8c7600d-2c13-4df1-b058-2d02432bd49e"
        ".rna_seq.augmented_star_gene_counts.tsv\t"
        "Transcriptome Profiling\tGene Expression Quantification\t"
        "TCGA-COAD\tTCGA-AA-3688\tTCGA-AA-3688-01A\tTumor\tPrimary\t"
        "Unknown\tUnknown"
    )


def test_sample_sheet_dated_name(tmp_path):
    path = write_sample_sheet([HIT], directory=tmp_path)
    assert path.name.startswith("gdc_sample_sheet.")
    assert path.name.endswith(".tsv")
