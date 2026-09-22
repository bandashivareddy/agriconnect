"""Actual work and expenses share one context; planned work and verification stay separate."""
import json
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from crop_management import Payload
from farm_inputs import InputUse, add_activity_inputs

ActivityType = Literal['land_preparation','sowing_planting','irrigation','fertilizer','pesticide','weed_management','labour','machinery','pruning','inspection','harvest_support','transport','repair','other']
ExpenseCategory = Literal['seed_planting_material','fertilizer','pesticide','labour','irrigation','diesel_fuel','machinery','repair','transport','harvesting','packing','electricity','miscellaneous']


class Context(Payload):
    farm_id: int = Field(gt=0)
    plot_id: int | None = Field(default=None,gt=0)
    farm_block_id: int | None = Field(default=None,gt=0)
    farm_crop_id: int | None = Field(default=None,gt=0)


class BlockFields(Payload):
    name: str = Field(min_length=1,max_length=150)
    description: str | None = None
    area: Decimal | None = Field(default=None,gt=0,max_digits=14,decimal_places=4)
    area_unit: Literal['acres','hectares','square_metres'] | None = None
    status: Literal['active','inactive'] = 'active'

    @model_validator(mode='after')
    def area_pair(self):
        if (self.area is None)!=(self.area_unit is None):raise ValueError('Provide area and unit together.')
        return self


class BlockCreate(BlockFields):
    farm_id: int = Field(gt=0)
    plot_id: int = Field(gt=0)


class BlockUpdate(BlockFields):
    expected_updated_at: AwareDatetime


class ActivityFields(Payload):
    activity_type: ActivityType
    activity_date: date
    description: str = Field(min_length=1)
    quantity: Decimal | None = Field(default=None,gt=0,max_digits=14,decimal_places=4)
    unit: str | None = Field(default=None,min_length=1,max_length=50)
    performed_by_user_id: int | None = Field(default=None,gt=0)
    notes: str | None = None

    @model_validator(mode='after')
    def quantity_pair(self):
        if (self.quantity is None)!=(self.unit is None):raise ValueError('Provide quantity and unit together.')
        return self


class ActivityCreate(ActivityFields,Context):
    inputs: list[InputUse] | None = Field(default=None,max_length=50)
    crop_task_id: int | None = Field(default=None,gt=0)
    field_visit_id: int | None = Field(default=None,gt=0)
    service_booking_id: int | None = Field(default=None,gt=0)
    source_type: Literal['manual','crop_task','field_visit','service_booking'] = 'manual'
    request_key: UUID

    @model_validator(mode='after')
    def source(self):
        task,visit,booking=bool(self.crop_task_id),bool(self.field_visit_id),bool(self.service_booking_id)
        valid={'manual':not(task or visit or booking),'crop_task':task and not(visit or booking),'field_visit':visit and not booking,'service_booking':booking and not visit}
        if not valid[self.source_type]:raise ValueError('Source type must match its reference.')
        return self


class ActivityUpdate(ActivityFields):
    expected_updated_at: AwareDatetime


class ExpenseFields(Payload):
    expense_date: date
    category: ExpenseCategory
    amount: Decimal = Field(gt=0,max_digits=14,decimal_places=2)
    vendor_person: str | None = Field(default=None,max_length=200)
    payment_mode: str | None = Field(default=None,max_length=50)
    notes: str | None = None


class ExpenseCreate(ExpenseFields,Context):
    activity_id: int | None = Field(default=None,gt=0)
    request_key: UUID


class ExpenseUpdate(ExpenseFields):
    expected_updated_at: AwareDatetime


