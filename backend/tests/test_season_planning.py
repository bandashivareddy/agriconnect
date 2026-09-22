from datetime import date
from uuid import uuid4
import pytest
from sqlalchemy.exc import IntegrityError
from test_crop_management import cm
from test_task_services import marketplace, provider_complete, work
from test_farm_ledger import activity, expense
from season_planning import season_label, next_season_start


def season(cm, **kwargs):
    return cm.cycle(period_started_on='2026-06-01', expected_planting_on='2026-06-20', expected_harvest_on='2026-10-01', **kwargs)


def generate(cm, cycle, **kwargs):
    return cm.ok('POST', f"/my/crop-cycles/{cycle['farm_crop_id']}/plan", {'sop_version_id': cm.version['sop_version_id'], **kwargs}, code=201)


def test_season_persistence_and_auto_label(cm):
    c = season(cm)
    assert c['season'] == '2026' and c['status'] == 'planned' and c['planted_on'] is None
    saved = cm.ok('GET', f"/my/crop-cycles/{c['farm_crop_id']}")
    assert saved['period_started_on'] == '2026-06-01' and saved['expected_planting_on'] == '2026-06-20'
    assert saved['plan'] is None


def test_season_override_and_correction(cm):
    c = season(cm, season='Local season')
    assert c['season'] == 'Local season'
    c = cm.ok('PATCH', f"/my/crop-cycles/{c['farm_crop_id']}", {'period_started_on':'2026-05-01', 'season':'Corrected'})
    assert c['season'] == 'Corrected'
    c = cm.ok('PATCH', f"/my/crop-cycles/{c['farm_crop_id']}", {'period_started_on':'2026-05-01','expected_harvest_on':'2026-11-01'})
    assert c['season'] == 'Corrected'


@pytest.mark.parametrize('kind,extra,due', [
    ('days_after_season_start', {'offset_days':3}, '2026-06-04'),
    ('days_before_planting', {'offset_days':10}, '2026-06-10'),
    ('days_after_planting', {'offset_days':2}, '2026-06-22'),
    ('days_before_harvest', {'offset_days':4}, '2026-09-27'),
    ('crop_stage', {'crop_stage_key':'Flower induction'}, None),
    ('condition', {'condition_text':'Farmer observes dry soil'}, None),
    ('manual', {}, None),
])
def test_all_scheduling_semantics(cm, kind, extra, due):
    cm.task(**{'phase':'pre_season', 'schedule_type':kind, 'offset_days':None, **extra})
    cm.publish()
    c = season(cm)
    p = generate(cm, c)
    t = p['tasks'][0]
    assert t['due_date'] == due and t['phase'] == 'pre_season'
    assert t['schedule_type'] == kind
    assert p['anchor_date'] == '2026-06-20' and p['season_start_snapshot'] == '2026-06-01'
    assert p['expected_harvest_snapshot'] == '2026-10-01'
    assert t['crop_stage_key'] == extra.get('crop_stage_key') and t['condition_text'] == extra.get('condition_text')
    assert cm.ok('GET', f"/my/crop-cycles/{c['farm_crop_id']}")['status'] == 'planned'
    # Stage/condition/manual and preparation work are actionable without fictitious planting.
    done = cm.ok('POST', f"/my/crop-tasks/{t['crop_task_id']}/status", {'expected_status':'pending','status':'completed'})
    assert done['status'] == 'completed'


def test_season_only_plan_needs_no_planting(cm):
    cm.task(phase='pre_season', schedule_type='days_after_season_start', offset_days=0); cm.publish()
    c = cm.cycle(period_started_on='2026-06-01')
    p = generate(cm, c)
    assert p['anchor_date'] is None and p['tasks'][0]['due_date'] == '2026-06-01'


@pytest.mark.parametrize('kind,fields', [
    ('days_after_season_start', {}),
    ('days_before_planting', {'period_started_on':'2026-06-01'}),
    ('days_after_planting', {'period_started_on':'2026-06-01'}),
    ('days_before_harvest', {'period_started_on':'2026-06-01'}),
])
def test_missing_required_anchors_are_rejected(cm, kind, fields):
    cm.task(phase='pre_season', schedule_type=kind); cm.publish(); c = cm.cycle(**fields)
    assert cm.call('POST', f"/my/crop-cycles/{c['farm_crop_id']}/plan", {'sop_version_id':cm.version['sop_version_id']}).status_code == 422
    assert cm.ok('GET', f"/my/crop-cycles/{c['farm_crop_id']}")['plan'] is None


