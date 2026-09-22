from uuid import uuid4
import pytest
from sqlalchemy.exc import IntegrityError
from farm_inputs import SourceData, VarietyData, ProductMaster, InputFacts
from test_crop_management import cm
from test_field_work import fw, start
from test_farm_ledger import activity, expense


def source(cm,**extra):
    return cm.ok('POST','/admin/planting-material-sources',{'source_name':'Test Nursery','source_type':'nursery','brand_name':'Test Brand',**extra},cm.admin,201)


def variety(cm,**extra):
    return cm.ok('POST','/admin/crop-varieties',{'crop_id':cm.crop,'variety_name':'Test Cultivar','variety_type':'cultivar','duration_min_days':130,'duration_max_days':150,'days_to_first_harvest_min':70,'days_to_first_harvest_max':80,**extra},cm.admin,201)


def product(cm,**extra):
    return cm.ok('POST','/admin/farm-input-products',{'input_type':'fertilizer','product_name':'Test Product','brand_name':'Test Brand','manufacturer_name':'Test Maker','nutrient_composition':{'N':19,'P2O5':19,'K2O':19},'default_unit':'kg',**extra},cm.admin,201)


def update(record,model,**extra):
    return {**{key:record[key] for key in model.model_fields},'expected_updated_at':record['updated_at'],**extra}


def usage(product,**extra):
    return {'farm_input_product_id':product['farm_input_product_id'],'quantity':'25','unit':'kg',**extra}


def test_planting_snapshot_master_rename_inactive_compatibility(cm):
    s=source(cm);v=variety(cm,default_planting_material_source_id=s['planting_material_source_id'])
    cycle=cm.cycle(crop_variety_id=v['crop_variety_id'],planting_material_source_id=s['planting_material_source_id'],seed_or_material_lot='LOT-2026')
    assert cycle['planting_snapshot']['variety']['variety_name']=='Test Cultivar'
    assert cycle['planting_snapshot']['source']['source_name']=='Test Nursery'
    cm.ok('PUT',f"/admin/crop-varieties/{v['crop_variety_id']}",update(v,VarietyData,variety_name='Renamed',status='inactive',duration_max_days=160),cm.admin)
    cm.ok('PUT',f"/admin/planting-material-sources/{s['planting_material_source_id']}",update(s,SourceData,source_name='Renamed source',status='inactive'),cm.admin)
    saved=cm.ok('GET',f"/my/crop-cycles/{cycle['farm_crop_id']}")
    assert saved['planting_snapshot']==cycle['planting_snapshot'] and saved['seed_or_material_lot']=='LOT-2026'
    edited=cm.ok('PATCH',f"/my/crop-cycles/{cycle['farm_crop_id']}",{'seed_or_material_lot':'Corrected lot'})
    assert edited['planting_snapshot']==cycle['planting_snapshot']
    assert cm.call('POST',f'/my/farms/{cm.farm}/crop-cycles',{'plot_id':cm.plot,'crop_id':cm.crop,'crop_variety_id':v['crop_variety_id']}).status_code==422
    assert cm.call('POST',f'/my/farms/{cm.farm}/crop-cycles',{'plot_id':cm.plot,'crop_id':cm.crop,'planting_material_source_id':s['planting_material_source_id']}).status_code==422
    assert cm.cycle()['planting_snapshot'] is None
    fallback=cm.cycle(variety_text='Local saved variety')
    assert fallback['planting_snapshot']['variety']=={'variety_name':'Local saved variety','unlisted':True}


def test_variety_crop_and_duplicate_normalized_names(cm):
    v=variety(cm,variety_name='  Local   Hybrid  ')
    assert cm.call('POST','/admin/crop-varieties',{'crop_id':cm.crop,'variety_name':'local hybrid'},cm.admin).status_code==409
    other_crop=cm.sql("INSERT INTO crops(crop_name) VALUES('Other crop') RETURNING crop_id").scalar_one()
    assert cm.call('POST',f'/my/farms/{cm.farm}/crop-cycles',{'plot_id':cm.plot,'crop_id':other_crop,'crop_variety_id':v['crop_variety_id']}).status_code==404
    assert cm.call('PUT',f"/admin/crop-varieties/{v['crop_variety_id']}",update(v,VarietyData,crop_id=other_crop),cm.admin).status_code==422
    c=cm.cycle(crop_variety_id=v['crop_variety_id'])
    with pytest.raises(IntegrityError),cm.connection.begin_nested():cm.sql('UPDATE farm_crops SET crop_id=:crop WHERE farm_crop_id=:id',crop=other_crop,id=c['farm_crop_id'])
    assert cm.call('POST',f'/my/farms/{cm.farm}/crop-cycles',{'plot_id':cm.plot,'crop_id':cm.crop,'crop_variety_id':v['crop_variety_id'],'variety_text':'Also local'}).status_code==422
    cm.ok('PUT',f"/admin/crop-varieties/{v['crop_variety_id']}",update(v,VarietyData,status='inactive'),cm.admin)
    assert variety(cm,variety_name='local hybrid')['crop_variety_id']!=v['crop_variety_id']


