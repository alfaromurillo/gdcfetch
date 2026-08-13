"""Authentication for controlled-access GDC data.

GDC gates controlled-access files (e.g. the `structural-variants`
preset) behind dbGaP authorization: a researcher applies for access
to a specific project through dbGaP, authenticates via eRA Commons,
then downloads a token from the GDC Data Portal
(https://portal.gdc.cancer.gov -> user icon -> Download Token). That
token is sent as an ``X-Auth-Token`` HTTP header on download
requests -- this module is a thin, honest wrapper around exactly
that mechanism. It does not grant access to anything; it only lets
an already-authorized researcher's own token reach the API the way
GDC expects.

Searching (`client.search_files`) does not require a token even for
controlled-access files -- GDC lists their metadata openly. Only
downloading the bytes (`client.download_files`,
`client.download_by_uuid`) needs an authenticated session.
"""

from pathlib import Path

import requests


def load_token(path: str | Path) -> str:
    """Read a GDC token file (as downloaded from the GDC Data Portal).

    The portal's download is a bare token string in a file named
    something like ``gdc-user-token.<date>.txt`` -- this just reads
    and strips it.
    """
    return Path(path).read_text().strip()


def authenticated_session(token: str) -> requests.Session:
    """Return a `requests.Session` that sends ``token`` as X-Auth-Token.

    Pass the result as ``session=`` to `client.download_files` or
    `client.download_by_uuid` to download controlled-access files
    you're authorized for.
    """
    session = requests.Session()
    session.headers["X-Auth-Token"] = token
    return session
