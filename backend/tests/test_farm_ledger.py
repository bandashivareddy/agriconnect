from uuid import uuid4
import pytest
from sqlalchemy.exc import IntegrityError
from test_crop_management import cm
from test_field_work import fw, start


def activity(cm,**extra):
    return dict(farm_id=cm.farm,activity_type='irrigation',activity_date='2026-09-01',description='Watered the soil',request_key=str(uuid4()),**extra)


def expense(cm,**extra):
    return dict(farm_id=cm.farm,expense_date='2026-09-01',category='labour',amount='120.25',request_key=str(uuid4()),**extra)


def block(cm,**extra):
    return cm.ok('POST','/my/farm-blocks',dict(farm_id=cm.farm,plot_id=cm.plot,name='North block',**extra),code=201)


def edit_body(record,kind,**updates):
    fields={'activity':['activity_type','activity_date','description','quantity','unit','performed_by_user_id','notes'],
            'expense':['expense_date','category','amount','vendor_person','payment_mode','notes'],
            'block':['name','description','area','area_unit','status']}[kind]
    return {**{k:record[k] for k in fields},'expected_updated_at':record['updated_at'],**updates}


def other_farm(cm):
    f=cm.sql("INSERT INTO farms(farmer_id,farm_name,location) VALUES(:id,'Other','Village') RETURNING farm_id",id=cm.other['user_id']).scalar_one()
    p=cm.sql("INSERT INTO farm_plots(farm_id,plot_name) VALUES(:id,'Other') RETURNING plot_id",id=f).scalar_one()
    return f,p


def test_blocks_crud_ownership_optional(cm):
    b=block(cm,area='2.25',area_unit='acres');bid=b['farm_block_id']
    assert cm.ok('GET',f'/my/farm-blocks?farm_id={cm.farm}&plot_id={cm.plot}')[0]['farm_block_id']==bid
    assert cm.call('GET',f'/my/farm-blocks?farm_id={cm.farm}',as_user=cm.other).status_code==404
    assert cm.call('PUT',f'/my/farm-blocks/{bid}',edit_body(b,'block'),cm.other).status_code==404
    changed=cm.ok('PUT',f'/my/farm-blocks/{bid}',edit_body(b,'block',name='Renamed'))
    assert cm.call('PUT',f'/my/farm-blocks/{bid}',edit_body(b,'block')).status_code==409
    cycle=cm.cycle(farm_block_id=bid)
    assert cycle['farm_block_id']==bid and cm.cycle()['farm_block_id'] is None
    cm.ok('PUT',f'/my/farm-blocks/{bid}',edit_body(changed,'block',status='inactive'))
    assert cm.call('POST',f'/my/farms/{cm.farm}/crop-cycles',{'plot_id':cm.plot,'crop_id':cm.crop,'farm_block_id':bid}).status_code==409
    assert cm.ok('GET',f"/my/crop-cycles/{cycle['farm_crop_id']}")['farm_block_id']==bid


@pytest.mark.parametrize('change',[{'name':' '},{'area':-1,'area_unit':'acres'},{'area':2},{'area_unit':'acres'},{'status':'deleted'}])
def test_block_validation(cm,change):
    assert cm.call('POST','/my/farm-blocks',{'farm_id':cm.farm,'plot_id':cm.plot,'name':'Block',**change}).status_code==422


def test_cross_farm_block(cm):
    _,plot=other_farm(cm)
    assert cm.call('POST','/my/farm-blocks',{'farm_id':cm.farm,'plot_id':plot,'name':'Wrong'}).status_code==404
    with pytest.raises(IntegrityError),cm.connection.begin_nested():
        cm.sql("INSERT INTO farm_blocks(farm_id,plot_id,name,created_by,updated_by) VALUES(:farm,:plot,'Wrong',:actor,:actor)",farm=cm.farm,plot=plot,actor=cm.farmer['user_id'])


