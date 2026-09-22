from uuid import uuid4
import pytest
from sqlalchemy.exc import IntegrityError
import main as api
from test_crop_management import cm


def signup(cm, intent='field_officer', **extra):
    body={'full_name':'Applicant Test','phone':'9'+str(uuid4().int)[:9],'password':'TestPass123!','signup_intent':intent,**extra}
    user=cm.ok('POST','/auth/register',body,code=201)['user']
    return user,body


def application(cm,user=None,**fields):
    return cm.ok('POST','/my/field-officer-application',fields,as_user=user,code=201)


def review(cm,app,status='approved',as_user=None,reason=None):
    return cm.call('POST',f"/admin/field-officer-applications/{app['application_id']}/review",{'status':status,'rejection_reason':reason},as_user=as_user or cm.admin)


def test_signup_options_stable_codes(cm):
    options=cm.client.get('/auth/signup-options').json()
    assert [o['code'] for o in options]==['farmer','provider','field_officer','landowner']
    assert options[1]['label']=='Service Provider' and options[2]['notice']=='Application required'


@pytest.mark.parametrize('intent,role,caps',[('farmer','farmer',['farmer']),('provider','supplier',['provider']),('field_officer','member',[]),('landowner','member',[])])
def test_shared_signup_and_mobile_login(cm,intent,role,caps):
    u,body=signup(cm,intent)
    assert u['user_role']==role and u['email'] is None
    login=cm.ok('POST','/auth/login',{'phone':body['phone'],'password':body['password']})
    assert login['user']['user_id']==u['user_id'] and login['user']['capabilities']==caps
    assert login['user']['signup_intent']==intent
    me=cm.ok('GET','/auth/me',as_user=u)
    assert me['phone']==body['phone'] and me['signup_intent']==intent
    if intent=='provider':
        assert cm.sql('SELECT supplier_id FROM supplier_profiles WHERE supplier_id=:id',id=u['user_id']).scalar_one()==u['user_id']
        assert cm.ok('GET','/supplier/services',as_user=u)==[]
    if intent=='farmer': assert cm.ok('GET','/my/farms',as_user=u)==[]
    app=cm.ok('GET','/my/field-officer-application',as_user=u)
    assert (app is not None)==(intent=='field_officer')
    if app:
        assert app['status']=='pending' and app['reviewed_at'] is None
        assert cm.call('GET','/field-work',as_user=u).status_code==403


def test_existing_farmer_can_become_provider_and_apply(cm):
    u,_=signup(cm,'farmer')
    cm.ok('POST','/provider/profile',{'business_name':'Farm Services'},as_user=u,code=201)
    a=application(cm,u,qualification='Agriculture diploma')
    assert review(cm,a).status_code==200
    assert set(cm.ok('GET','/auth/me',as_user=u)['capabilities'])=={'farmer','provider','field_officer'}
    assert cm.sql('SELECT count(*) FROM users WHERE user_id=:id',id=u['user_id']).scalar_one()==1


def test_pending_details_reuse_contact_and_admin_queue(cm):
    u,body=signup(cm,field_officer_application={'qualification':'Diploma','experience_years':2.5,'operating_area_text':'Local mandal','languages_known':'Telugu','notes':'Available part time'})
    a=cm.ok('GET','/my/field-officer-application',as_user=u)
    assert a['full_name']==body['full_name'] and a['phone']==body['phone'] and a['experience_years']==2.5
    assert a['qualification']=='Diploma' and a['reviewed_by'] is None
    queue=cm.ok('GET','/admin/field-officer-applications',as_user=cm.admin)
    assert any(x['application_id']==a['application_id'] for x in queue)
    assert cm.ok('GET',f"/admin/field-officer-applications/{a['application_id']}",as_user=cm.admin)['user_id']==u['user_id']


def test_approval_retry_grants_once_without_assignments(cm):
    u,_=signup(cm); a=cm.ok('GET','/my/field-officer-application',as_user=u)
    r=review(cm,a); assert r.status_code==200; saved=r.json()
    assert saved['reviewed_by']==cm.admin['user_id'] and saved['reviewed_at']
    assert review(cm,a).json()==saved
    assert cm.sql("SELECT count(*) FROM user_capabilities WHERE user_id=:id AND capability='field_officer'",id=u['user_id']).scalar_one()==1
    assert cm.ok('GET','/field-work',as_user=u)['assignments']==[]
    c=cm.cycle()
    assert cm.call('GET',f"/field-work/crop-cycles/{c['farm_crop_id']}",as_user=u).status_code==404
    assert cm.call('GET','/my/farms',as_user=u).status_code==403
    assert cm.call('GET',f"/my/crop-cycles/{c['farm_crop_id']}",as_user=u).status_code==403


def test_approval_assignment_and_revoked_assignment_access(cm):
    u,_=signup(cm); a=cm.ok('GET','/my/field-officer-application',as_user=u)
    c=cm.cycle();other=cm.cycle()
    assert cm.call('POST','/admin/field-work/assignments',{'field_officer_id':u['user_id'],'farm_crop_id':c['farm_crop_id']},cm.admin).status_code==404
    assert review(cm,a).status_code==200
    assigned=cm.ok('POST','/admin/field-work/assignments',{'field_officer_id':u['user_id'],'farm_crop_id':c['farm_crop_id']},cm.admin,201)
    assert cm.call('GET',f"/field-work/crop-cycles/{c['farm_crop_id']}",as_user=u).status_code==200
    assert cm.call('GET',f"/field-work/crop-cycles/{other['farm_crop_id']}",as_user=u).status_code==404
    cm.ok('PATCH',f"/admin/field-work/assignments/{assigned['assignment_id']}",{'expected_status':'active','status':'completed'},cm.admin)
    assert cm.call('GET',f"/field-work/crop-cycles/{c['farm_crop_id']}",as_user=u).status_code==404


