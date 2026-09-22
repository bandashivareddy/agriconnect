"""Field operations: rollback fixtures reuse the Slice 1 identity and cycle setup."""
from datetime import date
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import pytest
from test_crop_management import cm

@pytest.fixture
def fw(cm):
    cm.sql("INSERT INTO user_capabilities(user_id,capability) VALUES(:id,'field_officer')",id=cm.provider['user_id'])
    cm.sql("INSERT INTO user_capabilities(user_id,capability) VALUES(:id,'field_officer')",id=cm.other['user_id'])
    cm.task();cm.task(2);cm.publish()
    cycle=cm.cycle(status='active',planted_on='2026-01-01');plan=cm.plan(cycle['farm_crop_id'])
    assignment=cm.ok('POST','/admin/field-work/assignments',{'field_officer_id':cm.provider['user_id'],'farm_crop_id':cycle['farm_crop_id'],'notes':'Initial assignment'},cm.admin,201)
    visit=cm.ok('POST','/admin/field-work/visits',{'assignment_id':assignment['assignment_id'],'planned_visit_date':'2026-09-09'},cm.admin,201)
    cm.cycle_record=cycle;cm.plan_record=plan;cm.assignment=assignment;cm.visit=visit
    return cm


def start(fw):
    return fw.ok('POST',f"/field-work/visits/{fw.visit['visit_id']}/status",{'expected_status':'planned','status':'in_progress'},fw.provider)


def observation():return {'observation_type':'crop_condition','severity':'medium','title':'Yellow leaves','detailed_notes':'Observed yellowing on several lower leaves. No treatment prescribed.'}


def test_capability_grant_preserves_identity(cm):
    assert cm.call('GET','/field-work',as_user=cm.provider).status_code==403
    result=cm.ok('POST','/admin/field-officers',{'user_id':cm.provider['user_id']},cm.admin)
    assert result['user_role']=='supplier'
    cm.ok('POST','/admin/field-officers',{'user_id':cm.provider['user_id']},cm.admin)
    user=cm.ok('GET','/auth/me',as_user=cm.provider)
    assert set(user['capabilities'])=={'provider','field_officer'}
    assert cm.ok('GET','/field-work',as_user=cm.provider)['assignments']==[]
    assert cm.call('POST','/admin/field-officers',{'user_id':cm.other['user_id']}).status_code==403


def test_assignment_history_and_reassignment(fw):
    body={'field_officer_id':fw.provider['user_id'],'farm_crop_id':fw.cycle_record['farm_crop_id']}
    assert fw.call('POST','/admin/field-work/assignments',body,fw.admin).status_code==409
    fw.ok('PATCH',f"/admin/field-work/assignments/{fw.assignment['assignment_id']}",{'expected_status':'active','status':'completed','notes':'New officer follows'},fw.admin)
    assert fw.call('GET',f"/field-work/visits/{fw.visit['visit_id']}",as_user=fw.provider).status_code==404
    assert fw.sql('SELECT status FROM field_visits WHERE visit_id=:id',id=fw.visit['visit_id']).scalar_one()=='cancelled'
    assert fw.call('POST','/admin/field-work/visits',{'assignment_id':fw.assignment['assignment_id'],'planned_visit_date':'2026-09-10'},fw.admin).status_code==409
    replacement=fw.ok('POST','/admin/field-work/assignments',body,fw.admin,201)
    assert replacement['assignment_id']!=fw.assignment['assignment_id']
    history=fw.ok('GET',f"/my/crop-cycles/{fw.cycle_record['farm_crop_id']}/field-work")
    assert {a['status'] for a in history['assignments']}=={'active','completed'}
    assert fw.call('GET',f"/field-work/visits/{fw.visit['visit_id']}",as_user=fw.provider).status_code==404


def test_visit_verification_and_observation_do_not_execute_tasks(fw):
    detail=start(fw);assert len(detail['tasks'])==2
    task=fw.plan_record['tasks'][0]
    verification=fw.ok('PUT',f"/field-work/visits/{fw.visit['visit_id']}/tasks/{task['crop_task_id']}",{'verification_status':'observed_partial','officer_note':'Only half inspected'},fw.provider)
    assert verification['verified_by']==fw.provider['user_id']
    assert fw.sql('SELECT status FROM crop_tasks WHERE crop_task_id=:id',id=task['crop_task_id']).scalar_one()=='pending'
    obs=fw.ok('POST',f"/field-work/visits/{fw.visit['visit_id']}/observations",observation(),fw.provider,201)
    changed=fw.ok('PUT',f"/field-work/visits/{fw.visit['visit_id']}/observations/{obs['observation_id']}",{**observation(),'title':'Updated observation','expected_updated_at':obs['updated_at']},fw.provider)
    assert changed['title']=='Updated observation'
    history=fw.ok('GET',f"/my/crop-cycles/{fw.cycle_record['farm_crop_id']}/field-work")
    assert history['observations'][0]['field_officer_id']==fw.provider['user_id']
    completed=fw.ok('POST',f"/field-work/visits/{fw.visit['visit_id']}/status",{'expected_status':'in_progress','status':'completed','visit_notes':'Inspection complete'},fw.provider)
    assert completed['completed_at'] and completed['started_at']
    assert fw.call('POST',f"/field-work/visits/{fw.visit['visit_id']}/observations",observation(),fw.provider).status_code==409
    assert fw.call('PUT',f"/field-work/visits/{fw.visit['visit_id']}/tasks/{task['crop_task_id']}",{'verification_status':'observed_completed'},fw.provider).status_code==409


