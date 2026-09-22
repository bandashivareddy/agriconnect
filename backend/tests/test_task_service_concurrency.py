from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
import main as api
from task_services import create_task_service_router
from test_crop_management_concurrency import concurrent_cm
from test_field_work_concurrency import fc,race
from test_farm_ledger_concurrency import ledger
from test_crop_inputs_concurrency import catalogue
from test_harvest_concurrency import harvests
from test_production_concurrency import production


@pytest.fixture
def integrated(production,monkeypatch):
    h=production;e=h['engine']
    path=Path(__file__).resolve().parents[1]/'alembic/versions/c7f216a2e485_task_service_booking.py'
    spec=spec_from_file_location('booking_integration_migration',path);migration=module_from_spec(spec);spec.loader.exec_module(migration)
    with e.begin() as c:
        for table in ('service_categories','supplier_profiles','supplier_services','availability_slots','bookings','booking_items','booking_slot_reservations','booking_status_history','notifications'):
            c.execute(text(f'CREATE TABLE {table} (LIKE public.{table} INCLUDING ALL)'))
        c.execute(text('''DROP TRIGGER task_service_snapshot_guard ON crop_tasks; DROP FUNCTION task_service_snapshot_guard();
          ALTER TABLE sop_tasks DROP COLUMN service_category_id,DROP COLUMN service_category_name_snapshot;
          ALTER TABLE crop_tasks DROP COLUMN service_category_id,DROP COLUMN service_category_name_snapshot;
          ALTER TABLE bookings DROP COLUMN crop_task_id,DROP COLUMN crop_context_snapshot,DROP COLUMN crop_request_key,DROP COLUMN crop_request_payload;'''))
        # The earlier ledger fixture predates its local booking table; retarget that FK.
        for name in c.execute(text("SELECT conname FROM pg_constraint WHERE conrelid='farm_activities'::regclass AND contype='f' AND confrelid='public.bookings'::regclass")).scalars():
            c.execute(text('ALTER TABLE farm_activities DROP CONSTRAINT "'+name+'"'))
        c.execute(text('ALTER TABLE farm_activities ADD FOREIGN KEY(service_booking_id) REFERENCES bookings ON DELETE RESTRICT'))
        with Operations.context(MigrationContext.configure(c)):migration.upgrade()
        category=c.execute(text("INSERT INTO service_categories(category_name) VALUES('Cultivation') RETURNING category_id")).scalar_one()
        provider=h['officer']['user_id']
        c.execute(text("INSERT INTO supplier_profiles(supplier_id,business_name,verified_at) VALUES(:id,'Provider','2025-01-01')"),{'id':provider})
        service=c.execute(text("INSERT INTO supplier_services(supplier_id,category_id,service_name,pricing_unit,base_price) VALUES(:id,:cat,'Cultivate','fixed',100) RETURNING supplier_service_id"),{'id':provider,'cat':category}).scalar_one()
        c.execute(text("INSERT INTO availability_slots(supplier_service_id,starts_at,ends_at,capacity) VALUES(:id,'2026-01-02 08:00','2026-01-02 09:00',1)"),{'id':service})
    cm=h['cm'];cm['ok']('PATCH',f"/admin/sop-tasks/{cm['task']['sop_task_id']}",{'service_category_id':category})
    cm['ok']('POST',f"/admin/sop-versions/{cm['version']['sop_version_id']}/publish")
    task=cm['ok']('POST',h['base']+'/plan',{'sop_version_id':cm['version']['sop_version_id'],'anchor_date':'2026-01-01'},201)['tasks'][0]
    h['app'].dependency_overrides[api.get_current_user]=h['current']
    h['app'].add_api_route('/my/bookings',api.create_my_booking,methods=['POST'],status_code=201)
    h['app'].include_router(create_task_service_router(e,h['current'],api.get_effective_capabilities))
    body={'supplier_service_id':service,'farm_id':cm['farm'],'requested_start_at':'2026-01-02T08:00:00','requested_end_at':'2026-01-02T09:00:00','quantity':1,'crop_task_id':task['crop_task_id'],'crop_request_key':str(uuid4())}
    with monkeypatch.context() as patch:
        patch.setattr(api,'engine',e)
        yield {**h,'body':body,'task':task,'integration_migration':migration}


