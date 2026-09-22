from datetime import datetime, timedelta

import main as api
from sqlalchemy import text


def future_hour(offset):
    value = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=7, hours=offset)
    return value


def service_with_slots(data, starts, capacity=1, verified=True):
    provider = data.provider(verified=verified)
    category_id = None
    with api.engine.begin() as connection:
        category_id = connection.execute(text("INSERT INTO service_categories (category_name) VALUES (:name) RETURNING category_id"), {"name": f"Booking pytest {provider['user_id']}"}).scalar_one()
        service_id = connection.execute(text("""INSERT INTO supplier_services (supplier_id, category_id, service_name, pricing_unit, base_price, is_active) VALUES (:provider, :category, :name, 'hour', 100, TRUE) RETURNING supplier_service_id"""), {"provider": provider["user_id"], "category": category_id, "name": f"Booking service {provider['user_id']}"}).scalar_one()
        slot_ids = []
        for start in starts:
            slot_ids.append(connection.execute(text("""INSERT INTO availability_slots (supplier_service_id, starts_at, ends_at, capacity, status) VALUES (:service, :start, :end, :capacity, 'available') RETURNING availability_slot_id"""), {"service": service_id, "start": start, "end": start + timedelta(hours=1), "capacity": capacity}).scalar_one())
    return provider, service_id, slot_ids, category_id


def booking_payload(service_id, start, hours=1):
    return {"supplier_service_id": service_id, "requested_start_at": start.isoformat(), "requested_end_at": (start + timedelta(hours=hours)).isoformat(), "quantity": 1}


def reservation_count(booking_id):
    with api.engine.connect() as connection:
        return connection.execute(text("SELECT count(*) FROM booking_slot_reservations WHERE booking_id=:booking"), {"booking": booking_id}).scalar_one()


def test_canonical_booking_creates_relational_side_effects(client, data):
    farmer = data.create_user()
    provider, service_id, _, _ = service_with_slots(data, [future_hour(1)])
    response = client.post("/my/bookings", json=booking_payload(service_id, future_hour(1)), headers=data.headers(farmer))
    assert response.status_code == 201, response.text
    booking_id = response.json()["booking_id"]
    with api.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM booking_items WHERE booking_id=:id"), {"id": booking_id}).scalar_one() == 1
        assert connection.execute(text("SELECT count(*) FROM booking_status_history WHERE booking_id=:id"), {"id": booking_id}).scalar_one() == 1
        assert connection.execute(text("SELECT count(*) FROM notifications WHERE user_id=:id AND related_booking_id=:booking"), {"id": provider["user_id"], "booking": booking_id}).scalar_one() == 1
    assert reservation_count(booking_id) == 1


def test_capacity_and_unverified_provider_rejections_leave_no_booking(client, data):
    first = data.create_user()
    second = data.create_user()
    _, service_id, _, _ = service_with_slots(data, [future_hour(2)])
    first_response = client.post("/my/bookings", json=booking_payload(service_id, future_hour(2)), headers=data.headers(first))
    assert first_response.status_code == 201
    assert client.post("/my/bookings", json=booking_payload(service_id, future_hour(2)), headers=data.headers(second)).status_code == 400
    _, hidden_service, _, _ = service_with_slots(data, [future_hour(3)], verified=False)
    assert client.post("/my/bookings", json=booking_payload(hidden_service, future_hour(3)), headers=data.headers(second)).status_code == 403


def test_multi_hour_and_missing_slot_requests_are_atomic(client, data):
    farmer = data.create_user()
    start = future_hour(4)
    _, service_id, slot_ids, _ = service_with_slots(data, [start, start + timedelta(hours=1), start + timedelta(hours=2)])
    response = client.post("/my/bookings", json=booking_payload(service_id, start, 3), headers=data.headers(farmer))
    assert response.status_code == 201, response.text
    assert reservation_count(response.json()["booking_id"]) == 3
    missing_start = future_hour(8)
    _, missing_service, _, _ = service_with_slots(data, [missing_start, missing_start + timedelta(hours=2)])
    failed = client.post("/my/bookings", json=booking_payload(missing_service, missing_start, 3), headers=data.headers(farmer))
    assert failed.status_code == 400
    with api.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM bookings WHERE farmer_id=:farmer AND supplier_id=(SELECT supplier_id FROM supplier_services WHERE supplier_service_id=:service)"), {"farmer": farmer["user_id"], "service": missing_service}).scalar_one() == 0


def test_legacy_booking_delegates_to_transactional_path(client, data):
    farmer = data.create_user()
    _, service_id, _, _ = service_with_slots(data, [future_hour(12)])
    payload = {"farmer_id": farmer["user_id"], **booking_payload(service_id, future_hour(12))}
    assert client.post("/bookings", json=payload).status_code == 401
    response = client.post("/bookings", json=payload, headers=data.headers(farmer))
    assert response.status_code == 200, response.text
    assert reservation_count(response.json()["booking_id"]) == 1


