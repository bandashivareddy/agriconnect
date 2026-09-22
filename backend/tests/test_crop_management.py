from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import main as api
from crop_management import is_overdue

@pytest.fixture
def cm(monkeypatch, client):
    connection=api.engine.connect(); outer=connection.begin()
    @contextmanager
    def read():
        yield connection
    @contextmanager
    def write():
        with connection.begin_nested(): yield connection
    monkeypatch.setattr(api.engine,'connect',read); monkeypatch.setattr(api.engine,'begin',write)
    def sql(query,**params): return connection.execute(text(query),params)
    def user(role):
        return dict(sql("INSERT INTO users(full_name,email,password_hash,user_role) VALUES('Crop Test',:email,'unused',:role) RETURNING *",email=uuid4().hex+'@pytest.agriconnect.test',role=role).mappings().one())
    farmer=user('farmer');admin=user('admin');other=user('farmer');provider=user('supplier')
    crop=sql('INSERT INTO crops(crop_name) VALUES(:name) RETURNING crop_id',name='Test '+uuid4().hex).scalar_one()
    farm=sql("INSERT INTO farms(farmer_id,farm_name,location,total_area_acres) VALUES(:actor,'Farm','Village',1) RETURNING farm_id",actor=farmer['user_id']).scalar_one()
    plot=sql("INSERT INTO farm_plots(farm_id,plot_name,area_acres) VALUES(:farm,'Plot',5) RETURNING plot_id",farm=farm).scalar_one()
    def call(method,path,body=None,as_user=None):
        who=as_user or farmer
        return client.request(method,path,json=body,headers={'Authorization':'Bearer '+api.create_access_token(who['user_id'],who['user_role'])})
    def ok(method,path,body=None,as_user=None,code=200):
        r=call(method,path,body,as_user); assert r.status_code==code,r.text
        return r.json() if code!=204 else None
    template=ok('POST','/admin/sop-templates',{'crop_id':crop,'name':'Test SOP'},admin,201)
    version=ok('POST',f"/admin/sop-templates/{template['sop_template_id']}/versions",{},admin,201)
    def task(n=1,**overrides):
        return ok('POST',f"/admin/sop-versions/{version['sop_version_id']}/tasks",{'sequence_no':n,'title':f'Task {n}','instructions':'Check carefully','task_type':'inspection','schedule_type':'days_after_planting','offset_days':n-1,**overrides},admin,201)
    def cycle(**overrides): return ok('POST',f'/my/farms/{farm}/crop-cycles',{'plot_id':plot,'crop_id':crop,**overrides},code=201)
    def publish(): return ok('POST',f"/admin/sop-versions/{version['sop_version_id']}/publish",as_user=admin)
    def plan(cycle_id,anchor='2026-01-01',code=201): return ok('POST',f'/my/crop-cycles/{cycle_id}/plan',{'sop_version_id':version['sop_version_id'],'anchor_date':anchor},code=code)
    yield SimpleNamespace(**locals())
    outer.rollback();connection.close()


def test_generation_snapshot_retry_and_planned(cm):
    cm.task(offset_days=0);cm.task(2,offset_days=2);cm.publish();cycle=cm.cycle();plan=cm.plan(cycle['farm_crop_id'],'2028-02-28')
    assert [t['due_date'] for t in plan['tasks']]==['2028-02-28','2028-03-01']
    assert cm.plan(cycle['farm_crop_id'],'2028-02-28',200)['plan_id']==plan['plan_id']
    assert cm.call('POST',f"/my/crop-cycles/{cycle['farm_crop_id']}/plan",{'sop_version_id':cm.version['sop_version_id'],'anchor_date':'2028-03-01'}).status_code==409
    saved=cm.ok('GET',f"/my/crop-cycles/{cycle['farm_crop_id']}")
    assert saved['status']=='planned' and saved['planted_on'] is None and saved['summary']['total_tasks']==2
    cm.ok('PATCH',f"/admin/sop-templates/{cm.template['sop_template_id']}",{'name':'Renamed'},cm.admin)
    cm.ok('POST',f"/admin/sop-versions/{cm.version['sop_version_id']}/retire",as_user=cm.admin)
    assert cm.plan(cycle['farm_crop_id'],'2028-02-28',200)['sop_template_name_snapshot']=='Test SOP'


