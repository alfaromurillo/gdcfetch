"""TCGA aliquot-barcode parsing and case-level GDC metadata lookups.

Every ``somatic-mutations``-preset (and similar) download produces
one file per sequenced *aliquot*, with no sample-type filtering or
per-case deduplication -- a case (patient) with multiple sequenced
aliquots (a re-plated portion, or both a primary and a metastatic
tumor) becomes multiple independent files, and nothing here decides
that for you. This module gives downstream consumers (sigmutsel's
``tcga_sample_selection``, or anyone else parsing what
`download_files`/`download_tcga_maf_files`-style tools fetched) the
two pieces of GDC metadata needed to make that call themselves: what
a barcode's sample-type code means, and each case's real per-sample
collection day / prior-treatment status (both live in GDC's clinical
data, not the barcode).
"""

import logging
from dataclasses import dataclass

import requests

from .client import GDC_API

logger = logging.getLogger(__name__)

# Official TCGA sample type codes, as tabulated at
# https://gdc.cancer.gov/resources-tcga-users/tcga-code-tables/sample-type-codes
# (verified 2026-08-21).
SAMPLE_TYPE_CODES = {
    "01": "Primary Solid Tumor",
    "02": "Recurrent Solid Tumor",
    "03": "Primary Blood Derived Cancer - Peripheral Blood",
    "04": "Recurrent Blood Derived Cancer - Bone Marrow",
    "05": "Additional - New Primary",
    "06": "Metastatic",
    "07": "Additional Metastatic",
    "08": "Human Tumor Original Cells",
    "09": "Primary Blood Derived Cancer - Bone Marrow",
    "10": "Blood Derived Normal",
    "11": "Solid Tissue Normal",
    "12": "Buccal Cell Normal",
    "13": "EBV Immortalized Normal",
    "14": "Bone Marrow Normal",
    "15": "sample type 15",
    "16": "sample type 16",
    "20": "Control Analyte",
    "40": "Recurrent Blood Derived Cancer - Peripheral Blood",
    "50": "Cell Lines",
    "60": "Primary Xenograft Tissue",
    "61": "Cell Line Derived Xenograft Tissue",
    "99": "sample type 99",
}


@dataclass(frozen=True, slots=True)
class TcgaBarcodeInfo:
    """Parsed fields of one TCGA aliquot barcode.

    See https://docs.gdc.cancer.gov/Encyclopedia/pages/TCGA_Barcode/
    for the field layout.
    """

    barcode: str
    case_id: str  # e.g. "TCGA-AA-3971"
    # e.g. "TCGA-AA-3971-01A" -- matches GDC's samples.submitter_id
    sample_id: str
    sample_type_code: str  # e.g. "01"
    vial: str  # e.g. "A"
    portion_analyte: str | None
    plate: str | None
    center: str | None

    @property
    def sample_type_name(self) -> str:
        return SAMPLE_TYPE_CODES.get(self.sample_type_code, "unknown")


def parse_tcga_barcode(barcode: str) -> TcgaBarcodeInfo:
    """Parse a TCGA aliquot barcode into its component fields.

    Parameters
    ----------
    barcode : str
        A full TCGA aliquot barcode, e.g.
        ``"TCGA-AA-3971-01A-01W-0995-10"``.

    Returns
    -------
    TcgaBarcodeInfo

    Raises
    ------
    ValueError
        If *barcode* does not have the minimum ``TCGA-XX-XXXX-SSV``
        structure (project, TSS, participant, sample-type+vial).
    """
    fields = barcode.split("-")
    if len(fields) < 4 or len(fields[3]) < 2:
        raise ValueError(
            f"Not a valid TCGA aliquot barcode: {barcode!r}"
        )
    case_id = "-".join(fields[:3])
    type_vial = fields[3]
    sample_type_code = type_vial[:2]
    vial = type_vial[2:]
    sample_id = f"{case_id}-{type_vial}"
    portion_analyte = fields[4] if len(fields) > 4 else None
    plate = fields[5] if len(fields) > 5 else None
    center = fields[6] if len(fields) > 6 else None
    return TcgaBarcodeInfo(
        barcode=barcode,
        case_id=case_id,
        sample_id=sample_id,
        sample_type_code=sample_type_code,
        vial=vial,
        portion_analyte=portion_analyte,
        plate=plate,
        center=center,
    )


def fetch_case_metadata(
    case_ids: list[str],
    *,
    session: requests.Session | None = None,
    timeout: int = 60,
) -> dict[str, dict]:
    """Fetch per-sample collection day and prior-treatment status from GDC.

    Queries the GDC cases endpoint (``POST /cases``) for each case's
    ``samples.submitter_id``/``samples.days_to_collection`` and
    ``diagnoses.prior_treatment``.

    Parameters
    ----------
    case_ids : list of str
        TCGA case (patient) barcodes, e.g. ``"TCGA-AA-3971"``.
    session : requests.Session or None
        Reused if given (matches `client.search_files`'s convention).
    timeout : int, default 60
        Request timeout in seconds.

    Returns
    -------
    dict[str, dict]
        Keyed by case_id. Each value has:

        - ``"prior_treatment"``: ``"Yes"``, ``"No"``, or ``None`` if
          not reported (case-level; GDC's ``diagnoses`` field does
          not distinguish which sample a treatment record relates
          to).
        - ``"sample_days_to_collection"``: dict mapping
          ``samples.submitter_id`` (e.g. ``"TCGA-AA-3971-01A"``) to
          its ``days_to_collection`` (int) or ``None`` if not
          reported.

    Notes
    -----
    ``days_to_collection`` and ``prior_treatment`` are frequently
    ``null`` in GDC for TCGA cases (spot-checked 2026-08-21 against
    live cases with multiple aliquots) -- callers doing
    date-ordered selection among a case's files should expect some
    cases to have no usable dates at all.
    """
    case_ids = list(dict.fromkeys(case_ids))  # de-dupe, keep order
    if not case_ids:
        return {}

    session = session or requests.Session()
    filters = {
        "op": "in",
        "content": {"field": "submitter_id", "value": case_ids},
    }
    fields = ",".join(
        [
            "submitter_id",
            "samples.submitter_id",
            "samples.days_to_collection",
            "diagnoses.prior_treatment",
        ]
    )
    payload = {
        "filters": filters,
        "fields": fields,
        "size": len(case_ids),
    }
    logger.info(
        "Querying GDC cases API for %d case(s)...", len(case_ids)
    )
    response = session.post(
        f"{GDC_API}/cases", json=payload, timeout=timeout
    )
    response.raise_for_status()
    hits = response.json()["data"]["hits"]

    metadata: dict[str, dict] = {}
    for hit in hits:
        case_id = hit.get("submitter_id")
        if case_id is None:
            continue
        diagnoses = hit.get("diagnoses") or []
        prior_treatment = None
        if diagnoses:
            prior_treatment = diagnoses[0].get("prior_treatment")
        sample_days = {
            sample.get("submitter_id"): sample.get(
                "days_to_collection"
            )
            for sample in (hit.get("samples") or [])
            if sample.get("submitter_id") is not None
        }
        metadata[case_id] = {
            "prior_treatment": prior_treatment,
            "sample_days_to_collection": sample_days,
        }

    missing = set(case_ids) - metadata.keys()
    if missing:
        logger.warning(
            "GDC cases API returned no record for %d case(s): %s",
            len(missing),
            sorted(missing)[:10],
        )
    return metadata
