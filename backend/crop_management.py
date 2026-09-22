"""Additive Crop Management API. Existing marketplace handlers remain untouched."""
from contextlib import contextmanager
import json
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from season_planning import DATE_SCHEDULES, season_label, validate_season_dates, task_due

TaskPhase = Literal['pre_season','planting','crop_stage','harvest','miscellaneous']
TaskType = Literal['irrigation','fertilizer','pest_monitoring','disease_monitoring','weed_management','field_operation','harvest','inspection','general']
ScheduleType = Literal['days_after_season_start','days_before_planting','days_after_planting','days_before_harvest','crop_stage','condition','manual']
TaskStatus = Literal['pending','in_progress','completed','partial','not_applicable','cancelled']
CycleStatus = Literal['planned','active','harvested','cancelled']
OPEN_TASKS = ('pending', 'in_progress', 'partial')
TASK_TRANSITIONS = {
    'pending': {'in_progress','completed','partial','not_applicable','cancelled'},
    'in_progress': {'completed','partial','not_applicable','cancelled'},
    'partial': {'in_progress','completed','cancelled'},
}
CYCLE_TRANSITIONS = {'planned': {'active','cancelled'}, 'active': {'harvested','cancelled'}}
SNAPSHOT_FIELDS = ('phase','sequence_no','title','instructions','task_type','schedule_type','offset_days','crop_stage_key','condition_text','service_category_id')


def business_today():
    # India has no daylight-saving transitions; avoid OS timezone database dependency.
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).date()


def is_overdue(task, cycle_status, today=None):
    return bool((cycle_status == 'active' or (cycle_status == 'planned' and task.get('phase') is not None)) and task['status'] in OPEN_TASKS
                and task['due_date'] and task['due_date'] < (today or business_today()))


class Payload(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class TemplateCreate(Payload):
    crop_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=150)
    description: str | None = None


class TemplatePatch(Payload):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    is_active: bool | None = None


class VersionCreate(Payload):
    clone_from_version_id: int | None = Field(default=None, gt=0)
    version_notes: str | None = None


class VersionPatch(Payload):
    version_notes: str | None = None


class TaskDefinition(Payload):
    phase: TaskPhase | None = None
    service_category_id: int | None = Field(default=None, gt=0)
    sequence_no: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    instructions: str = Field(min_length=1)
    task_type: TaskType
    schedule_type: ScheduleType
    offset_days: int | None = Field(default=None, ge=0, le=36500)
    crop_stage_key: str | None = Field(default=None, min_length=1, max_length=100)
    condition_text: str | None = Field(default=None, min_length=1)

    @model_validator(mode='after')
    def scheduling(self):
        relative = self.schedule_type in DATE_SCHEDULES
        if relative != (self.offset_days is not None):
            raise ValueError('Offset days are required only for date-relative scheduling.')
        if (self.schedule_type == 'crop_stage') != (self.crop_stage_key is not None):
            raise ValueError('A crop stage key is required only for crop-stage scheduling.')
        if (self.schedule_type == 'condition') != (self.condition_text is not None):
            raise ValueError('Condition text is required only for condition scheduling.')
        return self


class TaskPatch(Payload):
    phase: TaskPhase | None = None
    service_category_id: int | None = Field(default=None, gt=0)
    sequence_no: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    instructions: str | None = Field(default=None, min_length=1)
    task_type: TaskType | None = None
    schedule_type: ScheduleType | None = None
    offset_days: int | None = Field(default=None, ge=0, le=36500)
    crop_stage_key: str | None = Field(default=None, min_length=1, max_length=100)
    condition_text: str | None = Field(default=None, min_length=1)


class CycleCreate(Payload):
    period_started_on: date | None = None
    expected_planting_on: date | None = None
    crop_variety_id: int | None = Field(default=None, gt=0)
    planting_material_source_id: int | None = Field(default=None, gt=0)
    seed_or_material_lot: str | None = Field(default=None, min_length=1, max_length=150)
    variety_text: str | None = Field(default=None, min_length=1, max_length=200)
    plot_id: int = Field(gt=0)
    farm_block_id: int | None = Field(default=None, gt=0)
    crop_id: int = Field(gt=0)
    season: str | None = Field(default=None, max_length=50)
    status: Literal['planned','active'] = 'planned'
    planted_on: date | None = None
    expected_harvest_on: date | None = None

    @model_validator(mode='after')
    def dates(self):
        if self.status == 'active' and self.planted_on is None:
            raise ValueError('An active crop requires its actual planting date.')
        if self.status == 'planned' and self.planted_on is not None:
            raise ValueError('Record actual planting when activating the crop, not while planned.')
        check_dates(self.planted_on, self.expected_harvest_on)
        return self


