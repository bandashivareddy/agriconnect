from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy.exc import IntegrityError
from test_crop_management import cm
from test_harvest_management import harvest_body, sale_body, edit_body
from test_farm_ledger import expense, activity, block


def active(cm, **extra):
    c=cm.cycle(status='active',planted_on='2020-01-01',**extra)
    return c,f"/my/crop-cycles/{c['farm_crop_id']}"


def perennial(cm):
    cm.sql("UPDATE crops SET lifecycle_type='perennial',crop_group='orchard',harvest_pattern='recurring' WHERE crop_id=:id",id=cm.crop)
    return active(cm)


def enable(cm,base):
    return cm.ok('POST',base+'/enable-seasons',{'season':'2026-27','period_started_on':'2026-01-01'},code=201)


def season_body(**extra):
    return {'season':'2027-28','period_started_on':'2027-01-01','request_key':str(uuid4()),**extra}


@pytest.mark.parametrize('group',['seasonal','vegetable'])
def test_completion_reconciliation_unsold_and_history(cm,group):
    cm.sql('UPDATE crops SET crop_group=:group WHERE crop_id=:id',group=group,id=cm.crop)
    cycle,base=active(cm)
    h=cm.ok('POST',base+'/harvests',{**harvest_body(),'quantity':'1000','wastage_quantity':'50'},code=201)
    cm.ok('POST',base+f"/harvests/{h['harvest_event_id']}/sales",sale_body(quantity_sold='900',total_amount='45000'),code=201)
    cm.ok('POST','/my/farm-expenses',{**expense(cm,farm_crop_id=cycle['farm_crop_id']),'amount':'28000'},code=201)
    preview=cm.ok('GET',base+'/reconciliation')
    q=preview['quantities'][0]
    assert q=={'unit':'kg','total_harvested_quantity':1000,'total_wastage':50,'total_sold_quantity':900,'remaining_quantity':50}
    assert preview['total_revenue']==45000 and preview['total_expenses']==28000 and preview['net_return']==17000
    result=cm.ok('POST',base+'/complete',{'note':'Finished picking'})
    assert result['status']=='harvested' and result['completed_by']==cm.farmer['user_id'] and result['completed_at']
    assert cm.ok('POST',base+'/complete',{})==result
    assert cm.ok('GET',base+'/reconciliation')==result
    assert cycle['farm_crop_id'] in [x['farm_crop_id'] for x in cm.ok('GET','/my/crop-cycles?view=history')]
    assert cycle['farm_crop_id'] not in [x['farm_crop_id'] for x in cm.ok('GET','/my/crop-cycles?view=current')]


def test_repeated_harvests_and_unit_separation(cm):
    _,base=active(cm)
    for unit,amount in [('kg','10'),('kg','20'),('crate','2')]:
        cm.ok('POST',base+'/harvests',{**harvest_body(),'quantity':amount,'unit':unit},code=201)
    assert cm.ok('GET',base)['status']=='active'
    result=cm.ok('POST',base+'/complete',{})
    assert [(q['unit'],q['remaining_quantity']) for q in result['quantities']]==[('crate',2),('kg',30)]
    assert len(cm.ok('GET',base+'/harvests'))==3


def test_tasks_and_work_preserved(cm):
    cycle,base=active(cm)
    for n in range(1,7):cm.task(n)
    cm.publish();plan=cm.plan(cycle['farm_crop_id'],'2020-01-01')
    statuses=['completed','not_applicable','cancelled','pending','in_progress','partial']
    for t,status in zip(plan['tasks'],statuses):
        if status!='pending':cm.ok('POST',f"/my/crop-tasks/{t['crop_task_id']}/status",{'expected_status':'pending','status':status,'status_note':'Original'})
    a=cm.ok('POST','/my/farm-activities',activity(cm,farm_crop_id=cycle['farm_crop_id'],inputs=[{'custom_product':{'input_type':'other','product_name':'Mulch'},'quantity':'1','unit':'kg'}]),code=201)
    cm.ok('POST',base+'/complete',{})
    saved=cm.ok('GET',base)
    assert [t['status'] for t in saved['plan']['tasks']]==['completed','not_applicable','cancelled','cancelled','cancelled','cancelled']
    assert all('before this task was completed' in t['status_note'] for t in saved['plan']['tasks'][3:])
    assert cm.sql('SELECT count(*) FROM farm_activity_inputs WHERE activity_id=:id',id=a['activity_id']).scalar_one()==1


def test_historical_corrections_are_live(cm):
    cycle,base=active(cm);h=cm.ok('POST',base+'/harvests',harvest_body(),code=201)
    hp=base+'/harvests/'+str(h['harvest_event_id'])
    s=cm.ok('POST',hp+'/sales',sale_body(),code=201)
    e=cm.ok('POST','/my/farm-expenses',expense(cm,farm_crop_id=cycle['farm_crop_id']),code=201)
    completed=cm.ok('POST',base+'/complete',{})
    cm.ok('PUT',hp,edit_body(h,quantity='120',wastage_quantity='10'))
    cm.ok('PUT',hp+'/sales/'+str(s['harvest_sale_id']),edit_body(s,True,quantity_sold='40',total_amount='2000'))
    fields=('expense_date','category','amount','vendor_person','payment_mode','notes')
    cm.ok('PUT','/my/farm-expenses/'+str(e['expense_id']),{**{k:e[k] for k in fields},'amount':'500','expected_updated_at':e['updated_at']})
    now=cm.ok('GET',base+'/reconciliation')
    assert now['quantities'][0]['remaining_quantity']==70 and now['net_return']==1500
    assert now['completed_at']==completed['completed_at']