def test_harvest_closes_unfinished_preserving_history(cm):
    for i in range(1,7): cm.task(i)
    cm.publish();cycle=cm.cycle(status='active',planted_on='2026-01-01');plan=cm.plan(cycle['farm_crop_id'])
    for task,status in zip(plan['tasks'],['completed','not_applicable','cancelled','pending','in_progress','partial']):
        if status!='pending': cm.ok('POST',f"/my/crop-tasks/{task['crop_task_id']}/status",{'expected_status':'pending','status':status,'status_note':'Original note'})
    result=cm.ok('POST',f"/my/crop-cycles/{cycle['farm_crop_id']}/status",{'expected_status':'active','status':'harvested'});tasks=result['plan']['tasks']
    assert [t['status'] for t in tasks]==['completed','not_applicable','cancelled','cancelled','cancelled','cancelled']
    assert tasks[0]['completed_by']==cm.farmer['user_id'] and tasks[0]['completed_at']
    assert tasks[1]['status_note']==tasks[2]['status_note']=='Original note'
    assert 'harvested before' in tasks[3]['status_note'] and 'Original note' in tasks[5]['status_note']
    assert all(not t['is_overdue'] for t in tasks)
    assert cm.ok('POST',f"/my/crop-cycles/{cycle['farm_crop_id']}/status",{'expected_status':'active','status':'harvested'})['status']=='harvested'


def test_anchor_activation(cm):
    cm.task();cm.publish();active=cm.cycle(status='active',planted_on='2026-01-02')
    assert cm.call('POST',f"/my/crop-cycles/{active['farm_crop_id']}/plan",{'sop_version_id':cm.version['sop_version_id'],'anchor_date':'2026-01-01'}).status_code==422
    cycle=cm.cycle();plan=cm.plan(cycle['farm_crop_id'])
    assert cm.call('POST',f"/my/crop-tasks/{plan['tasks'][0]['crop_task_id']}/status",{'expected_status':'pending','status':'completed'}).status_code==409
    activated=cm.ok('POST',f"/my/crop-cycles/{cycle['farm_crop_id']}/status",{'expected_status':'planned','status':'active','planted_on':'2026-01-03'})
    assert activated['plan']['planting_date_mismatch'] and activated['plan']['tasks'][0]['due_date']=='2026-01-01'

@pytest.mark.parametrize('kind,extras',[('manual',{}),('condition',{'condition_text':'When dry'}),('crop_stage',{'crop_stage_key':'flowering'}),('days_before_harvest',{'offset_days':5})])
def test_reserved_schedules_draft_only(cm,kind,extras):
    cm.task(**{'schedule_type':kind,'offset_days':None,**extras})
    assert cm.call('POST',f"/admin/sop-versions/{cm.version['sop_version_id']}/publish",as_user=cm.admin).status_code==422

@pytest.mark.parametrize('overrides',[{'offset_days':None},{'offset_days':-1},{'crop_stage_key':'flowering'},{'task_type':'unknown'},{'title':'  '}])
def test_bad_definitions(cm,overrides):
    body={'sequence_no':1,'title':'Task','instructions':'Check','task_type':'general','schedule_type':'days_after_planting','offset_days':0,**overrides}
    assert cm.call('POST',f"/admin/sop-versions/{cm.version['sop_version_id']}/tasks",body,cm.admin).status_code==422


def test_publication_clone_and_sql_immutability(cm):
    assert cm.call('POST',f"/admin/sop-versions/{cm.version['sop_version_id']}/publish",as_user=cm.admin).status_code==422
    task=cm.task();cm.publish()
    for query in ["UPDATE sop_tasks SET title='Changed' WHERE sop_task_id=:id",'DELETE FROM sop_tasks WHERE sop_task_id=:id']:
        with pytest.raises(IntegrityError),cm.connection.begin_nested(): cm.sql(query,id=task['sop_task_id'])
    with pytest.raises(IntegrityError),cm.connection.begin_nested(): cm.sql("UPDATE sop_versions SET version_notes='changed' WHERE sop_version_id=:id",id=cm.version['sop_version_id'])
    assert cm.call('DELETE',f"/admin/sop-tasks/{task['sop_task_id']}",as_user=cm.admin).status_code==409
    clone=cm.ok('POST',f"/admin/sop-templates/{cm.template['sop_template_id']}/versions",{'clone_from_version_id':cm.version['sop_version_id']},cm.admin,201)
    detail=cm.ok('GET',f"/admin/sop-versions/{clone['sop_version_id']}",as_user=cm.admin)
    assert clone['version_number']==2 and detail['tasks'][0]['sop_task_id']!=task['sop_task_id']
    assert cm.call('GET',f"/sop-versions/{clone['sop_version_id']}").status_code==404