@pytest.mark.parametrize('extra',[{'duration_min_days':0},{'duration_max_days':-1},{'duration_min_days':160,'duration_max_days':150},{'days_to_first_harvest_min':80,'days_to_first_harvest_max':70},{'days_to_first_harvest_min':0},{'variety_type':'seed_company'},{'variety_name':' '},{'duration_max_days':36501}])
def test_variety_validation(cm,extra):
    assert cm.call('POST','/admin/crop-varieties',{'crop_id':cm.crop,'variety_name':'Valid',**extra},cm.admin).status_code==422


def test_estimates_separate_and_farmer_override(cm):
    v=variety(cm)
    suggestion=cm.ok('GET',f"/catalogue/crop-varieties/{v['crop_variety_id']}/duration-suggestion?planting_date=2026-06-10")
    assert suggestion['total_duration_window']=={'from':'2026-10-18','to':'2026-11-07'}
    assert suggestion['first_harvest_window']=={'from':'2026-08-19','to':'2026-08-29'}
    cycle=cm.cycle(status='active',planted_on='2026-06-10',expected_harvest_on='2026-10-01',crop_variety_id=v['crop_variety_id'])
    assert cycle['expected_harvest_on']=='2026-10-01'
    cm.ok('PATCH',f"/my/crop-cycles/{cycle['farm_crop_id']}",{'seed_or_material_lot':'X'})
    assert cm.ok('GET',f"/my/crop-cycles/{cycle['farm_crop_id']}")['expected_harvest_on']=='2026-10-01'
    assert cm.call('PATCH',f"/my/crop-cycles/{cycle['farm_crop_id']}",{'expected_harvest_on':'2026-06-10'}).status_code==422
    assert cm.call('GET',f"/catalogue/crop-varieties/{v['crop_variety_id']}/duration-suggestion?planting_date=9999-12-31").status_code==422


def test_crop_metadata_optional_perennial_duration(cm):
    result=cm.ok('PUT',f'/admin/crops/{cm.crop}/metadata',{'crop_group':'orchard','lifecycle_type':'perennial','harvest_pattern':'recurring'},cm.admin)
    assert result['crop_group']=='orchard'
    v=variety(cm,duration_min_days=None,duration_max_days=None,days_to_first_harvest_min=None,days_to_first_harvest_max=None)
    assert cm.cycle(crop_variety_id=v['crop_variety_id'])['crop_variety_id']==v['crop_variety_id']
    assert cm.call('PUT',f'/admin/crops/{cm.crop}/metadata',{'crop_group':'tree'},cm.admin).status_code==422
    assert cm.call('PUT',f'/admin/crops/{cm.crop}/metadata',{}).status_code==403


def test_sources_search_and_invalid_reference(cm):
    s=source(cm)
    assert cm.ok('GET','/catalogue/planting-material-sources?q=Nursery')[0]['planting_material_source_id']==s['planting_material_source_id']
    assert cm.ok('GET',f"/catalogue/planting-material-sources/{s['planting_material_source_id']}")['brand_name']=='Test Brand'
    assert cm.call('POST','/admin/planting-material-sources',{'source_name':'X','source_type':'seed'},cm.admin).status_code==422
    assert cm.call('POST',f'/my/farms/{cm.farm}/crop-cycles',{'plot_id':cm.plot,'crop_id':cm.crop,'planting_material_source_id':2147483647}).status_code==404