@pytest.mark.parametrize('operation',['reconciliation','complete','enable-seasons'])
def test_authorization(cm,client,operation):
    _,base=perennial(cm)
    method='GET' if operation=='reconciliation' else 'POST'
    body=None if method=='GET' else {'season':'2026','period_started_on':'2026-01-01'} if operation=='enable-seasons' else {}
    assert client.request(method,base+'/'+operation,json=body).status_code==401
    assert cm.call(method,base+'/'+operation,body,cm.other).status_code==404
    assert cm.call(method,base+'/'+operation,body,cm.provider).status_code==403


def test_admin_completion(cm):
    _,base=active(cm);adminbase=base.replace('/my/','/admin/')
    assert cm.call('POST',adminbase+'/complete',{}).status_code==403
    result=cm.ok('POST',adminbase+'/complete',{},cm.admin)
    assert result['completed_by']==cm.admin['user_id']
    assert cm.ok('GET',adminbase+'/reconciliation',as_user=cm.admin)==result


@pytest.mark.parametrize('status',['planned','cancelled'])
def test_cannot_complete_nonactive(cm,status):
    c=cm.cycle();base=f"/my/crop-cycles/{c['farm_crop_id']}"
    if status=='cancelled':cm.ok('POST',base+'/status',{'expected_status':'planned','status':'cancelled','note':'Stopped'})
    assert cm.call('POST',base+'/complete',{}).status_code==409


def test_legacy_completion_no_fabricated_audit(cm):
    _,base=active(cm)
    cm.ok('POST',base+'/status',{'expected_status':'active','status':'harvested'})
    r=cm.ok('POST',base+'/complete',{})
    assert r['completed_at'] is None and r['completed_by'] is None


def test_perennial_seasons_and_isolated_history(cm):
    cycle,base=perennial(cm)
    h=cm.ok('POST',base+'/harvests',harvest_body(),code=201)
    assert cm.call('POST',base+'/complete',{}).status_code==422
    p=enable(cm,base);pid=p['perennial_planting_id'];pb=f'/my/perennial-plantings/{pid}'
    assert cm.ok('POST',base+'/enable-seasons',{'season':'2026-27','period_started_on':'2026-01-01'})['perennial_planting_id']==pid
    assert cm.call('POST',pb+'/seasons',season_body()).status_code==409
    cm.ok('POST',base+'/complete',{})
    payload=season_body();next=cm.ok('POST',pb+'/seasons',payload,code=201)
    assert next['status']=='active' and next['planted_on']==cycle['planted_on']
    assert next['farm_id']==cycle['farm_id'] and next['plot_id']==cycle['plot_id']
    assert next['farm_crop_id']!=cycle['farm_crop_id'] and next['perennial_planting_id']==pid
    nb=f"/my/crop-cycles/{next['farm_crop_id']}"
    assert cm.ok('GET',nb)['plan'] is None
    assert cm.ok('GET',nb+'/reconciliation')['quantities']==[]
    assert cm.ok('GET',base+'/harvests')[0]['harvest_event_id']==h['harvest_event_id']
    assert len(cm.ok('GET',pb)['seasons'])==2 and len(cm.ok('GET','/my/perennial-plantings'))==1
    assert cm.ok('POST',pb+'/seasons',payload)['farm_crop_id']==next['farm_crop_id']
    assert cm.call('POST',pb+'/seasons',{**payload,'season':'Different'}).status_code==409
    cm.ok('POST',nb+'/complete',{})
    third=cm.ok('POST',pb+'/seasons',season_body(season='2028-29',period_started_on='2028-01-01'),code=201)
    assert third['perennial_planting_id']==pid


@pytest.mark.parametrize('change',[{'season':'2026-27'},{'period_started_on':'2025-01-01'},{'expected_harvest_on':'2026-01-01'},{'farm_id':1}])
def test_bad_future_season(cm,change):
    _,base=perennial(cm);p=enable(cm,base);cm.ok('POST',base+'/complete',{})
    assert cm.call('POST',f"/my/perennial-plantings/{p['perennial_planting_id']}/seasons",season_body(**change)).status_code in (409,422)


def test_planting_ownership_and_identity(cm):
    c,base=perennial(cm);p=enable(cm,base);pb=f"/my/perennial-plantings/{p['perennial_planting_id']}"
    assert cm.call('GET',pb,as_user=cm.other).status_code==404
    assert cm.call('POST',pb+'/seasons',season_body(),cm.other).status_code==404
    assert cm.ok('GET','/my/perennial-plantings',as_user=cm.other)==[]
    for query in ['UPDATE farm_crops SET perennial_planting_id=NULL WHERE farm_crop_id=:id', 'UPDATE farm_crops SET planted_on=\'2021-01-01\' WHERE farm_crop_id=:id','UPDATE farm_crops SET season=\'changed\' WHERE farm_crop_id=:id']:
        with pytest.raises(IntegrityError),cm.connection.begin_nested():cm.sql(query,id=c['farm_crop_id'])


def test_atomic_completion_rollback(cm,monkeypatch):
    _,base=active(cm);original=cm.connection.execute
    def fail(statement,*args,**kwargs):
        if "UPDATE crop_tasks SET status='cancelled'" in str(statement):raise RuntimeError('Injected task closure failure')
        return original(statement,*args,**kwargs)
    monkeypatch.setattr(cm.connection,'execute',fail)
    assert cm.call('POST',base+'/complete',{}).status_code==500
    saved=cm.ok('GET',base)
    assert saved['status']=='active' and saved['completed_at'] is None
