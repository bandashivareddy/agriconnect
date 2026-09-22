"""Real concurrent transactions in a disposable schema inside the guarded test DB."""
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Barrier, Event
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

import main as api
from crop_management import create_router


@pytest.fixture
def concurrent_cm():
    import os
    expected = os.environ['AGRI_TEST_DB_NAME']
    schema = 'cmtest_' + uuid4().hex
    assert schema.startswith('cmtest_') and schema[7:].isalnum()
    with api.engine.begin() as c:
        assert c.execute(text('SELECT current_database()')).scalar_one() == expected
        assert 'test' in expected.lower()
        c.execute(text(f'CREATE SCHEMA {schema}'))
    engine=create_engine(api.engine.url, connect_args={'options':f'-csearch_path={schema},public'})
    try:
        with engine.begin() as c:
            for table in ('users','crops','farms','farm_plots','farm_crops','user_capabilities'):
                c.execute(text(f'CREATE TABLE {schema}.{table} (LIKE public.{table} INCLUDING ALL)'))
            c.execute(text('ALTER TABLE farm_crops DROP COLUMN created_at,DROP COLUMN updated_at,DROP COLUMN created_by,DROP COLUMN updated_by'))
            path=Path(__file__).resolve().parents[1]/'alembic/versions/c901a7b2d310_crop_management.py'
            spec=spec_from_file_location('cm_migration',path);migration=module_from_spec(spec);spec.loader.exec_module(migration)
            with Operations.context(MigrationContext.configure(c)):
                migration.upgrade()
            service_path=Path(__file__).resolve().parents[1]/'alembic/versions/c7f216a2e485_task_service_booking.py'
            service_spec=spec_from_file_location('task_requirement_migration',service_path)
            service_migration=module_from_spec(service_spec);service_spec.loader.exec_module(service_migration)
            with Operations.context(MigrationContext.configure(c)):
                service_migration.upgrade_task_requirements()
            season_path=Path(__file__).resolve().parents[1]/'alembic/versions/d8a327b3f596_season_planning.py'
            season_spec=spec_from_file_location('season_planning_migration',season_path)
            season_migration=module_from_spec(season_spec);season_spec.loader.exec_module(season_migration)
            with Operations.context(MigrationContext.configure(c)):
                season_migration.upgrade_planning()
            farmer=dict(c.execute(text("INSERT INTO users(full_name,password_hash,user_role) VALUES('Concurrent farmer','unused','farmer') RETURNING *")).mappings().one())
            crop=c.execute(text("INSERT INTO crops(crop_name) VALUES('Concurrent crop') RETURNING crop_id")).scalar_one()
            farm=c.execute(text("INSERT INTO farms(farmer_id,farm_name,location) VALUES(:id,'Farm','Village') RETURNING farm_id"),{'id':farmer['user_id']}).scalar_one()
            plot=c.execute(text("INSERT INTO farm_plots(farm_id,plot_name) VALUES(:id,'Plot') RETURNING plot_id"),{'id':farm}).scalar_one()
        app=FastAPI()
        app.include_router(create_router(engine,lambda:farmer,lambda *args:['farmer','admin']))
        client=TestClient(app)
        def ok(method,path,body=None,code=200):
            response=client.request(method,path,json=body)
            assert response.status_code==code,response.text
            return response.json()
        template=ok('POST','/admin/sop-templates',{'crop_id':crop,'name':'Concurrent SOP'},201)
        version=ok('POST',f"/admin/sop-templates/{template['sop_template_id']}/versions",{},201)
        task=ok('POST',f"/admin/sop-versions/{version['sop_version_id']}/tasks",{'sequence_no':1,'title':'Inspect','instructions':'Check leaves','task_type':'inspection','schedule_type':'days_after_planting','offset_days':0},201)
        cycle=ok('POST',f'/my/farms/{farm}/crop-cycles',{'plot_id':plot,'crop_id':crop,'status':'active','planted_on':'2026-01-01'},201)
        yield locals()
        client.close()
    finally:
        engine.dispose()
        # Only this test's generated schema is removed; no public records are touched.
        with api.engine.begin() as c:
            assert c.execute(text('SELECT current_database()')).scalar_one() == expected
            c.execute(text(f'DROP SCHEMA {schema} CASCADE'))


