from datetime import datetime, timedelta, timezone

import jwt

import main as api


def test_security_headers_are_present_on_successful_response(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_invalid_and_expired_tokens_are_rejected_safely(client):
    invalid = client.get(
        "/my/farms",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    expired_token = jwt.encode(
        {
            "sub": "1",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        api.JWT_SECRET,
        algorithm=api.JWT_ALGORITHM,
    )
    expired = client.get(
        "/my/farms",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert invalid.status_code == 401
    assert expired.status_code == 401
    assert invalid.json()["detail"] == "Invalid or expired sign-in token."
    assert expired.json()["detail"] == "Invalid or expired sign-in token."


def test_unsafe_request_id_is_replaced(client):
    unsafe_request_id = "unsafe request id\n" + ("x" * 200)
    response = client.get("/", headers={"X-Request-ID": unsafe_request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != unsafe_request_id
    assert len(response.headers["X-Request-ID"]) <= api.MAX_REQUEST_ID_LENGTH


def test_cors_and_trusted_host_configuration_parsing():
    assert api.parse_comma_separated_values(
        " http://localhost:5173, ,https://pilot.example.com,http://localhost:5173 ",
        api.DEFAULT_CORS_ORIGINS,
    ) == ["http://localhost:5173", "https://pilot.example.com"]
    assert api.parse_comma_separated_values("  ", api.DEFAULT_TRUSTED_HOSTS) == []
    assert api.api_docs_enabled(None) is True
    assert api.api_docs_enabled("false") is False


def test_untrusted_host_is_rejected(client):
    response = client.get("/", headers={"Host": "untrusted.example"})

    assert response.status_code == 400
