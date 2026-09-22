"""Real transactions check overselling, retries and migration preservation."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import pytest
import main as api
from harvest_management import create_harvest_router
from test_crop_management_concurrency import concurrent_cm
from test_field_work_concurrency import fc, race
from test_farm_ledger_concurrency import ledger
from test_crop_inputs_concurrency import catalogue
from test_harvest_management import harvest_body, sale_body, edit_body


@pytest.fixture
def harvests(catalogue):
    c=catalogue
    path=Path(__file__).resolve().parents[1]/'alembic/versions/a5d094e0c263_harvest_revenue.py'
    spec=spec_from_file_location('harvest_migration',path);migration=module_from_spec(spec);spec.loader.exec_module(migration)
    with c['engine'].begin() as db:
        before=db.execute(text('SELECT to_jsonb(fc) FROM farm_crops fc ORDER BY farm_crop_id')).all()
        with Operations.context(MigrationContext.configure(db)):migration.upgrade()
        assert before==db.execute(text('SELECT to_jsonb(fc) FROM farm_crops fc ORDER BY farm_crop_id')).all()
    c['app'].include_router(create_harvest_router(c['engine'],c['current'],api.get_effective_capabilities))
    base=f"/my/crop-cycles/{c['cm']['cycle']['farm_crop_id']}"
    def call(method,path,body=None):return c['call'](method,path,body,c['cm']['farmer'])
    return {**c,'base':base,'call_farmer':call,'harvest_migration':migration}


def create(h):
    r=h['call_farmer']('POST',h['base']+'/harvests',harvest_body());assert r.status_code==201,r.text
    event=r.json();return event,h['base']+'/harvests/'+str(event['harvest_event_id'])


@pytest.mark.parametrize('sale',[False,True])
def test_retry_race(harvests,sale):
    h=harvests
    if sale:
        _,path=create(h);path+='/sales';body=sale_body()
    else:path=h['base']+'/harvests';body=harvest_body()
    results=race([lambda:h['call_farmer']('POST',path,body) for _ in range(2)])
    assert sorted(r.status_code for r in results)==[200,201]
    with h['engine'].connect() as db:
        table='harvest_sales' if sale else 'harvest_events'
        assert db.execute(text(f'SELECT count(*) FROM {table}')).scalar_one()==1


def test_oversell_race(harvests):
    h=harvests;_,path=create(h)
    results=race([lambda:h['call_farmer']('POST',path+'/sales',sale_body(quantity_sold='60')) for _ in range(2)])
    assert sorted(r.status_code for r in results)==[201,409]


def test_sale_vs_harvest_correction(harvests):
    h=harvests;event,path=create(h)
    results=race([lambda:h['call_farmer']('POST',path+'/sales',sale_body(quantity_sold='60')),
      lambda:h['call_farmer']('PUT',path,edit_body(event,quantity='50'))])
    assert sorted(r.status_code for r in results) in ([201,409],[200,409])
    with h['engine'].connect() as db:
        assert db.execute(text('SELECT coalesce(sum(s.quantity_sold),0)<=h.quantity-coalesce(h.wastage_quantity,0) FROM harvest_events h LEFT JOIN harvest_sales s USING(harvest_event_id) GROUP BY h.harvest_event_id')).scalar_one()


def test_stale_edit_race(harvests):
    h=harvests;event,path=create(h)
    results=race([lambda:h['call_farmer']('PUT',path,edit_body(event,notes='Corrected')) for _ in range(2)])
    assert sorted(r.status_code for r in results)==[200,409]


def test_direct_sql_oversell_race(harvests):
    h=harvests;event,_=create(h)
    def insert():
        from uuid import uuid4
        try:
            with h['engine'].begin() as db:
                db.execute(text('''INSERT INTO harvest_sales(harvest_event_id,quantity_sold,unit,total_amount,sold_on,created_by,updated_by,request_key,request_payload)
                  VALUES(:id,60,'kg',3000,'2026-09-02',:actor,:actor,:key,'{}')'''),{'id':event['harvest_event_id'],'actor':h['cm']['farmer']['user_id'],'key':str(uuid4())})
            return True
        except IntegrityError:return False
    assert sorted(race([insert,insert]))==[False,True]


def test_migration_empty_downgrade_and_history_guard(harvests):
    h=harvests;m=h['harvest_migration']
    with h['engine'].begin() as db:
        with Operations.context(MigrationContext.configure(db)):
            m.downgrade();m.upgrade()
    create(h)
    with pytest.raises(RuntimeError,match='Refusing'),h['engine'].begin() as db:
        with Operations.context(MigrationContext.configure(db)):m.downgrade()


def test_officer_denied(harvests):
    h=harvests
    for prefix in ['/my','/admin']:
        assert h['call']('GET',h['base'].replace('/my',prefix)+'/harvest-summary',who=h['officer']).status_code==403
