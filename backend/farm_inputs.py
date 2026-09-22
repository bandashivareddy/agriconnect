"""Catalogue metadata and actual inputs; no recommendations, prices or stock accounting."""
import json
import math
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid5, NAMESPACE_URL
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from crop_management import Payload

Unit = Literal['kg','g','L','ml','tonne','unit']
InputType = Literal['fertilizer','pesticide','fungicide','herbicide','bio_input','growth_regulator','soil_amendment','micronutrient','other']


class CropCreate(Payload):
    crop_name: str = Field(min_length=1, max_length=100)


class SourceData(Payload):
    source_name: str = Field(min_length=1,max_length=200)
    brand_name: str | None = Field(default=None,max_length=200)
    source_type: Literal['seed_company','nursery','tissue_culture_supplier','farmer_saved','local_supplier','other']
    notes: str | None = None
    status: Literal['active','inactive'] = 'active'


class VarietyData(Payload):
    crop_id: int = Field(gt=0)
    variety_name: str = Field(min_length=1,max_length=200)
    variety_type: Literal['hybrid','open_pollinated','cultivar','clone','local','other'] | None = None
    default_planting_material_source_id: int | None = Field(default=None,gt=0)
    duration_min_days: int | None = Field(default=None,ge=1,le=36500)
    duration_max_days: int | None = Field(default=None,ge=1,le=36500)
    days_to_first_harvest_min: int | None = Field(default=None,ge=1,le=36500)
    days_to_first_harvest_max: int | None = Field(default=None,ge=1,le=36500)
    notes: str | None = None
    status: Literal['active','inactive'] = 'active'

    @model_validator(mode='after')
    def durations(self):
        for lo,hi in ((self.duration_min_days,self.duration_max_days),(self.days_to_first_harvest_min,self.days_to_first_harvest_max)):
            if lo is not None and hi is not None and lo>hi:raise ValueError('Minimum duration must not exceed maximum.')
        return self


class ProductData(Payload):
    input_type: InputType
    product_name: str = Field(min_length=1,max_length=200)
    brand_name: str | None = Field(default=None,max_length=200)
    manufacturer_name: str | None = Field(default=None,max_length=200)
    active_ingredient: str | None = None
    formulation: str | None = Field(default=None,max_length=200)
    nutrient_composition: dict[str,float] | None = None
    default_unit: Unit | None = None
    notes: str | None = None

    @model_validator(mode='after')
    def nutrients(self):
        allowed={'N','P','K','P2O5','K2O','S','Ca','Mg','Zn','B','Fe','Mn','Cu','Mo'}
        if self.nutrient_composition and any(k not in allowed or not math.isfinite(v) or not 0<=v<=100 for k,v in self.nutrient_composition.items()):
            raise ValueError('Store labelled nutrient percentages (0–100) using supported nutrient keys. Do not infer composition.')
        return self


class ProductMaster(ProductData):
    status: Literal['active','inactive'] = 'active'


class SourceUpdate(SourceData):
    expected_updated_at: AwareDatetime
class VarietyUpdate(VarietyData):
    expected_updated_at: AwareDatetime
class ProductUpdate(ProductMaster):
    expected_updated_at: AwareDatetime


class CropMetadata(Payload):
    crop_group: Literal['orchard','seasonal','vegetable'] | None = None
    lifecycle_type: Literal['seasonal','perennial'] | None = None
    harvest_pattern: Literal['single','multiple','recurring'] | None = None


class InputFacts(Payload):
    quantity: Decimal = Field(gt=0,max_digits=14,decimal_places=4)
    unit: Unit
    application_method: str | None = Field(default=None,max_length=200)
    target_reason: str | None = None
    notes: str | None = None


class InputUse(InputFacts):
    farm_input_product_id: int | None = Field(default=None,gt=0)
    custom_product: ProductData | None = None

    @model_validator(mode='after')
    def product_choice(self):
        if (self.farm_input_product_id is None)==(self.custom_product is None):raise ValueError('Select a catalogue product or enter one unlisted product.')
        return self


class InputCreate(InputUse):
    request_key: UUID
class InputUpdate(InputFacts):
    expected_updated_at: AwareDatetime


def rows(c,sql,**params):return [dict(r) for r in c.execute(text(sql),params).mappings()]
def one(c,sql,**params):
    found=rows(c,sql,**params)
    if not found:raise HTTPException(404,'Record not found.')
    return found[0]


