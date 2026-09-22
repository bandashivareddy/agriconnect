"""Crop-scoped harvests and sales. Costs remain in farm_expenses."""
import json
from contextlib import contextmanager
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from crop_management import Payload

Unit = Literal['kg', 'g', 'tonne', 'quintal', 'unit', 'crate', 'box', 'bag', 'bunch']


class HarvestFields(Payload):
    harvested_on: date
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=4)
    unit: Unit
    grade: str | None = Field(default=None, max_length=100)
    wastage_quantity: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    notes: str | None = None

    @model_validator(mode='after')
    def wastage_limit(self):
        if self.wastage_quantity is not None and self.wastage_quantity > self.quantity:
            raise ValueError('Wastage cannot exceed harvested quantity.')
        return self


class HarvestCreate(HarvestFields):
    request_key: UUID


class HarvestUpdate(HarvestFields):
    expected_updated_at: AwareDatetime


class SaleFields(Payload):
    quantity_sold: Decimal = Field(gt=0, max_digits=14, decimal_places=4)
    unit: Unit
    price_per_unit: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=4)
    total_amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    buyer_name: str | None = Field(default=None, max_length=200)
    sold_on: date
    notes: str | None = None

    @model_validator(mode='after')
    def amount(self):
        if self.price_per_unit is None and self.total_amount is None:
            raise ValueError('Enter a total amount or price per unit.')
        if self.price_per_unit is not None:
            calculated = (self.quantity_sold * self.price_per_unit).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            if not 0 < calculated < Decimal('1000000000000'):
                raise ValueError('Calculated sale amount is outside the supported range.')
            if self.total_amount is not None and self.total_amount != calculated:
                raise ValueError('Total must equal quantity × price, rounded to two decimal places.')
            self.total_amount = calculated
        return self


class SaleCreate(SaleFields):
    request_key: UUID


class SaleUpdate(SaleFields):
    expected_updated_at: AwareDatetime