def create_ledger_router(engine,get_current_user,get_effective_capabilities):
    router=APIRouter(tags=['Farm activities and expenses'])
    def rows(c,sql,**params):return [dict(r) for r in c.execute(text(sql),params).mappings()]
    def one(c,sql,**params):
        result=rows(c,sql,**params)
        if not result:raise HTTPException(404,'Record not found.')
        return result[0]
    @contextmanager
    def tx():
        try:
            with engine.begin() as c:yield c
        except IntegrityError as exc:raise HTTPException(409,'This conflicts with saved farm history. Refresh and retry.') from exc
    def require(cap):
        def dependency(user=Depends(get_current_user)):
            with engine.connect() as c:
                if cap not in get_effective_capabilities(c,user['user_id'],user['user_role']):raise HTTPException(403,f'{cap} access is required.')
            return user
        return dependency
    farmer=require('farmer');officer=require('field_officer')
    def own(c,farm,user):return one(c,'SELECT * FROM farms WHERE farm_id=:id AND farmer_id=:actor',id=farm,actor=user['user_id'])
    def assigned(c,cycle,user):
        return one(c,"SELECT * FROM crop_officer_assignments WHERE farm_crop_id=:id AND field_officer_id=:actor AND status='active' FOR UPDATE",id=cycle,actor=user['user_id'])
    def merge_context(data,reference):
        for key in ('farm_id','plot_id','farm_block_id','farm_crop_id'):
            if key not in reference:continue
            if data.get(key) is not None and data[key]!=reference[key]:raise HTTPException(422,'References must belong to the same farm, plot, block and crop.')
            data[key]=reference[key]
    def context(c,data,user,is_officer=False):
        if is_officer:
            if not data.get('farm_crop_id'):raise HTTPException(422,'An assigned crop cycle is required.')
            a=assigned(c,data['farm_crop_id'],user)
        else:own(c,data['farm_id'],user)
        if data.get('field_visit_id'):
            visit=one(c,'''SELECT v.*,a.farm_crop_id,a.field_officer_id,a.status AS assignment_status FROM field_visits v
              JOIN crop_officer_assignments a USING(assignment_id) WHERE v.visit_id=:id FOR UPDATE OF v''',id=data['field_visit_id'])
            if is_officer and (visit['assignment_id']!=a['assignment_id'] or visit['field_officer_id']!=user['user_id']):raise HTTPException(404,'Record not found.')
            if is_officer and visit['status']!='in_progress':raise HTTPException(409,'Record visit work while the visit is in progress.')
            merge_context(data,{'farm_crop_id':visit['farm_crop_id']})
        if data.get('crop_task_id'):
            ref=one(c,'SELECT p.farm_crop_id FROM crop_tasks t JOIN crop_cycle_plans p USING(plan_id) WHERE t.crop_task_id=:id',id=data['crop_task_id'])
            merge_context(data,ref)
        if data.get('activity_id'):
            activity=one(c,'SELECT * FROM farm_activities WHERE activity_id=:id FOR SHARE',id=data['activity_id'])
            merge_context(data,activity)
        if data.get('farm_crop_id'):
            cycle=one(c,'SELECT * FROM farm_crops WHERE farm_crop_id=:id FOR UPDATE',id=data['farm_crop_id'])
            merge_context(data,cycle)
        if data.get('farm_block_id'):
            block=one(c,'SELECT * FROM farm_blocks WHERE farm_block_id=:id FOR SHARE',id=data['farm_block_id'])
            merge_context(data,{'farm_id':block['farm_id'],'plot_id':block['plot_id']})
            if block['status']!='active':raise HTTPException(409,'This block is inactive. Existing history remains available.')
        if data.get('plot_id'):one(c,'SELECT plot_id FROM farm_plots WHERE plot_id=:id AND farm_id=:farm',id=data['plot_id'],farm=data['farm_id'])
        if data.get('service_booking_id'):
            if is_officer:raise HTTPException(403,'Booking linkage is farmer-only.')
            one(c,'SELECT booking_id FROM bookings WHERE booking_id=:id AND farm_id=:farm AND farmer_id=:actor',id=data['service_booking_id'],farm=data['farm_id'],actor=user['user_id'])
            from task_services import validate_booked_activity
            validate_booked_activity(c,data,user['user_id'])
        if not is_officer:own(c,data['farm_id'],user)
        if data.get('performed_by_user_id') and data['performed_by_user_id']!=user['user_id']:
            raise HTTPException(422,'Only identify yourself as the performer; describe other workers in notes.')
    def clean(record):return {k:v for k,v in record.items() if k not in ('request_payload',)}
    def insert(c,table,data):
        # Table/column names are exclusively internal constants or validated model fields.
        columns=','.join(data);values=','.join('CAST(:request_payload AS jsonb)' if k=='request_payload' else ':'+k for k in data)
        return one(c,f'INSERT INTO {table}({columns}) VALUES({values}) RETURNING *',**data)
    def create(c,table,body,user,response,is_officer=False):
        data=body.model_dump();payload=body.model_dump(mode='json');key=str(body.request_key)
        inputs=data.pop('inputs',None)
        if not inputs:payload.pop('inputs',None)
        # Serializes retries including requests whose response was lost after commit.
        c.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'),{'key':str(user['user_id'])+':'+key})
        if is_officer:assigned(c,data.get('farm_crop_id'),user)
        else:own(c,data['farm_id'],user)
        existing=rows(c,f'SELECT * FROM {table} WHERE created_by=:actor AND request_key=:key',actor=user['user_id'],key=key)
        if existing:
            if existing[0]['request_payload']!=payload:raise HTTPException(409,'Request key was already used with different details.')
            response.status_code=200;return clean(existing[0])
        context(c,data,user,is_officer)
        data.update(request_key=key,request_payload=json.dumps(payload),created_by=user['user_id'],updated_by=user['user_id'])
        saved=insert(c,table,data)
        if inputs:add_activity_inputs(c,saved['activity_id'],body.inputs,user['user_id'],key)
        return clean(saved)
    def edit(c,table,idcol,id,body,user,is_officer=False,cycle=None):
        ref=one(c,f'SELECT * FROM {table} WHERE {idcol}=:id',id=id)
        if is_officer:
            assigned(c,cycle,user)
            if ref['farm_crop_id']!=cycle or ref['created_by']!=user['user_id']:raise HTTPException(404,'Record not found.')
            if ref['field_visit_id']:
                v=one(c,'SELECT status FROM field_visits WHERE visit_id=:id FOR UPDATE',id=ref['field_visit_id'])
                if v['status']!='in_progress':raise HTTPException(409,'Completed/cancelled visit work is read-only for officers.')
        else:own(c,ref['farm_id'],user)
        saved=one(c,f'SELECT * FROM {table} WHERE {idcol}=:id FOR UPDATE',id=id)
        if saved['updated_at']!=body.expected_updated_at:raise HTTPException(409,'Record changed. Refresh before editing.')
        data=body.model_dump(exclude={'expected_updated_at'})
        performer=data.get('performed_by_user_id')
        if performer and performer not in (user['user_id'],saved.get('performed_by_user_id')):raise HTTPException(422,'Cannot attribute work to another account.')
        return clean(one(c,f"UPDATE {table} SET "+','.join(k+'=:'+k for k in data)+f',updated_at=clock_timestamp(),updated_by=:actor WHERE {idcol}=:id RETURNING *',**data,actor=user['user_id'],id=id))

    @router.post('/my/farm-blocks',status_code=201)
    def add_block(body:BlockCreate,user=Depends(farmer)):
        with tx() as c:
            own(c,body.farm_id,user)
            one(c,'SELECT plot_id FROM farm_plots WHERE plot_id=:id AND farm_id=:farm',id=body.plot_id,farm=body.farm_id)
            return insert(c,'farm_blocks',{**body.model_dump(),'created_by':user['user_id'],'updated_by':user['user_id']})
    @router.get('/my/farm-blocks')
    def blocks(farm_id:int,plot_id:int|None=None,user=Depends(farmer)):
        with engine.connect() as c:
            own(c,farm_id,user)
            return rows(c,'SELECT * FROM farm_blocks WHERE farm_id=:farm'+(' AND plot_id=:plot' if plot_id else '')+' ORDER BY name,farm_block_id',farm=farm_id,plot=plot_id)
    @router.put('/my/farm-blocks/{id}')
    def update_block(id:int,body:BlockUpdate,user=Depends(farmer)):
        with tx() as c:return edit(c,'farm_blocks','farm_block_id',id,body,user)

    @router.post('/my/farm-activities',status_code=201)
    def add_activity(body:ActivityCreate,response:Response,user=Depends(farmer)):
        with tx() as c:return create(c,'farm_activities',body,user,response)
    @router.post('/my/crop-tasks/{task_id}/record-work',status_code=201)
    def record_work(task_id:int,body:ActivityCreate,response:Response,user=Depends(farmer)):
        if body.crop_task_id!=task_id or body.source_type!='crop_task':raise HTTPException(422,'Use the selected crop task as the activity source.')
        with tx() as c:return create(c,'farm_activities',body,user,response)
    @router.get('/my/farm-activities/{id}')
    def activity(id:int,user=Depends(farmer)):
        with engine.connect() as c:
            result=one(c,'SELECT a.* FROM farm_activities a JOIN farms f USING(farm_id) WHERE a.activity_id=:id AND f.farmer_id=:actor',id=id,actor=user['user_id']);return clean(result)
    @router.put('/my/farm-activities/{id}')
    def update_activity(id:int,body:ActivityUpdate,user=Depends(farmer)):
        with tx() as c:return edit(c,'farm_activities','activity_id',id,body,user)
    @router.post('/my/farm-expenses',status_code=201)
    def add_expense(body:ExpenseCreate,response:Response,user=Depends(farmer)):
        with tx() as c:return create(c,'farm_expenses',body,user,response)
    @router.get('/my/farm-expenses/{id}')
    def expense(id:int,user=Depends(farmer)):
        with engine.connect() as c:
            result=one(c,'SELECT e.* FROM farm_expenses e JOIN farms f USING(farm_id) WHERE e.expense_id=:id AND f.farmer_id=:actor',id=id,actor=user['user_id']);return clean(result)
    @router.put('/my/farm-expenses/{id}')
    def update_expense(id:int,body:ExpenseUpdate,user=Depends(farmer)):
        with tx() as c:return edit(c,'farm_expenses','expense_id',id,body,user)

    def listing(c,table,filters,user,limit,offset):
        where='f.farmer_id=:actor';params={'actor':user['user_id'],'limit':limit,'offset':offset}
        for key,value in filters.items():
            if value is None:continue
            column=('activity_date' if table=='farm_activities' else 'expense_date') if key in ('date_from','date_to') else key
            operator='>=' if key=='date_from' else '<=' if key=='date_to' else '='
            where+=f' AND r.{column}{operator}:{key}';params[key]=value
        if filters.get('date_from') and filters.get('date_to') and filters['date_from']>filters['date_to']:raise HTTPException(422,'Date range is reversed.')
        base=f' FROM {table} r JOIN farms f USING(farm_id) WHERE '+where
        d='activity_date' if table=='farm_activities' else 'expense_date';pk='activity_id' if table=='farm_activities' else 'expense_id'
        result={'items':[clean(r) for r in rows(c,'SELECT r.*'+base+f' ORDER BY r.{d} DESC,r.{pk} DESC LIMIT :limit OFFSET :offset',**params)]}
        result.update(one(c,'SELECT count(*) AS count'+(',COALESCE(sum(r.amount),0) AS total_amount' if table=='farm_expenses' else '')+base,**params))
        if table=='farm_expenses':result['currency']='INR'
        return result
    @router.get('/my/farm-activities')
    def activities(farm_id:int|None=None,plot_id:int|None=None,farm_block_id:int|None=None,farm_crop_id:int|None=None,crop_task_id:int|None=None,activity_type:ActivityType|None=None,date_from:date|None=None,date_to:date|None=None,limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0),user=Depends(farmer)):
        filters=dict(farm_id=farm_id,plot_id=plot_id,farm_block_id=farm_block_id,farm_crop_id=farm_crop_id,crop_task_id=crop_task_id,activity_type=activity_type,date_from=date_from,date_to=date_to)
        with engine.connect() as c:return listing(c,'farm_activities',filters,user,limit,offset)
    @router.get('/my/farm-expenses')
    def expenses(farm_id:int|None=None,plot_id:int|None=None,farm_block_id:int|None=None,farm_crop_id:int|None=None,activity_id:int|None=None,category:ExpenseCategory|None=None,date_from:date|None=None,date_to:date|None=None,limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0),user=Depends(farmer)):
        filters=dict(farm_id=farm_id,plot_id=plot_id,farm_block_id=farm_block_id,farm_crop_id=farm_crop_id,activity_id=activity_id,category=category,date_from=date_from,date_to=date_to)
        with engine.connect() as c:return listing(c,'farm_expenses',filters,user,limit,offset)
    @router.get('/field-work/crop-cycles/{cycle_id}/activities')
    def officer_activities(cycle_id:int,limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0),user=Depends(officer)):
        with tx() as c:
            assigned(c,cycle_id,user)
            return [clean(r) for r in rows(c,'''SELECT a.*,(a.created_by=:actor AND (a.field_visit_id IS NULL OR EXISTS(
              SELECT 1 FROM field_visits v JOIN crop_officer_assignments ca USING(assignment_id)
              WHERE v.visit_id=a.field_visit_id AND v.status='in_progress' AND ca.status='active' AND ca.field_officer_id=:actor))) AS can_edit_inputs
              FROM farm_activities a WHERE farm_crop_id=:id ORDER BY activity_date DESC,activity_id DESC LIMIT :limit OFFSET :offset''',actor=user['user_id'],id=cycle_id,limit=limit,offset=offset)]
    @router.post('/field-work/crop-cycles/{cycle_id}/activities',status_code=201)
    def officer_add(cycle_id:int,body:ActivityCreate,response:Response,user=Depends(officer)):
        if body.farm_crop_id!=cycle_id:raise HTTPException(422,'Crop context does not match.')
        with tx() as c:return create(c,'farm_activities',body,user,response,True)
    @router.put('/field-work/crop-cycles/{cycle_id}/activities/{id}')
    def officer_edit(cycle_id:int,id:int,body:ActivityUpdate,user=Depends(officer)):
        with tx() as c:return edit(c,'farm_activities','activity_id',id,body,user,True,cycle_id)
    return router
