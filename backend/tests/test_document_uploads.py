from sqlalchemy import text

import main as api


PDF_CONTENT = b"%PDF-1.4\nprovider verification test\n"


def upload(client, user, document_type="driving_licence", filename="licence.pdf", content=PDF_CONTENT, content_type="application/pdf"):
    return client.post(
        "/provider/documents",
        data={"document_type": document_type},
        files={"file": (filename, content, content_type)},
        headers={"Authorization": f"Bearer {api.create_access_token(user['user_id'], user['user_role'])}"},
    )


def test_provider_upload_and_authenticated_file_access(client, data, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DOCUMENT_STORAGE_DIR", tmp_path)
    provider = data.provider()
    other_provider = data.provider()
    admin = data.create_user("admin")

    response = upload(client, provider, filename="../licence.pdf")
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["has_uploaded_file"] is True
    assert document["file_name"] == "licence.pdf"
    with api.engine.connect() as connection:
        reference = connection.execute(text("SELECT file_url FROM documents WHERE document_id=:id"), {"id": document["document_id"]}).scalar_one()
    assert reference.startswith(api.STORED_DOCUMENT_REFERENCE_PREFIX)
    assert (tmp_path / reference.split(":", 1)[1]).is_file()

    own = client.get(f"/provider/documents/{document['document_id']}/file", headers=data.headers(provider))
    other = client.get(f"/provider/documents/{document['document_id']}/file", headers=data.headers(other_provider))
    admin_response = client.get(f"/provider/documents/{document['document_id']}/file", headers=data.headers(admin))
    assert own.status_code == 200
    assert own.headers["content-type"] == "application/pdf"
    assert other.status_code == 403
    assert admin_response.status_code == 200
    assert client.get(f"/provider/documents/{document['document_id']}/file").status_code == 401


def test_upload_rejects_unsupported_or_oversized_content(client, data, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DOCUMENT_STORAGE_DIR", tmp_path)
    provider = data.provider()
    assert upload(client, provider, filename="bad.txt", content=b"text", content_type="text/plain").status_code == 400
    monkeypatch.setattr(api, "MAX_DOCUMENT_UPLOAD_BYTES", 10)
    assert upload(client, provider, content=PDF_CONTENT, content_type="application/pdf").status_code == 400
    assert not list(tmp_path.iterdir())


def test_database_rejection_removes_written_file(client, data, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DOCUMENT_STORAGE_DIR", tmp_path)
    supplier_without_profile = data.create_user("supplier")
    response = upload(client, supplier_without_profile)
    assert response.status_code == 404
    assert not list(tmp_path.iterdir())
