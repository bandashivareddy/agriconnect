from uuid import uuid4
import pytest
from sqlalchemy.exc import IntegrityError
from test_crop_management import cm
from test_farm_ledger import activity, expense


def marketplace(cm):
    category=cm.sql('INSERT INTO service_categories(category_name) VALUES(:name) RETURNING category_id',name='Cultivation '+uuid4().hex).scalar_one()
    cm.sql("INSERT INTO supplier_profiles(supplier_id,business_name,is_active,verified_at) VALUES(:id,'Provider',true,'2025-01-01')",id=cm.provider['user_id'])
    service=cm.sql("INSERT INTO supplier_services(supplier_id,category_id,service_name,pricing_unit,base_price) VALUES(:actor,:category,'Cultivation','fixed',1000) RETURNING supplier_service_id",actor=cm.provider['user_id'],category=category).scalar_one()
    slot=cm.sql("INSERT INTO availability_slots(supplier_service_id,starts_at,ends_at,capacity) VALUES(:id,'2026-01-02 08:00','2026-01-02 09:00',1) RETURNING availability_slot_id",id=service).scalar_one()
    return category,service,slot


def setup(cm, requirement=True, **cycle_fields):
    category,service,slot=marketplace(cm)
    cm.task(service_category_id=category if requirement else None);cm.publish()
    cycle=cm.cycle(status='active',planted_on='2026-01-01',**cycle_fields)
    plan=cm.plan(cycle['farm_crop_id']);task=plan['tasks'][0]
    body={'supplier_service_id':service,'farm_id':cm.farm,'requested_start_at':'2026-01-02T08:00:00','requested_end_at':'2026-01-02T09:00:00','quantity':1,'crop_task_id':task['crop_task_id'],'crop_request_key':str(uuid4())}
    return cycle,task,body,slot


def book(cm,body):return cm.ok('POST','/my/bookings',body,code=201)


def provider_complete(cm,booking):
    for status in ('confirmed','in_progress','completed'):
        cm.ok('PUT',f"/supplier/bookings/{booking['booking_id']}/status",{'new_status':status},cm.provider)


def work(cm,cycle,task,booking):
    return activity(cm,farm_crop_id=cycle['farm_crop_id'],crop_task_id=task['crop_task_id'],service_booking_id=booking['booking_id'],source_type='service_booking')


def test_optional_requirement_and_no_matching_services(cm):
    _,task,body,_=setup(cm,False)
    assert cm.ok('GET',f"/my/crop-tasks/{task['crop_task_id']}/service-context")['can_book'] is False
    assert cm.call('POST','/my/bookings',body).status_code==409
    assert cm.ok('GET','/services?category_id=2147483647')==[]


def test_sop_snapshot_clone_and_immutability(cm):
    category,_,_=marketplace(cm)
    draft=cm.task(service_category_id=category);original=draft['service_category_name_snapshot']
    cm.publish();cm.sql("UPDATE service_categories SET category_name='Renamed' WHERE category_id=:id",id=category)
    cycle=cm.cycle();t=cm.plan(cycle['farm_crop_id'])['tasks'][0]
    assert t['service_category_id']==category and t['service_category_name_snapshot']==original
    with pytest.raises(IntegrityError),cm.connection.begin_nested():cm.sql('UPDATE crop_tasks SET service_category_id=NULL,service_category_name_snapshot=NULL WHERE crop_task_id=:id',id=t['crop_task_id'])
    assert cm.call('PATCH',f"/admin/sop-tasks/{draft['sop_task_id']}",{'service_category_id':None},cm.admin).status_code==409
    clone=cm.ok('POST',f"/admin/sop-templates/{cm.template['sop_template_id']}/versions",{'clone_from_version_id':cm.version['sop_version_id']},cm.admin,201)
    assert cm.ok('GET',f"/admin/sop-versions/{clone['sop_version_id']}",as_user=cm.admin)['tasks'][0]['service_category_name_snapshot']==original


def test_draft_requirement_edit_and_remove(cm):
    category,_,_=marketplace(cm);task=cm.task()
    t=cm.ok('PATCH',f"/admin/sop-tasks/{task['sop_task_id']}",{'service_category_id':category},cm.admin)
    assert t['service_category_id']==category
    t=cm.ok('PATCH',f"/admin/sop-tasks/{task['sop_task_id']}",{'service_category_id':None},cm.admin)
    assert t['service_category_name_snapshot'] is None


