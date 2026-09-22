"""Live reconciliation and repeat seasons reusing the existing crop execution record."""
import json
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from crop_management import Payload, close_unfinished_tasks
from harvest_management import harvest_summary
from season_planning import season_label, next_season_start


class Completion(Payload):
    note: str | None = Field(default=None, max_length=2000)


class SeasonIdentity(Payload):
    season: str | None = Field(default=None, min_length=1, max_length=50)
    period_started_on: date


class SeasonCreate(SeasonIdentity):
    request_key: UUID
    expected_harvest_on: date | None = None


def reconciliation(c, cycle):
    result = harvest_summary(c, cycle['farm_crop_id'])
    for q in result['quantities']:
        q['remaining_quantity'] = Decimal(str(q['total_harvested_quantity'])) - Decimal(str(q['total_sold_quantity'])) - Decimal(str(q['total_wastage']))
    return {**result, 'farm_crop_id': cycle['farm_crop_id'], 'status': cycle['status'],
            'perennial_planting_id': cycle['perennial_planting_id'],
            'completed_at': cycle['completed_at'], 'completed_by': cycle['completed_by'],
            'completion_note': cycle['completion_note'],
            'completion_action': 'Close Season' if cycle['perennial_planting_id'] else
                ('Complete Production Period' if cycle.get('crop_group') == 'vegetable' else 'Complete Crop')}


