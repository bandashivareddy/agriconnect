"""Field work conflicts use real transactions in a disposable guarded test schema."""
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from threading import Barrier
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from sqlalchemy import text
import pytest
import main as api
from field_work import create_field_router
from test_crop_management_concurrency import concurrent_cm

@pytest.fixture
def fc(concurrent_cm):
    cm=concurrent_cm;engine=cm['engine']
    with engine.begin() as c:
        path=Path(__file__).resolve().parents[1]/'alembic/versions/d2a041f9b620_field_work.py'
        spec=spec_from_file_location('fw_migration',path);migration=module_from_spec(spec);spec.loader.exec_module(migration)
        # Compare crop task snapshots and legacy identity across the additive migration.
        before=c.execute(text('SELECT * FROM farm_crops ORDER BY farm_crop_id')).all()
        with Operations.context(MigrationContext.configure(c)):migration.upgrade()
        assert before==c.execute(text('SELECT * FROM farm_crops ORDER BY farm_crop_id')).all()
        officer=dict(c.execute(text("INSERT INTO users(full_name,password_hash,user_role) VALUES('Test Officer','unused','supplier') RETURNING *")).mappings().one())
        admin=dict(c.execute(text("INSERT INTO users(full_name,password_hash,user_role) VALUES('Test Admin','unused','admin') RETURNING *")).mappings().one())
        c.execute(text("INSERT INTO user_capabilities(user_id,capability) VALUES(:id,'field_officer')"),{'id':officer['user_id']})
    app=FastAPI()
    def current(x_user: int=Header()):
        with engine.connect() as c:return dict(c.execute(text('SELECT * FROM users WHERE user_id=:id'),{'id':x_user}).mappings().one())
    app.include_router(create_field_router(engine,current,api.get_effective_capabilities));client=TestClient(app)
    def call(method,path,body=None,who=None):return client.request(method,path,json=body,headers={'x-user':str((who or admin)['user_id'])})
    body={'field_officer_id':officer['user_id'],'farm_crop_id':cm['cycle']['farm_crop_id']}
    assignment=call('POST','/admin/field-work/assignments',body).json()
    visit=call('POST','/admin/field-work/visits',{'assignment_id':assignment['assignment_id'],'planned_visit_date':'2026-09-09'}).json()
    yield locals()
    client.close()


def race(actions):
    barrier=Barrier(len(actions))
    def perform(action):barrier.wait(timeout=5);return action()
    with ThreadPoolExecutor(max_workers=len(actions)) as pool:return list(pool.map(perform,actions))


def test_duplicate_assignment_race(fc):
    # A second officer/crop pair is not already active.
    fc['call']('PATCH',f"/admin/field-work/assignments/{fc['assignment']['assignment_id']}",{'expected_status':'active','status':'completed'})
    results=race([lambda:fc['call']('POST','/admin/field-work/assignments',fc['body']) for _ in range(2)])
    assert sorted(r.status_code for r in results)==[201,409]


def test_close_assignment_vs_start_visit(fc):
    aid=fc['assignment']['assignment_id'];vid=fc['visit']['visit_id']
    results=race([
        lambda:fc['call']('PATCH',f'/admin/field-work/assignments/{aid}',{'expected_status':'active','status':'cancelled'}),
        lambda:fc['call']('POST',f'/field-work/visits/{vid}/status',{'expected_status':'planned','status':'in_progress'},fc['officer'])])
    assert results[0].status_code==200 and results[1].status_code in (200,404)
    with fc['engine'].connect() as c:
        assert c.execute(text('SELECT status FROM field_visits WHERE visit_id=:id'),{'id':vid}).scalar_one()=='cancelled'
    assert fc['call']('GET',f'/field-work/visits/{vid}',who=fc['officer']).status_code==404


def test_observation_vs_visit_completion(fc):
    vid=fc['visit']['visit_id'];officer=fc['officer'];call=fc['call']
    assert call('POST',f'/field-work/visits/{vid}/status',{'expected_status':'planned','status':'in_progress'},officer).status_code==200
    body={'observation_type':'general','severity':'low','title':'Field checked','detailed_notes':'Conditions recorded'}
    results=race([
        lambda:call('POST',f'/field-work/visits/{vid}/status',{'expected_status':'in_progress','status':'completed'},officer),
        lambda:call('POST',f'/field-work/visits/{vid}/observations',body,officer)])
    assert results[0].status_code==200 and results[1].status_code in (201,409)
    assert call('POST',f'/field-work/visits/{vid}/observations',body,officer).status_code==409


def test_conflicting_verification_updates(fc):
    cm=fc['cm'];version=cm['version']['sop_version_id'];cycle=cm['cycle']['farm_crop_id']
    cm['ok']('POST',f'/admin/sop-versions/{version}/publish')
    plan=cm['ok']('POST',f'/my/crop-cycles/{cycle}/plan',{'sop_version_id':version,'anchor_date':'2026-01-01'},201)
    vid=fc['visit']['visit_id'];officer=fc['officer'];call=fc['call'];task=plan['tasks'][0]['crop_task_id']
    assert call('POST',f'/field-work/visits/{vid}/status',{'expected_status':'planned','status':'in_progress'},officer).status_code==200
    path=f'/field-work/visits/{vid}/tasks/{task}'
    results=race([lambda:call('PUT',path,{'verification_status':'observed_completed'},officer),lambda:call('PUT',path,{'verification_status':'not_done','officer_note':'Not observed'},officer)])
    assert sorted(r.status_code for r in results)==[200,409]
    with fc['engine'].connect() as c:assert c.execute(text('SELECT status FROM crop_tasks WHERE crop_task_id=:id'),{'id':task}).scalar_one()=='pending'


def test_downgrade_refuses_history(fc):
    with fc['engine'].begin() as c:
        with pytest.raises(RuntimeError),Operations.context(MigrationContext.configure(c)):
            fc['migration'].downgrade()
