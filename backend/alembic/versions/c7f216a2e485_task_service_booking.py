"""Optional task requirements and links into the existing booking/ledger engine."""
from alembic import op
from sqlalchemy import text

revision = 'c7f216a2e485'
down_revision = 'b6e105f1d374'
branch_labels = None
depends_on = None


def upgrade_task_requirements():
    for table in ('sop_tasks','crop_tasks'):
        op.execute(f'''ALTER TABLE {table} ADD COLUMN service_category_id integer REFERENCES service_categories ON DELETE RESTRICT,
          ADD COLUMN service_category_name_snapshot varchar(100),
          ADD CONSTRAINT {table}_service_pair CHECK((service_category_id IS NULL)=(service_category_name_snapshot IS NULL));''')
    op.execute('''CREATE FUNCTION task_service_snapshot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF ROW(NEW.service_category_id,NEW.service_category_name_snapshot) IS DISTINCT FROM ROW(OLD.service_category_id,OLD.service_category_name_snapshot) THEN
          RAISE EXCEPTION 'Generated service requirement is immutable' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER task_service_snapshot_guard BEFORE UPDATE ON crop_tasks FOR EACH ROW EXECUTE FUNCTION task_service_snapshot_guard();''')


def source_check(with_task):
    return """CHECK((source_type='manual' AND crop_task_id IS NULL AND field_visit_id IS NULL AND service_booking_id IS NULL)
      OR (source_type='crop_task' AND crop_task_id IS NOT NULL AND field_visit_id IS NULL AND service_booking_id IS NULL)
      OR (source_type='field_visit' AND field_visit_id IS NOT NULL AND service_booking_id IS NULL)
      OR (source_type='service_booking' AND service_booking_id IS NOT NULL AND field_visit_id IS NULL""" + ('' if with_task else ' AND crop_task_id IS NULL') + '))'


