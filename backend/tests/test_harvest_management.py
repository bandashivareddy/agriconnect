from uuid import uuid4
from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError
from test_crop_management import cm
from test_farm_ledger import expense, block


def harvest_body(**extra):
    return dict(harvested_on='2026-09-01', quantity='100', unit='kg', request_key=str(uuid4()), **extra)


def sale_body(**extra):
    return {**dict(sold_on='2026-09-02', quantity_sold='30', unit='kg', total_amount='1500', request_key=str(uuid4())), **extra}


def setup(cm, **cycle_fields):
    cycle = cm.cycle(**cycle_fields)
    base = f"/my/crop-cycles/{cycle['farm_crop_id']}"
    return cycle, base, cm.ok('POST', base+'/harvests', harvest_body(), code=201)


def edit_body(record, sale=False, **extra):
    fields = ('quantity_sold','unit','price_per_unit','total_amount','buyer_name','sold_on','notes') if sale else ('harvested_on','quantity','unit','grade','wastage_quantity','notes')
    return {**{k:record[k] for k in fields}, 'expected_updated_at':record['updated_at'], **extra}


@pytest.mark.parametrize('status',['planned','active'])
def test_repeated_harvest_preserves_cycle(cm,status):
    cycle,base,h=setup(cm,**({'status':'active','planted_on':'2026-01-01'} if status=='active' else {}))
    cm.ok('POST',base+'/harvests',harvest_body(),code=201)
    saved=cm.ok('GET',base)
    assert saved['status']==status and saved['planted_on']==cycle['planted_on']
    assert len(cm.ok('GET',base+'/harvests'))==2
    assert h['farm_id']==cm.farm and h['plot_id']==cm.plot and h['farm_block_id'] is None
    assert h['created_by']==h['updated_by']==cm.farmer['user_id'] and h['created_at']


@pytest.mark.parametrize('change',[{'quantity':'0'},{'quantity':'-1'},{'quantity':'NaN'},{'quantity':'Infinity'}, {'quantity':'10000000000'}, {'quantity':'1.00001'}, {'wastage_quantity':'-1'},{'wastage_quantity':'101'},{'unit':'litres'},{'farm_id':1}])
def test_harvest_validation(cm,change):
    cycle=cm.cycle()
    assert cm.call('POST',f"/my/crop-cycles/{cycle['farm_crop_id']}/harvests",{**harvest_body(),**change}).status_code==422


def test_sales_summary_and_costs(cm):
    cycle,base,h=setup(cm)
    path=base+f"/harvests/{h['harvest_event_id']}/sales"
    cm.ok('POST',path,sale_body(),code=201)
    cm.ok('POST',path,sale_body(quantity_sold='40',total_amount=None,price_per_unit='50'),code=201)
    cm.ok('POST','/my/farm-expenses',expense(cm,farm_crop_id=cycle['farm_crop_id']),code=201)
    cm.ok('POST',base+'/harvests',{**harvest_body(),'quantity':'2','unit':'crate'},code=201)
    summary=cm.ok('GET',base+'/harvest-summary')
    assert Decimal(str(summary['total_revenue']))==3500
    assert Decimal(str(summary['total_expenses']))==Decimal('120.25')
    assert Decimal(str(summary['net_return']))==Decimal('3379.75')
    assert summary['quantities']==[{'unit':'crate','total_harvested_quantity':2,'total_wastage':0,'total_sold_quantity':0},{'unit':'kg','total_harvested_quantity':100,'total_wastage':0,'total_sold_quantity':70}]
    assert len(cm.ok('GET',path))==2
    assert cm.call('POST',path,sale_body(quantity_sold='31')).status_code==409
    assert cm.ok('GET',base+'/harvests')[1]['available_quantity']==30


@pytest.mark.parametrize('change,code',[({'quantity_sold':'0'},422),({'total_amount':'0'},422),({'total_amount':None},422),({'price_per_unit':'2'},422),({'unit':'bag'},409),({'sold_on':'2026-08-31'},409),({'quantity_sold':'101'},409),({'quantity_sold':'9999999999','price_per_unit':'9999999999','total_amount':None},422),({'quantity_sold':'0.0001','price_per_unit':'0.0001','total_amount':None},422)])
def test_sale_validation(cm,change,code):
    _,base,h=setup(cm)
    assert cm.call('POST',base+f"/harvests/{h['harvest_event_id']}/sales",sale_body(**change)).status_code==code


