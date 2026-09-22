import os
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


load_dotenv(Path(__file__).resolve().parents[1] / ".env")
normal_name = os.environ.get("DB_NAME", "")
test_name = os.environ.get("AGRI_TEST_DB_NAME", "")
if not test_name or test_name == normal_name or "test" not in test_name.lower():
    raise RuntimeError("Refusing to run tests without a distinct test-named database.")

os.environ["DB_NAME"] = test_name

import main as api  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def test_database_guard():
    with api.engine.connect() as connection:
        actual_name = connection.execute(text("SELECT current_database()")).scalar_one()
    if actual_name != test_name:
        raise RuntimeError("Refusing to run tests against a database other than AGRI_TEST_DB_NAME.")


@pytest.fixture
def client():
    return TestClient(api.app)


@pytest.fixture
def data():
    created_emails = []

    def create_user(role="farmer", capabilities=()):
        identifier = uuid4().hex
        email = f"{identifier}@pytest.agriconnect.test"
        with api.engine.begin() as connection:
            user = connection.execute(text("""
                INSERT INTO users (full_name, email, phone, password_hash, user_role)
                VALUES (:name, :email, :phone, :password_hash, :role)
                RETURNING user_id, full_name, email, user_role
            """), {
                "name": f"Pytest {role} {identifier[:6]}", "email": email,
                "phone": f"9{identifier[:9]}", "password_hash": api.password_hash.hash("TestPass123!"),
                "role": role,
            }).mappings().one()
            for capability in capabilities:
                connection.execute(text("INSERT INTO user_capabilities (user_id, capability) VALUES (:user_id, :capability)"), {"user_id": user["user_id"], "capability": capability})
        created_emails.append(email)
        return dict(user)

    def provider(verified=False, active=True):
        user = create_user("supplier", ())
        with api.engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO supplier_profiles (supplier_id, business_name, is_active, verified_at)
                VALUES (:user_id, :name, :active, :verified_at)
            """), {"user_id": user["user_id"], "name": f"Provider {user['user_id']}", "active": active, "verified_at": "2025-01-01" if verified else None})
        return user

    def headers(user):
        return {"Authorization": f"Bearer {api.create_access_token(user['user_id'], user['user_role'])}"}

    yield type("Data", (), {"create_user": create_user, "provider": provider, "headers": headers})

    with api.engine.begin() as connection:
        users = connection.execute(text("SELECT user_id FROM users WHERE email = ANY(:emails)"), {"emails": created_emails}).scalars().all()
        if users:
            booking_ids = connection.execute(text("SELECT booking_id FROM bookings WHERE farmer_id = ANY(:users) OR supplier_id = ANY(:users)"), {"users": users}).scalars().all()
            if booking_ids:
                connection.execute(text("DELETE FROM notifications WHERE related_booking_id = ANY(:bookings)"), {"bookings": booking_ids})
                connection.execute(text("DELETE FROM booking_status_history WHERE booking_id = ANY(:bookings)"), {"bookings": booking_ids})
                connection.execute(text("DELETE FROM booking_slot_reservations WHERE booking_id = ANY(:bookings)"), {"bookings": booking_ids})
                connection.execute(text("DELETE FROM booking_items WHERE booking_id = ANY(:bookings)"), {"bookings": booking_ids})
                connection.execute(text("DELETE FROM bookings WHERE booking_id = ANY(:bookings)"), {"bookings": booking_ids})
            connection.execute(text("DELETE FROM notifications WHERE user_id = ANY(:users)"), {"users": users})
            connection.execute(text("DELETE FROM documents WHERE user_id = ANY(:users)"), {"users": users})
            connection.execute(text("DELETE FROM availability_slots WHERE supplier_service_id IN (SELECT supplier_service_id FROM supplier_services WHERE supplier_id = ANY(:users))"), {"users": users})
            connection.execute(text("DELETE FROM supplier_services WHERE supplier_id = ANY(:users)"), {"users": users})
            connection.execute(text("DELETE FROM supplier_profiles WHERE supplier_id = ANY(:users)"), {"users": users})
            connection.execute(text("DELETE FROM user_capabilities WHERE user_id = ANY(:users)"), {"users": users})
            connection.execute(text("DELETE FROM users WHERE user_id = ANY(:users)"), {"users": users})