def prepare_planting(c,crop_id,data,saved=None):
    """Refresh only explicitly changed identity components, never from mutable master reads."""
    saved=saved or {}
    variety=data.get('crop_variety_id');source=data.get('planting_material_source_id');fallback=data.get('variety_text')
    if variety and fallback:raise HTTPException(422,'Select a variety or enter unlisted variety text, not both.')
    snapshot=dict(saved.get('planting_snapshot') or {})
    changed_var=(variety,fallback)!=(saved.get('crop_variety_id'),saved.get('variety_text'))
    if variety and (changed_var or crop_id!=saved.get('crop_id')):
        v=one(c,'SELECT * FROM crop_varieties WHERE crop_variety_id=:id AND crop_id=:crop FOR SHARE',id=variety,crop=crop_id)
        if changed_var and v['status']!='active':raise HTTPException(422,'Choose an active variety.')
        if changed_var:snapshot['variety']={k:v[k] for k in VarietyData.model_fields if k not in ('status','default_planting_material_source_id')}
    elif changed_var:snapshot['variety']={'variety_name':fallback,'unlisted':True} if fallback else None
    if source!=saved.get('planting_material_source_id'):
        if source:
            s=one(c,'SELECT * FROM planting_material_sources WHERE planting_material_source_id=:id FOR SHARE',id=source)
            if s['status']!='active':raise HTTPException(422,'Choose an active planting material source.')
            snapshot['source']={k:s[k] for k in SourceData.model_fields if k!='status'}
        else:snapshot['source']=None
    return snapshot or None


def harvest_suggestion(variety,planting_date):
    result={'total_duration_days':{'min':variety.get('duration_min_days'),'max':variety.get('duration_max_days')},
            'first_harvest_days':{'min':variety.get('days_to_first_harvest_min'),'max':variety.get('days_to_first_harvest_max')},'planting_date':planting_date}
    for key,low,high in [('total_duration_window','duration_min_days','duration_max_days'),('first_harvest_window','days_to_first_harvest_min','days_to_first_harvest_max')]:
        try:result[key]={part:planting_date+timedelta(days=variety[field]) if planting_date and variety.get(field) else None for part,field in [('from',low),('to',high)]}
        except OverflowError as exc:raise HTTPException(422,'Suggested date exceeds the supported date range.') from exc
    return result


def add_input(c,activity_id,body,user_id,key,response=None):
    payload=body.model_dump(mode='json',exclude={'request_key'})
    existing=rows(c,'SELECT * FROM farm_activity_inputs WHERE activity_id=:id AND request_key=:key',id=activity_id,key=str(key))
    if existing:
        if existing[0]['request_payload']!=payload:raise HTTPException(409,'Request key was already used with different input details.')
        if response is not None:response.status_code=200
        return {k:v for k,v in existing[0].items() if k!='request_payload'}
    if body.farm_input_product_id:
        product=one(c,'SELECT * FROM farm_input_products WHERE farm_input_product_id=:id FOR SHARE',id=body.farm_input_product_id)
        if product['status']!='active':raise HTTPException(422,'Choose an active product, or record an unlisted product.')
        snapshot={k:product[k] for k in ProductData.model_fields}
    else:snapshot=body.custom_product.model_dump(mode='json')
    facts=body.model_dump(exclude={'farm_input_product_id','custom_product','request_key'})
    result=one(c,'''INSERT INTO farm_activity_inputs(activity_id,farm_input_product_id,product_snapshot,is_unlisted,quantity,unit,application_method,target_reason,notes,created_by,updated_by,request_key,request_payload)
      VALUES(:activity,:product,CAST(:snapshot AS jsonb),:unlisted,:quantity,:unit,:application_method,:target_reason,:notes,:actor,:actor,:key,CAST(:payload AS jsonb)) RETURNING *''',
      **facts,activity=activity_id,product=body.farm_input_product_id,snapshot=json.dumps(snapshot),unlisted=body.farm_input_product_id is None,actor=user_id,key=str(key),payload=json.dumps(payload))
    return {k:v for k,v in result.items() if k!='request_payload'}


def add_activity_inputs(c,activity_id,inputs,user_id,request_key):
    for index,item in enumerate(inputs or []):add_input(c,activity_id,item,user_id,uuid5(NAMESPACE_URL,f'agriconnect:{request_key}:input:{index}'))


