"""Snapshot/retry races and additive migration checks in an isolated test schema."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
import pytest
import main as api
from farm_inputs import create_catalogue_router
from test_crop_management_concurrency import concurrent_cm
from test_field_work_concurrency import fc, race
from test_farm_ledger_concurrency import ledger, work


@pytest.fixture
def catalogue(ledger):
    with ledger['engine'].begin() as c:
        c.execute(text('ALTER TABLE farm_crops DROP COLUMN crop_variety_id,DROP COLUMN planting_material_source_id,DROP COLUMN seed_or_material_lot,DROP COLUMN variety_text,DROP COLUMN planting_snapshot'))
        c.execute(text('ALTER TABLE crops DROP COLUMN crop_group,DROP COLUMN lifecycle_type,DROP COLUMN harvest_pattern'))
        path=Path(__file__).resolve().parents[1]/'alembic/versions/f4c083d9b152_crop_inputs.py'
        spec=spec_from_file_location('input_migration',path);migration=module_from_spec(spec);spec.loader.exec_module(migration)
        before=c.execute(text('SELECT farm_crop_id,farm_id,crop_id,planted_on,status FROM farm_crops ORDER BY farm_crop_id')).all()
        with Operations.context(MigrationContext.configure(c)):migration.upgrade()
        assert before==c.execute(text('SELECT farm_crop_id,farm_id,crop_id,planted_on,status FROM farm_crops ORDER BY farm_crop_id')).all()
        assert c.execute(text('SELECT count(*) FROM farm_crops WHERE planting_snapshot IS NOT NULL')).scalar_one()==0
    ledger['app'].include_router(create_catalogue_router(ledger['engine'],ledger['current'],api.get_effective_capabilities))
    p=ledger['call']('POST','/admin/farm-input-products',{'input_type':'fertilizer','product_name':'Original label','nutrient_composition':{'N':46}})
    assert p.status_code==201,p.text
    return {**ledger,'product':p.json(),'input_migration':migration}


def test_concurrent_activity_with_inputs_retry(catalogue):
    c=catalogue;body={**work(c),'inputs':[{'farm_input_product_id':c['product']['farm_input_product_id'],'quantity':'25','unit':'kg'},{'custom_product':{'input_type':'other','product_name':'Unlisted'},'quantity':'1','unit':'unit'}]}
    responses=race([lambda:c['call']('POST','/my/farm-activities',body,c['cm']['farmer']) for _ in range(2)])
    assert sorted(r.status_code for r in responses)==[200,201]
    with c['engine'].connect() as db:
        assert db.execute(text('SELECT count(*) FROM farm_activities')).scalar_one()==1
        assert db.execute(text('SELECT count(*) FROM farm_activity_inputs')).scalar_one()==2


def test_concurrent_input_append_retry(catalogue):
    c=catalogue;a=c['call']('POST','/my/farm-activities',work(c),c['cm']['farmer']).json()
    body={'farm_input_product_id':c['product']['farm_input_product_id'],'quantity':'25','unit':'kg','request_key':str(uuid4())}
    results=race([lambda:c['call']('POST',f"/my/farm-activities/{a['activity_id']}/inputs",body,c['cm']['farmer']) for _ in range(2)])
    assert sorted(r.status_code for r in results)==[200,201]
    assert len({r.json()['farm_activity_input_id'] for r in results})==1


def test_deactivate_product_races_snapshot(catalogue):
    c=catalogue;p=c['product'];body={**work(c),'inputs':[{'farm_input_product_id':p['farm_input_product_id'],'quantity':'1','unit':'kg'}]}
    fields=('input_type','product_name','brand_name','manufacturer_name','active_ingredient','formulation','nutrient_composition','default_unit','notes','status')
    change={**{k:p[k] for k in fields},'status':'inactive','product_name':'Changed label','expected_updated_at':p['updated_at']}
    results=race([lambda:c['call']('PUT',f"/admin/farm-input-products/{p['farm_input_product_id']}",change),lambda:c['call']('POST','/my/farm-activities',body,c['cm']['farmer'])])
    assert results[0].status_code==200 and results[1].status_code in (201,422)
    with c['engine'].connect() as db:
        snapshots=db.execute(text('SELECT product_snapshot FROM farm_activity_inputs')).scalars().all()
        assert all(s['product_name']=='Original label' for s in snapshots)
        assert len(snapshots)==(1 if results[1].status_code==201 else 0)


def test_concurrent_variety_duplicates(catalogue):
    c=catalogue;body={'crop_id':c['cm']['crop'],'variety_name':'Same variety'}
    responses=race([lambda:c['call']('POST','/admin/crop-varieties',body) for _ in range(2)])
    assert sorted(r.status_code for r in responses)==[201,409]


def test_input_migration_downgrade_preserves_history(catalogue):
    with catalogue['engine'].begin() as c,pytest.raises(RuntimeError,match='history'):
        with Operations.context(MigrationContext.configure(c)):catalogue['input_migration'].downgrade()