def test_concurrent_plan_generation(concurrent_cm):
    cm=concurrent_cm;client=cm['client'];version=cm['version']['sop_version_id'];cycle=cm['cycle']['farm_crop_id']
    cm['ok']('POST',f'/admin/sop-versions/{version}/publish')
    barrier=Barrier(2)
    def generate():
        barrier.wait(timeout=5)
        return client.post(f'/my/crop-cycles/{cycle}/plan',json={'sop_version_id':version,'anchor_date':'2026-01-01'})
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:generate(),range(2)))
    assert sorted(r.status_code for r in results)==[200,201]
    assert len({r.json()['plan_id'] for r in results})==1
    with cm['engine'].connect() as c:
        assert c.execute(text('SELECT count(*) FROM crop_cycle_plans')).scalar_one()==1
        assert c.execute(text('SELECT count(*) FROM crop_tasks')).scalar_one()==1


def test_concurrent_version_allocation(concurrent_cm):
    cm=concurrent_cm;barrier=Barrier(2)
    def create():
        barrier.wait(timeout=5)
        return cm['client'].post(f"/admin/sop-templates/{cm['template']['sop_template_id']}/versions",json={})
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:create(),range(2)))
    assert all(r.status_code==201 for r in results)
    assert sorted(r.json()['version_number'] for r in results)==[2,3]


def test_publication_serializes_with_task_edit(concurrent_cm):
    cm=concurrent_cm;engine=cm['engine'];version=cm['version']['sop_version_id'];started=Event()
    with engine.begin() as lock:
        lock.execute(text('SELECT * FROM sop_versions WHERE sop_version_id=:id FOR UPDATE'),{'id':version})
        def edit():
            started.set()
            with engine.begin() as c:
                c.execute(text("UPDATE sop_tasks SET title='Late edit' WHERE sop_task_id=:id"),{'id':cm['task']['sop_task_id']})
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(edit);assert started.wait(5)
            lock.execute(text("UPDATE sop_versions SET status='published',published_at=CURRENT_TIMESTAMP,published_by=:actor WHERE sop_version_id=:id"),{'actor':cm['farmer']['user_id'],'id':version})
            lock.commit()
            with pytest.raises(IntegrityError):future.result(timeout=5)
    assert cm['ok']('GET',f'/admin/sop-versions/{version}')['tasks'][0]['title']=='Inspect'


def test_harvest_races_safely_with_task_completion(concurrent_cm):
    cm=concurrent_cm;version=cm['version']['sop_version_id'];cycle=cm['cycle']['farm_crop_id'];client=cm['client']
    cm['ok']('POST',f'/admin/sop-versions/{version}/publish')
    plan=cm['ok']('POST',f'/my/crop-cycles/{cycle}/plan',{'sop_version_id':version,'anchor_date':'2026-01-01'},201)
    barrier=Barrier(2)
    def request(kind):
        barrier.wait(timeout=5)
        return client.post(f'/my/crop-cycles/{cycle}/status',json={'expected_status':'active','status':'harvested'}) if kind=='harvest' else client.post(f"/my/crop-tasks/{plan['tasks'][0]['crop_task_id']}/status",json={'expected_status':'pending','status':'completed'})
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(request,['harvest','complete']))
    assert results[0].status_code==200 and results[1].status_code in (200,409)
    saved=cm['ok']('GET',f'/my/crop-cycles/{cycle}')
    assert saved['status']=='harvested' and saved['plan']['tasks'][0]['status'] in ('completed','cancelled')