def test_booking_context_matching_and_original_engine(cm):
    cycle,task,body,slot=setup(cm)
    ctx=cm.ok('GET',f"/my/crop-tasks/{task['crop_task_id']}/service-context")
    assert ctx['farm_crop_id']==cycle['farm_crop_id'] and ctx['farm_id']==cm.farm and ctx['plot_id']==cm.plot
    services=cm.ok('GET',f"/services?category_id={task['service_category_id']}")
    assert len(services)==1 and services[0]['supplier_service_id']==body['supplier_service_id']
    b=book(cm,body)
    assert b['crop_context_snapshot']['farm_crop_id']==cycle['farm_crop_id'] and b['crop_task_id']==task['crop_task_id']
    assert cm.sql('SELECT count(*) FROM booking_items WHERE booking_id=:id',id=b['booking_id']).scalar_one()==1
    assert cm.sql('SELECT reserved_quantity FROM booking_slot_reservations WHERE booking_id=:id AND availability_slot_id=:slot',id=b['booking_id'],slot=slot).scalar_one()==1
    assert cm.sql('SELECT count(*) FROM booking_status_history WHERE booking_id=:id',id=b['booking_id']).scalar_one()==1
    assert cm.ok('POST','/my/bookings',body)['booking_id']==b['booking_id']
    assert cm.call('POST','/my/bookings',{**body,'quantity':2}).status_code==409
    assert cm.call('POST','/my/bookings',{**body,'crop_request_key':str(uuid4())}).status_code==400
    assert cm.ok('GET',f"/my/crop-tasks/{task['crop_task_id']}/bookings")[0]['booking_id']==b['booking_id']
    assert cm.ok('GET',f"/farmers/{cm.farmer['user_id']}/bookings")[0]['crop_task_id']==task['crop_task_id']
    assert cm.ok('GET','/supplier/bookings',as_user=cm.provider)[0]['crop_context_snapshot']['title']==task['title']


def test_complete_confirm_expense_and_task_chain(cm):
    cycle,task,body,_=setup(cm);b=book(cm,body)
    w=work(cm,cycle,task,b)
    assert cm.call('POST','/my/farm-activities',w).status_code==409
    provider_complete(cm,b)
    assert cm.sql('SELECT status FROM crop_tasks WHERE crop_task_id=:id',id=task['crop_task_id']).scalar_one()=='pending'
    assert cm.sql('SELECT count(*) FROM farm_activities WHERE service_booking_id=:id',id=b['booking_id']).scalar_one()==0
    assert cm.sql('SELECT count(*) FROM farm_expenses WHERE farm_crop_id=:id',id=cycle['farm_crop_id']).scalar_one()==0
    a=cm.ok('POST','/my/farm-activities',w,code=201)
    assert a['service_booking_id']==b['booking_id'] and a['crop_task_id']==task['crop_task_id'] and a['plot_id']==cm.plot
    assert cm.ok('POST','/my/farm-activities',w)['activity_id']==a['activity_id']
    assert cm.call('POST','/my/farm-activities',{**w,'request_key':str(uuid4())}).status_code==409
    ebody={**expense(cm,activity_id=a['activity_id']),'amount':'950'}
    e=cm.ok('POST','/my/farm-expenses',ebody,code=201)
    assert cm.ok('POST','/my/farm-expenses',ebody)['expense_id']==e['expense_id']
    assert e['farm_crop_id']==cycle['farm_crop_id'] and e['amount']==950
    result=cm.ok('POST',f"/my/crop-tasks/{task['crop_task_id']}/status",{'expected_status':'pending','status':'completed'})
    assert result['status']=='completed'
    assert cm.sql('SELECT count(*) FROM visit_tasks WHERE crop_task_id=:id',id=task['crop_task_id']).scalar_one()==0


@pytest.mark.parametrize('status',['cancelled','rejected'])
def test_cancel_reject_rebook(cm,status):
    _,task,body,_=setup(cm);b=book(cm,body)
    cm.ok('PUT',f"/supplier/bookings/{b['booking_id']}/status",{'new_status':status},cm.provider)
    assert cm.sql('SELECT status FROM crop_tasks WHERE crop_task_id=:id',id=task['crop_task_id']).scalar_one()=='pending'
    assert book(cm,{**body,'crop_request_key':str(uuid4())})['booking_id']!=b['booking_id']
    assert cm.ok('POST','/my/bookings',body)['booking_id']==b['booking_id']


@pytest.mark.parametrize('change,code',[({'farm_id':2147483647},422),({'crop_task_id':2147483647},404),({'crop_request_key':None},422),({'supplier_service_id':2147483647},422)])
def test_bad_booking_context(cm,change,code):
    _,_,body,_=setup(cm)
    assert cm.call('POST','/my/bookings',{**body,**change}).status_code==code


def test_wrong_service_category(cm):
    _,_,body,_=setup(cm)
    other=cm.sql("INSERT INTO service_categories(category_name) VALUES(:n) RETURNING category_id",n=uuid4().hex).scalar_one()
    cm.sql('UPDATE supplier_services SET category_id=:cat WHERE supplier_service_id=:id',cat=other,id=body['supplier_service_id'])
    assert cm.call('POST','/my/bookings',body).status_code==422


def test_owner_and_provider_authorization(cm,client):
    cycle,task,body,_=setup(cm);path=f"/my/crop-tasks/{task['crop_task_id']}"
    assert client.get(path+'/service-context').status_code==401
    for suffix in ('/service-context','/bookings'):
        assert cm.call('GET',path+suffix,as_user=cm.other).status_code==404
        assert cm.call('GET',path+suffix,as_user=cm.provider).status_code==403
    assert cm.call('POST','/my/bookings',body,cm.other).status_code==404
    b=book(cm,body);provider_complete(cm,b)
    assert cm.call('POST','/my/farm-activities',work(cm,cycle,task,b),cm.provider).status_code==403


