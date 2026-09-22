"""Ledger writes race using real transactions; migrations use a disposable test schema."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
import pytest
import main as api
from farm_ledger import create_ledger_router
from test_field_work_concurrency import fc, race
from test_crop_management_concurrency import concurrent_cm


@pytest.fixture
def ledger(fc):
    with fc['engine'].begin() as c:
        # The old fixture clones current public columns before replaying older migrations.
        c.execute(text('ALTER TABLE farm_crops DROP COLUMN farm_block_id'))
        path=Path(__file__).resolve().parents[1]/'alembic/versions/e3b072c8a941_farm_ledger.py'
        spec=spec_from_file_location('ledger_migration',path);migration=module_from_spec(spec);spec.loader.exec_module(migration)
        before=c.execute(text('SELECT farm_crop_id,farm_id,plot_id,crop_id,planted_on,status FROM farm_crops ORDER BY farm_crop_id')).all()
        with Operations.context(MigrationContext.configure(c)):migration.upgrade()
        assert before==c.execute(text('SELECT farm_crop_id,farm_id,plot_id,crop_id,planted_on,status FROM farm_crops ORDER BY farm_crop_id')).all()
    fc['app'].include_router(create_ledger_router(fc['engine'],fc['current'],api.get_effective_capabilities))
    return {**fc,'migration':migration}


def work(ledger):
    cm=ledger['cm']
    return {'farm_id':cm['farm'],'farm_crop_id':cm['cycle']['farm_crop_id'],'activity_date':'2026-09-01','activity_type':'inspection','description':'Inspected leaves','request_key':str(uuid4())}


def test_concurrent_record_work_retry(ledger):
    cm=ledger['cm'];cm['ok']('POST',f"/admin/sop-versions/{cm['version']['sop_version_id']}/publish")
    plan=cm['ok']('POST',f"/my/crop-cycles/{cm['cycle']['farm_crop_id']}/plan",{'sop_version_id':cm['version']['sop_version_id'],'anchor_date':'2026-01-01'},201)
    task=plan['tasks'][0]['crop_task_id'];body={**work(ledger),'crop_task_id':task,'source_type':'crop_task'}
    results=race([lambda:ledger['call']('POST',f'/my/crop-tasks/{task}/record-work',body,cm['farmer']) for _ in range(2)])
    assert sorted(r.status_code for r in results)==[200,201],[(r.status_code,r.text) for r in results]
    assert len({r.json()['activity_id'] for r in results})==1
    with ledger['engine'].connect() as c:
        assert c.execute(text('SELECT count(*) FROM farm_activities')).scalar_one()==1
        assert c.execute(text('SELECT status FROM crop_tasks WHERE crop_task_id=:id'),{'id':task}).scalar_one()=='pending'


def test_concurrent_expense_retries(ledger):
    cm=ledger['cm'];body={'farm_id':cm['farm'],'expense_date':'2026-09-01','category':'labour','amount':'123.45','request_key':str(uuid4())}
    results=race([lambda:ledger['call']('POST','/my/farm-expenses',body,cm['farmer']) for _ in range(2)])
    assert sorted(r.status_code for r in results)==[200,201]
    with ledger['engine'].connect() as c:assert str(c.execute(text('SELECT sum(amount) FROM farm_expenses')).scalar_one())=='123.45'


def test_concurrent_edits(ledger):
    cm=ledger['cm'];saved=ledger['call']('POST','/my/farm-activities',work(ledger),cm['farmer']).json()
    data={k:saved[k] for k in ('activity_date','activity_type','description','quantity','unit','notes','performed_by_user_id')}
    data['expected_updated_at']=saved['updated_at']
    results=race([lambda:ledger['call']('PUT',f"/my/farm-activities/{saved['activity_id']}",{**data,'description':'Correction A'},cm['farmer']),lambda:ledger['call']('PUT',f"/my/farm-activities/{saved['activity_id']}",{**data,'description':'Correction B'},cm['farmer'])])
    assert sorted(r.status_code for r in results)==[200,409]


def test_close_assignment_races_activity(ledger):
    cycle=ledger['cm']['cycle']['farm_crop_id'];body=work(ledger)
    results=race([lambda:ledger['call']('PATCH',f"/admin/field-work/assignments/{ledger['assignment']['assignment_id']}",{'expected_status':'active','status':'cancelled'}),lambda:ledger['call']('POST',f'/field-work/crop-cycles/{cycle}/activities',body,ledger['officer'])])
    assert results[0].status_code==200 and results[1].status_code in (201,404)
    assert ledger['call']('POST',f'/field-work/crop-cycles/{cycle}/activities',body,ledger['officer']).status_code==404


def test_migration_refuses_populated_downgrade(ledger):
    ledger['call']('POST','/my/farm-activities',work(ledger),ledger['cm']['farmer'])
    with ledger['engine'].begin() as c,pytest.raises(RuntimeError,match='history'):
        with Operations.context(MigrationContext.configure(c)):ledger['migration'].downgrade()