@pytest.mark.parametrize('changes', [
    {'expected_planting_on':'2026-05-30'},
    {'expected_harvest_on':'2026-06-01'},
    {'expected_harvest_on':'2026-06-15'},
])
def test_invalid_season_dates(cm, changes):
    body = {'plot_id':cm.plot,'crop_id':cm.crop,'period_started_on':'2026-06-01','expected_planting_on':'2026-06-20','expected_harvest_on':'2026-10-01',**changes}
    assert cm.call('POST', f'/my/farms/{cm.farm}/crop-cycles', body).status_code == 422


def test_task_before_season_rejected_atomically(cm):
    cm.task(phase='pre_season',schedule_type='days_before_planting',offset_days=30); cm.publish(); c=season(cm)
    assert cm.call('POST',f"/my/crop-cycles/{c['farm_crop_id']}/plan",{'sop_version_id':cm.version['sop_version_id']}).status_code==422
    assert cm.sql('SELECT count(*) FROM crop_cycle_plans WHERE farm_crop_id=:id',id=c['farm_crop_id']).scalar_one()==0


def test_snapshot_clone_and_date_corrections(cm):
    source = cm.task(phase='crop_stage',schedule_type='crop_stage',offset_days=None,crop_stage_key='Flowering'); cm.publish()
    c=season(cm); p=generate(cm,c); t=p['tasks'][0]
    assert cm.call('PATCH',f"/admin/sop-tasks/{source['sop_task_id']}",{'phase':'harvest'},cm.admin).status_code==409
    for table, key, id, change in [('sop_tasks','sop_task_id',source['sop_task_id'],"phase='harvest'"),('crop_tasks','crop_task_id',t['crop_task_id'],"crop_stage_key='Changed'"),('crop_cycle_plans','plan_id',p['plan_id'],"season_start_snapshot='2026-07-01'")]:
        with pytest.raises(IntegrityError), cm.connection.begin_nested():
            cm.sql(f'UPDATE {table} SET {change} WHERE {key}=:id',id=id)
    clone=cm.ok('POST',f"/admin/sop-templates/{cm.template['sop_template_id']}/versions",{'clone_from_version_id':cm.version['sop_version_id']},cm.admin,201)
    cloned=cm.ok('GET',f"/admin/sop-versions/{clone['sop_version_id']}",as_user=cm.admin)['tasks'][0]
    assert cloned['phase']=='crop_stage' and cloned['crop_stage_key']=='Flowering'
    cm.ok('PATCH',f"/admin/sop-tasks/{cloned['sop_task_id']}",{'crop_stage_key':'Fruit set'},cm.admin)
    cm.ok('PATCH',f"/my/crop-cycles/{c['farm_crop_id']}",{'period_started_on':'2026-05-01','expected_harvest_on':'2026-11-01'})
    saved=cm.ok('GET',f"/my/crop-cycles/{c['farm_crop_id']}")['plan']
    assert saved['season_date_mismatch'] and saved['tasks'][0]['crop_stage_key']=='Flowering'
    assert saved['season_start_snapshot']=='2026-06-01'


def test_actual_planting_used_and_conflicting_anchor_rejected(cm):
    cm.task(phase='planting'); cm.publish()
    c=season(cm,status='active',planted_on='2026-06-21')
    path=f"/my/crop-cycles/{c['farm_crop_id']}/plan"
    assert cm.call('POST',path,{'sop_version_id':cm.version['sop_version_id'],'anchor_date':'2026-06-20'}).status_code==422
    assert generate(cm,c)['tasks'][0]['due_date']=='2026-06-21'


def test_plan_retry_and_closed_season(cm):
    cm.task(phase='pre_season',schedule_type='days_after_season_start'); cm.publish()
    c=season(cm,status='active',planted_on='2026-06-20'); p=generate(cm,c)
    path=f"/my/crop-cycles/{c['farm_crop_id']}"
    cm.ok('POST',path+'/complete',{})
    assert cm.ok('POST',path+'/plan',{'sop_version_id':cm.version['sop_version_id']})['plan_id']==p['plan_id']
    assert cm.call('POST',f"/my/crop-tasks/{p['tasks'][0]['crop_task_id']}/status",{'expected_status':'cancelled','status':'in_progress'}).status_code==409
    assert cm.call('PATCH',path,{'period_started_on':'2026-01-01'}).status_code==409