@pytest.mark.parametrize('same_key',[True,False])
def test_booking_retry_and_capacity_races(integrated,same_key):
    h=integrated;a=h['body'];b=a if same_key else {**a,'crop_request_key':str(uuid4())}
    result=race([lambda:h['call_farmer']('POST','/my/bookings',a),lambda:h['call_farmer']('POST','/my/bookings',b)])
    assert sorted(r.status_code for r in result)==([200,201] if same_key else [201,400])
    with h['engine'].connect() as c:
        for table in ('bookings','booking_items','booking_slot_reservations','booking_status_history'):
            assert c.execute(text(f'SELECT count(*) FROM {table}')).scalar_one()==1


def confirmed_booking(h):
    r=h['call_farmer']('POST','/my/bookings',h['body']);assert r.status_code==201,r.text
    booking=r.json()
    with h['engine'].begin() as c:c.execute(text("UPDATE bookings SET status='completed' WHERE booking_id=:id"),{'id':booking['booking_id']})
    return booking


@pytest.mark.parametrize('same_key',[True,False])
def test_work_confirmation_race(integrated,same_key):
    h=integrated;b=confirmed_booking(h)
    a={'farm_id':h['cm']['farm'],'farm_crop_id':h['cm']['cycle']['farm_crop_id'],'crop_task_id':h['task']['crop_task_id'],
       'service_booking_id':b['booking_id'],'source_type':'service_booking','activity_type':'machinery','activity_date':'2026-01-02','description':'Cultivated','request_key':str(uuid4())}
    other=a if same_key else {**a,'request_key':str(uuid4())}
    results=race([lambda:h['call_farmer']('POST','/my/farm-activities',a),lambda:h['call_farmer']('POST','/my/farm-activities',other)])
    assert sorted(r.status_code for r in results)==([200,201] if same_key else [201,409])
    with h['engine'].connect() as c:assert c.execute(text('SELECT count(*) FROM farm_activities')).scalar_one()==1


def test_close_vs_new_booking(integrated):
    h=integrated
    results=race([lambda:h['call_farmer']('POST','/my/bookings',h['body']),lambda:h['call_farmer']('POST',h['base']+'/complete',{})])
    assert results[1].status_code==200 and results[0].status_code in (201,409)
    assert h['call_farmer']('POST','/my/bookings',{**h['body'],'crop_request_key':str(uuid4())}).status_code==409


def test_populated_downgrade_refused(integrated):
    h=integrated
    with pytest.raises(RuntimeError,match='Refusing'),h['engine'].begin() as c:
        with Operations.context(MigrationContext.configure(c)):h['integration_migration'].downgrade()


def test_linked_expense_retry_race(integrated):
    h=integrated;b=confirmed_booking(h)
    body={'farm_id':h['cm']['farm'],'farm_crop_id':h['cm']['cycle']['farm_crop_id'],'crop_task_id':h['task']['crop_task_id'],
          'service_booking_id':b['booking_id'],'source_type':'service_booking','activity_type':'machinery','activity_date':'2026-01-02','description':'Cultivated','request_key':str(uuid4())}
    r=h['call_farmer']('POST','/my/farm-activities',body);assert r.status_code==201,r.text
    expense={'farm_id':h['cm']['farm'],'activity_id':r.json()['activity_id'],'expense_date':'2026-01-02','category':'machinery','amount':'95','request_key':str(uuid4())}
    results=race([lambda:h['call_farmer']('POST','/my/farm-expenses',expense) for _ in range(2)])
    assert sorted(r.status_code for r in results)==[200,201]
    with h['engine'].connect() as c:assert c.execute(text('SELECT count(*) FROM farm_expenses')).scalar_one()==1