def create_harvest_router(engine, get_current_user, get_effective_capabilities):
    router = APIRouter(tags=['Harvests and revenue'])

    def rows(c, sql, **params):
        return [dict(row) for row in c.execute(text(sql), params).mappings()]

    def one(c, sql, **params):
        result = rows(c, sql, **params)
        if not result:
            raise HTTPException(404, 'Record not found.')
        return result[0]

    @contextmanager
    def tx():
        try:
            with engine.begin() as c:
                yield c
        except IntegrityError as exc:
            raise HTTPException(409, 'This conflicts with saved harvest or sale records. Refresh and check quantities, dates and units.') from exc

    def require(capability):
        def dependency(user=Depends(get_current_user)):
            with engine.connect() as c:
                if capability not in get_effective_capabilities(c, user['user_id'], user['user_role']):
                    raise HTTPException(403, f'{capability} access is required.')
            return user
        return dependency

    def cycle(c, cycle_id, user, admin, lock=False):
        return one(c, '''SELECT fc.* FROM farm_crops fc JOIN farms f USING(farm_id)
            WHERE fc.farm_crop_id=:id''' + ('' if admin else ' AND f.farmer_id=:actor') +
            (' FOR UPDATE OF fc' if lock else ''), id=cycle_id, actor=user['user_id'])

    def harvest(c, cycle_id, event_id, lock=False):
        return one(c, 'SELECT * FROM harvest_events WHERE farm_crop_id=:cycle AND harvest_event_id=:id' +
                   (' FOR UPDATE' if lock else ''), cycle=cycle_id, id=event_id)

    def clean(record):
        return {k: v for k, v in record.items() if k != 'request_payload'}

    def create(c, table, body, scope, user, response):
        # Scope is included in the original payload, so keys cannot be replayed on another crop/harvest.
        payload = {**body.model_dump(mode='json'), **scope}
        key = str(body.request_key)
        c.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'),
                  {'key': f"harvest:{table}:{user['user_id']}:{key}"})
        existing = rows(c, f'SELECT * FROM {table} WHERE created_by=:actor AND request_key=:key', actor=user['user_id'], key=key)
        if existing:
            if existing[0]['request_payload'] != payload:
                raise HTTPException(409, 'Request key was already used with different details.')
            response.status_code = 200
            return clean(existing[0])
        data = {**body.model_dump(), **scope, 'request_key': key, 'request_payload': json.dumps(payload),
                'created_by': user['user_id'], 'updated_by': user['user_id']}
        columns = ','.join(data)
        values = ','.join('CAST(:request_payload AS jsonb)' if k == 'request_payload' else ':' + k for k in data)
        return clean(one(c, f'INSERT INTO {table}({columns}) VALUES({values}) RETURNING *', **data))

    def edit(c, table, idcol, saved, body, user):
        if saved['updated_at'] != body.expected_updated_at:
            raise HTTPException(409, 'Record changed. Refresh before editing.')
        data = body.model_dump(exclude={'expected_updated_at'})
        return clean(one(c, f'UPDATE {table} SET ' + ','.join(k + '=:' + k for k in data) +
                         f',updated_at=clock_timestamp(),updated_by=:actor WHERE {idcol}=:id RETURNING *',
                         **data, actor=user['user_id'], id=saved[idcol]))

    # Separate namespaces keep farmer ownership and explicit admin access unambiguous.
    def register(prefix, admin):
        access = require('admin' if admin else 'farmer')
        base = prefix + '/crop-cycles/{cycle_id}'

        @router.get(base + '/harvests')
        def list_harvests(cycle_id: int, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), user=Depends(access)):
            with engine.connect() as c:
                cycle(c, cycle_id, user, admin)
                items = rows(c, '''SELECT h.*,coalesce(s.sold,0) AS quantity_sold,
                    h.quantity-coalesce(h.wastage_quantity,0)-coalesce(s.sold,0) AS available_quantity,
                    coalesce(s.revenue,0) AS total_revenue FROM harvest_events h
                    LEFT JOIN LATERAL (SELECT sum(quantity_sold) sold,sum(total_amount) revenue FROM harvest_sales
                    WHERE harvest_event_id=h.harvest_event_id) s ON true WHERE h.farm_crop_id=:id
                    ORDER BY h.harvested_on DESC,h.harvest_event_id DESC LIMIT :limit OFFSET :offset''', id=cycle_id, limit=limit, offset=offset)
                return [clean(item) for item in items]

        @router.post(base + '/harvests', status_code=201)
        def add_harvest(cycle_id: int, body: HarvestCreate, response: Response, user=Depends(access)):
            with tx() as c:
                ref = cycle(c, cycle_id, user, admin, True)
                scope = {k: ref[k] for k in ('farm_crop_id', 'farm_id', 'plot_id', 'farm_block_id')}
                return create(c, 'harvest_events', body, scope, user, response)

        @router.get(base + '/harvests/{event_id}')
        def get_harvest(cycle_id: int, event_id: int, user=Depends(access)):
            with engine.connect() as c:
                cycle(c, cycle_id, user, admin)
                return clean(harvest(c, cycle_id, event_id))

        @router.put(base + '/harvests/{event_id}')
        def update_harvest(cycle_id: int, event_id: int, body: HarvestUpdate, user=Depends(access)):
            with tx() as c:
                cycle(c, cycle_id, user, admin, True)
                saved = harvest(c, cycle_id, event_id, True)
                return edit(c, 'harvest_events', 'harvest_event_id', saved, body, user)

        @router.get(base + '/harvests/{event_id}/sales')
        def list_sales(cycle_id: int, event_id: int, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), user=Depends(access)):
            with engine.connect() as c:
                cycle(c, cycle_id, user, admin)
                harvest(c, cycle_id, event_id)
                return [clean(item) for item in rows(c, '''SELECT * FROM harvest_sales WHERE harvest_event_id=:id
                    ORDER BY sold_on DESC,harvest_sale_id DESC LIMIT :limit OFFSET :offset''', id=event_id, limit=limit, offset=offset)]

        @router.post(base + '/harvests/{event_id}/sales', status_code=201)
        def add_sale(cycle_id: int, event_id: int, body: SaleCreate, response: Response, user=Depends(access)):
            with tx() as c:
                cycle(c, cycle_id, user, admin, True)
                harvest(c, cycle_id, event_id, True)
                return create(c, 'harvest_sales', body, {'harvest_event_id': event_id}, user, response)

        @router.put(base + '/harvests/{event_id}/sales/{sale_id}')
        def update_sale(cycle_id: int, event_id: int, sale_id: int, body: SaleUpdate, user=Depends(access)):
            with tx() as c:
                cycle(c, cycle_id, user, admin, True)
                harvest(c, cycle_id, event_id, True)
                saved = one(c, 'SELECT * FROM harvest_sales WHERE harvest_sale_id=:id AND harvest_event_id=:event FOR UPDATE', id=sale_id, event=event_id)
                return edit(c, 'harvest_sales', 'harvest_sale_id', saved, body, user)

        @router.get(base + '/harvest-summary')
        def summary(cycle_id: int, user=Depends(access)):
            with engine.connect() as c:
                cycle(c, cycle_id, user, admin)
                return harvest_summary(c, cycle_id)

    register('/my', False)
    register('/admin', True)
    return router


def harvest_summary(c, cycle_id):
    # Independent aggregates avoid multiplying revenue/expenses by the number of harvests.
    result = dict(c.execute(text( '''WITH h AS (SELECT * FROM harvest_events WHERE farm_crop_id=:id),
      quantities AS (SELECT unit,sum(quantity) total_harvested_quantity,
        sum(coalesce(wastage_quantity,0)) total_wastage FROM h GROUP BY unit),
      sales AS (SELECT s.unit,sum(s.quantity_sold) total_sold_quantity,sum(s.total_amount) revenue
        FROM harvest_sales s JOIN h USING(harvest_event_id) GROUP BY s.unit),
      q AS (SELECT q.*,coalesce(s.total_sold_quantity,0) total_sold_quantity
        FROM quantities q LEFT JOIN sales s USING(unit))
      SELECT coalesce((SELECT jsonb_agg(to_jsonb(q) ORDER BY unit) FROM q),'[]'::jsonb) quantities,
        coalesce((SELECT sum(revenue) FROM sales),0) total_revenue,
        coalesce((SELECT sum(amount) FROM farm_expenses WHERE farm_crop_id=:id),0) total_expenses'''), {'id':cycle_id}).mappings().one())
    return {**result, 'net_return': result['total_revenue'] - result['total_expenses'], 'currency': 'INR'}
