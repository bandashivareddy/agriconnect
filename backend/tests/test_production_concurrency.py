from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
import main as api
from production_lifecycle import create_lifecycle_router
from test_crop_management_concurrency import concurrent_cm
from test_field_work_concurrency import fc, race
from test_farm_ledger_concurrency import ledger
from test_crop_inputs_concurrency import catalogue
from test_harvest_concurrency import harvests, create
from test_harvest_management import sale_body
from test_production_lifecycle import season_body


@pytest.fixture
def production(harvests):
    h=harvests
    path=Path(__file__).resolve().parents[1]/'alembic/versions/b6e105f1d374_production_lifecycle.py'
    spec=spec_from_file_location('production_migration',path);m=module_from_spec(spec);spec.loader.exec_module(m)
    with h['engine'].begin() as c:
        c.execute(text('''ALTER TABLE farm_crops DROP COLUMN perennial_planting_id,DROP COLUMN period_started_on,
            DROP COLUMN period_request_key,DROP COLUMN period_request_payload,DROP COLUMN completed_at,DROP COLUMN completed_by,DROP COLUMN completion_note'''))
        before=c.execute(text('SELECT to_jsonb(fc) FROM farm_crops fc ORDER BY farm_crop_id')).all()
        with Operations.context(MigrationContext.configure(c)):m.upgrade()
        after=c.execute(text("SELECT to_jsonb(fc)-ARRAY['perennial_planting_id','period_started_on','period_request_key','period_request_payload','completed_at','completed_by','completion_note'] FROM farm_crops fc ORDER BY farm_crop_id")).all()
        assert before==after
        assert c.execute(text('SELECT count(*) FROM farm_crops WHERE completed_at IS NOT NULL OR perennial_planting_id IS NOT NULL')).scalar_one()==0
    h['app'].include_router(create_lifecycle_router(h['engine'],h['current'],api.get_effective_capabilities))
    return {**h,'production_migration':m}


def test_duplicate_completion_race(production):
    h=production
    results=race([lambda:h['call_farmer']('POST',h['base']+'/complete',{}) for _ in range(2)])
    assert [r.status_code for r in results]==[200,200]
    assert results[0].json()['completed_at']==results[1].json()['completed_at']


def test_complete_vs_sale(production):
    h=production;_,path=create(h)
    results=race([lambda:h['call_farmer']('POST',h['base']+'/complete',{}),lambda:h['call_farmer']('POST',path+'/sales',sale_body())])
    assert [r.status_code for r in results]==[200,201]
    result=h['call_farmer']('GET',h['base']+'/reconciliation').json()
    assert result['status']=='harvested' and result['total_revenue']==1500 and result['quantities'][0]['remaining_quantity']==70


def enable(h):
    with h['engine'].begin() as c:
        c.execute(text("UPDATE crops SET lifecycle_type='perennial' WHERE crop_id=:id"),{'id':h['cm']['crop']})
    r=h['call_farmer']('POST',h['base']+'/enable-seasons',{'season':'2026','period_started_on':'2026-01-01'})
    assert r.status_code==201,r.text
    return '/my/perennial-plantings/'+str(r.json()['perennial_planting_id'])


@pytest.mark.parametrize('same_key',[True,False])
def test_concurrent_next_seasons(production,same_key):
    h=production;p=enable(h);assert h['call_farmer']('POST',h['base']+'/complete',{}).status_code==200
    a=season_body();b=a if same_key else season_body(season='Other season')
    result=race([lambda:h['call_farmer']('POST',p+'/seasons',a),lambda:h['call_farmer']('POST',p+'/seasons',b)])
    assert sorted(r.status_code for r in result)==([200,201] if same_key else [201,409])
    assert len(h['call_farmer']('GET',p).json()['seasons'])==2


def test_duplicate_enable(production):
    h=production
    with h['engine'].begin() as c:c.execute(text("UPDATE crops SET lifecycle_type='perennial' WHERE crop_id=:id"),{'id':h['cm']['crop']})
    payload={'season':'2026','period_started_on':'2026-01-01'}
    r=race([lambda:h['call_farmer']('POST',h['base']+'/enable-seasons',payload) for _ in range(2)])
    assert sorted(x.status_code for x in r)==[200,201]


def test_migration_roundtrip_and_history_guard(production):
    h=production;m=h['production_migration']
    with h['engine'].begin() as c:
        with Operations.context(MigrationContext.configure(c)):m.downgrade();m.upgrade()
    assert h['call_farmer']('POST',h['base']+'/complete',{}).status_code==200
    with pytest.raises(RuntimeError,match='Refusing'),h['engine'].begin() as c:
        with Operations.context(MigrationContext.configure(c)):m.downgrade()


def test_officer_denied(production):
    h=production
    for prefix in ['/my','/admin']:
        assert h['call']('POST',h['base'].replace('/my',prefix)+'/complete',{},h['officer']).status_code==403
