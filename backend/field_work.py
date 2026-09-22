"""Field work is assignment-scoped and never changes Crop Task execution status."""
from contextlib import contextmanager
from datetime import date, datetime, timezone, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from crop_management import Payload, business_today, is_overdue

class OfficerGrant(Payload):
    user_id: int = Field(gt=0)
class AssignmentCreate(Payload):
    field_officer_id: int = Field(gt=0)
    farm_crop_id: int = Field(gt=0)
    notes: str | None = None
class AssignmentUpdate(Payload):
    expected_status: Literal['active','completed','cancelled']
    status: Literal['active','completed','cancelled']
    notes: str | None = None
class VisitCreate(Payload):
    assignment_id: int = Field(gt=0)
    planned_visit_date: date
    visit_notes: str | None = None
class VisitTransition(Payload):
    expected_status: Literal['planned','in_progress','completed','cancelled']
    status: Literal['planned','in_progress','completed','cancelled']
    visit_notes: str | None = None
class VerifyTask(Payload):
    verification_status: Literal['observed_completed','observed_partial','not_done','not_applicable','unable_to_verify']
    officer_note: str | None = Field(default=None,min_length=1)
    expected_updated_at: AwareDatetime | None = None
    @model_validator(mode='after')
    def note(self):
        if self.verification_status!='observed_completed' and not self.officer_note:
            raise ValueError('Explain this verification outcome in a note.')
        return self
class Observation(Payload):
    observation_type: Literal['general','crop_condition','pest','disease','weed','water','nutrient','damage']
    severity: Literal['low','medium','high','critical']
    title: str = Field(min_length=1,max_length=200)
    detailed_notes: str = Field(min_length=1)
    observed_at: AwareDatetime | None = None
    expected_updated_at: AwareDatetime | None = None
    @model_validator(mode='after')
    def observed_time(self):
        if self.observed_at and self.observed_at > datetime.now(timezone.utc)+timedelta(minutes=5):
            raise ValueError('Observed time cannot be in the future.')
        return self