def test_auth_ownership(cm,client):
    cycle=cm.cycle();cm.task();cm.publish();plan=cm.plan(cycle['farm_crop_id'])
    assert client.get('/my/crop-cycles').status_code==401
    assert cm.call('GET','/my/crop-cycles',as_user=cm.provider).status_code==403
    for path in [f"/my/crop-cycles/{cycle['farm_crop_id']}",f"/my/crop-cycles/{cycle['farm_crop_id']}/plan",f"/my/crop-tasks/{plan['tasks'][0]['crop_task_id']}"]:
        assert cm.call('GET',path,as_user=cm.other).status_code==404
    assert cm.call('GET','/admin/sop-templates').status_code==403
    cm.sql("INSERT INTO user_capabilities(user_id,capability) VALUES(:id,'admin')",id=cm.other['user_id'])
    assert cm.call('GET','/admin/sop-templates',as_user=cm.other).status_code==200


def test_legacy_audits_and_area(cm):
    legacy=cm.sql('INSERT INTO farm_crops(farm_id,crop_id) VALUES(:farm,:crop) RETURNING *',farm=cm.farm,crop=cm.crop).mappings().one()
    assert all(legacy[k] is None for k in ('created_at','updated_at','created_by','updated_by'))
    assert cm.ok('GET',f'/my/farms/{cm.farm}')['crops']
    assert cm.ok('POST',f'/my/farms/{cm.farm}/plots',{'farm_id':cm.farm,'plot_name':'Large Plot','area_acres':100},code=201)['area_acres']==100
    assert cm.cycle()['created_by']==cm.farmer['user_id']

@pytest.mark.parametrize('operation',['generation','harvest'])
def test_atomic_rollback(cm,monkeypatch,operation):
    cm.task();cm.task(2);cm.publish();cycle=cm.cycle(status='active',planted_on='2026-01-01')
    if operation=='harvest':cm.plan(cycle['farm_crop_id'])
    original=cm.connection.execute; count=0
    def fail(statement,*args,**kwargs):
        nonlocal count
        if 'INSERT INTO crop_tasks' in str(statement):
            count+=1
            if count==2: raise RuntimeError('Injected failure')
        if operation=='harvest' and "UPDATE crop_tasks SET status='cancelled'" in str(statement): raise RuntimeError('Injected closure failure')
        return original(statement,*args,**kwargs)
    monkeypatch.setattr(cm.connection,'execute',fail)
    path=f"/my/crop-cycles/{cycle['farm_crop_id']}/"+('plan' if operation=='generation' else 'status')
    body={'sop_version_id':cm.version['sop_version_id'],'anchor_date':'2026-01-01'} if operation=='generation' else {'expected_status':'active','status':'harvested'}
    assert cm.call('POST',path,body).status_code==500
    assert cm.sql('SELECT status FROM farm_crops WHERE farm_crop_id=:id',id=cycle['farm_crop_id']).scalar_one()=='active'
    if operation=='generation': assert cm.sql('SELECT count(*) FROM crop_cycle_plans WHERE farm_crop_id=:id',id=cycle['farm_crop_id']).scalar_one()==0

@pytest.mark.parametrize('status,expected',[('pending',True),('in_progress',True),('partial',True),('completed',False),('not_applicable',False),('cancelled',False)])
def test_overdue(status,expected):
    task={'status':status,'due_date':date(2026,1,1)}
    assert is_overdue(task,'active',date(2026,1,2))==expected
    assert not is_overdue(task,'planned',date(2026,1,2))
    assert not is_overdue(task,'active',date(2026,1,1))

@pytest.mark.parametrize('before', ['pending','in_progress','partial','completed','not_applicable','cancelled'])
@pytest.mark.parametrize('after', ['pending','in_progress','completed','partial','not_applicable','cancelled'])
def test_all_task_transitions(cm,before,after):
    from crop_management import TASK_TRANSITIONS
    cm.task();cm.publish();cycle=cm.cycle(status='active',planted_on='2026-01-01');task=cm.plan(cycle['farm_crop_id'])['tasks'][0]
    cm.sql('''UPDATE crop_tasks SET status=CAST(:status AS varchar),status_note='Saved note',
        completed_at=CASE WHEN CAST(:status AS varchar)='completed' THEN CURRENT_TIMESTAMP ELSE NULL END,
        completed_by=CASE WHEN CAST(:status AS varchar)='completed' THEN :actor ELSE NULL END WHERE crop_task_id=:id''',status=before,actor=cm.farmer['user_id'],id=task['crop_task_id'])
    r=cm.call('POST',f"/my/crop-tasks/{task['crop_task_id']}/status",{'expected_status':before,'status':after,'status_note':'Saved note'})
    assert r.status_code==(200 if before==after or after in TASK_TRANSITIONS.get(before,set()) else 409),r.text


