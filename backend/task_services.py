"""Optional links into the existing marketplace, without a second booking engine."""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text


def task_context(c, task_id, actor, lock=False):
    # Lock cultivation before task, matching task status and crop completion handlers.
    ref=c.execute(text('''SELECT fc.farm_crop_id FROM crop_tasks t JOIN crop_cycle_plans p USING(plan_id)
      JOIN farm_crops fc USING(farm_crop_id) JOIN farms f USING(farm_id)
      WHERE t.crop_task_id=:id AND f.farmer_id=:actor''' + (' FOR UPDATE OF fc' if lock else '')),dict(id=task_id,actor=actor)).scalar()
    if ref is None:raise HTTPException(404,'Crop task not found.')
    row=c.execute(text('''SELECT t.crop_task_id,t.title,t.task_type,t.due_date,t.status AS task_status,
      t.service_category_id,t.service_category_name_snapshot,fc.farm_crop_id,fc.farm_id,fc.plot_id,fc.farm_block_id,
      fc.status AS cycle_status,fc.season,f.farm_name,cr.crop_name,fp.plot_name,fb.name AS block_name
      FROM crop_tasks t JOIN crop_cycle_plans p USING(plan_id) JOIN farm_crops fc USING(farm_crop_id)
      JOIN farms f USING(farm_id) JOIN crops cr USING(crop_id)
      LEFT JOIN farm_plots fp ON fp.plot_id=fc.plot_id LEFT JOIN farm_blocks fb ON fb.farm_block_id=fc.farm_block_id
      WHERE t.crop_task_id=:id''' + (' FOR UPDATE OF t' if lock else '')),dict(id=task_id)).mappings().one()
    result=dict(row)
    result['can_book']=result['cycle_status'] in ('planned','active') and result['task_status'] in ('pending','in_progress','partial') and bool(result['service_category_id'])
    return result


def prepare_task_booking(c, body, actor):
    if body.crop_task_id is None:
        if body.crop_request_key is not None:raise HTTPException(422,'A task is required with a crop booking request key.')
        return None,None
    if body.crop_request_key is None:raise HTTPException(422,'A request key is required for task bookings.')
    context=task_context(c,body.crop_task_id,actor,True)
    if body.farm_id is not None and body.farm_id!=context['farm_id']:
        raise HTTPException(422,'Booking farm must match the crop task.')
    body.farm_id=context['farm_id']
    payload=body.model_dump(mode='json')
    key=str(body.crop_request_key)
    c.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'),{'key':f'task-booking:{actor}:{key}'})
    saved=c.execute(text('SELECT * FROM bookings WHERE farmer_id=:actor AND crop_request_key=:key'),dict(actor=actor,key=key)).mappings().first()
    if saved:
        if saved['crop_request_payload']!=payload:raise HTTPException(409,'Request key already used with different booking details.')
        return None,{k:saved[k] for k in ('booking_id','booking_number','status','total_amount','crop_task_id','crop_context_snapshot')}
    if not context['can_book']:raise HTTPException(409,'This task is not available for a new service booking.')
    category=c.execute(text('''SELECT ss.category_id FROM supplier_services ss JOIN service_categories sc USING(category_id)
      WHERE ss.supplier_service_id=:id AND sc.is_active'''),{'id':body.supplier_service_id}).scalar()
    if category!=context['service_category_id']:raise HTTPException(422,'Choose a service in the task’s required category.')
    return {'crop_task_id':body.crop_task_id,'crop_context_snapshot':json.dumps(context,default=str),
            'crop_request_key':key,'crop_request_payload':json.dumps(payload)},None


def validate_booked_activity(c,data,actor):
    """Called by the ordinary ledger create flow after context/ownership validation."""
    booking=c.execute(text('SELECT * FROM bookings WHERE booking_id=:id FOR UPDATE'),{'id':data['service_booking_id']}).mappings().first()
    if not booking:raise HTTPException(404,'Booking not found.')
    if booking['crop_task_id'] is None and data.get('crop_task_id') is None:return
    if booking['farmer_id']!=actor or booking['crop_task_id']!=data.get('crop_task_id'):
        raise HTTPException(404,'Task booking not found.')
    if booking['status']!='completed':raise HTTPException(409,'Confirm work after the provider completes the booking.')
    state=c.execute(text('SELECT status FROM farm_crops WHERE farm_crop_id=:id'),{'id':data['farm_crop_id']}).scalar()
    if state not in ('planned','active'):raise HTTPException(409,'Confirm service work in a current crop season.')
    if c.execute(text('SELECT activity_id FROM farm_activities WHERE service_booking_id=:id AND crop_task_id IS NOT NULL'),{'id':booking['booking_id']}).first():
        raise HTTPException(409,'Work is already confirmed for this booking. Open the saved activity to correct it.')


def create_task_service_router(engine,get_current_user,get_effective_capabilities):
    router=APIRouter(tags=['Crop task services'])
    def farmer(user=Depends(get_current_user)):
        with engine.connect() as c:
            if 'farmer' not in get_effective_capabilities(c,user['user_id'],user['user_role']):raise HTTPException(403,'Farmer access is required.')
        return user

    @router.get('/my/crop-tasks/{task_id}/service-context')
    def context(task_id:int,user=Depends(farmer)):
        with engine.connect() as c:return task_context(c,task_id,user['user_id'])

    @router.get('/my/crop-tasks/{task_id}/bookings')
    def bookings(task_id:int,user=Depends(farmer)):
        with engine.connect() as c:
            task_context(c,task_id,user['user_id'])
            result=c.execute(text('''SELECT b.booking_id,b.booking_number,b.status,b.requested_start_at,b.requested_end_at,
              b.total_amount,b.payment_status,b.crop_context_snapshot,sp.business_name AS supplier_name,
              a.activity_id,(SELECT count(*) FROM farm_expenses e WHERE e.activity_id=a.activity_id) AS expense_count
              FROM bookings b JOIN supplier_profiles sp ON sp.supplier_id=b.supplier_id
              LEFT JOIN farm_activities a ON a.service_booking_id=b.booking_id AND a.crop_task_id=b.crop_task_id
              WHERE b.crop_task_id=:id AND b.farmer_id=:actor ORDER BY b.booking_id DESC'''),dict(id=task_id,actor=user['user_id'])).mappings()
            return [dict(r) for r in result]
    return router
