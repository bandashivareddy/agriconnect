from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import pytest
from fastapi import Header
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
import main as api
from officer_applications import create_application_router
from field_work import create_field_router
from test_crop_management_concurrency import concurrent_cm
from test_field_work_concurrency import race


@pytest.fixture
def officers(concurrent_cm):
    cm=concurrent_cm
    path=Path(__file__).resolve().parents[1]/'alembic/versions/e9b438c4a607_officer_applications.py'
    spec=spec_from_file_location('officer_migration',path);m=module_from_spec(spec);spec.loader.exec_module(m)
    with cm['engine'].begin() as c:
        c.execute(text('ALTER TABLE users DROP COLUMN signup_intent'))
        with Operations.context(MigrationContext.configure(c)):m.upgrade()
        admin=c.execute(text("INSERT INTO users(full_name,password_hash,user_role) VALUES('Review Admin','unused','admin') RETURNING user_id")).scalar_one()
    def current(x_user:int=Header()):
        with cm['engine'].connect() as c:return dict(c.execute(text('SELECT * FROM users WHERE user_id=:id'),{'id':x_user}).mappings().one())
    cm['app'].include_router(create_application_router(cm['engine'],current,api.get_effective_capabilities))
    cm['app'].include_router(create_field_router(cm['engine'],current,api.get_effective_capabilities))
    def call(path,body,as_admin=False):
        return cm['client'].post(path,json=body,headers={'x-user':str(admin if as_admin else cm['farmer']['user_id'])})
    return {**cm,'call':call,'migration':m}


def test_concurrent_approval_exactly_once(officers):
    h=officers;a=h['call']('/my/field-officer-application',{}).json()
    path=f"/admin/field-officer-applications/{a['application_id']}/review"
    r=race([lambda:h['call'](path,{'status':'approved'},True) for _ in range(2)])
    assert [x.status_code for x in r]==[200,200]
    assert r[0].json()==r[1].json()
    with h['engine'].connect() as c:
        assert c.execute(text("SELECT count(*) FROM user_capabilities WHERE user_id=:id AND capability='field_officer'"),{'id':a['user_id']}).scalar_one()==1


def test_approve_reject_race_one_terminal_decision(officers):
    h=officers;a=h['call']('/my/field-officer-application',{}).json()
    path=f"/admin/field-officer-applications/{a['application_id']}/review"
    r=race([lambda:h['call'](path,{'status':'approved'},True),lambda:h['call'](path,{'status':'rejected','rejection_reason':'Review reason'},True)])
    assert sorted(x.status_code for x in r)==[200,409]
    with h['engine'].connect() as c:
        status=c.execute(text('SELECT status FROM field_officer_applications WHERE application_id=:id'),{'id':a['application_id']}).scalar_one()
        count=c.execute(text("SELECT count(*) FROM user_capabilities WHERE user_id=:id AND capability='field_officer'"),{'id':a['user_id']}).scalar_one()
        assert count==(1 if status=='approved' else 0)


def test_concurrent_submission_is_retry_safe(officers):
    h=officers;r=race([lambda:h['call']('/my/field-officer-application',{'qualification':'Diploma'}) for _ in range(2)])
    assert sorted(x.status_code for x in r)==[200,201]
    assert r[0].json()['application_id']==r[1].json()['application_id']


def test_submission_and_legacy_grant_serialize(officers):
    h=officers
    r=race([lambda:h['call']('/my/field-officer-application',{}),lambda:h['call']('/admin/field-officers',{'user_id':h['farmer']['user_id']},True)])
    assert sorted(x.status_code for x in r) in ([201,409],[200,409])
    with h['engine'].connect() as c:
        assert not c.execute(text("SELECT 1 FROM field_officer_applications a JOIN user_capabilities uc USING(user_id) WHERE a.status='pending' AND uc.capability='field_officer'")).first()


def test_populated_application_downgrade_refused(officers):
    h=officers;assert h['call']('/my/field-officer-application',{}).status_code==201
    with h['engine'].begin() as c,Operations.context(MigrationContext.configure(c)):
        with pytest.raises(RuntimeError,match='Refusing'):h['migration'].downgrade()