class CyclePatch(Payload):
    period_started_on: date | None = None
    expected_planting_on: date | None = None
    crop_variety_id: int | None = Field(default=None, gt=0)
    planting_material_source_id: int | None = Field(default=None, gt=0)
    seed_or_material_lot: str | None = Field(default=None, min_length=1, max_length=150)
    variety_text: str | None = Field(default=None, min_length=1, max_length=200)
    plot_id: int | None = Field(default=None, gt=0)
    farm_block_id: int | None = Field(default=None, gt=0)
    crop_id: int | None = Field(default=None, gt=0)
    season: str | None = Field(default=None, max_length=50)
    expected_harvest_on: date | None = None


class CycleTransition(Payload):
    expected_status: CycleStatus
    status: CycleStatus
    planted_on: date | None = None
    note: str | None = Field(default=None, min_length=1)


class TaskTransition(Payload):
    expected_status: TaskStatus
    status: TaskStatus
    status_note: str | None = Field(default=None, min_length=1)


class PlanCreate(Payload):
    sop_version_id: int = Field(gt=0)
    anchor_date: date | None = Field(default=None, description='Planting reference only: expected planting for a planned crop; actual planted_on for an active crop. May be omitted when saved or unused by the selected season plan. Never defaults to today.')


def check_dates(planted, harvest):
    if planted and harvest and harvest <= planted:
        raise ValueError('Expected harvest must be after actual/expected planting.')