def test_wastage_rounding_corrections_and_retry(cm):
    _,base,h=setup(cm)
    hp=base+f"/harvests/{h['harvest_event_id']}"
    h=cm.ok('PUT',hp,edit_body(h,wastage_quantity='10'))
    payload=sale_body(quantity_sold='90',price_per_unit='1.0005',total_amount=None)
    s=cm.ok('POST',hp+'/sales',payload,code=201)
    assert Decimal(str(s['total_amount']))==Decimal('90.05')
    assert cm.ok('POST',hp+'/sales',payload)['harvest_sale_id']==s['harvest_sale_id']
    assert cm.call('POST',hp+'/sales',{**payload,'notes':'different'}).status_code==409
    for changes in ({'quantity':'99'},{'wastage_quantity':'11'},{'unit':'bag'},{'harvested_on':'2026-09-03'}):
        assert cm.call('PUT',hp,edit_body(h,**changes)).status_code==409
    corrected=cm.ok('PUT',hp+'/sales/'+str(s['harvest_sale_id']),edit_body(s,True,quantity_sold='80',price_per_unit=None,total_amount='400'))
    assert corrected['updated_at']!=s['updated_at']
    assert cm.call('PUT',hp+'/sales/'+str(s['harvest_sale_id']),edit_body(s,True)).status_code==409
    assert cm.ok('POST',hp+'/sales',payload)['quantity_sold']==80
    h2=cm.ok('PUT',hp,edit_body(h,quantity='90'))
    assert cm.call('PUT',hp,edit_body(h)).status_code==409
    assert cm.ok('GET',hp)['updated_at']==h2['updated_at']


def test_harvest_retry_and_cross_context(cm):
    a=cm.cycle();b=cm.cycle();p=f"/my/crop-cycles/{a['farm_crop_id']}/harvests";q=f"/my/crop-cycles/{b['farm_crop_id']}/harvests"
    body=harvest_body();h=cm.ok('POST',p,body,code=201)
    assert cm.ok('POST',p,body)['harvest_event_id']==h['harvest_event_id']
    assert cm.call('POST',q,body).status_code==409
    assert cm.call('GET',q+'/'+str(h['harvest_event_id'])).status_code==404
    assert cm.call('POST',q+'/'+str(h['harvest_event_id'])+'/sales',sale_body()).status_code==404
    h2=cm.ok('POST',q,harvest_body(),code=201)
    s=cm.ok('POST',p+'/'+str(h['harvest_event_id'])+'/sales',sale_body(),code=201)
    assert cm.call('PUT',q+'/'+str(h2['harvest_event_id'])+'/sales/'+str(s['harvest_sale_id']),edit_body(s,True)).status_code==404


@pytest.mark.parametrize('suffix',['/harvests','/harvest-summary'])
def test_authorization(cm,client,suffix):
    _,base,_=setup(cm)
    assert client.get(base+suffix).status_code==401
    assert cm.call('GET',base+suffix,as_user=cm.other).status_code==404
    assert cm.call('GET',base+suffix,as_user=cm.provider).status_code==403
    assert cm.call('GET',base.replace('/my/','/admin/')+suffix).status_code==403
    assert cm.call('GET',base.replace('/my/','/admin/')+suffix,as_user=cm.admin).status_code==200


def test_historical_admin_and_block(cm):
    b=block(cm)
    cycle,base,h=setup(cm,status='active',planted_on='2026-01-01',farm_block_id=b['farm_block_id'])
    assert h['farm_block_id']==b['farm_block_id']
    cm.ok('POST',base+'/status',{'expected_status':'active','status':'harvested'})
    adminbase=base.replace('/my/','/admin/')
    h2=cm.ok('POST',adminbase+'/harvests',harvest_body(),cm.admin,201)
    assert h2['created_by']==cm.admin['user_id']
    corrected=cm.ok('PUT',adminbase+'/harvests/'+str(h['harvest_event_id']),edit_body(h,notes='Historical correction'),cm.admin)
    assert corrected['updated_by']==cm.admin['user_id'] and corrected['created_by']==cm.farmer['user_id']
    cm.ok('POST',base+'/harvests/'+str(h['harvest_event_id'])+'/sales',sale_body(),code=201)
    assert cm.ok('GET',base)['status']=='harvested'