def create_lifecycle_router(engine, get_current_user, get_effective_capabilities):
    router = APIRouter(tags=['Production lifecycle'])

    def rows(c, sql, **params):
        return [dict(r) for r in c.execute(text(sql), params).mappings()]

    def one(c, sql, **params):
        result = rows(c, sql, **params)
        if not result: raise HTTPException(404, 'Record not found.')
        return result[0]

    @contextmanager
    def tx():
        try:
            with engine.begin() as c: yield c
        except IntegrityError as exc:
            raise HTTPException(409, 'This conflicts with saved crop or season history. Refresh and retry.') from exc

    def require(capability):
        def dependency(user=Depends(get_current_user)):
            with engine.connect() as c:
                if capability not in get_effective_capabilities(c, user['user_id'], user['user_role']):
                    raise HTTPException(403, f'{capability} access is required.')
            return user
        return dependency

    farmer = require('farmer')

    def cycle(c, id, user, admin=False, lock=False):
        return one(c, '''SELECT fc.*,cr.crop_group,cr.lifecycle_type FROM farm_crops fc
            JOIN farms f USING(farm_id) JOIN crops cr USING(crop_id) WHERE fc.farm_crop_id=:id'''
            + ('' if admin else ' AND f.farmer_id=:actor') + (' FOR UPDATE OF fc' if lock else ''), id=id, actor=user['user_id'])

    def planting(c, id, user, lock=False):
        return one(c, '''SELECT p.*,fc.farm_id,fc.crop_id,fc.plot_id,fc.farm_block_id,fc.planted_on,
          f.farm_name,cr.crop_name,fp.plot_name,fb.name AS block_name
          FROM perennial_plantings p JOIN farm_crops fc ON fc.farm_crop_id=p.source_farm_crop_id
          JOIN farms f USING(farm_id) JOIN crops cr USING(crop_id)
          LEFT JOIN farm_plots fp ON fp.plot_id=fc.plot_id LEFT JOIN farm_blocks fb ON fb.farm_block_id=fc.farm_block_id
          WHERE p.perennial_planting_id=:id AND f.farmer_id=:actor''' + (' FOR UPDATE OF p' if lock else ''), id=id, actor=user['user_id'])

    def periods(c, id):
        return rows(c, '''SELECT farm_crop_id,season,period_started_on,status,completed_at,completed_by FROM farm_crops
            WHERE perennial_planting_id=:id ORDER BY period_started_on DESC,farm_crop_id DESC''', id=id)

    def register(prefix, admin):
        access = require('admin' if admin else 'farmer')

        @router.get(prefix + '/crop-cycles/{cycle_id}/reconciliation')
        def preview(cycle_id: int, user=Depends(access)):
            with engine.connect() as c:
                return reconciliation(c, cycle(c, cycle_id, user, admin))

        @router.post(prefix + '/crop-cycles/{cycle_id}/complete')
        def complete(cycle_id: int, body: Completion, user=Depends(access)):
            with tx() as c:
                saved = cycle(c, cycle_id, user, admin, True)
                if saved['status'] == 'harvested':
                    return reconciliation(c, saved)  # Never fabricate audit on old closed records.
                if saved['status'] != 'active':
                    raise HTTPException(409, 'Only an active crop or season can be completed.')
                if saved['lifecycle_type'] == 'perennial' and not saved['perennial_planting_id']:
                    raise HTTPException(422, 'Enable seasons for this planting before closing its season.')
                one(c, '''UPDATE farm_crops SET status='harvested',completed_at=clock_timestamp(),completed_by=:actor,
                    completion_note=:note,updated_at=clock_timestamp(),updated_by=:actor WHERE farm_crop_id=:id RETURNING farm_crop_id''',
                    id=cycle_id, actor=user['user_id'], note=body.note)
                close_unfinished_tasks(c, cycle_id, user['user_id'],
                    'System: Crop season closed before this task was completed.' if saved['perennial_planting_id'] else
                    'System: Crop cycle was harvested before this task was completed.')
                return reconciliation(c, cycle(c, cycle_id, user, admin))

    register('/my', False)
    register('/admin', True)

    @router.post('/my/crop-cycles/{cycle_id}/enable-seasons', status_code=201)
    def enable_seasons(cycle_id: int, body: SeasonIdentity, response: Response, user=Depends(farmer)):
        with tx() as c:
            saved = cycle(c, cycle_id, user, lock=True)
            name = body.season or season_label(body.period_started_on, 'perennial')
            if saved['perennial_planting_id']:
                if saved['season'] != name or saved['period_started_on'] != body.period_started_on:
                    raise HTTPException(409, 'Seasons are already enabled with different details.')
                response.status_code = 200
                return planting(c, saved['perennial_planting_id'], user)
            if saved['lifecycle_type'] != 'perennial' or saved['status'] not in ('active','harvested') or not saved['planted_on']:
                raise HTTPException(422, 'Choose an established perennial crop with its actual planting date.')
            if body.period_started_on < saved['planted_on']:
                raise HTTPException(422, 'Season start cannot precede planting.')
            p = one(c, '''INSERT INTO perennial_plantings(source_farm_crop_id,created_by)
                VALUES(:id,:actor) RETURNING *''', id=cycle_id, actor=user['user_id'])
            c.execute(text('''UPDATE farm_crops SET perennial_planting_id=:p,season=:season,period_started_on=:started,
                updated_at=clock_timestamp(),updated_by=:actor WHERE farm_crop_id=:id'''),
                dict(p=p['perennial_planting_id'], season=name, started=body.period_started_on, actor=user['user_id'], id=cycle_id))
            return planting(c, p['perennial_planting_id'], user)

    @router.get('/my/perennial-plantings')
    def list_plantings(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), user=Depends(farmer)):
        with engine.connect() as c:
            ids = rows(c, '''SELECT p.perennial_planting_id FROM perennial_plantings p
                JOIN farm_crops fc ON fc.farm_crop_id=p.source_farm_crop_id JOIN farms f USING(farm_id)
                WHERE f.farmer_id=:actor ORDER BY p.perennial_planting_id DESC LIMIT :limit OFFSET :offset''', actor=user['user_id'], limit=limit, offset=offset)
            return [planting(c, r['perennial_planting_id'], user) for r in ids]

    @router.get('/my/perennial-plantings/{planting_id}')
    def get_planting(planting_id: int, user=Depends(farmer)):
        with engine.connect() as c:
            saved = planting(c, planting_id, user)
            history = periods(c, planting_id)
            proposal = None
            if history:
                try:
                    started = next_season_start(max(s['period_started_on'] for s in history))
                    proposal = {'period_started_on': started, 'season': season_label(started, 'perennial')}
                except ValueError:
                    pass
            return {**saved, 'seasons': history, 'next_season': proposal}

    @router.post('/my/perennial-plantings/{planting_id}/seasons', status_code=201)
    def new_season(planting_id: int, body: SeasonCreate, response: Response, user=Depends(farmer)):
        with tx() as c:
            # A planting serializes all new periods, including concurrent distinct request keys.
            p = planting(c, planting_id, user, True)
            payload = {**body.model_dump(mode='json'), 'perennial_planting_id': planting_id}
            key = str(body.request_key)
            c.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'), {'key':f"season:{user['user_id']}:{key}"})
            existing = rows(c, 'SELECT * FROM farm_crops WHERE created_by=:actor AND period_request_key=:key', actor=user['user_id'], key=key)
            if existing:
                if existing[0]['period_request_payload'] != payload:
                    raise HTTPException(409, 'Request key already used with different details.')
                response.status_code = 200
                return {k:v for k,v in existing[0].items() if k != 'period_request_payload'}
            history = periods(c, planting_id)
            if any(s['status'] in ('active','planned') for s in history):
                raise HTTPException(409, 'Close the current season before starting another.')
            if body.period_started_on <= max(s['period_started_on'] for s in history):
                raise HTTPException(422, 'The new season must start after the previous season started.')
            if body.expected_harvest_on and body.expected_harvest_on <= body.period_started_on:
                raise HTTPException(422, 'Expected harvest must be after the season starts.')
            result = one(c, '''INSERT INTO farm_crops(farm_id,plot_id,farm_block_id,crop_id,planted_on,
                crop_variety_id,planting_material_source_id,seed_or_material_lot,variety_text,planting_snapshot,
                status,season,period_started_on,perennial_planting_id,expected_harvest_on,
                period_request_key,period_request_payload,created_at,updated_at,created_by,updated_by)
                SELECT farm_id,plot_id,farm_block_id,crop_id,planted_on,crop_variety_id,planting_material_source_id,
                seed_or_material_lot,variety_text,planting_snapshot,'active',:season,:started,:p,:harvest,
                :key,CAST(:payload AS jsonb),clock_timestamp(),clock_timestamp(),:actor,:actor
                FROM farm_crops WHERE farm_crop_id=:source RETURNING *''',
                season=body.season or season_label(body.period_started_on, 'perennial'), started=body.period_started_on, p=planting_id, harvest=body.expected_harvest_on,
                key=key, payload=json.dumps(payload), actor=user['user_id'], source=p['source_farm_crop_id'])
            return {k:v for k,v in result.items() if k != 'period_request_payload'}

    return router
