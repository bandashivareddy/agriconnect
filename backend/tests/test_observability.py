import main as api


def test_successful_response_includes_generated_request_id(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_safe_client_request_id_is_reused(client):
    request_id = "agriconnect-client-request-123"
    response = client.get("/", headers={"X-Request-ID": request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


def test_business_error_keeps_detail_and_includes_request_id(client):
    response = client.get("/my/farms")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired sign-in token."
    assert response.headers["X-Request-ID"]


def test_unexpected_error_is_generic_and_includes_request_id(client, monkeypatch):
    def raise_unexpected_error():
        raise RuntimeError("sensitive internal database failure")

    monkeypatch.setattr(api.engine, "connect", raise_unexpected_error)

    response = client.get("/health/database")

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert "sensitive internal database failure" not in response.text
