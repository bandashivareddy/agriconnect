"""Applications reuse shared users, capabilities, and assignment-scoped field work."""
from contextlib import contextmanager
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from crop_management import Payload

SignupIntent = Literal['farmer','provider','field_officer','landowner']
SIGNUP_OPTIONS = [
    {'code':'farmer','label':'Farmer','description':'I manage or cultivate a farm'},
    {'code':'provider','label':'Service Provider','description':'I provide tractor, labour, spraying or other farm services'},
    {'code':'field_officer','label':'Field Officer','description':'I work with farms and support field operations','notice':'Application required'},
    {'code':'landowner','label':'Landowner','description':'I own land and may want farming managed for me','notice':'Managed farming coming later'},
]


class ApplicationFields(Payload):
    qualification: str | None = Field(default=None, max_length=300)
    experience_years: Decimal | None = Field(default=None, ge=0, le=80, decimal_places=1)
    crops_or_domains_known: str | None = Field(default=None, max_length=1000)
    operating_area_text: str | None = Field(default=None, max_length=500)
    languages_known: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)


class Review(Payload):
    status: Literal['approved','rejected']
    rejection_reason: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode='after')
    def reason(self):
        if (self.status=='rejected') != (self.rejection_reason is not None):
            raise ValueError('Rejection requires a reason; approval must not include a rejection reason.')
        return self


def submit_application(c, actor, body):
    # Same user-first lock order as legacy grants and admin review.
    c.execute(text('SELECT user_id FROM users WHERE user_id=:id FOR UPDATE'), {'id':actor}).one()
    saved=c.execute(text('SELECT * FROM field_officer_applications WHERE user_id=:id'), {'id':actor}).mappings().first()
    values=body.model_dump()
    if saved:
        if any(saved[key]!=value for key,value in values.items()):
            raise HTTPException(409,'An application is already submitted. Resubmission is not available yet.')
        return dict(saved),False
    if c.execute(text("SELECT 1 FROM user_capabilities WHERE user_id=:id AND capability='field_officer'"), {'id':actor}).first():
        raise HTTPException(409,'Field Officer access is already enabled for this account.')
    saved=c.execute(text('''INSERT INTO field_officer_applications(user_id,qualification,experience_years,crops_or_domains_known,operating_area_text,languages_known,notes)
      VALUES(:actor,:qualification,:experience_years,:crops_or_domains_known,:operating_area_text,:languages_known,:notes) RETURNING *'''),{**values,'actor':actor}).mappings().one()
    return dict(saved),True


def create_application_router(engine, get_current_user, get_effective_capabilities):
    router=APIRouter(tags=['Field Officer applications'])

    def admin(user=Depends(get_current_user)):
        with engine.connect() as c:
            if 'admin' not in get_effective_capabilities(c,user['user_id'],user['user_role']):
                raise HTTPException(403,'Admin access is required.')
        return user

    @contextmanager
    def tx():
        try:
            with engine.begin() as c: yield c
        except IntegrityError as exc:
            raise HTTPException(409,'Application or access changed. Refresh and retry.') from exc

    select='''SELECT a.*,u.full_name,u.phone,u.email,r.full_name AS reviewer_name FROM field_officer_applications a
      JOIN users u ON u.user_id=a.user_id LEFT JOIN users r ON r.user_id=a.reviewed_by'''

    @router.get('/auth/signup-options')
    def options():
        return SIGNUP_OPTIONS

    @router.get('/my/field-officer-application')
    def own(user=Depends(get_current_user)):
        with engine.connect() as c:
            saved=c.execute(text(select+' WHERE a.user_id=:id'),{'id':user['user_id']}).mappings().first()
            return dict(saved) if saved else None

    @router.post('/my/field-officer-application',status_code=201)
    def submit(body:ApplicationFields,response:Response,user=Depends(get_current_user)):
        with tx() as c:
            saved,created=submit_application(c,user['user_id'],body)
            if not created: response.status_code=200
            return saved

    @router.get('/admin/field-officer-applications')
    def applications(status:Literal['pending','approved','rejected']|None='pending',limit:int=Query(30,ge=1,le=100),offset:int=Query(0,ge=0),user=Depends(admin)):
        with engine.connect() as c:
            return [dict(r) for r in c.execute(text(select+(' WHERE a.status=:status' if status else '')+' ORDER BY a.created_at,a.application_id LIMIT :limit OFFSET :offset'),{'status':status,'limit':limit,'offset':offset}).mappings()]

    @router.get('/admin/field-officer-applications/{id}')
    def detail(id:int,user=Depends(admin)):
        with engine.connect() as c:
            saved=c.execute(text(select+' WHERE a.application_id=:id'),{'id':id}).mappings().first()
            if not saved: raise HTTPException(404,'Application not found.')
            return dict(saved)

    @router.post('/admin/field-officer-applications/{id}/review')
    def review(id:int,body:Review,user=Depends(admin)):
        with tx() as c:
            ref=c.execute(text('SELECT user_id FROM field_officer_applications WHERE application_id=:id'),{'id':id}).scalar()
            if ref is None: raise HTTPException(404,'Application not found.')
            if ref==user['user_id']: raise HTTPException(403,'Another admin must review your application.')
            c.execute(text('SELECT user_id FROM users WHERE user_id=:id FOR UPDATE'),{'id':ref}).one()
            saved=c.execute(text('SELECT * FROM field_officer_applications WHERE application_id=:id FOR UPDATE'),{'id':id}).mappings().one()
            if saved['status']!='pending':
                if saved['status']==body.status and saved['rejection_reason']==body.rejection_reason: return dict(saved)
                raise HTTPException(409,'This application has already been reviewed.')
            # The database approval trigger inserts the existing capability in this same transaction.
            return dict(c.execute(text('''UPDATE field_officer_applications SET status=:status,rejection_reason=:reason,
              reviewed_at=clock_timestamp(),reviewed_by=:actor,updated_at=clock_timestamp() WHERE application_id=:id RETURNING *'''),
              {'id':id,'status':body.status,'reason':body.rejection_reason,'actor':user['user_id']}).mappings().one())

    return router