def create_router(engine, get_current_user, get_effective_capabilities):
    router = APIRouter(tags=['Crop Management'])

    @contextmanager
    def transaction():
        try:
            with engine.begin() as connection:
                yield connection
        except IntegrityError as exc:
            raise HTTPException(409, 'This change conflicts with saved data or an immutable SOP. Refresh and retry.') from exc

    def rows(c, sql, **params):
        return [dict(row) for row in c.execute(text(sql), params).mappings()]

    def one(c, sql, **params):
        result = rows(c, sql, **params)
        if not result:
            raise HTTPException(404, 'Record not found.')
        return result[0]

    def require(capability):
        def dependency(user=Depends(get_current_user)):
            with engine.connect() as c:
                if capability not in get_effective_capabilities(c, user['user_id'], user['user_role']):
                    raise HTTPException(403, f'{capability.title()} access is required.')
            return user
        return dependency

    farmer = require('farmer')
    admin = require('admin')

    def owned_cycle(c, cycle_id, user, lock=False):
        return one(c, '''SELECT fc.*, f.farm_name, fp.plot_name, fb.name AS block_name, cr.crop_name, cr.crop_group, cr.lifecycle_type, cr.harvest_pattern
            FROM farm_crops fc JOIN farms f ON f.farm_id=fc.farm_id
            JOIN crops cr ON cr.crop_id=fc.crop_id LEFT JOIN farm_plots fp ON fp.plot_id=fc.plot_id
            LEFT JOIN farm_blocks fb ON fb.farm_block_id=fc.farm_block_id
            WHERE fc.farm_crop_id=:id AND f.farmer_id=:user_id''' + (' FOR UPDATE OF fc' if lock else ''),
            id=cycle_id, user_id=user['user_id'])

    def service_name(c, category_id):
        if category_id is None:return None
        return one(c, 'SELECT category_name FROM service_categories WHERE category_id=:id AND is_active',id=category_id)['category_name']

    def validate_plot(c, farm_id, plot_id):
        one(c, 'SELECT plot_id FROM farm_plots WHERE plot_id=:plot AND farm_id=:farm', plot=plot_id, farm=farm_id)

    def validate_block(c, farm_id, plot_id, block_id):
        if block_id is not None:
            block = one(c, 'SELECT status FROM farm_blocks WHERE farm_block_id=:id AND farm_id=:farm AND plot_id=:plot FOR SHARE', id=block_id,farm=farm_id,plot=plot_id)
            if block['status'] != 'active':
                raise HTTPException(409, 'Choose an active block.')

    def plan_data(c, cycle):
        plans = rows(c, 'SELECT * FROM crop_cycle_plans WHERE farm_crop_id=:id', id=cycle['farm_crop_id'])
        if not plans:
            return None
        plan = plans[0]
        tasks = rows(c, 'SELECT * FROM crop_tasks WHERE plan_id=:id ORDER BY due_date NULLS LAST,sequence_no,crop_task_id', id=plan['plan_id'])
        for task in tasks:
            task['is_overdue'] = is_overdue(task, cycle['status'])
        plan['tasks'] = tasks
        plan['season_date_mismatch'] = bool(plan['season_start_snapshot'] and (
            plan['season_start_snapshot'] != cycle['period_started_on'] or plan['expected_harvest_snapshot'] != cycle['expected_harvest_on']))
        plan['planting_date_mismatch'] = bool(plan['anchor_date'] and cycle['planted_on'] and cycle['planted_on'] != plan['anchor_date'])
        return plan

    def cycle_data(c, cycle):
        plan = plan_data(c, cycle)
        tasks = plan['tasks'] if plan else []
        cycle['plan'] = plan
        cycle['summary'] = {
            'completed_tasks': sum(t['status'] == 'completed' for t in tasks),
            'total_tasks': len(tasks),
            'overdue_tasks': sum(t['is_overdue'] for t in tasks),
            'next_task': next((t for t in tasks if t['status'] in OPEN_TASKS), None),
        }
        return cycle

    # All SOP writes acquire template then version locks; task mutations follow the same order.
    def locked_version(c, version_id):
        ref = one(c, 'SELECT sop_template_id FROM sop_versions WHERE sop_version_id=:id', id=version_id)
        template = one(c, 'SELECT * FROM sop_templates WHERE sop_template_id=:id FOR UPDATE', id=ref['sop_template_id'])
        version = one(c, 'SELECT * FROM sop_versions WHERE sop_version_id=:id FOR UPDATE', id=version_id)
        return template, version

    def draft(c, version_id):
        template, version = locked_version(c, version_id)
        if version['status'] != 'draft':
            raise HTTPException(409, 'Published SOP versions are immutable. Create a new draft version.')
        return template, version

    def touch_version(c, version_id, user):
        c.execute(text('UPDATE sop_versions SET updated_at=CURRENT_TIMESTAMP,updated_by=:actor WHERE sop_version_id=:id'), {'actor':user['user_id'],'id':version_id})

    @router.get('/admin/sop-templates')
    def admin_templates(user=Depends(admin)):
        with engine.connect() as c:
            return rows(c, 'SELECT t.*,cr.crop_name FROM sop_templates t JOIN crops cr USING(crop_id) ORDER BY t.sop_template_id DESC')

    @router.post('/admin/sop-templates', status_code=201)
    def create_template(body: TemplateCreate, user=Depends(admin)):
        with transaction() as c:
            one(c, 'SELECT crop_id FROM crops WHERE crop_id=:id', id=body.crop_id)
            return one(c, '''INSERT INTO sop_templates(crop_id,name,description,created_by,updated_by)
                VALUES(:crop_id,:name,:description,:actor,:actor) RETURNING *''', **body.model_dump(), actor=user['user_id'])

    @router.patch('/admin/sop-templates/{template_id}')
    def patch_template(template_id: int, body: TemplatePatch, user=Depends(admin)):
        updates = body.model_dump(exclude_unset=True)
        if any(updates.get(k, 'absent') is None for k in ('name','is_active')):
            raise HTTPException(422, 'Name and active flag cannot be null.')
        with transaction() as c:
            current = one(c, 'SELECT * FROM sop_templates WHERE sop_template_id=:id FOR UPDATE', id=template_id)
            current.update(updates)
            return one(c, '''UPDATE sop_templates SET name=:name,description=:description,is_active=:is_active,
                updated_at=CURRENT_TIMESTAMP,updated_by=:actor WHERE sop_template_id=:id RETURNING *''',
                name=current['name'],description=current['description'],is_active=current['is_active'],actor=user['user_id'],id=template_id)

    @router.get('/admin/sop-templates/{template_id}/versions')
    def admin_versions(template_id: int, user=Depends(admin)):
        with engine.connect() as c:
            one(c, 'SELECT sop_template_id FROM sop_templates WHERE sop_template_id=:id', id=template_id)
            return rows(c, 'SELECT * FROM sop_versions WHERE sop_template_id=:id ORDER BY version_number DESC', id=template_id)

    @router.post('/admin/sop-templates/{template_id}/versions', status_code=201)
    def create_version(template_id: int, body: VersionCreate, user=Depends(admin)):
        with transaction() as c:
            one(c, 'SELECT * FROM sop_templates WHERE sop_template_id=:id FOR UPDATE', id=template_id)
            source = None
            if body.clone_from_version_id:
                source = one(c, 'SELECT * FROM sop_versions WHERE sop_version_id=:id AND sop_template_id=:template FOR UPDATE', id=body.clone_from_version_id,template=template_id)
            version = one(c, '''INSERT INTO sop_versions(sop_template_id,version_number,version_notes,created_by,updated_by)
                SELECT :id, COALESCE(MAX(version_number),0)+1,:notes,:actor,:actor FROM sop_versions WHERE sop_template_id=:id RETURNING *''',
                id=template_id,notes=body.version_notes if body.version_notes is not None else (source['version_notes'] if source else None),actor=user['user_id'])
            if source:
                c.execute(text('''INSERT INTO sop_tasks(sop_version_id,sequence_no,title,instructions,task_type,schedule_type,offset_days,crop_stage_key,condition_text,service_category_id,service_category_name_snapshot,phase,created_by,updated_by)
                    SELECT :new,sequence_no,title,instructions,task_type,schedule_type,offset_days,crop_stage_key,condition_text,service_category_id,service_category_name_snapshot,phase,:actor,:actor FROM sop_tasks WHERE sop_version_id=:source'''),
                    {'new':version['sop_version_id'],'source':source['sop_version_id'],'actor':user['user_id']})
            return version

    def version_data(c, version_id, public=False):
        version = one(c, '''SELECT v.*,t.name AS template_name,t.crop_id FROM sop_versions v JOIN sop_templates t USING(sop_template_id)
            WHERE v.sop_version_id=:id''' + (" AND v.status='published' AND t.is_active" if public else ''), id=version_id)
        version['tasks'] = rows(c, 'SELECT * FROM sop_tasks WHERE sop_version_id=:id ORDER BY sequence_no', id=version_id)
        return version

    @router.get('/admin/sop-versions/{version_id}')
    def admin_version(version_id: int, user=Depends(admin)):
        with engine.connect() as c:
            return version_data(c, version_id)

    @router.patch('/admin/sop-versions/{version_id}')
    def patch_version(version_id: int, body: VersionPatch, user=Depends(admin)):
        with transaction() as c:
            draft(c, version_id)
            return one(c, '''UPDATE sop_versions SET version_notes=:notes,updated_at=CURRENT_TIMESTAMP,updated_by=:actor
                WHERE sop_version_id=:id RETURNING *''', notes=body.version_notes,actor=user['user_id'],id=version_id)

    @router.post('/admin/sop-versions/{version_id}/tasks', status_code=201)
    def create_sop_task(version_id: int, body: TaskDefinition, user=Depends(admin)):
        with transaction() as c:
            draft(c, version_id)
            task = one(c, '''INSERT INTO sop_tasks(sop_version_id,sequence_no,title,instructions,task_type,schedule_type,offset_days,crop_stage_key,condition_text,service_category_id,service_category_name_snapshot,phase,created_by,updated_by)
                VALUES(:version,:sequence_no,:title,:instructions,:task_type,:schedule_type,:offset_days,:crop_stage_key,:condition_text,:service_category_id,:service_name,:phase,:actor,:actor) RETURNING *''',
                **body.model_dump(),service_name=service_name(c,body.service_category_id),version=version_id,actor=user['user_id'])
            touch_version(c, version_id, user)
            return task

    @router.patch('/admin/sop-tasks/{task_id}')
    def patch_sop_task(task_id: int, body: TaskPatch, user=Depends(admin)):
        with transaction() as c:
            ref = one(c, 'SELECT sop_version_id FROM sop_tasks WHERE sop_task_id=:id', id=task_id)
            draft(c, ref['sop_version_id'])
            saved = one(c, 'SELECT * FROM sop_tasks WHERE sop_task_id=:id', id=task_id)
            try:
                definition = TaskDefinition.model_validate({**{key:saved[key] for key in SNAPSHOT_FIELDS}, **body.model_dump(exclude_unset=True)})
            except ValidationError as exc:
                raise HTTPException(422, '; '.join(error['msg'] for error in exc.errors())) from exc
            task = one(c, '''UPDATE sop_tasks SET sequence_no=:sequence_no,title=:title,instructions=:instructions,task_type=:task_type,
                schedule_type=:schedule_type,offset_days=:offset_days,crop_stage_key=:crop_stage_key,condition_text=:condition_text,service_category_id=:service_category_id,service_category_name_snapshot=:service_name,phase=:phase,
                updated_at=CURRENT_TIMESTAMP,updated_by=:actor WHERE sop_task_id=:id RETURNING *''', **definition.model_dump(),service_name=(saved['service_category_name_snapshot'] if definition.service_category_id==saved['service_category_id'] else service_name(c,definition.service_category_id)),actor=user['user_id'],id=task_id)
            touch_version(c, ref['sop_version_id'], user)
            return task

    @router.delete('/admin/sop-tasks/{task_id}', status_code=204)
    def delete_sop_task(task_id: int, user=Depends(admin)):
        with transaction() as c:
            ref = one(c, 'SELECT sop_version_id FROM sop_tasks WHERE sop_task_id=:id', id=task_id)
            draft(c, ref['sop_version_id'])
            c.execute(text('DELETE FROM sop_tasks WHERE sop_task_id=:id'), {'id':task_id})
            touch_version(c, ref['sop_version_id'], user)
        return Response(status_code=204)

    @router.post('/admin/sop-versions/{version_id}/publish')
    def publish(version_id: int, user=Depends(admin)):
        with transaction() as c:
            template, version = locked_version(c, version_id)
            if version['status'] == 'published':
                return version
            if version['status'] != 'draft' or not template['is_active']:
                raise HTTPException(409, 'Only a draft in an active template can be published.')
            tasks = rows(c, 'SELECT * FROM sop_tasks WHERE sop_version_id=:id', id=version_id)
            if not tasks:
                raise HTTPException(422, 'Add at least one task before publication.')
            if any(t['schedule_type'] != 'days_after_planting' and t['phase'] is None for t in tasks):
                raise HTTPException(422, 'Choose a task phase before publishing a season, stage, condition or manual schedule.')
            return one(c, '''UPDATE sop_versions SET status='published',published_at=CURRENT_TIMESTAMP,published_by=:actor,
                updated_at=CURRENT_TIMESTAMP,updated_by=:actor WHERE sop_version_id=:id RETURNING *''', actor=user['user_id'],id=version_id)

    @router.post('/admin/sop-versions/{version_id}/retire')
    def retire(version_id: int, user=Depends(admin)):
        with transaction() as c:
            _, version = locked_version(c, version_id)
            if version['status'] == 'retired':
                return version
            if version['status'] != 'published':
                raise HTTPException(409, 'Only a published version can be retired.')
            return one(c, '''UPDATE sop_versions SET status='retired',retired_at=CURRENT_TIMESTAMP,retired_by=:actor,
                updated_at=CURRENT_TIMESTAMP,updated_by=:actor WHERE sop_version_id=:id RETURNING *''',actor=user['user_id'],id=version_id)

    @router.get('/sop-templates')
    def discover(crop_id: int | None = None, user=Depends(farmer)):
        with engine.connect() as c:
            return rows(c, '''SELECT t.*,cr.crop_name FROM sop_templates t JOIN crops cr USING(crop_id)
                WHERE t.is_active AND EXISTS(SELECT 1 FROM sop_versions v WHERE v.sop_template_id=t.sop_template_id AND v.status='published')'''
                + (' AND t.crop_id=:crop' if crop_id is not None else '') + ' ORDER BY t.name', crop=crop_id)

    @router.get('/sop-templates/{template_id}/versions')
    def published_versions(template_id: int, user=Depends(farmer)):
        with engine.connect() as c:
            one(c, 'SELECT sop_template_id FROM sop_templates WHERE sop_template_id=:id AND is_active', id=template_id)
            return rows(c, "SELECT * FROM sop_versions WHERE sop_template_id=:id AND status='published' ORDER BY version_number DESC", id=template_id)

    @router.get('/sop-versions/{version_id}')
    def preview(version_id: int, user=Depends(farmer)):
        with engine.connect() as c:
            return version_data(c, version_id, public=True)

    @router.get('/my/crop-cycles')
    def list_cycles(farm_id: int | None = None, plot_id: int | None = None, crop_id: int | None = None,
                    status: CycleStatus | None = None, view: Literal['current','history'] | None = None,
                    limit: int = Query(20,ge=1,le=100), offset: int = Query(0,ge=0), user=Depends(farmer)):
        filters = {'farm_id':farm_id,'plot_id':plot_id,'crop_id':crop_id,'status':status}
        where = ''.join(f' AND fc.{key}=:{key}' for key,value in filters.items() if value is not None)
        if view == 'current':where += " AND fc.status IN ('planned','active')"
        elif view == 'history':where += " AND fc.status NOT IN ('planned','active')"
        with engine.connect() as c:
            ids = rows(c, 'SELECT fc.farm_crop_id FROM farm_crops fc JOIN farms f USING(farm_id) WHERE f.farmer_id=:actor' + where + ' ORDER BY fc.farm_crop_id DESC LIMIT :limit OFFSET :offset',
                actor=user['user_id'],limit=limit,offset=offset,**filters)
            return [cycle_data(c, owned_cycle(c, r['farm_crop_id'], user)) for r in ids]

    @router.post('/my/farms/{farm_id}/crop-cycles', status_code=201)
    def create_cycle(farm_id: int, body: CycleCreate, user=Depends(farmer)):
        with transaction() as c:
            one(c, 'SELECT farm_id FROM farms WHERE farm_id=:id AND farmer_id=:actor', id=farm_id,actor=user['user_id'])
            validate_plot(c, farm_id, body.plot_id)
            validate_block(c, farm_id, body.plot_id, body.farm_block_id)
            one(c, 'SELECT crop_id FROM crops WHERE crop_id=:id', id=body.crop_id)
            from farm_inputs import prepare_planting
            snapshot = prepare_planting(c, body.crop_id, body.model_dump())
            lifecycle = one(c, 'SELECT lifecycle_type FROM crops WHERE crop_id=:id', id=body.crop_id)['lifecycle_type']
            values = body.model_dump()
            values['season'] = body.season or season_label(body.period_started_on, lifecycle)
            try:
                validate_season_dates(body.period_started_on, body.planted_on or body.expected_planting_on, body.expected_harvest_on, lifecycle == 'perennial')
                check_dates(body.expected_planting_on, body.expected_harvest_on)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            return one(c, '''INSERT INTO farm_crops(farm_id,plot_id,farm_block_id,crop_id,season,status,planted_on,expected_harvest_on,period_started_on,expected_planting_on,created_at,updated_at,created_by,updated_by,
                crop_variety_id,planting_material_source_id,seed_or_material_lot,variety_text,planting_snapshot)
                VALUES(:farm,:plot_id,:farm_block_id,:crop_id,:season,:status,:planted_on,:expected_harvest_on,:period_started_on,:expected_planting_on,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,:actor,:actor,
                :crop_variety_id,:planting_material_source_id,:seed_or_material_lot,:variety_text,CAST(:snapshot AS jsonb)) RETURNING *''',
                **values,snapshot=json.dumps(snapshot) if snapshot else None,farm=farm_id,actor=user['user_id'])

    @router.get('/my/crop-cycles/{cycle_id}')
    def get_cycle(cycle_id: int, user=Depends(farmer)):
        with engine.connect() as c:
            return cycle_data(c, owned_cycle(c, cycle_id, user))

    @router.patch('/my/crop-cycles/{cycle_id}')
    def patch_cycle(cycle_id: int, body: CyclePatch, user=Depends(farmer)):
        updates = body.model_dump(exclude_unset=True)
        if any(updates.get(k,'absent') is None for k in ('plot_id','crop_id')):
            raise HTTPException(422, 'Crop and plot cannot be null.')
        with transaction() as c:
            current = owned_cycle(c, cycle_id, user, True)
            if current['status'] in ('harvested','cancelled'):
                raise HTTPException(409, 'A closed crop cycle cannot be edited.')
            if rows(c, 'SELECT plan_id FROM crop_cycle_plans WHERE farm_crop_id=:id', id=cycle_id) and any(k in updates and updates[k] != current[k] for k in ('plot_id','crop_id','farm_block_id')):
                raise HTTPException(409, 'Crop and plot cannot change after plan generation.')
            from farm_inputs import prepare_planting
            planting = {**current, **updates}
            snapshot = prepare_planting(c, planting['crop_id'], planting, current)
            if ('period_started_on' in updates and 'season' not in updates and
                    (not current['season'] or current['season'] == season_label(current['period_started_on'], current['lifecycle_type']))):
                updates['season'] = season_label(updates['period_started_on'], current['lifecycle_type'])
            current.update(updates)
            validate_plot(c, current['farm_id'], current['plot_id'])
            if any(k in updates for k in ('farm_block_id','plot_id')):
                validate_block(c, current['farm_id'], current['plot_id'], current['farm_block_id'])
            one(c, 'SELECT crop_id FROM crops WHERE crop_id=:id', id=current['crop_id'])
            try:
                validate_season_dates(current['period_started_on'], current['planted_on'] or current['expected_planting_on'], current['expected_harvest_on'], current['lifecycle_type'] == 'perennial')
                check_dates(current['expected_planting_on'], current['expected_harvest_on'])
                plans = rows(c, 'SELECT anchor_date FROM crop_cycle_plans WHERE farm_crop_id=:id', id=cycle_id)
                check_dates(current['planted_on'] or (plans[0]['anchor_date'] if plans else None), current['expected_harvest_on'])
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            return one(c, '''UPDATE farm_crops SET plot_id=:plot,farm_block_id=:block,crop_id=:crop,season=:season,expected_harvest_on=:harvest,period_started_on=:started,expected_planting_on=:expected,
                crop_variety_id=:variety,planting_material_source_id=:source,seed_or_material_lot=:lot,variety_text=:fallback,planting_snapshot=CAST(:snapshot AS jsonb),
                updated_at=clock_timestamp(),updated_by=:actor WHERE farm_crop_id=:id RETURNING *''',
                variety=current['crop_variety_id'],source=current['planting_material_source_id'],lot=current['seed_or_material_lot'],fallback=current['variety_text'],snapshot=json.dumps(snapshot) if snapshot else None,
                plot=current['plot_id'],block=current['farm_block_id'],crop=current['crop_id'],season=current['season'],harvest=current['expected_harvest_on'],started=current['period_started_on'],expected=current['expected_planting_on'],actor=user['user_id'],id=cycle_id)

    @router.post('/my/crop-cycles/{cycle_id}/status')
    def cycle_status(cycle_id: int, body: CycleTransition, user=Depends(farmer)):
        with transaction() as c:
            cycle = owned_cycle(c, cycle_id, user, True)
            if cycle['status'] == body.status:
                if body.planted_on and body.planted_on != cycle['planted_on']:
                    raise HTTPException(409, 'Planting date conflicts with the saved transition.')
                return cycle_data(c, cycle)
            if cycle['status'] != body.expected_status or body.status not in CYCLE_TRANSITIONS.get(cycle['status'], set()):
                raise HTTPException(409, 'Crop status changed or transition is not allowed. Refresh and retry.')
            planted = cycle['planted_on']
            if body.status == 'active':
                if not body.planted_on:
                    raise HTTPException(422, 'Enter the actual planting date.')
                planted = body.planted_on
            elif body.planted_on is not None:
                raise HTTPException(422, 'Planting date is only accepted when activating a crop.')
            try:
                if body.status == 'active':
                    check_dates(planted, cycle['expected_harvest_on'])
                    validate_season_dates(cycle['period_started_on'], planted, cycle['expected_harvest_on'], cycle['lifecycle_type'] == 'perennial')
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            if body.status == 'cancelled' and not body.note:
                raise HTTPException(422, 'Explain why the crop cycle is cancelled.')
            c.execute(text('''UPDATE farm_crops SET status=:status,planted_on=:planted,updated_at=CURRENT_TIMESTAMP,updated_by=:actor WHERE farm_crop_id=:id'''),
                {'status':body.status,'planted':planted,'actor':user['user_id'],'id':cycle_id})
            if body.status in ('harvested','cancelled'):
                note = ('System: Crop cycle was harvested before this task was completed.' if body.status == 'harvested'
                        else 'System: Crop cycle cancelled. ' + body.note)
                close_unfinished_tasks(c, cycle_id, user['user_id'], note)
            return cycle_data(c, owned_cycle(c, cycle_id, user))

    @router.get('/my/crop-cycles/{cycle_id}/plan')
    def get_plan(cycle_id: int, user=Depends(farmer)):
        with engine.connect() as c:
            plan = plan_data(c, owned_cycle(c, cycle_id, user))
            if not plan:
                raise HTTPException(404, 'No crop plan has been generated yet.')
            return plan

    @router.post('/my/crop-cycles/{cycle_id}/plan', status_code=201)
    def generate(cycle_id: int, body: PlanCreate, response: Response, user=Depends(farmer)):
        with transaction() as c:
            cycle = owned_cycle(c, cycle_id, user, True)
            existing = plan_data(c, cycle)
            if body.anchor_date is None and not cycle['period_started_on']:
                raise HTTPException(422, 'An explicit planting date is required for a legacy planting-based plan.')
            if existing:
                if existing['sop_version_id'] != body.sop_version_id or (body.anchor_date is not None and existing['anchor_date'] != body.anchor_date):
                    raise HTTPException(409, 'This cycle already has a plan with different settings.')
                response.status_code = 200
                return existing
            if cycle['status'] not in ('planned','active'):
                raise HTTPException(409, 'Only planned or active crops can receive a plan.')
            validate_plot(c, cycle['farm_id'], cycle['plot_id'])
            template, version = locked_version(c, body.sop_version_id)
            if template['crop_id'] != cycle['crop_id']:
                raise HTTPException(422, 'The SOP must match this crop.')
            if not template['is_active'] or version['status'] != 'published':
                raise HTTPException(409, 'Choose a published version from an active SOP.')
            anchor = body.anchor_date or cycle['planted_on'] or cycle['expected_planting_on']
            if cycle['status'] == 'planned' and cycle['expected_planting_on'] and anchor != cycle['expected_planting_on']:
                raise HTTPException(422, 'Use the saved expected planting date or correct it before generation.')
            if cycle['status'] == 'active' and cycle['planted_on'] and anchor != cycle['planted_on']:
                raise HTTPException(422, 'Use the actual planting date for this active crop.')
            tasks = rows(c, 'SELECT * FROM sop_tasks WHERE sop_version_id=:id ORDER BY sequence_no', id=body.sop_version_id)
            if not tasks:
                raise HTTPException(422, 'The SOP must contain at least one task.')
            if any(t['phase'] is not None for t in tasks) and not cycle['period_started_on']:
                raise HTTPException(422, 'Record season start before generating a season plan.')
            try:
                check_dates(anchor, cycle['expected_harvest_on'])
                validate_season_dates(cycle['period_started_on'], anchor, cycle['expected_harvest_on'], cycle['lifecycle_type'] == 'perennial')
                dates = [task_due(t, cycle['period_started_on'], anchor, cycle['expected_harvest_on']) for t in tasks]
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            plan = one(c, '''INSERT INTO crop_cycle_plans(farm_crop_id,sop_version_id,anchor_date,season_start_snapshot,expected_harvest_snapshot,sop_template_name_snapshot,sop_version_number_snapshot,generated_by)
                VALUES(:cycle,:version,:anchor,:start,:harvest,:name,:number,:actor) RETURNING *''',
                cycle=cycle_id,version=body.sop_version_id,anchor=anchor,start=cycle['period_started_on'],harvest=cycle['expected_harvest_on'],name=template['name'],number=version['version_number'],actor=user['user_id'])
            for task, due in zip(tasks, dates):
                c.execute(text('''INSERT INTO crop_tasks(plan_id,source_sop_task_id,sequence_no,title,instructions,task_type,schedule_type,offset_days,crop_stage_key,condition_text,service_category_id,service_category_name_snapshot,phase,due_date,created_by,updated_by)
                    VALUES(:plan,:source,:sequence_no,:title,:instructions,:task_type,:schedule_type,:offset_days,:crop_stage_key,:condition_text,:service_category_id,:service_name,:phase,:due,:actor,:actor)'''),
                    {**{k:task[k] for k in SNAPSHOT_FIELDS},'plan':plan['plan_id'],'source':task['sop_task_id'],'service_name':task['service_category_name_snapshot'],'due':due,'actor':user['user_id']})
            return plan_data(c, cycle)

    @router.get('/my/crop-tasks')
    def list_tasks(cycle_id: int | None = None, status: TaskStatus | None = None,
                   due_from: date | None = None, due_to: date | None = None,
                   limit: int = Query(20,ge=1,le=100), offset: int = Query(0,ge=0), user=Depends(farmer)):
        conditions = [('p.farm_crop_id=:cycle', cycle_id), ('ct.status=:status',status),('ct.due_date>=:start',due_from),('ct.due_date<=:end',due_to)]
        where = ''.join(' AND '+sql for sql,value in conditions if value is not None)
        with engine.connect() as c:
            tasks = rows(c, '''SELECT ct.*,fc.status AS cycle_status,p.farm_crop_id FROM crop_tasks ct JOIN crop_cycle_plans p USING(plan_id)
                JOIN farm_crops fc USING(farm_crop_id) JOIN farms f USING(farm_id) WHERE f.farmer_id=:actor''' + where +
                ' ORDER BY ct.due_date NULLS LAST,ct.sequence_no,ct.crop_task_id LIMIT :limit OFFSET :offset',
                actor=user['user_id'],cycle=cycle_id,status=status,start=due_from,end=due_to,limit=limit,offset=offset)
            for task in tasks:
                task['is_overdue'] = is_overdue(task,task['cycle_status'])
            return tasks

    def task_cycle(c, task_id, user, lock=False):
        ref = one(c, '''SELECT p.farm_crop_id FROM crop_tasks ct JOIN crop_cycle_plans p USING(plan_id)
            JOIN farm_crops fc USING(farm_crop_id) JOIN farms f USING(farm_id)
            WHERE ct.crop_task_id=:id AND f.farmer_id=:actor''', id=task_id,actor=user['user_id'])
        cycle = owned_cycle(c, ref['farm_crop_id'], user, lock)
        task = one(c, 'SELECT * FROM crop_tasks WHERE crop_task_id=:id' + (' FOR UPDATE' if lock else ''), id=task_id)
        task['is_overdue'] = is_overdue(task,cycle['status'])
        return cycle, task

    @router.get('/my/crop-tasks/{task_id}')
    def get_task(task_id: int, user=Depends(farmer)):
        with engine.connect() as c:
            return task_cycle(c, task_id, user)[1]

    @router.post('/my/crop-tasks/{task_id}/status')
    def task_status(task_id: int, body: TaskTransition, user=Depends(farmer)):
        with transaction() as c:
            cycle, task = task_cycle(c, task_id, user, True)
            if task['status'] == body.status and task['status_note'] == body.status_note:
                return task
            if cycle['status'] != 'active' and not (cycle['status'] == 'planned' and task['phase'] is not None):
                raise HTTPException(409, 'Tasks require an active crop or a planned season task.')
            if task['status'] != body.expected_status or body.status not in TASK_TRANSITIONS.get(task['status'],set()):
                raise HTTPException(409, 'Task status changed or transition is not allowed. Refresh and retry.')
            if body.status in ('partial','not_applicable','cancelled') and not body.status_note:
                raise HTTPException(422, 'A note is required for this status.')
            one(c, '''UPDATE crop_tasks SET status=CAST(:status AS varchar),status_note=:note,updated_at=CURRENT_TIMESTAMP,updated_by=:actor,
                completed_at=CASE WHEN CAST(:status AS varchar)='completed' THEN CURRENT_TIMESTAMP ELSE NULL END,
                completed_by=CASE WHEN CAST(:status AS varchar)='completed' THEN :actor ELSE NULL END WHERE crop_task_id=:id RETURNING *''',
                status=body.status,note=body.status_note,actor=user['user_id'],id=task_id)
            return task_cycle(c,task_id,user)[1]

    return router


def close_unfinished_tasks(c, cycle_id, actor, note):
    c.execute(text('''UPDATE crop_tasks SET status='cancelled',
        status_note=CASE WHEN status_note IS NULL THEN :note ELSE status_note || E'\n' || :note END,
        updated_at=CURRENT_TIMESTAMP,updated_by=:actor
        WHERE plan_id IN (SELECT plan_id FROM crop_cycle_plans WHERE farm_crop_id=:id)
        AND status IN ('pending','in_progress','partial')'''), {'note':note,'actor':actor,'id':cycle_id})