def test_database_guards(cm):
    cycle,base,h=setup(cm)
    hp=base+'/harvests/'+str(h['harvest_event_id'])
    s=cm.ok('POST',hp+'/sales',sale_body(),code=201)
    queries=[('UPDATE harvest_events SET farm_crop_id=:value WHERE harvest_event_id=:id',cm.cycle()['farm_crop_id'],h['harvest_event_id']),
      ('UPDATE farm_crops SET plot_id=NULL WHERE farm_crop_id=:id',None,cycle['farm_crop_id']),
      ('UPDATE harvest_events SET quantity=20 WHERE harvest_event_id=:id',None,h['harvest_event_id']),
      ('UPDATE harvest_sales SET quantity_sold=101 WHERE harvest_sale_id=:id',None,s['harvest_sale_id']),
      ('UPDATE harvest_events SET created_by=:value WHERE harvest_event_id=:id',cm.admin['user_id'],h['harvest_event_id']),
      ('UPDATE harvest_sales SET unit=\'bag\' WHERE harvest_sale_id=:id',None,s['harvest_sale_id'])]
    for query,value,id in queries:
        with pytest.raises(IntegrityError),cm.connection.begin_nested():cm.sql(query,id=id,value=value)


def test_empty_summary_and_pagination(cm):
    c=cm.cycle();base=f"/my/crop-cycles/{c['farm_crop_id']}"
    s=cm.ok('GET',base+'/harvest-summary')
    assert s['quantities']==[] and s['net_return']==0
    for _ in range(3):cm.ok('POST',base+'/harvests',harvest_body(),code=201)
    assert len(cm.ok('GET',base+'/harvests?limit=2'))==2
    assert len(cm.ok('GET',base+'/harvests?limit=2&offset=2'))==1


def test_write_authorization_and_sale_scope(cm):
    _,base,h=setup(cm);hp=base+'/harvests/'+str(h['harvest_event_id'])
    s=cm.ok('POST',hp+'/sales',sale_body(),code=201)
    for user,code in [(cm.other,404),(cm.provider,403)]:
        for method,path,body in [('POST',base+'/harvests',harvest_body()),('PUT',hp,edit_body(h)),('POST',hp+'/sales',sale_body()),('PUT',hp+'/sales/'+str(s['harvest_sale_id']),edit_body(s,True))]:
            assert cm.call(method,path,body,user).status_code==code
    r=cm.ok('PUT',hp.replace('/my/','/admin/')+'/sales/'+str(s['harvest_sale_id']),edit_body(s,True,notes='Admin correction'),cm.admin)
    assert r['updated_by']==cm.admin['user_id'] and r['created_by']==cm.farmer['user_id']


def test_cancelled_crop_late_entry_and_net_loss(cm):
    cycle=cm.cycle();base=f"/my/crop-cycles/{cycle['farm_crop_id']}"
    cm.ok('POST',base+'/status',{'expected_status':'planned','status':'cancelled','note':'Crop stopped; recording a late harvest entry.'})
    h=cm.ok('POST',base+'/harvests',{**harvest_body(),'wastage_quantity':'100'},code=201)
    assert cm.call('POST',base+'/harvests/'+str(h['harvest_event_id'])+'/sales',sale_body()).status_code==409
    cm.ok('POST','/my/farm-expenses',expense(cm,farm_crop_id=cycle['farm_crop_id']),code=201)
    cm.ok('POST','/my/farm-expenses',{**expense(cm),'amount':'999'},code=201) # Farm overhead is not allocated.
    s=cm.ok('GET',base+'/harvest-summary')
    assert Decimal(str(s['net_return']))==Decimal('-120.25') and s['quantities'][0]['total_wastage']==100
    assert cm.ok('GET',base)['status']=='cancelled'


def test_harvest_does_not_change_plan_tasks(cm):
    cm.task();cm.publish();cycle=cm.cycle(status='active',planted_on='2026-01-01')
    before=cm.plan(cycle['farm_crop_id'])
    base=f"/my/crop-cycles/{cycle['farm_crop_id']}"
    cm.ok('POST',base+'/harvests',harvest_body(),code=201)
    assert cm.ok('GET',base)['plan']['tasks']==before['tasks']


def test_legacy_no_plot_context(cm):
    cycle=cm.sql('INSERT INTO farm_crops(farm_id,crop_id) VALUES(:farm,:crop) RETURNING farm_crop_id',farm=cm.farm,crop=cm.crop).scalar_one()
    h=cm.ok('POST',f'/my/crop-cycles/{cycle}/harvests',harvest_body(),code=201)
    assert h['plot_id'] is None and h['farm_block_id'] is None
    assert cm.sql('SELECT created_at FROM farm_crops WHERE farm_crop_id=:id',id=cycle).scalar_one() is None


def test_rejected_sale_is_atomic_and_key_reusable(cm):
    _,base,h=setup(cm);path=base+'/harvests/'+str(h['harvest_event_id'])+'/sales'
    body=sale_body(quantity_sold='101')
    assert cm.call('POST',path,body).status_code==409
    assert cm.ok('GET',path)==[]
    body['quantity_sold']='100'
    cm.ok('POST',path,body,code=201)
    assert cm.ok('GET',base+'/harvests')[0]['available_quantity']==0
