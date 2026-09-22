from uuid import uuid4
import pytest
from sqlalchemy import text
import main as api


@pytest.fixture
def registered(client):
    ids = []
    def create(**overrides):
        payload = {'full_name': 'Onboarding Test', 'phone': '9' + str(uuid4().int)[:9],
                   'password': 'TestPass123!', 'user_role': 'farmer', **overrides}
        response = client.post('/auth/register', json=payload)
        assert response.status_code == 201, response.text
        ids.append(response.json()['user']['user_id'])
        return payload, response.json()['user']
    yield create
    with api.engine.begin() as connection:
        for table, column in [('supplier_services', 'supplier_id'), ('supplier_profiles', 'supplier_id'),
                              ('user_capabilities', 'user_id'), ('farms', 'farmer_id'), ('addresses', 'user_id'), ('users', 'user_id')]:
            connection.execute(text(f'DELETE FROM {table} WHERE {column} = ANY(:ids)'), {'ids': ids})


def test_mobile_only_registration_and_login(client, registered):
    payload, user = registered()
    assert user['email'] is None
    response = client.post('/auth/login', json={'phone': payload['phone'], 'password': payload['password']})
    assert response.status_code == 200
    assert response.json()['user']['user_id'] == user['user_id']
    assert client.post('/auth/login', json={'phone': payload['phone'], 'password': 'incorrect'}).status_code == 401
    assert client.post('/auth/register', json={**payload, 'phone': payload['phone'][:5] + ' ' + payload['phone'][5:]}).status_code == 409


def test_email_login_still_works(client, registered):
    payload, user = registered(email=f'{uuid4().hex}@pytest.agriconnect.test', phone=None)
    response = client.post('/auth/login', json={'email': payload['email'].upper(), 'password': payload['password']})
    assert response.status_code == 200
    assert response.json()['user']['user_id'] == user['user_id']


def test_missing_contact_rejected(client):
    assert client.post('/auth/register', json={'full_name': 'Test Farmer', 'password': 'TestPass123!', 'user_role': 'farmer'}).status_code == 422
    assert client.post('/auth/login', json={'password': 'TestPass123!'}).status_code == 422
    assert client.post('/auth/login', json={'phone': 'letters', 'password': 'TestPass123!'}).status_code == 422


def test_saved_farm_and_address_available_for_booking(client, registered):
    payload, user = registered()
    headers = {'Authorization': f"Bearer {api.create_access_token(user['user_id'], 'farmer')}"}
    assert client.get('/my/farms', headers=headers).json() == []
    farm = client.post('/farms', headers=headers, json={'farm_name': 'First Farm', 'location': 'Test Village', 'total_area_acres': 2})
    assert farm.status_code == 201
    address = client.post('/addresses', headers=headers, json={'address_line1': 'Farm Road', 'village_or_city': 'Test Village', 'state': 'Telangana'})
    assert address.status_code == 201
    assert client.get('/my/farms', headers=headers).json()[0]['farm_id'] == farm.json()['farm_id']
    assert client.get('/my/addresses', headers=headers).json()[0]['address_id'] == address.json()['address_id']


@pytest.mark.parametrize('role', ['farmer', 'supplier'])
def test_first_provider_service_uses_same_account(client, registered, role):
    payload, user = registered(user_role=role, business_name='Test Services')
    headers = {'Authorization': f"Bearer {api.create_access_token(user['user_id'], role)}"}
    if role == 'farmer':
        assert client.post('/provider/profile', headers=headers, json={'business_name': 'Test Services'}).status_code == 201
    assert client.get('/supplier/services', headers=headers).json() == []
    with api.engine.begin() as connection:
        parent = connection.execute(text("INSERT INTO service_categories (category_name) VALUES ('Onboarding test') RETURNING category_id")).scalar_one()
        child = connection.execute(text("INSERT INTO service_categories (category_name, parent_category_id) VALUES ('Onboarding child', :parent) RETURNING category_id"), {'parent': parent}).scalar_one()
    try:
        service = client.post('/supplier/services', headers=headers, json={'category_id': child, 'pricing_unit': 'acre', 'base_price': 100})
        assert service.status_code == 201, service.text
        assert len(client.get('/supplier/services', headers=headers).json()) == 1
        assert client.get('/auth/me', headers=headers).json()['user_id'] == user['user_id']
    finally:
        with api.engine.begin() as connection:
            connection.execute(text('DELETE FROM supplier_services WHERE supplier_id = :id'), {'id': user['user_id']})
            connection.execute(text('DELETE FROM service_categories WHERE category_id = :id'), {'id': child})
            connection.execute(text('DELETE FROM service_categories WHERE category_id = :id'), {'id': parent})