def test_track_myself_no_plan_and_edits(cm):
    cycle=cm.cycle();body=activity(cm,farm_crop_id=cycle['farm_crop_id'])
    saved=cm.ok('POST','/my/farm-activities',body,code=201)
    assert saved['crop_task_id'] is None and saved['plot_id']==cm.plot
    assert cm.ok('GET',f"/my/crop-cycles/{cycle['farm_crop_id']}")['plan'] is None
    path=f"/my/farm-activities/{saved['activity_id']}"
    changed=cm.ok('PUT',path,edit_body(saved,'activity',description='Corrected work note'))
    assert cm.ok('GET',path)['description']=='Corrected work note'
    assert cm.call('PUT',path,edit_body(saved,'activity')).status_code==409
    assert cm.call('PUT',path,{**edit_body(changed,'activity'),'farm_id':999}).status_code==422
    assert cm.call('GET',path,as_user=cm.other).status_code==404
    assert cm.call('PUT',path,edit_body(changed,'activity'),cm.other).status_code==404
    assert cm.ok('GET',f"/my/farm-activities?farm_crop_id={cycle['farm_crop_id']}")['count']==1
    assert cm.ok('GET',f'/my/farm-activities?farm_id={cm.farm}',as_user=cm.other)['count']==0
    # Replaying the original create after an edit returns the current record, not a duplicate.
    assert cm.ok('POST','/my/farm-activities',body)['description']=='Corrected work note'


def test_task_record_work_retry_distinct_events_and_no_execution_side_effect(cm):
    cm.task();cm.publish();cycle=cm.cycle();plan=cm.plan(cycle['farm_crop_id']);task=plan['tasks'][0]
    body=activity(cm,crop_task_id=task['crop_task_id'],source_type='crop_task')
    path=f"/my/crop-tasks/{task['crop_task_id']}/record-work"
    saved=cm.ok('POST',path,body,code=201)
    assert saved['farm_crop_id']==cycle['farm_crop_id']
    assert cm.ok('POST',path,body)['activity_id']==saved['activity_id']
    assert cm.call('POST',path,{**body,'description':'Changed payload'}).status_code==409
    cm.ok('POST',path,{**body,'request_key':str(uuid4())},code=201)
    assert cm.ok('GET',f"/my/farm-activities?crop_task_id={task['crop_task_id']}")['count']==2
    assert cm.ok('GET',f"/my/crop-tasks/{task['crop_task_id']}")['status']=='pending'
    assert cm.ok('GET','/my/farm-expenses')['total_amount']==0


@pytest.mark.parametrize('change',[{'quantity':'0'},{'quantity':'NaN','unit':'kg'},{'quantity':1},{'unit':'kg'},{'activity_type':'tree_harvest'},{'description':' '},{'source_type':'crop_task'},{'source_type':'service_booking'}])
def test_activity_validation(cm,change):
    assert cm.call('POST','/my/farm-activities',{**activity(cm),**change}).status_code==422


def test_context_mismatch_and_history_guard(cm):
    b=block(cm);cycle=cm.cycle(farm_block_id=b['farm_block_id']);_,foreign_plot=other_farm(cm)
    assert cm.call('POST','/my/farm-activities',activity(cm,plot_id=foreign_plot)).status_code==404
    assert cm.call('POST','/my/farm-activities',activity(cm,farm_crop_id=cycle['farm_crop_id'],plot_id=foreign_plot)).status_code==422
    saved=cm.ok('POST','/my/farm-activities',activity(cm,farm_crop_id=cycle['farm_crop_id']),code=201)
    assert saved['farm_block_id']==b['farm_block_id']
    assert cm.call('PATCH',f"/my/crop-cycles/{cycle['farm_crop_id']}",{'farm_block_id':None}).status_code==409
    with pytest.raises(IntegrityError),cm.connection.begin_nested():
        cm.sql('UPDATE farm_activities SET plot_id=:plot WHERE activity_id=:id',plot=foreign_plot,id=saved['activity_id'])


def test_standalone_multiple_linked_expenses_totals_and_edits(cm):
    b=block(cm);cycle=cm.cycle(farm_block_id=b['farm_block_id']);a=cm.ok('POST','/my/farm-activities',activity(cm,farm_crop_id=cycle['farm_crop_id']),code=201)
    standalone=cm.ok('POST','/my/farm-expenses',expense(cm),code=201)
    body=expense(cm,activity_id=a['activity_id'])
    first=cm.ok('POST','/my/farm-expenses',body,code=201)
    cm.ok('POST','/my/farm-expenses',expense(cm,activity_id=a['activity_id']),code=201)
    assert cm.ok('POST','/my/farm-expenses',body)['expense_id']==first['expense_id']
    assert cm.call('POST','/my/farm-expenses',{**body,'amount':'5.00'}).status_code==409
    for query,total in [(f'farm_id={cm.farm}',360.75),(f'farm_block_id={b["farm_block_id"]}',240.50),(f'farm_crop_id={cycle["farm_crop_id"]}',240.50),(f'activity_id={a["activity_id"]}',240.50),('date_from=2026-09-02',0)]:
        data=cm.ok('GET',f'/my/farm-expenses?{query}&limit=1');assert float(data['total_amount'])==total
    assert standalone['activity_id'] is None and first['plot_id']==cm.plot and first['farm_block_id']==b['farm_block_id']
    path=f"/my/farm-expenses/{first['expense_id']}"
    updated=cm.ok('PUT',path,edit_body(first,'expense',amount='50.10'))
    assert float(cm.ok('GET',path)['amount'])==50.10
    assert cm.call('PUT',path,edit_body(first,'expense')).status_code==409
    assert cm.call('GET',path,as_user=cm.other).status_code==404
    assert cm.call('PUT',path,edit_body(updated,'expense'),cm.other).status_code==404
    assert cm.ok('GET',f'/my/farm-expenses?farm_id={cm.farm}',as_user=cm.other)['total_amount']==0