def upgrade():
    upgrade_task_requirements()
    op.execute('''ALTER TABLE bookings ADD COLUMN crop_task_id integer REFERENCES crop_tasks ON DELETE RESTRICT,
      ADD COLUMN crop_context_snapshot jsonb, ADD COLUMN crop_request_key uuid, ADD COLUMN crop_request_payload jsonb,
      ADD CONSTRAINT booking_crop_pair CHECK((crop_task_id IS NULL AND crop_context_snapshot IS NULL AND crop_request_key IS NULL AND crop_request_payload IS NULL)
        OR (crop_task_id IS NOT NULL AND crop_context_snapshot IS NOT NULL AND crop_request_key IS NOT NULL AND crop_request_payload IS NOT NULL AND farm_id IS NOT NULL));
      CREATE UNIQUE INDEX booking_crop_retry ON bookings(farmer_id,crop_request_key) WHERE crop_request_key IS NOT NULL;
      CREATE INDEX booking_crop_task ON bookings(crop_task_id) WHERE crop_task_id IS NOT NULL;
      CREATE UNIQUE INDEX activity_one_task_booking ON farm_activities(service_booking_id) WHERE crop_task_id IS NOT NULL AND service_booking_id IS NOT NULL;''')
    names=op.get_bind().execute(text("SELECT conname FROM pg_constraint WHERE conrelid='farm_activities'::regclass AND contype='c' AND pg_get_constraintdef(oid) LIKE '%source_type%'")).scalars().all()
    for name in names:op.execute('ALTER TABLE farm_activities DROP CONSTRAINT "'+name.replace('"','""')+'"')
    op.execute('ALTER TABLE farm_activities ADD CONSTRAINT activity_source_scope '+source_check(True))
    op.execute("""
    CREATE FUNCTION booking_crop_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE r record;
    BEGIN
      IF TG_OP='UPDATE' THEN
        IF ROW(NEW.crop_task_id,NEW.crop_context_snapshot,NEW.crop_request_key,NEW.crop_request_payload) IS DISTINCT FROM ROW(OLD.crop_task_id,OLD.crop_context_snapshot,OLD.crop_request_key,OLD.crop_request_payload)
          OR (OLD.crop_task_id IS NOT NULL AND ROW(NEW.farm_id,NEW.farmer_id,NEW.supplier_id) IS DISTINCT FROM ROW(OLD.farm_id,OLD.farmer_id,OLD.supplier_id)) THEN
          RAISE EXCEPTION 'Booking crop origin is immutable' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END IF;
      IF NEW.crop_task_id IS NOT NULL THEN
        SELECT fc.*,f.farmer_id,t.status task_status,t.service_category_id INTO r FROM crop_tasks t
          JOIN crop_cycle_plans p USING(plan_id) JOIN farm_crops fc USING(farm_crop_id) JOIN farms f USING(farm_id)
          WHERE t.crop_task_id=NEW.crop_task_id FOR UPDATE OF fc,t;
        IF NOT FOUND OR r.farm_id<>NEW.farm_id OR r.farmer_id<>NEW.farmer_id OR r.status NOT IN ('planned','active')
          OR r.task_status NOT IN ('pending','in_progress','partial') OR r.service_category_id IS NULL
          OR (NEW.crop_context_snapshot->>'farm_crop_id')::integer IS DISTINCT FROM r.farm_crop_id
          OR (NEW.crop_context_snapshot->>'plot_id')::integer IS DISTINCT FROM r.plot_id
          OR (NEW.crop_context_snapshot->>'farm_block_id')::integer IS DISTINCT FROM r.farm_block_id THEN
          RAISE EXCEPTION 'Booking must match an actionable owned crop task' USING ERRCODE='23514';
        END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER booking_crop_guard BEFORE INSERT OR UPDATE ON bookings FOR EACH ROW EXECUTE FUNCTION booking_crop_guard();
    CREATE FUNCTION booking_task_item_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE required integer;
    BEGIN
      SELECT t.service_category_id INTO required FROM bookings b JOIN crop_tasks t USING(crop_task_id) WHERE b.booking_id=NEW.booking_id;
      IF required IS NOT NULL AND NOT EXISTS(SELECT 1 FROM supplier_services WHERE supplier_service_id=NEW.supplier_service_id AND category_id=required) THEN
        RAISE EXCEPTION 'Service must match task category' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER booking_task_item_guard BEFORE INSERT OR UPDATE ON booking_items FOR EACH ROW EXECUTE FUNCTION booking_task_item_guard();
    CREATE FUNCTION activity_task_booking_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE r record;
    BEGIN
      IF NEW.service_booking_id IS NOT NULL THEN
        SELECT b.*,p.farm_crop_id INTO r FROM bookings b LEFT JOIN crop_tasks t USING(crop_task_id)
          LEFT JOIN crop_cycle_plans p USING(plan_id) WHERE b.booking_id=NEW.service_booking_id;
        IF r.crop_task_id IS NOT NULL OR NEW.crop_task_id IS NOT NULL THEN
          IF NEW.source_type<>'service_booking' OR r.crop_task_id IS DISTINCT FROM NEW.crop_task_id OR r.farm_crop_id IS DISTINCT FROM NEW.farm_crop_id
            OR r.status<>'completed' OR r.farmer_id<>NEW.created_by THEN
            RAISE EXCEPTION 'Work must match a completed owned task booking' USING ERRCODE='23514';
          END IF;
          IF TG_OP='INSERT' AND NOT EXISTS(SELECT 1 FROM farm_crops WHERE farm_crop_id=NEW.farm_crop_id AND status IN ('planned','active')) THEN
            RAISE EXCEPTION 'Confirm booked work in a current crop season' USING ERRCODE='23514';
          END IF;
        END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER activity_task_booking_guard BEFORE INSERT OR UPDATE ON farm_activities FOR EACH ROW EXECUTE FUNCTION activity_task_booking_guard();
    """)


def downgrade():
    c=op.get_bind()
    if any(c.execute(text(f'SELECT EXISTS(SELECT 1 FROM {t} WHERE {column} IS NOT NULL)')).scalar() for t,column in [('bookings','crop_task_id'),('sop_tasks','service_category_id'),('crop_tasks','service_category_id')]):
        raise RuntimeError('Refusing to discard task service history.')
    op.execute('''DROP TRIGGER activity_task_booking_guard ON farm_activities; DROP FUNCTION activity_task_booking_guard();
      DROP TRIGGER booking_task_item_guard ON booking_items; DROP FUNCTION booking_task_item_guard();
      DROP TRIGGER booking_crop_guard ON bookings; DROP FUNCTION booking_crop_guard();
      DROP INDEX activity_one_task_booking;
      ALTER TABLE farm_activities DROP CONSTRAINT activity_source_scope;''')
    op.execute('ALTER TABLE farm_activities ADD CONSTRAINT activity_source_scope '+source_check(False))
    op.execute('''ALTER TABLE bookings DROP COLUMN crop_task_id,DROP COLUMN crop_context_snapshot,DROP COLUMN crop_request_key,DROP COLUMN crop_request_payload;
      DROP TRIGGER task_service_snapshot_guard ON crop_tasks; DROP FUNCTION task_service_snapshot_guard();
      ALTER TABLE sop_tasks DROP COLUMN service_category_id,DROP COLUMN service_category_name_snapshot;
      ALTER TABLE crop_tasks DROP COLUMN service_category_id,DROP COLUMN service_category_name_snapshot;''')
