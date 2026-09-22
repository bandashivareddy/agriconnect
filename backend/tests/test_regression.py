import main as api
from sqlalchemy import text


def test_auth_me_reports_dual_capabilities(client, data):
    user = data.create_user("farmer", ("provider",))
    response = client.get("/auth/me", headers=data.headers(user))
    assert response.status_code == 200
    assert set(response.json()["capabilities"]) == {"farmer", "provider"}


def test_private_endpoint_requires_authentication(client):
    assert client.get("/my/farms").status_code == 401


def test_provider_cannot_access_farmer_routes(client, data):
    provider = data.provider()
    for path in (f"/farmers/{provider['user_id']}/farms", f"/farmers/{provider['user_id']}/addresses"):
        assert client.get(path, headers=data.headers(provider)).status_code == 403


def test_farmer_can_only_access_own_legacy_data(client, data):
    farmer = data.create_user()
    other = data.create_user()
    assert client.get(f"/farmers/{farmer['user_id']}/farms", headers=data.headers(farmer)).status_code == 200
    assert client.get(f"/farmers/{farmer['user_id']}/addresses", headers=data.headers(farmer)).status_code == 200
    assert client.get(f"/farmers/{other['user_id']}/farms", headers=data.headers(farmer)).status_code == 403


def test_provider_document_starts_pending_and_rejects_unknown_type(client, data):
    provider = data.provider()
    payload = {"document_type": "driving_licence", "file_name": "licence.pdf", "file_url": "https://example.test/licence.pdf"}
    response = client.post("/provider/documents", json=payload, headers=data.headers(provider))
    assert response.status_code == 201
    assert response.json()["verification_status"] == "pending"
    payload["document_type"] = "arbitrary_document"
    assert client.post("/provider/documents", json=payload, headers=data.headers(provider)).status_code == 400


def test_marketplace_hides_unverified_and_inactive_provider_services(client, data):
    verified = data.provider(verified=True)
    unverified = data.provider()
    inactive = data.provider(verified=True, active=False)
    category_id = None
    with api.engine.begin() as connection:
        category_id = connection.execute(text("INSERT INTO service_categories (category_name) VALUES (:name) RETURNING category_id"), {"name": f"Pytest category {verified['user_id']}"}).scalar_one()
        for user, name in ((verified, "Visible"), (unverified, "Hidden"), (inactive, "Inactive")):
            connection.execute(text("""INSERT INTO supplier_services (supplier_id, category_id, service_name, pricing_unit, base_price, is_active) VALUES (:supplier, :category, :name, 'hour', 100, TRUE)"""), {"supplier": user["user_id"], "category": category_id, "name": f"{name} {user['user_id']}"})
    try:
        names = {item["service_name"] for item in client.get("/services").json()}
        assert f"Visible {verified['user_id']}" in names
        assert f"Hidden {unverified['user_id']}" not in names
        assert f"Inactive {inactive['user_id']}" not in names
    finally:
        with api.engine.begin() as connection:
            connection.execute(text("DELETE FROM supplier_services WHERE category_id = :category_id"), {"category_id": category_id})
            connection.execute(text("DELETE FROM service_categories WHERE category_id = :category_id"), {"category_id": category_id})