@pytest.mark.parametrize('amount',['0','-1','NaN','Infinity','1.001','1000000000000'])
def test_positive_exact_amount(cm,amount):
    assert cm.call('POST','/my/farm-expenses',{**expense(cm),'amount':amount}).status_code==422


def test_expense_context_rejection(cm):
    _,foreign_plot=other_farm(cm)
    a=cm.ok('POST','/my/farm-activities',activity(cm,plot_id=cm.plot),code=201)
    assert cm.call('POST','/my/farm-expenses',expense(cm,plot_id=foreign_plot)).status_code==404
    assert cm.call('POST','/my/farm-expenses',expense(cm,activity_id=a['activity_id'],plot_id=foreign_plot)).status_code==422
    assert cm.call('POST','/my/farm-expenses',expense(cm),cm.other).status_code==404
    cycle=cm.cycle()
    assert cm.call('POST','/my/farm-expenses',expense(cm,activity_id=a['activity_id'],farm_crop_id=cycle['farm_crop_id'])).status_code==422
    assert cm.call('GET','/my/farm-expenses?date_from=2026-10-01&date_to=2026-01-01').status_code==422


def test_task_and_block_context_cannot_be_mixed(cm):
    cm.task();cm.publish();first=cm.cycle();second=cm.cycle();plan=cm.plan(first['farm_crop_id'])
    assert cm.call('POST','/my/farm-activities',activity(cm,farm_crop_id=second['farm_crop_id'],crop_task_id=plan['tasks'][0]['crop_task_id'],source_type='crop_task')).status_code==422
    b=block(cm)
    assert cm.call('POST','/my/farm-activities',activity(cm,farm_crop_id=first['farm_crop_id'],farm_block_id=b['farm_block_id'])).status_code==422


def test_booking_reference_only_same_owned_farm(cm):
    cm.sql("INSERT INTO supplier_profiles(supplier_id,business_name) VALUES(:id,'Test provider')",id=cm.provider['user_id'])
    def booking(farm,owner):
        return cm.sql("INSERT INTO bookings(booking_number,farmer_id,supplier_id,farm_id,requested_start_at) VALUES(:number,:actor,:supplier,:farm,'2026-09-01') RETURNING booking_id",number=uuid4().hex[:25],actor=owner,supplier=cm.provider['user_id'],farm=farm).scalar_one()
    own_booking=booking(cm.farm,cm.farmer['user_id'])
    saved=cm.ok('POST','/my/farm-activities',activity(cm,source_type='service_booking',service_booking_id=own_booking),code=201)
    assert saved['service_booking_id']==own_booking
    assert cm.sql('SELECT status FROM bookings WHERE booking_id=:id',id=own_booking).scalar_one()=='pending'
    farm,_=other_farm(cm);foreign=booking(farm,cm.other['user_id'])
    for bid in (foreign,booking(None,cm.farmer['user_id'])):
        assert cm.call('POST','/my/farm-activities',activity(cm,source_type='service_booking',service_booking_id=bid)).status_code==404
    assert cm.ok('GET','/my/farm-expenses')['count']==0


def test_expense_db_context_guard_and_no_implicit_activity_on_task_status(cm):
    cm.task();cm.publish();cycle=cm.cycle(status='active',planted_on='2026-01-01');plan=cm.plan(cycle['farm_crop_id'])
    cm.ok('POST',f"/my/crop-tasks/{plan['tasks'][0]['crop_task_id']}/status",{'expected_status':'pending','status':'completed'})
    assert cm.ok('GET','/my/farm-activities')['count']==0
    a=cm.ok('POST','/my/farm-activities',activity(cm,plot_id=cm.plot),code=201)
    e=cm.ok('POST','/my/farm-expenses',expense(cm,activity_id=a['activity_id']),code=201)
    with pytest.raises(IntegrityError),cm.connection.begin_nested():
        cm.sql('UPDATE farm_expenses SET plot_id=NULL WHERE expense_id=:id',id=e['expense_id'])