def test_track_myself_season(cm):
    c=season(cm)
    a=cm.ok('POST','/my/farm-activities',activity(cm,farm_crop_id=c['farm_crop_id']),code=201)
    cm.ok('POST','/my/farm-expenses',expense(cm,farm_crop_id=c['farm_crop_id'],activity_id=a['activity_id']),code=201)
    assert cm.ok('GET',f"/my/crop-cycles/{c['farm_crop_id']}")['plan'] is None


def test_perennial_season_auto_proposal_and_independent_snapshots(cm):
    cm.sql("UPDATE crops SET lifecycle_type='perennial',crop_group='orchard' WHERE crop_id=:id",id=cm.crop)
    assert next(c for c in cm.ok('GET','/crops') if c['crop_id']==cm.crop)['lifecycle_type']=='perennial'
    cm.task(phase='pre_season',schedule_type='days_after_season_start',offset_days=2); cm.publish()
    c=cm.cycle(status='active',planted_on='2011-05-10',period_started_on='2026-09-01')
    assert c['season']=='2026-27'
    base=f"/my/crop-cycles/{c['farm_crop_id']}"
    planting=cm.ok('POST',base+'/enable-seasons',{'period_started_on':'2026-09-01'},code=201)
    p=generate(cm,c); assert p['tasks'][0]['due_date']=='2026-09-03'
    cm.ok('POST',base+'/complete',{})
    path=f"/my/perennial-plantings/{planting['perennial_planting_id']}"
    proposal=cm.ok('GET',path)['next_season']
    assert proposal=={'period_started_on':'2027-09-01','season':'2027-28'}
    body={'period_started_on':proposal['period_started_on'],'request_key':str(uuid4())}
    n=cm.ok('POST',path+'/seasons',body,code=201)
    assert cm.ok('POST',path+'/seasons',body)['farm_crop_id']==n['farm_crop_id']
    assert n['season']=='2027-28' and n['planted_on']=='2011-05-10'
    np=generate(cm,n)
    assert np['tasks'][0]['due_date']=='2027-09-03' and np['plan_id']!=p['plan_id']
    assert cm.ok('GET',base)['plan']['tasks'][0]['status']=='cancelled'


def test_season_service_booking_confirm_retry_no_automatic_completion(cm):
    category,service,_=marketplace(cm)
    cm.task(phase='pre_season',schedule_type='days_after_season_start',service_category_id=category); cm.publish()
    c=cm.cycle(period_started_on='2026-01-01',expected_planting_on='2026-01-20'); t=generate(cm,c)['tasks'][0]
    body={'supplier_service_id':service,'requested_start_at':'2026-01-02T08:00:00','requested_end_at':'2026-01-02T09:00:00','quantity':1,'crop_task_id':t['crop_task_id'],'crop_request_key':str(uuid4())}
    b=cm.ok('POST','/my/bookings',body,code=201)
    assert cm.ok('POST','/my/bookings',body)['booking_id']==b['booking_id']
    provider_complete(cm,b)
    assert cm.ok('GET',f"/my/crop-tasks/{t['crop_task_id']}")['status']=='pending'
    assert cm.sql('SELECT count(*) FROM farm_activities WHERE farm_crop_id=:id',id=c['farm_crop_id']).scalar_one()==0
    payload=work(cm,c,t,b)
    a=cm.ok('POST','/my/farm-activities',payload,code=201)
    assert cm.ok('POST','/my/farm-activities',payload)['activity_id']==a['activity_id']
    assert cm.call('POST','/my/farm-activities',{**payload,'request_key':str(uuid4())}).status_code==409
    assert cm.sql('SELECT count(*) FROM farm_expenses WHERE farm_crop_id=:id',id=c['farm_crop_id']).scalar_one()==0
    assert cm.ok('GET',f"/my/crop-tasks/{t['crop_task_id']}")['status']=='pending'
    cm.ok('POST',f"/my/crop-tasks/{t['crop_task_id']}/status",{'expected_status':'pending','status':'completed'})