def test_product_crud_search_identity_and_stale_edits(cm):
    p=product(cm,input_type='pesticide',active_ingredient='Test ingredient',formulation='5% SG',nutrient_composition=None)
    for query in ('Product','Brand','Maker','ingredient'):
        assert any(r['farm_input_product_id']==p['farm_input_product_id'] for r in cm.ok('GET',f'/catalogue/farm-input-products?q={query}'))
    changed=cm.ok('PUT',f"/admin/farm-input-products/{p['farm_input_product_id']}",update(p,ProductMaster,product_name='Renamed'),cm.admin)
    assert changed['active_ingredient']=='Test ingredient' and changed['formulation']=='5% SG'
    assert cm.call('PUT',f"/admin/farm-input-products/{p['farm_input_product_id']}",update(p,ProductMaster),cm.admin).status_code==409
    cm.ok('PUT',f"/admin/farm-input-products/{p['farm_input_product_id']}",update(changed,ProductMaster,status='inactive'),cm.admin)
    assert not cm.ok('GET','/catalogue/farm-input-products?q=Renamed')
    assert cm.ok('GET','/admin/farm-input-products?status=inactive&q=Renamed',as_user=cm.admin)


@pytest.mark.parametrize('extra',[{'input_type':'seed'},{'input_type':'prescription'},{'product_name':''},{'nutrient_composition':{'N':101}},{'nutrient_composition':{'N':-1}},{'nutrient_composition':{'unknown':5}},{'nutrient_composition':{'N':'NaN'}},{'default_unit':'bucket'}])
def test_product_validation(cm,extra):
    assert cm.call('POST','/admin/farm-input-products',{'input_type':'fertilizer','product_name':'Product',**extra},cm.admin).status_code==422


def test_multiple_actual_inputs_atomic_retry_snapshots_expenses(cm):
    p=product(cm);p2=product(cm,product_name='Micronutrient',input_type='micronutrient',nutrient_composition={'Zn':10})
    body=activity(cm,inputs=[usage(p),usage(p2,quantity='2')])
    a=cm.ok('POST','/my/farm-activities',body,code=201)
    assert cm.ok('POST','/my/farm-activities',body)['activity_id']==a['activity_id']
    path=f"/my/farm-activities/{a['activity_id']}/inputs"
    inputs=cm.ok('GET',path);assert len(inputs)==2
    assert inputs[0]['product_snapshot']['nutrient_composition']=={'N':19,'P2O5':19,'K2O':19}
    assert cm.ok('GET','/my/farm-expenses')['count']==0
    for _ in range(2):cm.ok('POST','/my/farm-expenses',expense(cm,activity_id=a['activity_id']),code=201)
    assert cm.ok('GET',f"/my/farm-expenses?activity_id={a['activity_id']}")['count']==2
    cm.ok('PUT',f"/admin/farm-input-products/{p['farm_input_product_id']}",update(p,ProductMaster,product_name='Changed',nutrient_composition={'N':46},status='inactive'),cm.admin)
    assert cm.ok('GET',path)==inputs
    assert cm.call('POST',path,{**usage(p),'request_key':str(uuid4())}).status_code==422
    # Existing successful requests still replay after deactivation.
    assert cm.ok('POST','/my/farm-activities',body)['activity_id']==a['activity_id']


def test_unlisted_input_and_corrections_keep_identity(cm):
    a=cm.ok('POST','/my/farm-activities',activity(cm),code=201);path=f"/my/farm-activities/{a['activity_id']}/inputs"
    body={'custom_product':{'input_type':'bio_input','product_name':'Unlisted local product','manufacturer_name':'Local maker'},'quantity':'100','unit':'ml','request_key':str(uuid4())}
    saved=cm.ok('POST',path,body,code=201)
    assert saved['is_unlisted'] and saved['farm_input_product_id'] is None
    assert not cm.ok('GET','/catalogue/farm-input-products?q=Unlisted')
    assert cm.ok('POST',path,body)['farm_activity_input_id']==saved['farm_activity_input_id']
    assert cm.call('POST',path,{**body,'quantity':'200'}).status_code==409
    corrected=cm.ok('PUT',f"{path}/{saved['farm_activity_input_id']}",update(saved,InputFacts,quantity='90'))
    assert corrected['product_snapshot']==saved['product_snapshot']
    assert cm.call('PUT',f"{path}/{saved['farm_activity_input_id']}",update(saved,InputFacts)).status_code==409
    with pytest.raises(IntegrityError),cm.connection.begin_nested():cm.sql("UPDATE farm_activity_inputs SET product_snapshot='{}'::jsonb WHERE farm_activity_input_id=:id",id=saved['farm_activity_input_id'])