def test_officer_activity_scope_financial_restriction_and_visit(fw):
    cycle=fw.cycle_record['farm_crop_id'];path=f'/field-work/crop-cycles/{cycle}/activities'
    body=activity(fw,farm_crop_id=cycle)
    assert fw.call('POST',path,body,fw.other).status_code==404
    assert fw.call('GET',path,as_user=fw.other).status_code==404
    saved=fw.ok('POST',path,body,fw.provider,201)
    assert fw.ok('GET',path,as_user=fw.provider)[0]['activity_id']==saved['activity_id']
    fw.ok('PUT',f"{path}/{saved['activity_id']}",edit_body(saved,'activity',description='Fact corrected'),fw.provider)
    e=fw.ok('POST','/my/farm-expenses',expense(fw,activity_id=saved['activity_id']),code=201)
    for financial in ['/my/farm-expenses',f"/my/farm-expenses/{e['expense_id']}"]:
        assert fw.call('GET',financial,as_user=fw.provider).status_code==403
    assert fw.call('POST','/my/farm-expenses',expense(fw),fw.provider).status_code==403
    assert fw.call('PUT',f"/my/farm-expenses/{e['expense_id']}",edit_body(e,'expense'),fw.provider).status_code==403
    farmer_activity=fw.ok('POST','/my/farm-activities',activity(fw,farm_crop_id=cycle),code=201)
    assert fw.call('PUT',f"{path}/{farmer_activity['activity_id']}",edit_body(farmer_activity,'activity'),fw.provider).status_code==404
    visit_body=activity(fw,farm_crop_id=cycle,field_visit_id=fw.visit['visit_id'],source_type='field_visit')
    assert fw.call('POST',path,visit_body,fw.provider).status_code==409
    start(fw)
    fw.ok('POST',path,visit_body,fw.provider,201)
    assert fw.sql("SELECT count(*) FROM visit_tasks WHERE visit_id=:id AND verification_status<>'unverified'",id=fw.visit['visit_id']).scalar_one()==0
    fw.ok('PATCH',f"/admin/field-work/assignments/{fw.assignment['assignment_id']}",{'expected_status':'active','status':'cancelled'},fw.admin)
    assert fw.call('GET',path,as_user=fw.provider).status_code==404
    assert fw.call('POST',path,body,fw.provider).status_code==404
    assert fw.ok('GET',f"/my/farm-activities/{saved['activity_id']}")['description']=='Fact corrected'


@pytest.mark.parametrize('role',['provider','admin','other'])
def test_no_implicit_farmer_access(cm,role):
    actor=getattr(cm,role)
    expected=404 if role=='other' else 403
    assert cm.call('POST','/my/farm-activities',activity(cm),actor).status_code==expected
    assert cm.call('POST','/my/farm-expenses',expense(cm),actor).status_code==expected


def test_strict_harvest_dates_create_patch_plan_activation_legacy(cm):
    date='2026-09-02'
    assert cm.call('POST',f'/my/farms/{cm.farm}/crop-cycles',{'plot_id':cm.plot,'crop_id':cm.crop,'status':'active','planted_on':date,'expected_harvest_on':date}).status_code==422
    active=cm.cycle(status='active',planted_on=date,expected_harvest_on='2026-09-03')
    assert cm.call('PATCH',f"/my/crop-cycles/{active['farm_crop_id']}",{'expected_harvest_on':date}).status_code==422
    planned=cm.cycle(expected_harvest_on=date);cm.task();cm.publish()
    assert cm.call('POST',f"/my/crop-cycles/{planned['farm_crop_id']}/plan",{'sop_version_id':cm.version['sop_version_id'],'anchor_date':date}).status_code==422
    assert cm.call('POST',f"/my/crop-cycles/{planned['farm_crop_id']}/status",{'expected_status':'planned','status':'active','planted_on':date}).status_code==422
    cycle=cm.cycle();cm.plan(cycle['farm_crop_id'],date)
    assert cm.call('PATCH',f"/my/crop-cycles/{cycle['farm_crop_id']}",{'expected_harvest_on':date}).status_code==422
    cm.ok('PATCH',f"/my/crop-cycles/{cycle['farm_crop_id']}",{'expected_harvest_on':'2026-09-03'})
    legacy={'farm_id':cm.farm,'plot_id':cm.plot,'crop_id':cm.crop,'planted_on':date,'expected_harvest_on':date}
    assert cm.call('POST',f'/my/farms/{cm.farm}/crops',legacy).status_code==400