def create_field_router(engine,get_current_user,get_effective_capabilities):
    router=APIRouter(tags=['Field work'])
    def rows(c,sql,**params):return [dict(r) for r in c.execute(text(sql),params).mappings()]
    def one(c,sql,**params):
        result=rows(c,sql,**params)
        if not result:raise HTTPException(404,'Record not found.')
        return result[0]
    @contextmanager
    def tx():
        try:
            with engine.begin() as c:yield c
        except IntegrityError as exc:
            raise HTTPException(409,'This change conflicts with saved field work. Refresh and retry.') from exc
    def require(cap):
        def dependency(user=Depends(get_current_user)):
            with engine.connect() as c:
                if cap not in get_effective_capabilities(c,user['user_id'],user['user_role']):raise HTTPException(403,f'{cap.replace("_"," ").title()} access is required.')
            return user
        return dependency
    admin=require('admin');officer=require('field_officer');farmer=require('farmer')
    cycle_select='''SELECT fc.*,f.farm_name,f.farmer_id,u.full_name AS farmer_name,fp.plot_name,cr.crop_name
      FROM farm_crops fc JOIN farms f USING(farm_id) JOIN users u ON u.user_id=f.farmer_id
      LEFT JOIN farm_plots fp USING(plot_id) JOIN crops cr USING(crop_id)'''
    assignment_select='''SELECT a.*,u.full_name AS officer_name,f.farm_name,fp.plot_name,cr.crop_name,
      fu.full_name AS farmer_name FROM crop_officer_assignments a JOIN users u ON u.user_id=a.field_officer_id
      JOIN farm_crops fc USING(farm_crop_id) JOIN farms f USING(farm_id) JOIN users fu ON fu.user_id=f.farmer_id
      LEFT JOIN farm_plots fp USING(plot_id) JOIN crops cr USING(crop_id)'''
    visit_select='''SELECT v.*,a.farm_crop_id,a.field_officer_id,a.status AS assignment_status,u.full_name AS officer_name,
      f.farm_name,fp.plot_name,cr.crop_name,fu.full_name AS farmer_name
      FROM field_visits v JOIN crop_officer_assignments a USING(assignment_id)
      JOIN users u ON u.user_id=a.field_officer_id JOIN farm_crops fc USING(farm_crop_id)
      JOIN farms f USING(farm_id) JOIN users fu ON fu.user_id=f.farmer_id
      LEFT JOIN farm_plots fp USING(plot_id) JOIN crops cr USING(crop_id)'''
    def assignment(c,id,user=None,lock=False):
        result=one(c,'SELECT * FROM crop_officer_assignments WHERE assignment_id=:id'+(' FOR UPDATE' if lock else ''),id=id)
        if user and (result['field_officer_id']!=user['user_id'] or result['status']!='active'):raise HTTPException(404,'Record not found.')
        return result
    def authorized_visit(c,id,user=None,lock=False):
        ref=one(c,'SELECT assignment_id FROM field_visits WHERE visit_id=:id',id=id)
        a=assignment(c,ref['assignment_id'],user,lock)
        v=one(c,'SELECT * FROM field_visits WHERE visit_id=:id'+(' FOR UPDATE' if lock else ''),id=id)
        return a,v
    def mutable_visit(c,id,user):
        a,v=authorized_visit(c,id,user,True)
        if v['status']!='in_progress':raise HTTPException(409,'Start the visit before recording field work. Completed/cancelled visits are read-only.')
        return a,v
    def observations(c,where,**params):
        return rows(c,'''SELECT o.*,a.farm_crop_id,a.field_officer_id,u.full_name AS officer_name
          FROM field_observations o JOIN field_visits v USING(visit_id) JOIN crop_officer_assignments a USING(assignment_id)
          JOIN users u ON u.user_id=a.field_officer_id WHERE '''+where+' ORDER BY o.observed_at DESC,o.observation_id DESC LIMIT 50',**params)
    def detail(c,id):
        visit=one(c,visit_select+' WHERE v.visit_id=:id',id=id)
        cycle=one(c,cycle_select+' WHERE fc.farm_crop_id=:id',id=visit['farm_crop_id'])
        tasks=rows(c,'''SELECT ct.*,vt.verification_status,vt.officer_note,vt.verified_at,vt.updated_at AS verification_updated_at
          FROM crop_tasks ct JOIN crop_cycle_plans p USING(plan_id)
          LEFT JOIN visit_tasks vt ON vt.crop_task_id=ct.crop_task_id AND vt.visit_id=:visit
          WHERE p.farm_crop_id=:cycle AND (ct.due_date<=:day OR vt.visit_id IS NOT NULL)
          ORDER BY ct.due_date NULLS LAST,ct.sequence_no,ct.crop_task_id''',visit=id,cycle=visit['farm_crop_id'],day=max(business_today(),visit['planned_visit_date']))
        for task in tasks:
            task['is_overdue']=is_overdue(task,cycle['status'])
            task['verification_status']=task['verification_status'] or 'unverified'
        return {**visit,'cycle':cycle,'tasks':tasks,'observations':observations(c,'o.visit_id=:id',id=id),'business_date':business_today()}

    @router.get('/admin/field-officers')
    def officers(user=Depends(admin)):
        with engine.connect() as c:return rows(c,"SELECT u.user_id,u.full_name,u.user_role FROM users u JOIN user_capabilities uc USING(user_id) WHERE uc.capability='field_officer' ORDER BY u.full_name,u.user_id")
    @router.get('/admin/field-work/users')
    def candidates(q: str=Query('',max_length=100),user=Depends(admin)):
        with engine.connect() as c:return rows(c,"""SELECT u.user_id,u.full_name,u.user_role,
          EXISTS(SELECT 1 FROM user_capabilities uc WHERE uc.user_id=u.user_id AND capability='field_officer') AS is_field_officer
          FROM users u WHERE u.full_name ILIKE :q OR u.phone ILIKE :q OR u.email ILIKE :q ORDER BY u.full_name LIMIT 50""",q='%'+q+'%')
    @router.post('/admin/field-officers')
    def grant(body:OfficerGrant,user=Depends(admin)):
        with tx() as c:
            target=one(c,'SELECT user_id,full_name,user_role FROM users WHERE user_id=:id FOR UPDATE',id=body.user_id)
            pending=rows(c,"SELECT status FROM field_officer_applications WHERE user_id=:id AND status<>'approved'",id=body.user_id)
            if pending:
                raise HTTPException(409,'Review this account in Field Officer Applications before enabling access.')
            c.execute(text("INSERT INTO user_capabilities(user_id,capability) VALUES(:id,'field_officer') ON CONFLICT DO NOTHING"),{'id':body.user_id})
            return target
    @router.get('/admin/field-work/crop-cycles')
    def admin_cycles(q:str=Query('',max_length=100),limit:int=Query(30,ge=1,le=100),offset:int=Query(0,ge=0),user=Depends(admin)):
        with engine.connect() as c:return rows(c,cycle_select+' WHERE f.farm_name ILIKE :q OR u.full_name ILIKE :q OR cr.crop_name ILIKE :q ORDER BY fc.farm_crop_id DESC LIMIT :limit OFFSET :offset',q='%'+q+'%',limit=limit,offset=offset)
    @router.get('/admin/field-work/assignments')
    def assignments(limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0),user=Depends(admin)):
        with engine.connect() as c:return rows(c,assignment_select+' ORDER BY a.assignment_id DESC LIMIT :limit OFFSET :offset',limit=limit,offset=offset)
    @router.post('/admin/field-work/assignments',status_code=201)
    def assign(body:AssignmentCreate,user=Depends(admin)):
        with tx() as c:
            one(c,'SELECT user_id FROM users WHERE user_id=:id FOR UPDATE',id=body.field_officer_id)
            one(c,"SELECT user_id FROM user_capabilities WHERE user_id=:id AND capability='field_officer'",id=body.field_officer_id)
            one(c,'SELECT farm_crop_id FROM farm_crops WHERE farm_crop_id=:id',id=body.farm_crop_id)
            return one(c,'''INSERT INTO crop_officer_assignments(field_officer_id,farm_crop_id,notes,assigned_by,updated_by)
              VALUES(:field_officer_id,:farm_crop_id,:notes,:actor,:actor) RETURNING *''',**body.model_dump(),actor=user['user_id'])
    @router.patch('/admin/field-work/assignments/{id}')
    def update_assignment(id:int,body:AssignmentUpdate,user=Depends(admin)):
        with tx() as c:
            a=assignment(c,id,lock=True)
            if a['status']==body.status and a['notes']==body.notes:return a
            if a['status']!=body.expected_status or a['status']!='active':raise HTTPException(409,'Assignment changed or is closed. Create a new assignment for a new period.')
            result=one(c,'UPDATE crop_officer_assignments SET status=:status,notes=:notes,updated_at=CURRENT_TIMESTAMP,updated_by=:actor WHERE assignment_id=:id RETURNING *',status=body.status,notes=body.notes,actor=user['user_id'],id=id)
            if body.status!='active':
                c.execute(text("""UPDATE field_visits SET status='cancelled',visit_notes=COALESCE(visit_notes || E'\n','') || :note,
                  updated_at=CURRENT_TIMESTAMP,updated_by=:actor WHERE assignment_id=:id AND status IN ('planned','in_progress')"""),
                  {'note':'System: Assignment closed before visit completion.','actor':user['user_id'],'id':id})
            return result
    @router.get('/admin/field-work/visits')
    def admin_visits(limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0),user=Depends(admin)):
        with engine.connect() as c:return rows(c,visit_select+' ORDER BY v.planned_visit_date DESC,v.visit_id DESC LIMIT :limit OFFSET :offset',limit=limit,offset=offset)
    @router.post('/admin/field-work/visits',status_code=201)
    def schedule(body:VisitCreate,user=Depends(admin)):
        with tx() as c:
            a=assignment(c,body.assignment_id,lock=True)
            if a['status']!='active':raise HTTPException(409,'Visits require an active assignment.')
            return one(c,'''INSERT INTO field_visits(assignment_id,planned_visit_date,visit_notes,created_by,updated_by)
              VALUES(:assignment_id,:planned_visit_date,:visit_notes,:actor,:actor) RETURNING *''',**body.model_dump(),actor=user['user_id'])
    @router.get('/admin/field-work/visits/{id}')
    def admin_visit(id:int,user=Depends(admin)):
        with engine.connect() as c:return detail(c,id)
    @router.post('/admin/field-work/visits/{id}/cancel')
    def cancel_visit(id:int,body:VisitTransition,user=Depends(admin)):
        with tx() as c:
            _,v=authorized_visit(c,id,lock=True)
            if body.status!='cancelled' or not body.visit_notes:raise HTTPException(422,'Supply cancelled status and a reason.')
            if v['status']=='cancelled':return v
            if v['status']!=body.expected_status or v['status'] not in ('planned','in_progress'):raise HTTPException(409,'Visit changed or is already completed.')
            return one(c,"UPDATE field_visits SET status='cancelled',visit_notes=COALESCE(visit_notes || E'\n','') || :notes,updated_by=:actor,updated_at=CURRENT_TIMESTAMP WHERE visit_id=:id RETURNING *",notes='Cancelled by admin: '+body.visit_notes,actor=user['user_id'],id=id)
    @router.get('/field-work')
    def my_work(user=Depends(officer)):
        with engine.connect() as c:
            assigned=rows(c,assignment_select+" WHERE a.field_officer_id=:actor AND a.status='active' ORDER BY a.assignment_id DESC",actor=user['user_id'])
            visits=rows(c,visit_select+" WHERE a.field_officer_id=:actor AND a.status='active' ORDER BY v.planned_visit_date,v.visit_id",actor=user['user_id'])
            return {'assignments':assigned,'visits':visits,'business_date':business_today()}
    @router.get('/field-work/crop-cycles/{id}')
    def officer_cycle(id:int,user=Depends(officer)):
        with engine.connect() as c:
            one(c,"SELECT assignment_id FROM crop_officer_assignments WHERE farm_crop_id=:id AND field_officer_id=:actor AND status='active'",id=id,actor=user['user_id'])
            cycle=one(c,cycle_select+' WHERE fc.farm_crop_id=:id',id=id)
            cycle['visits']=rows(c,visit_select+" WHERE a.farm_crop_id=:id AND a.field_officer_id=:actor AND a.status='active' ORDER BY v.planned_visit_date DESC",id=id,actor=user['user_id'])
            return cycle
    @router.get('/field-work/visits/{id}')
    def my_visit(id:int,user=Depends(officer)):
        with engine.connect() as c:
            authorized_visit(c,id,user)
            return detail(c,id)
    @router.post('/field-work/visits/{id}/status')
    def visit_status(id:int,body:VisitTransition,user=Depends(officer)):
        with tx() as c:
            a,v=authorized_visit(c,id,user,True)
            if v['status']==body.status and v['visit_notes']==body.visit_notes:return detail(c,id)
            if v['status']!=body.expected_status or (v['status'],body.status) not in (('planned','in_progress'),('in_progress','completed')):
                raise HTTPException(409,'Visit changed or transition is not allowed.')
            one(c,'''UPDATE field_visits SET status=CAST(:status AS varchar),visit_notes=:notes,
              started_at=CASE WHEN CAST(:status AS varchar)='in_progress' THEN CURRENT_TIMESTAMP ELSE started_at END,
              completed_at=CASE WHEN CAST(:status AS varchar)='completed' THEN CURRENT_TIMESTAMP ELSE NULL END,
              updated_at=CURRENT_TIMESTAMP,updated_by=:actor WHERE visit_id=:id RETURNING *''',status=body.status,notes=body.visit_notes,actor=user['user_id'],id=id)
            if body.status=='in_progress':
                c.execute(text('''INSERT INTO visit_tasks(visit_id,crop_task_id)
                  SELECT :visit,ct.crop_task_id FROM crop_tasks ct JOIN crop_cycle_plans p USING(plan_id)
                  WHERE p.farm_crop_id=:cycle AND ct.due_date<=:day ON CONFLICT DO NOTHING'''),{'visit':id,'cycle':a['farm_crop_id'],'day':max(business_today(),v['planned_visit_date'])})
            return detail(c,id)
    @router.put('/field-work/visits/{id}/tasks/{task_id}')
    def verify(id:int,task_id:int,body:VerifyTask,user=Depends(officer)):
        with tx() as c:
            a,_=mutable_visit(c,id,user)
            one(c,'''SELECT ct.crop_task_id FROM crop_tasks ct JOIN crop_cycle_plans p USING(plan_id)
              WHERE ct.crop_task_id=:task AND p.farm_crop_id=:cycle''',task=task_id,cycle=a['farm_crop_id'])
            saved=rows(c,'SELECT * FROM visit_tasks WHERE visit_id=:visit AND crop_task_id=:task',visit=id,task=task_id)
            if saved and saved[0]['verification_status']==body.verification_status and saved[0]['officer_note']==body.officer_note:return saved[0]
            if saved and saved[0]['verification_status']!='unverified' and saved[0]['updated_at']!=body.expected_updated_at:
                raise HTTPException(409,'Verification changed. Refresh before editing.')
            return one(c,'''INSERT INTO visit_tasks(visit_id,crop_task_id,verification_status,officer_note,verified_at,verified_by)
              VALUES(:visit,:task,:status,:note,CURRENT_TIMESTAMP,:actor)
              ON CONFLICT(visit_id,crop_task_id) DO UPDATE SET verification_status=EXCLUDED.verification_status,
              officer_note=EXCLUDED.officer_note,verified_at=CURRENT_TIMESTAMP,verified_by=EXCLUDED.verified_by,updated_at=CURRENT_TIMESTAMP RETURNING *''',visit=id,task=task_id,status=body.verification_status,note=body.officer_note,actor=user['user_id'])
    @router.post('/field-work/visits/{id}/observations',status_code=201)
    def add_observation(id:int,body:Observation,user=Depends(officer)):
        with tx() as c:
            mutable_visit(c,id,user)
            return one(c,'''INSERT INTO field_observations(visit_id,observation_type,severity,title,detailed_notes,observed_at,created_by,updated_by)
              VALUES(:visit,:observation_type,:severity,:title,:detailed_notes,:observed_at,:actor,:actor) RETURNING *''',
              **body.model_dump(exclude={'expected_updated_at','observed_at'}),observed_at=body.observed_at or datetime.now(timezone.utc),visit=id,actor=user['user_id'])
    @router.put('/field-work/visits/{id}/observations/{observation_id}')
    def edit_observation(id:int,observation_id:int,body:Observation,user=Depends(officer)):
        with tx() as c:
            mutable_visit(c,id,user)
            saved=one(c,'SELECT * FROM field_observations WHERE observation_id=:obs AND visit_id=:visit AND created_by=:actor',obs=observation_id,visit=id,actor=user['user_id'])
            if saved['updated_at']!=body.expected_updated_at:raise HTTPException(409,'Observation changed. Refresh before editing.')
            return one(c,'''UPDATE field_observations SET observation_type=:observation_type,severity=:severity,title=:title,detailed_notes=:detailed_notes,
              observed_at=:observed_at,updated_at=CURRENT_TIMESTAMP,updated_by=:actor WHERE observation_id=:obs RETURNING *''',
              **body.model_dump(exclude={'expected_updated_at','observed_at'}),observed_at=body.observed_at or saved['observed_at'],actor=user['user_id'],obs=observation_id)
    @router.get('/my/crop-cycles/{id}/field-work')
    def farmer_history(id:int,user=Depends(farmer)):
        with engine.connect() as c:
            one(c,'SELECT fc.farm_crop_id FROM farm_crops fc JOIN farms f USING(farm_id) WHERE fc.farm_crop_id=:id AND f.farmer_id=:actor',id=id,actor=user['user_id'])
            assigned=rows(c,assignment_select+' WHERE a.farm_crop_id=:id ORDER BY a.assigned_at DESC',id=id)
            visits=rows(c,visit_select+' WHERE a.farm_crop_id=:id ORDER BY COALESCE(v.started_at,v.created_at) DESC,v.visit_id DESC LIMIT 20',id=id)
            return {'assignments':assigned,'visits':visits,'observations':observations(c,'a.farm_crop_id=:id',id=id)}
    @router.get('/my/crop-cycles/{id}/field-visits/{visit_id}')
    def farmer_visit(id:int,visit_id:int,user=Depends(farmer)):
        with engine.connect() as c:
            one(c,'''SELECT v.visit_id FROM field_visits v JOIN crop_officer_assignments a USING(assignment_id)
              JOIN farm_crops fc USING(farm_crop_id) JOIN farms f USING(farm_id)
              WHERE v.visit_id=:visit AND fc.farm_crop_id=:id AND f.farmer_id=:actor''',visit=visit_id,id=id,actor=user['user_id'])
            return detail(c,visit_id)
    return router