def create_catalogue_router(engine,get_current_user,get_effective_capabilities):
    router=APIRouter(tags=['Crop and input catalogue'])
    @contextmanager
    def tx():
        try:
            with engine.begin() as c:yield c
        except IntegrityError as exc:raise HTTPException(409,'This conflicts with existing catalogue or planting history.') from exc
    def require(*caps):
        def dependency(user=Depends(get_current_user)):
            with engine.connect() as c:
                if not set(caps).intersection(get_effective_capabilities(c,user['user_id'],user['user_role'])):raise HTTPException(403,'Applicable capability required.')
            return user
        return dependency
    admin=require('admin');reader=require('farmer','field_officer','admin');farmer=require('farmer');officer=require('field_officer')

    def install_catalogue(path,table,idcol,model,update_model,search_columns):
        def validate(c,data,saved=None):
            if table=='crop_varieties':
                one(c,'SELECT crop_id FROM crops WHERE crop_id=:id',id=data['crop_id'])
                if saved and saved['crop_id']!=data['crop_id']:raise HTTPException(422,'A variety cannot move to another crop.')
                source=data['default_planting_material_source_id']
                if source and (not saved or source!=saved['default_planting_material_source_id']):
                    one(c,"SELECT planting_material_source_id FROM planting_material_sources WHERE planting_material_source_id=:id AND status='active'",id=source)
        def bindings(data):return {k:json.dumps(v) if k=='nutrient_composition' and v is not None else v for k,v in data.items()}
        def value(k):return f'CAST(:{k} AS jsonb)' if k=='nutrient_composition' else ':'+k
        def create(body:model,user=Depends(admin)):
            with tx() as c:
                data=body.model_dump();validate(c,data)
                return one(c,f"INSERT INTO {table}({','.join(data)},created_by,updated_by) VALUES({','.join(value(k) for k in data)},:actor,:actor) RETURNING *",**bindings(data),actor=user['user_id'])
        def update(id:int,body:update_model,user=Depends(admin)):
            with tx() as c:
                saved=one(c,f'SELECT * FROM {table} WHERE {idcol}=:id FOR UPDATE',id=id)
                if saved['updated_at']!=body.expected_updated_at:raise HTTPException(409,'Catalogue record changed. Refresh before editing.')
                data=body.model_dump(exclude={'expected_updated_at'});validate(c,data,saved)
                return one(c,f'UPDATE {table} SET '+','.join(k+'='+value(k) for k in data)+f',updated_at=clock_timestamp(),updated_by=:actor WHERE {idcol}=:id RETURNING *',**bindings(data),actor=user['user_id'],id=id)
        def listing(c,q,crop_id,input_type,status,limit,offset):
            params=dict(q='%'+q+'%',crop=crop_id,kind=input_type,status=status,limit=limit,offset=offset)
            where='('+' OR '.join(f"COALESCE({k},'') ILIKE :q" for k in search_columns)+')'
            if status:where+=' AND status=:status'
            if crop_id is not None and table=='crop_varieties':where+=' AND crop_id=:crop'
            if input_type and table=='farm_input_products':where+=' AND input_type=:kind'
            return rows(c,f'SELECT * FROM {table} WHERE '+where+f' ORDER BY {idcol} DESC LIMIT :limit OFFSET :offset',**params)
        def admin_list(q:str=Query('',max_length=200),crop_id:int|None=None,input_type:InputType|None=None,status:Literal['active','inactive']|None=None,limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0),user=Depends(admin)):
            with engine.connect() as c:return listing(c,q,crop_id,input_type,status,limit,offset)
        def public_list(q:str=Query('',max_length=200),crop_id:int|None=None,input_type:InputType|None=None,limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0),user=Depends(reader)):
            with engine.connect() as c:return listing(c,q,crop_id,input_type,'active',limit,offset)
        def detail(id:int,user=Depends(reader)):
            with engine.connect() as c:return one(c,f"SELECT * FROM {table} WHERE {idcol}=:id AND status='active'",id=id)
        router.add_api_route('/admin/'+path,create,methods=['POST'],status_code=201,name='create_'+table)
        router.add_api_route('/admin/'+path+'/{id}',update,methods=['PUT'],name='update_'+table)
        router.add_api_route('/admin/'+path,admin_list,methods=['GET'],name='admin_list_'+table)
        router.add_api_route('/catalogue/'+path,public_list,methods=['GET'],name='list_'+table)
        router.add_api_route('/catalogue/'+path+'/{id}',detail,methods=['GET'],name='get_'+table)
    install_catalogue('planting-material-sources','planting_material_sources','planting_material_source_id',SourceData,SourceUpdate,['source_name','brand_name'])
    install_catalogue('crop-varieties','crop_varieties','crop_variety_id',VarietyData,VarietyUpdate,['variety_name'])
    install_catalogue('farm-input-products','farm_input_products','farm_input_product_id',ProductMaster,ProductUpdate,['product_name','brand_name','manufacturer_name','active_ingredient'])

    @router.post('/admin/crops', status_code=201)
    def create_crop(body:CropCreate,user=Depends(admin)):
        with tx() as c:
            # Serialize catalogue creates so case-insensitive duplicate checks also cover races.
            # The existing unique crop_name constraint remains the final exact-name safeguard.
            c.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('agriconnect:base-crop-create',0))"))
            if rows(c,'SELECT crop_id FROM crops WHERE lower(trim(crop_name))=lower(:name)',name=body.crop_name):
                raise HTTPException(409,'A crop with this name already exists. Select it to edit its metadata.')
            return one(c,'INSERT INTO crops(crop_name) VALUES(:name) RETURNING *',name=body.crop_name)

    @router.get('/catalogue/crops')
    def crops(q:str=Query('',max_length=200),limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0),user=Depends(reader)):
        with engine.connect() as c:return rows(c,'SELECT * FROM crops WHERE crop_name ILIKE :q ORDER BY crop_name,crop_id LIMIT :limit OFFSET :offset',q='%'+q+'%',limit=limit,offset=offset)
    @router.put('/admin/crops/{id}/metadata')
    def metadata(id:int,body:CropMetadata,user=Depends(admin)):
        with tx() as c:return one(c,'UPDATE crops SET crop_group=:crop_group,lifecycle_type=:lifecycle_type,harvest_pattern=:harvest_pattern WHERE crop_id=:id RETURNING *',**body.model_dump(),id=id)
    @router.get('/catalogue/crop-varieties/{id}/duration-suggestion')
    def suggestion(id:int,planting_date:date|None=None,user=Depends(reader)):
        with engine.connect() as c:return harvest_suggestion(one(c,"SELECT * FROM crop_varieties WHERE crop_variety_id=:id AND status='active'",id=id),planting_date)

    def authorized_activity(c,id,user,is_officer,write=False):
        activity=one(c,'SELECT a.*,f.farmer_id FROM farm_activities a JOIN farms f USING(farm_id) WHERE activity_id=:id',id=id)
        if is_officer:
            assignment=one(c,"SELECT * FROM crop_officer_assignments WHERE farm_crop_id=:crop AND field_officer_id=:actor AND status='active' FOR UPDATE",crop=activity['farm_crop_id'],actor=user['user_id'])
            if write and activity['created_by']!=user['user_id']:raise HTTPException(404,'Record not found.')
            if write and activity['field_visit_id']:
                visit=one(c,'SELECT * FROM field_visits WHERE visit_id=:id FOR UPDATE',id=activity['field_visit_id'])
                if visit['assignment_id']!=assignment['assignment_id'] or visit['status']!='in_progress':raise HTTPException(409,'Only your in-progress visit work can be edited.')
        elif activity['farmer_id']!=user['user_id']:raise HTTPException(404,'Record not found.')
        return one(c,'SELECT * FROM farm_activities WHERE activity_id=:id FOR UPDATE',id=id)
    def install_usage(prefix,dependency,is_officer):
        def listing(activity_id:int,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0),user=Depends(dependency)):
            with tx() as c:
                authorized_activity(c,activity_id,user,is_officer)
                return [{k:v for k,v in r.items() if k!='request_payload'} for r in rows(c,'SELECT * FROM farm_activity_inputs WHERE activity_id=:id ORDER BY farm_activity_input_id LIMIT :limit OFFSET :offset',id=activity_id,limit=limit,offset=offset)]
        def create(activity_id:int,body:InputCreate,response:Response,user=Depends(dependency)):
            with tx() as c:
                authorized_activity(c,activity_id,user,is_officer,True)
                return add_input(c,activity_id,body,user['user_id'],body.request_key,response)
        def update(activity_id:int,id:int,body:InputUpdate,user=Depends(dependency)):
            with tx() as c:
                authorized_activity(c,activity_id,user,is_officer,True)
                saved=one(c,'SELECT * FROM farm_activity_inputs WHERE farm_activity_input_id=:id AND activity_id=:activity FOR UPDATE',id=id,activity=activity_id)
                if saved['updated_at']!=body.expected_updated_at:raise HTTPException(409,'Input usage changed. Refresh before editing.')
                result=one(c,'''UPDATE farm_activity_inputs SET quantity=:quantity,unit=:unit,application_method=:application_method,target_reason=:target_reason,notes=:notes,
                  updated_by=:actor,updated_at=clock_timestamp() WHERE farm_activity_input_id=:id RETURNING *''',**body.model_dump(exclude={'expected_updated_at'}),actor=user['user_id'],id=id)
                return {k:v for k,v in result.items() if k!='request_payload'}
        router.add_api_route(prefix+'/{activity_id}/inputs',listing,methods=['GET'],name=('officer' if is_officer else 'farmer')+'_inputs')
        router.add_api_route(prefix+'/{activity_id}/inputs',create,methods=['POST'],status_code=201,name=('officer' if is_officer else 'farmer')+'_add_input')
        router.add_api_route(prefix+'/{activity_id}/inputs/{id}',update,methods=['PUT'],name=('officer' if is_officer else 'farmer')+'_edit_input')
    install_usage('/my/farm-activities',farmer,False)
    install_usage('/field-work/activities',officer,True)
    return router
