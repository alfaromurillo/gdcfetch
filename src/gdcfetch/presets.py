"""Named query presets for the file types cancer researchers actually want.

GDC's own vocabulary (`data_type`, `workflow_type`, ...) is precise
but not obvious -- you have to already know that mutation calls are
called "Masked Somatic Mutation", or that copy number comes in four
different flavors with different pipelines behind them. This module
is the answer to "I don't want to memorize GDC's schema, I just want
the files that feed mutational-signature analysis X" or "the two
covariates sigmutsel/sigmutselcovs use".

Every entry here was checked live against the GDC API (2026-08) --
`doc_count` in `browse.py`'s output is the way to reverify a preset
still matches reality for a given project, since GDC's available
workflows do occasionally change as pipelines are reprocessed.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Preset:
    """One named, ready-to-use `client.search_files` filter."""

    name: str
    data_type: str
    workflow_type: str | None
    access: str
    description: str
    signature_classes: tuple[str, ...] = ()
    is_covariate: bool = False
    notes: str = ""

    def search_kwargs(self) -> dict:
        """Keyword args to splat into `client.search_files`."""
        return {
            "data_type": self.data_type,
            "workflow_type": self.workflow_type,
            "access": self.access,
        }


PRESETS: dict[str, Preset] = {
    "somatic-mutations": Preset(
        name="somatic-mutations",
        data_type="Masked Somatic Mutation",
        workflow_type="Aliquot Ensemble Somatic Variant Merging and Masking",
        access="open",
        signature_classes=("SBS", "DBS", "ID"),
        description=(
            "Per-aliquot MAF files: single-nucleotide (SNP), "
            "double/triple-nucleotide (DNP/TNP), and short indel "
            "(INS/DEL) calls in the same file, distinguished by the "
            "Variant_Type column."
        ),
        notes=(
            "One download covers SBS, DBS, and ID signature classes "
            "-- COSMIC's SBS/DBS/ID catalogs are all derived from "
            "this same variant-call set, just grouped by adjacency "
            "and length rather than being separate GDC data types. "
            "There is no separate 'DBS calls' or 'indel calls' file "
            "to look for."
        ),
    ),
    "copy-number-segments": Preset(
        name="copy-number-segments",
        data_type="Copy Number Segment",
        workflow_type=None,
        access="open",
        signature_classes=("CN",),
        description="Segment-level copy number calls (unmasked).",
        notes=(
            "Two workflows coexist for TCGA (DNAcopy, GATK4 CNV) -- "
            "leave workflow_type unset to get both, or check "
            "`browse.list_workflow_types(project, "
            "data_type='Copy Number Segment')` and filter to one."
        ),
    ),
    "masked-copy-number-segments": Preset(
        name="masked-copy-number-segments",
        data_type="Masked Copy Number Segment",
        workflow_type="DNAcopy",
        access="open",
        signature_classes=("CN",),
        description=(
            "Segment-level copy number with germline-variant "
            "regions masked out -- the version most CN-signature "
            "pipelines expect."
        ),
    ),
    "gene-level-copy-number": Preset(
        name="gene-level-copy-number",
        data_type="Gene Level Copy Number",
        workflow_type=None,
        access="open",
        signature_classes=("CN",),
        description="Per-gene (not per-segment) copy number calls.",
        notes=(
            "Three workflows exist (ABSOLUTE LiftOver, ASCAT2, "
            "ASCAT3) -- pick one via workflow_type if you need a "
            "single consistent caller across samples."
        ),
    ),
    "allele-specific-copy-number": Preset(
        name="allele-specific-copy-number",
        data_type="Allele-specific Copy Number Segment",
        workflow_type=None,
        access="open",
        signature_classes=("CN",),
        description=(
            "Segment-level copy number split by allele (major/minor "
            "copy number), from ASCAT2 or ASCAT3."
        ),
    ),
    "structural-variants": Preset(
        name="structural-variants",
        data_type="Structural Rearrangement",
        workflow_type=None,
        access="controlled",
        signature_classes=("SV",),
        description="Manta / SvABA structural variant (SV) calls.",
        notes=(
            "CONTROLLED ACCESS -- unlike every other preset here, "
            "this requires dbGaP authorization; `client.search_files` "
            "with access='controlled' will list the files, but "
            "`download_files` will fail with a 403 on the open GDC "
            "API without an authorized token."
        ),
    ),
    "gene-expression": Preset(
        name="gene-expression",
        data_type="Gene Expression Quantification",
        workflow_type="STAR - Counts",
        access="open",
        is_covariate=True,
        description=(
            "Per-sample RNA-seq gene expression (STAR - Counts "
            "workflow: unstranded/stranded counts, TPM, FPKM, "
            "FPKM-UQ)."
        ),
        notes=(
            "Used as a covariate (sigmutselcovs.covariates_"
            "gene_expression), not a mutation-signature input."
        ),
    ),
}


def list_presets() -> dict[str, Preset]:
    """Return all presets, keyed by name."""
    return dict(PRESETS)


def get_preset(name: str) -> Preset:
    """Return one preset by name, raising a helpful error if unknown."""
    try:
        return PRESETS[name]
    except KeyError:
        raise ValueError(
            f"Unknown preset {name!r}; available: "
            f"{', '.join(sorted(PRESETS))}"
        ) from None