def test_rejection_reason_login_and_no_access(cm):
    u,body=signup(cm);a=cm.ok('GET','/my/field-officer-application',as_user=u)
    assert review(cm,a,'rejected').status_code==422
    r=review(cm,a,'rejected',reason='Need relevant field experience');assert r.status_code==200
    assert review(cm,a,'rejected',reason='Need relevant field experience').json()==r.json()
    assert review(cm,a).status_code==409
    assert cm.ok('GET','/my/field-officer-application',as_user=u)['rejection_reason']=='Need relevant field experience'
    assert cm.ok('POST','/auth/login',{'phone':body['phone'],'password':body['password']})['user']['capabilities']==[]
    assert cm.call('GET','/field-work',as_user=u).status_code==403
    assert cm.sql('SELECT count(*) FROM user_capabilities WHERE user_id=:id',id=u['user_id']).scalar_one()==0


@pytest.mark.parametrize('decision',['approved','rejected'])
def test_non_admin_and_self_review_denied(cm,decision):
    a=application(cm)
    for u in (cm.farmer,cm.other,cm.provider):
        assert review(cm,a,decision,u,reason='Reason' if decision=='rejected' else None).status_code==403
    admin_app=application(cm,cm.admin)
    assert review(cm,admin_app,decision,cm.admin,reason='Reason' if decision=='rejected' else None).status_code==403


def test_other_user_cannot_read_or_mutate_application(cm):
    a=application(cm)
    assert cm.ok('GET','/my/field-officer-application',as_user=cm.other) is None
    assert cm.call('GET',f"/admin/field-officer-applications/{a['application_id']}",as_user=cm.other).status_code==403
    assert cm.call('POST','/my/field-officer-application',{'user_id':cm.farmer['user_id']},cm.other).status_code==422
    assert cm.call('PATCH',f"/my/field-officer-application/{a['application_id']}",{'notes':'Changed'},cm.other).status_code in (404,405)


def test_submission_retry_and_immutable_history(cm):
    a=application(cm,notes='Original')
    assert cm.ok('POST','/my/field-officer-application',{'notes':'Original'})['application_id']==a['application_id']
    assert cm.call('POST','/my/field-officer-application',{'notes':'Different'}).status_code==409
    assert review(cm,a).status_code==200
    assert cm.ok('POST','/my/field-officer-application',{'notes':'Original'})['status']=='approved'
    with pytest.raises(IntegrityError),cm.connection.begin_nested():
        cm.sql("UPDATE field_officer_applications SET notes='Tampered' WHERE application_id=:id",id=a['application_id'])


@pytest.mark.parametrize('status',['pending','rejected'])
def test_old_grant_cannot_bypass_review(cm,status):
    a=application(cm)
    if status=='rejected': assert review(cm,a,status,reason='Not eligible').status_code==200
    assert cm.call('POST','/admin/field-officers',{'user_id':cm.farmer['user_id']},cm.admin).status_code==409
    with pytest.raises(IntegrityError),cm.connection.begin_nested():
        cm.sql("INSERT INTO user_capabilities(user_id,capability) VALUES(:id,'field_officer')",id=cm.farmer['user_id'])


def test_existing_officer_and_historical_users_unchanged(cm):
    before=dict(cm.sql('SELECT * FROM users WHERE user_id=:id',id=cm.provider['user_id']).mappings().one())
    cm.ok('POST','/admin/field-officers',{'user_id':cm.provider['user_id']},cm.admin)
    assert cm.call('POST','/my/field-officer-application',{},cm.provider).status_code==409
    assert dict(cm.sql('SELECT * FROM users WHERE user_id=:id',id=cm.provider['user_id']).mappings().one())==before
    assert set(cm.ok('GET','/auth/me',as_user=cm.provider)['capabilities'])=={'provider','field_officer'}


@pytest.mark.parametrize('body',[{'signup_intent':'admin'},{'signup_intent':'agronomist'},{'user_role':'field_officer'}, {'signup_intent':'field_officer','user_role':'farmer'},{'signup_intent':'farmer','field_officer_application':{}},{'signup_intent':'field_officer','field_officer_application':{'status':'approved'}}])
def test_signup_injection_and_conflicting_roles_rejected(cm,body):
    assert cm.call('POST','/auth/register',{'full_name':'Unsafe','phone':'9'+str(uuid4().int)[:9],'password':'TestPass123!',**body}).status_code==422


def test_registration_application_failure_atomic(cm,monkeypatch):
    phone='9'+str(uuid4().int)[:9]
    def fail(*args):raise RuntimeError('Injected application failure')
    monkeypatch.setattr(api,'submit_application',fail)
    assert cm.call('POST','/auth/register',{'full_name':'Atomic Test','phone':phone,'password':'TestPass123!','signup_intent':'field_officer'}).status_code==500
    assert cm.sql('SELECT count(*) FROM users WHERE phone=:phone',phone=phone).scalar_one()==0


def test_approval_capability_failure_atomic(cm,monkeypatch):
    from sqlalchemy import event
    a=application(cm)
    # Force a failure after UPDATE/trigger work, before transaction commit.
    def fail(connection,cursor,statement,parameters,context,executemany):
        if 'UPDATE field_officer_applications SET status=' in statement:raise RuntimeError('Injected review failure')
    event.listen(cm.connection,'after_cursor_execute',fail)
    try:
        assert review(cm,a).status_code==500
    finally:event.remove(cm.connection,'after_cursor_execute',fail)
    assert cm.ok('GET','/my/field-officer-application')['status']=='pending'
    assert 'field_officer' not in cm.ok('GET','/auth/me')['capabilities']