def test_cross_crop_activity_and_closed_period(cm):
    cycle,task,body,_=setup(cm);b=book(cm,body);provider_complete(cm,b)
    other=cm.cycle(status='active',planted_on='2026-01-01');other_task=cm.plan(other['farm_crop_id'])['tasks'][0]
    assert cm.call('POST','/my/farm-activities',work(cm,other,other_task,b)).status_code==404
    cm.ok('POST',f"/my/crop-cycles/{cycle['farm_crop_id']}/complete",{})
    assert cm.call('POST','/my/farm-activities',work(cm,cycle,task,b)).status_code==409
    assert cm.call('POST','/my/bookings',{**body,'crop_request_key':str(uuid4())}).status_code==409
    assert cm.ok('POST','/my/bookings',body)['booking_id']==b['booking_id']


def test_self_work_and_booking_link_immutable(cm):
    cycle,task,body,_=setup(cm);b=book(cm,body)
    cm.ok('POST',f"/my/crop-tasks/{task['crop_task_id']}/record-work",activity(cm,farm_crop_id=cycle['farm_crop_id'],crop_task_id=task['crop_task_id'],source_type='crop_task'),code=201)
    with pytest.raises(IntegrityError),cm.connection.begin_nested():cm.sql('UPDATE bookings SET crop_task_id=NULL,crop_context_snapshot=NULL,crop_request_key=NULL,crop_request_payload=NULL WHERE booking_id=:id',id=b['booking_id'])


def test_perennial_current_season_only(cm):
    cycle,task,body,_=setup(cm)
    cm.sql("UPDATE crops SET lifecycle_type='perennial',crop_group='orchard' WHERE crop_id=:id",id=cm.crop)
    base=f"/my/crop-cycles/{cycle['farm_crop_id']}"
    p=cm.ok('POST',base+'/enable-seasons',{'season':'2026','period_started_on':'2026-01-01'},code=201)
    cm.ok('POST',base+'/complete',{})
    next=cm.ok('POST',f"/my/perennial-plantings/{p['perennial_planting_id']}/seasons",{'season':'2027','period_started_on':'2027-01-01','request_key':str(uuid4())},code=201)
    nt=cm.plan(next['farm_crop_id'])['tasks'][0]
    cm.sql("INSERT INTO availability_slots(supplier_service_id,starts_at,ends_at,capacity) VALUES(:id,'2027-01-02 08:00','2027-01-02 09:00',1)",id=body['supplier_service_id'])
    b=book(cm,{**body,'crop_task_id':nt['crop_task_id'],'requested_start_at':'2027-01-02T08:00:00','requested_end_at':'2027-01-02T09:00:00'})
    assert b['crop_context_snapshot']['farm_crop_id']==next['farm_crop_id']
    assert b['crop_context_snapshot']['season']=='2027'
    assert cm.call('POST','/my/bookings',{**body,'crop_request_key':str(uuid4())}).status_code==409
    assert cm.ok('GET',f"/my/crop-tasks/{task['crop_task_id']}/bookings")==[]


def test_booking_provider_verification_and_multi_hour_reservations(cm):
    _,_,body,_=setup(cm)
    cm.sql('UPDATE supplier_profiles SET verified_at=NULL WHERE supplier_id=:id',id=cm.provider['user_id'])
    assert cm.call('POST','/my/bookings',body).status_code==403
    cm.sql("UPDATE supplier_profiles SET verified_at='2025-01-01' WHERE supplier_id=:id",id=cm.provider['user_id'])
    longer={**body,'requested_end_at':'2026-01-02T10:00:00'}
    assert cm.call('POST','/my/bookings',longer).status_code==400
    cm.sql("INSERT INTO availability_slots(supplier_service_id,starts_at,ends_at,capacity) VALUES(:id,'2026-01-02 09:00','2026-01-02 10:00',1)",id=body['supplier_service_id'])
    b=book(cm,longer)
    assert cm.sql('SELECT count(*) FROM booking_slot_reservations WHERE booking_id=:id',id=b['booking_id']).scalar_one()==2


def test_planned_preparation_work_before_activation(cm):
    category,service,_=marketplace(cm);cm.task(service_category_id=category);cm.publish()
    cycle=cm.cycle();task=cm.plan(cycle['farm_crop_id'])['tasks'][0]
    body={'supplier_service_id':service,'crop_task_id':task['crop_task_id'],'crop_request_key':str(uuid4()),
          'requested_start_at':'2026-01-02T08:00:00','requested_end_at':'2026-01-02T09:00:00','quantity':1}
    b=book(cm,body);provider_complete(cm,b)
    saved=cm.ok('POST','/my/farm-activities',work(cm,cycle,task,b),code=201)
    assert saved['farm_crop_id']==cycle['farm_crop_id']
    assert cm.ok('GET',f"/my/crop-cycles/{cycle['farm_crop_id']}")['status']=='planned'
    assert cm.call('POST',f"/my/crop-tasks/{task['crop_task_id']}/status",{'expected_status':'pending','status':'completed'}).status_code==409