def test_provider_can_confirm_pending_booking_and_invalid_transition_is_rejected(client, data):
    farmer = data.create_user()
    provider, service_id, _, _ = service_with_slots(data, [future_hour(14)])
    created = client.post("/my/bookings", json=booking_payload(service_id, future_hour(14)), headers=data.headers(farmer)).json()
    booking_id = created["booking_id"]
    confirmed = client.put(f"/supplier/bookings/{booking_id}/status", json={"new_status": "confirmed"}, headers=data.headers(provider))
    assert confirmed.status_code == 200, confirmed.text
    assert client.put(f"/supplier/bookings/{booking_id}/status", json={"new_status": "completed"}, headers=data.headers(provider)).status_code == 400
    with api.engine.connect() as connection:
        assert connection.execute(text("SELECT status FROM bookings WHERE booking_id=:id"), {"id": booking_id}).scalar_one() == "confirmed"
        assert connection.execute(text("SELECT count(*) FROM booking_status_history WHERE booking_id=:id AND new_status='confirmed'"), {"id": booking_id}).scalar_one() == 1


def test_successful_reschedule_moves_all_reservations(client, data):
    farmer = data.create_user()
    start = future_hour(16)
    target = start + timedelta(hours=5)
    provider, service_id, slots, _ = service_with_slots(data, [start + timedelta(hours=i) for i in range(3)] + [target + timedelta(hours=i) for i in range(3)])
    created = client.post("/my/bookings", json=booking_payload(service_id, start, 3), headers=data.headers(farmer)).json()
    booking_id = created["booking_id"]
    response = client.post(f"/my/bookings/{booking_id}/reschedule", json={"requested_start_at": target.isoformat(), "requested_end_at": (target + timedelta(hours=3)).isoformat()}, headers=data.headers(farmer))
    assert response.status_code == 200, response.text
    with api.engine.connect() as connection:
        reserved = set(connection.execute(text("SELECT availability_slot_id FROM booking_slot_reservations WHERE booking_id=:id"), {"id": booking_id}).scalars())
        booking = connection.execute(text("SELECT requested_start_at, requested_end_at, supplier_id FROM bookings WHERE booking_id=:id"), {"id": booking_id}).mappings().one()
        assert connection.execute(text("SELECT count(*) FROM booking_status_history WHERE booking_id=:id"), {"id": booking_id}).scalar_one() == 2
        assert connection.execute(text("SELECT count(*) FROM notifications WHERE related_booking_id=:id AND user_id=:provider"), {"id": booking_id, "provider": provider["user_id"]}).scalar_one() == 2
    assert reserved == set(slots[3:])
    assert booking["requested_start_at"] == target and booking["requested_end_at"] == target + timedelta(hours=3)


def test_failed_full_slot_reschedule_preserves_original_reservation(client, data):
    farmer_a, farmer_b = data.create_user(), data.create_user()
    start, target = future_hour(25), future_hour(28)
    _, service_id, slots, _ = service_with_slots(data, [start, target], capacity=1)
    booking_a = client.post("/my/bookings", json=booking_payload(service_id, start), headers=data.headers(farmer_a)).json()["booking_id"]
    booking_b = client.post("/my/bookings", json=booking_payload(service_id, target), headers=data.headers(farmer_b)).json()["booking_id"]
    failed = client.post(f"/my/bookings/{booking_a}/reschedule", json={"requested_start_at": target.isoformat(), "requested_end_at": (target + timedelta(hours=1)).isoformat()}, headers=data.headers(farmer_a))
    assert failed.status_code == 400
    with api.engine.connect() as connection:
        reservations = connection.execute(text("SELECT booking_id, availability_slot_id FROM booking_slot_reservations WHERE booking_id IN (:a, :b) ORDER BY booking_id"), {"a": booking_a, "b": booking_b}).all()
        original_start = connection.execute(text("SELECT requested_start_at FROM bookings WHERE booking_id=:id"), {"id": booking_a}).scalar_one()
    assert reservations == [(booking_a, slots[0]), (booking_b, slots[1])]
    assert original_start == start


def test_reschedule_duration_and_missing_slot_rejections_keep_original_reservation(client, data):
    farmer = data.create_user()
    start, target = future_hour(31), future_hour(35)
    _, service_id, slots, _ = service_with_slots(data, [start, start + timedelta(hours=1), target, target + timedelta(hours=2)])
    booking_id = client.post("/my/bookings", json=booking_payload(service_id, start, 2), headers=data.headers(farmer)).json()["booking_id"]
    shorter = client.post(f"/my/bookings/{booking_id}/reschedule", json={"requested_start_at": target.isoformat(), "requested_end_at": (target + timedelta(hours=1)).isoformat()}, headers=data.headers(farmer))
    missing = client.post(f"/my/bookings/{booking_id}/reschedule", json={"requested_start_at": target.isoformat(), "requested_end_at": (target + timedelta(hours=2)).isoformat()}, headers=data.headers(farmer))
    assert shorter.status_code == 400 and missing.status_code == 400
    with api.engine.connect() as connection:
        reserved = set(connection.execute(text("SELECT availability_slot_id FROM booking_slot_reservations WHERE booking_id=:id"), {"id": booking_id}).scalars())
    assert reserved == set(slots[:2])
