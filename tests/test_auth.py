"""Auth helper tests."""

from gdcfetch.auth import authenticated_session, load_token


def test_load_token_strips_whitespace(tmp_path):
    path = tmp_path / "gdc-user-token.txt"
    path.write_text("  abc123token  \n")
    assert load_token(path) == "abc123token"


def test_authenticated_session_sets_header():
    session = authenticated_session("abc123token")
    assert session.headers["X-Auth-Token"] == "abc123token"


def test_authenticated_session_is_a_real_session_object():
    import requests

    session = authenticated_session("t")
    assert isinstance(session, requests.Session)