def test_notes_stale_requests_and_cancellation(cm):
    cm.task();cm.publish();cycle=cm.cycle(status='active',planted_on='2026-01-01');task=cm.plan(cycle['farm_crop_id'])['tasks'][0]
    path=f"/my/crop-tasks/{task['crop_task_id']}/status"
    for status in ('partial','not_applicable','cancelled'):
        assert cm.call('POST',path,{'expected_status':'pending','status':status}).status_code==422
    cm.ok('POST',path,{'expected_status':'pending','status':'in_progress'})
    assert cm.call('POST',path,{'expected_status':'pending','status':'completed'}).status_code==409
    result=cm.ok('POST',f"/my/crop-cycles/{cycle['farm_crop_id']}/status",{'expected_status':'active','status':'cancelled','note':'Field unavailable'})
    assert result['plan']['tasks'][0]['status']=='cancelled' and 'Field unavailable' in result['plan']['tasks'][0]['status_note']


def test_draft_patch_delete_and_discovery(cm):
    task=cm.task();path=f"/admin/sop-tasks/{task['sop_task_id']}"
    changed=cm.ok('PATCH',path,{'title':'New title'},cm.admin)
    assert changed['title']=='New title' and changed['instructions']==task['instructions']
    assert cm.call('PATCH',path,{'schedule_type':'manual'},cm.admin).status_code==422
    cm.ok('PATCH',f"/admin/sop-versions/{cm.version['sop_version_id']}",{'version_notes':'Edited notes'},cm.admin)
    assert not any(t['sop_template_id']==cm.template['sop_template_id'] for t in cm.ok('GET',f'/sop-templates?crop_id={cm.crop}'))
    cm.ok('DELETE',path,as_user=cm.admin,code=204)
    assert cm.ok('GET',f"/admin/sop-versions/{cm.version['sop_version_id']}",as_user=cm.admin)['tasks']==[]
    cm.task();cm.publish();assert cm.ok('GET',f'/sop-templates?crop_id={cm.crop}')[0]['sop_template_id']==cm.template['sop_template_id']


def test_generation_eligibility_and_cycle_edits(cm):
    cm.task();cycle=cm.cycle();path=f"/my/crop-cycles/{cycle['farm_crop_id']}/plan";body={'sop_version_id':cm.version['sop_version_id'],'anchor_date':'2026-01-01'}
    assert cm.call('POST',path,body).status_code==409
    cm.publish();cm.ok('PATCH',f"/admin/sop-templates/{cm.template['sop_template_id']}",{'is_active':False},cm.admin)
    assert cm.call('POST',path,body).status_code==409
    cm.ok('PATCH',f"/admin/sop-templates/{cm.template['sop_template_id']}",{'is_active':True},cm.admin)
    other_crop=cm.sql('INSERT INTO crops(crop_name) VALUES(:name) RETURNING crop_id',name=uuid4().hex).scalar_one()
    wrong=cm.cycle(crop_id=other_crop)
    assert cm.call('POST',f"/my/crop-cycles/{wrong['farm_crop_id']}/plan",body).status_code==422
    cm.plan(cycle['farm_crop_id']);assert cm.call('PATCH',f"/my/crop-cycles/{cycle['farm_crop_id']}",{'crop_id':other_crop}).status_code==409
    assert cm.ok('PATCH',f"/my/crop-cycles/{cycle['farm_crop_id']}",{'season':'Rabi'})['season']=='Rabi'
    assert cm.call('POST',path,{'sop_version_id':cm.version['sop_version_id']}).status_code==422


def test_cross_owner_writes_filters(cm):
    cm.task();cm.publish();cycle=cm.cycle();plan=cm.plan(cycle['farm_crop_id'])
    for method,path,body in [('POST',f"/my/crop-cycles/{cycle['farm_crop_id']}/plan",{'sop_version_id':cm.version['sop_version_id'],'anchor_date':'2026-01-01'}),('PATCH',f"/my/crop-cycles/{cycle['farm_crop_id']}",{'season':'Other'}),('POST',f"/my/crop-tasks/{plan['tasks'][0]['crop_task_id']}/status",{'expected_status':'pending','status':'completed'})]:
        assert cm.call(method,path,body,cm.other).status_code==404
    assert cm.ok('GET',f'/my/crop-cycles?farm_id={cm.farm}&status=planned')[0]['farm_crop_id']==cycle['farm_crop_id']
    assert cm.ok('GET',f"/my/crop-tasks?cycle_id={cycle['farm_crop_id']}&due_from=2026-01-01&due_to=2026-01-01")[0]['crop_task_id']==plan['tasks'][0]['crop_task_id']
    assert cm.ok('GET','/my/crop-tasks',as_user=cm.other)==[]


def test_business_timezone_midnight(monkeypatch):
    import crop_management as module
    from datetime import datetime,timezone
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return cls(2026,1,1,18,30,tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(module,'datetime',Clock)
    assert module.business_today()==date(2026,1,2)