@pytest.mark.parametrize('extra',[{'quantity':'0'},{'quantity':'-1'},{'quantity':'NaN'},{'quantity':'Infinity'},{'quantity':'1.00001'},{'unit':'bucket'},{'farm_input_product_id':None},{'custom_product':{'input_type':'other','product_name':'Both'}}])
def test_usage_validation(cm,extra):
    p=product(cm)
    assert cm.call('POST','/my/farm-activities',activity(cm,inputs=[{**usage(p),**extra}])).status_code==422


def test_rollback_invalid_second_input_and_plan_unchanged(cm):
    p=product(cm);cm.task();cm.publish();cycle=cm.cycle();plan=cm.plan(cycle['farm_crop_id']);task=plan['tasks'][0]
    body=activity(cm,source_type='crop_task',crop_task_id=task['crop_task_id'],inputs=[usage(p),usage(p,farm_input_product_id=2147483647)])
    path=f"/my/crop-tasks/{task['crop_task_id']}/record-work"
    assert cm.call('POST',path,body).status_code==404
    assert cm.ok('GET','/my/farm-activities')['count']==0 and cm.sql('SELECT count(*) FROM farm_activity_inputs').scalar_one()==0
    body['inputs']=[usage(p)]
    a=cm.ok('POST',path,body,code=201)
    assert len(cm.ok('GET',f"/my/farm-activities/{a['activity_id']}/inputs"))==1
    assert cm.ok('GET',f"/my/crop-tasks/{task['crop_task_id']}")['status']=='pending'
    assert cm.ok('GET',f"/my/crop-cycles/{cycle['farm_crop_id']}")['plan']['tasks'][0]['instructions']==task['instructions']


def test_catalogue_and_usage_authorization(cm):
    p=product(cm);a=cm.ok('POST','/my/farm-activities',activity(cm,inputs=[usage(p)]),code=201)
    path=f"/my/farm-activities/{a['activity_id']}/inputs"
    for actor in (cm.other,cm.provider,cm.admin):
        expected=404 if actor==cm.other else 403
        assert cm.call('GET',path,as_user=actor).status_code==expected
        assert cm.call('POST',path,{**usage(p),'request_key':str(uuid4())},actor).status_code==expected
    assert cm.call('GET','/catalogue/farm-input-products',as_user=cm.provider).status_code==403
    assert cm.call('POST','/admin/crop-varieties',{'crop_id':cm.crop,'variety_name':'No admin'}).status_code==403


def test_officer_inputs_assignment_creator_visit_and_finance(fw):
    p=product(fw);cycle=fw.cycle_record['farm_crop_id'];start(fw)
    body=activity(fw,farm_crop_id=cycle,field_visit_id=fw.visit['visit_id'],source_type='field_visit',inputs=[usage(p)])
    a=fw.ok('POST',f'/field-work/crop-cycles/{cycle}/activities',body,fw.provider,201)
    path=f"/field-work/activities/{a['activity_id']}/inputs"
    first=fw.ok('GET',path,as_user=fw.provider)[0]
    fw.ok('POST',path,{**usage(p,quantity='2'),'request_key':str(uuid4())},fw.provider,201)
    assert fw.call('GET',path,as_user=fw.other).status_code==404
    assert fw.call('POST',path,{**usage(p),'request_key':str(uuid4())},fw.other).status_code==404
    fa=fw.ok('POST','/my/farm-activities',activity(fw,farm_crop_id=cycle),code=201)
    assert fw.call('POST',f"/field-work/activities/{fa['activity_id']}/inputs",{**usage(p),'request_key':str(uuid4())},fw.provider).status_code==404
    assert fw.call('GET','/my/farm-expenses',as_user=fw.provider).status_code==403
    fw.ok('POST',f"/field-work/visits/{fw.visit['visit_id']}/status",{'expected_status':'in_progress','status':'completed'},fw.provider)
    assert fw.call('PUT',f"{path}/{first['farm_activity_input_id']}",update(first,InputFacts,quantity='20'),fw.provider).status_code==409
    fw.ok('PATCH',f"/admin/field-work/assignments/{fw.assignment['assignment_id']}",{'expected_status':'active','status':'completed'},fw.admin)
    assert fw.call('GET',path,as_user=fw.provider).status_code==404
    assert len(fw.ok('GET',f"/my/farm-activities/{a['activity_id']}/inputs"))==2