def test_cross_officer_farmer_and_admin_boundaries(fw):
    vid=fw.visit['visit_id'];cid=fw.cycle_record['farm_crop_id']
    for path in [f'/field-work/visits/{vid}',f'/field-work/crop-cycles/{cid}']:
        assert fw.call('GET',path,as_user=fw.other).status_code==404
        assert fw.call('GET',path,as_user=fw.admin).status_code==403
    assert fw.call('GET',f'/my/crop-cycles/{cid}/field-work',as_user=fw.other).status_code==404
    assert fw.call('POST',f'/field-work/visits/{vid}/observations',observation()).status_code==403
    assert fw.call('POST',f'/field-work/visits/{vid}/observations',observation(),fw.other).status_code==404
    assert fw.call('POST',f'/field-work/visits/{vid}/status',{'expected_status':'planned','status':'in_progress'},fw.admin).status_code==403
    assert fw.ok('GET',f'/admin/field-work/visits/{vid}',as_user=fw.admin)['visit_id']==vid
    assert fw.ok('GET',f'/my/crop-cycles/{cid}/field-visits/{vid}')['visit_id']==vid


@pytest.mark.parametrize('changes',[{'observation_type':'prescription'},{'severity':'extreme'},{'title':' '},{'detailed_notes':''},{'pesticide_dose':'100 ml'},{'observed_at':'2999-01-01T00:00:00Z'},{'observed_at':'2026-01-01T00:00:00'}])
def test_observation_validation(fw,changes):
    start(fw)
    assert fw.call('POST',f"/field-work/visits/{fw.visit['visit_id']}/observations",{**observation(),**changes},fw.provider).status_code==422


@pytest.mark.parametrize('before,after,expected',[('planned','completed',409),('planned','cancelled',409),('planned','in_progress',200),('in_progress','completed',200),('in_progress','planned',409),('completed','in_progress',409)])
def test_visit_transitions(fw,before,after,expected):
    if before in ('in_progress','completed'):start(fw)
    if before=='completed':fw.ok('POST',f"/field-work/visits/{fw.visit['visit_id']}/status",{'expected_status':'in_progress','status':'completed'},fw.provider)
    assert fw.call('POST',f"/field-work/visits/{fw.visit['visit_id']}/status",{'expected_status':before,'status':after},fw.provider).status_code==expected


def test_task_link_validation_and_cross_cycle(fw):
    start(fw)
    cycle=fw.cycle(status='active',planted_on='2026-01-01');plan=fw.plan(cycle['farm_crop_id']);task=plan['tasks'][0]
    path=f"/field-work/visits/{fw.visit['visit_id']}/tasks/{task['crop_task_id']}"
    assert fw.call('PUT',path,{'verification_status':'observed_completed'},fw.provider).status_code==404
    with pytest.raises(IntegrityError),fw.connection.begin_nested():
        fw.sql('INSERT INTO visit_tasks(visit_id,crop_task_id) VALUES(:visit,:task)',visit=fw.visit['visit_id'],task=task['crop_task_id'])
    own=fw.plan_record['tasks'][0]['crop_task_id']
    assert fw.call('PUT',f"/field-work/visits/{fw.visit['visit_id']}/tasks/{own}",{'verification_status':'not_done'},fw.provider).status_code==422


def test_stale_updates_and_admin_cancel(fw):
    start(fw);task=fw.plan_record['tasks'][0]['crop_task_id'];vid=fw.visit['visit_id']
    fw.ok('PUT',f'/field-work/visits/{vid}/tasks/{task}',{'verification_status':'observed_completed'},fw.provider)
    assert fw.call('PUT',f'/field-work/visits/{vid}/tasks/{task}',{'verification_status':'not_done','officer_note':'Different'},fw.provider).status_code==409
    assert fw.call('POST',f'/field-work/visits/{vid}/status',{'expected_status':'planned','status':'completed'},fw.provider).status_code==409
    fw.sql('UPDATE field_visits SET visit_notes=:note WHERE visit_id=:id',note='Original field notes',id=vid)
    cancelled=fw.ok('POST',f'/admin/field-work/visits/{vid}/cancel',{'expected_status':'in_progress','status':'cancelled','visit_notes':'Rescheduled'},fw.admin)
    assert cancelled['visit_notes']=='Original field notes\nCancelled by admin: Rescheduled'
    assert fw.call('POST',f'/field-work/visits/{vid}/observations',observation(),fw.provider).status_code==409


def test_assignment_close_rolls_back_visits(fw,monkeypatch):
    original=fw.connection.execute
    def fail(statement,*args,**kwargs):
        if "UPDATE field_visits SET status='cancelled'" in str(statement):raise RuntimeError('Injected closure failure')
        return original(statement,*args,**kwargs)
    monkeypatch.setattr(fw.connection,'execute',fail)
    assert fw.call('PATCH',f"/admin/field-work/assignments/{fw.assignment['assignment_id']}",{'expected_status':'active','status':'cancelled'},fw.admin).status_code==500
    assert fw.sql('SELECT status FROM crop_officer_assignments WHERE assignment_id=:id',id=fw.assignment['assignment_id']).scalar_one()=='active'