@pytest.mark.parametrize('start,expected',[('2024-02-29','2025-02-28'),('2026-09-01','2027-09-01')])
def test_next_start_calendar_only(start,expected):
    assert next_season_start(date.fromisoformat(start))==date.fromisoformat(expected)
    assert season_label(date.fromisoformat(start))==start[:4]


def test_new_schedule_authorization_and_bad_phase(cm):
    assert cm.call('POST',f"/admin/sop-versions/{cm.version['sop_version_id']}/tasks",{}).status_code==403
    c=season(cm)
    assert cm.call('PATCH',f"/my/crop-cycles/{c['farm_crop_id']}",{'period_started_on':'2026-01-01'},cm.other).status_code==404
    assert cm.call('POST',f"/admin/sop-versions/{cm.version['sop_version_id']}/tasks",{'phase':'post_harvest'},cm.admin).status_code==422


def test_planned_overdue_and_conflicting_expected_planting(cm):
    cm.task(phase='pre_season',schedule_type='days_before_planting',offset_days=10); cm.publish()
    c=season(cm); path=f"/my/crop-cycles/{c['farm_crop_id']}/plan"
    assert cm.call('POST',path,{'sop_version_id':cm.version['sop_version_id'],'anchor_date':'2026-06-22'}).status_code==422
    p=generate(cm,c)
    from crop_management import is_overdue
    t={**p['tasks'][0], 'due_date':date(2026,6,10)}
    assert is_overdue(t,'planned',date(2026,6,11))
    assert not is_overdue({**t,'due_date':None},'planned',date(2026,6,11))
    assert not is_overdue(t,'harvested',date(2026,6,11))


def test_perennial_next_season_booking_isolation_and_closed_work(cm):
    category,service,_=marketplace(cm)
    cm.sql("UPDATE crops SET lifecycle_type='perennial' WHERE crop_id=:id",id=cm.crop)
    cm.task(phase='pre_season',schedule_type='days_after_season_start',service_category_id=category); cm.publish()
    c=cm.cycle(status='active',planted_on='2011-05-10',period_started_on='2026-01-01')
    base=f"/my/crop-cycles/{c['farm_crop_id']}"
    planting=cm.ok('POST',base+'/enable-seasons',{'period_started_on':'2026-01-01'},code=201)
    t=generate(cm,c)['tasks'][0]
    body={'supplier_service_id':service,'requested_start_at':'2026-01-02T08:00:00','requested_end_at':'2026-01-02T09:00:00','quantity':1,'crop_task_id':t['crop_task_id'],'crop_request_key':str(uuid4())}
    b=cm.ok('POST','/my/bookings',body,code=201); provider_complete(cm,b)
    cm.ok('POST',base+'/complete',{})
    assert cm.call('POST','/my/bookings',{**body,'crop_request_key':str(uuid4())}).status_code==409
    assert cm.call('POST','/my/farm-activities',work(cm,c,t,b)).status_code==409
    assert cm.ok('POST','/my/bookings',body)['booking_id']==b['booking_id']
    n=cm.ok('POST',f"/my/perennial-plantings/{planting['perennial_planting_id']}/seasons",{'period_started_on':'2027-01-01','request_key':str(uuid4())},code=201)
    nt=generate(cm,n)['tasks'][0]
    cm.sql("INSERT INTO availability_slots(supplier_service_id,starts_at,ends_at,capacity) VALUES(:id,'2027-01-02 08:00','2027-01-02 09:00',1)",id=service)
    nb=cm.ok('POST','/my/bookings',{**body,'crop_task_id':nt['crop_task_id'],'crop_request_key':str(uuid4()),'requested_start_at':'2027-01-02T08:00:00','requested_end_at':'2027-01-02T09:00:00'},code=201)
    assert nb['crop_context_snapshot']['farm_crop_id']==n['farm_crop_id']
    assert nb['crop_context_snapshot']['season']=='2027-28'
    assert [x['booking_id'] for x in cm.ok('GET',f"/my/crop-tasks/{t['crop_task_id']}/bookings")]==[b['booking_id']]
    assert [x['booking_id'] for x in cm.ok('GET',f"/my/crop-tasks/{nt['crop_task_id']}/bookings")]==[nb['booking_id']]
