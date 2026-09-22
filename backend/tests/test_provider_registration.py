from sqlalchemy import text
import main as api


def test_farmer_registers_provider_on_same_account(client, data):
    farmer = data.create_user()
    headers = data.headers(farmer)
    assert client.get('/provider/profile', headers=headers).status_code == 404
    assert client.get('/supplier/dashboard', headers=headers).status_code == 403
    response = client.post('/provider/profile', headers=headers, json={'business_name': 'Farm Services'})
    assert response.status_code == 201, response.text
    assert response.json()['supplier_id'] == farmer['user_id']
    user = client.get('/auth/me', headers=headers).json()
    assert user['user_id'] == farmer['user_id']
    assert user['user_role'] == 'farmer'
    assert set(user['capabilities']) == {'farmer', 'provider'}
    assert client.get('/supplier/dashboard', headers=headers).status_code == 200
    assert client.get('/provider/profile', headers=headers).status_code == 200
    assert client.post('/provider/profile', headers=headers, json={'business_name': 'Duplicate'}).status_code == 409
    with api.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM users WHERE email = :email'), {'email': farmer['email']}).scalar_one() == 1
        assert connection.execute(text('SELECT count(*) FROM supplier_profiles WHERE supplier_id = :id'), {'id': farmer['user_id']}).scalar_one() == 1


def test_invalid_registration_does_not_grant_access(client, data):
    farmer = data.create_user()
    headers = data.headers(farmer)
    assert client.post('/provider/profile', headers=headers, json={'business_name': ''}).status_code == 422
    assert client.get('/auth/me', headers=headers).json()['capabilities'] == ['farmer']
    assert client.get('/provider/profile', headers=headers).status_code == 404


def test_registration_requires_eligible_authenticated_account(client, data):
    assert client.post('/provider/profile', json={'business_name': 'Services'}).status_code == 401
    admin = data.create_user('admin')
    assert client.post('/provider/profile', headers=data.headers(admin), json={'business_name': 'Services'}).status_code == 403


def test_existing_provider_can_still_create_and_edit_profile(client, data):
    provider = data.create_user('supplier')
    headers = data.headers(provider)
    assert client.post('/provider/profile', headers=headers, json={'business_name': 'Services'}).status_code == 201
    assert client.put('/provider/profile', headers=headers, json={'business_name': 'Updated Services'}).status_code == 200
