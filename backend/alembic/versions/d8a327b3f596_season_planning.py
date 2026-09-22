"""Season planning using existing farm_crops production periods."""
from alembic import op
from sqlalchemy import text

revision = 'd8a327b3f596'
down_revision = 'c7f216a2e485'
branch_labels = None
depends_on = None

RELATIVE = "'days_after_season_start','days_before_planting','days_after_planting','days_before_harvest'"


def scheduling_constraints(extended=True):
    relative = RELATIVE if extended else "'days_after_planting','days_before_harvest'"
    for table in ('sop_tasks', 'crop_tasks'):
        names = op.get_bind().execute(text("SELECT conname FROM pg_constraint WHERE conrelid=CAST(:table AS regclass) AND contype='c' AND (pg_get_constraintdef(oid) LIKE '%schedule_type%' OR pg_get_constraintdef(oid) LIKE '%crop_stage_key%')"), {'table': table}).scalars().all()
        for name in names:
            op.execute(f'ALTER TABLE {table} DROP CONSTRAINT "{name.replace(chr(34), chr(34)*2)}"')
        op.execute(f"""ALTER TABLE {table} ADD CONSTRAINT {table}_schedule_fields CHECK(
          (schedule_type IN ({relative}) AND offset_days IS NOT NULL AND offset_days>=0 AND crop_stage_key IS NULL AND condition_text IS NULL)
          OR (schedule_type='crop_stage' AND offset_days IS NULL AND crop_stage_key IS NOT NULL AND length(trim(crop_stage_key))>0 AND condition_text IS NULL)
          OR (schedule_type='condition' AND offset_days IS NULL AND crop_stage_key IS NULL AND condition_text IS NOT NULL AND length(trim(condition_text))>0)
          OR (schedule_type='manual' AND offset_days IS NULL AND crop_stage_key IS NULL AND condition_text IS NULL))""")
    op.execute(f"ALTER TABLE crop_tasks ADD CONSTRAINT crop_tasks_schedule_date CHECK(schedule_type NOT IN ({relative}) OR due_date IS NOT NULL)")


def publication_guard(extended):
    # Preserve the full original identity/retirement guard; change only its publication predicate.
    definition = op.get_bind().execute(text("SELECT pg_get_functiondef('cm_protect_version()'::regprocedure)")).scalar_one()
    old = "schedule_type<>'days_after_planting'"
    new = "schedule_type<>'days_after_planting' AND phase IS NULL"
    definition = definition.replace(old, new) if extended else definition.replace(new, old)
    op.execute(definition)


def upgrade_planning():
    """Also used by the existing isolated Slice 1 concurrency fixture."""
    for table in ('sop_tasks', 'crop_tasks'):
        op.execute(f"ALTER TABLE {table} ADD COLUMN phase varchar(20) CHECK(phase IN ('pre_season','planting','crop_stage','harvest','miscellaneous'))")
    scheduling_constraints()
    publication_guard(True)
    op.execute("""ALTER TABLE crop_cycle_plans ALTER COLUMN anchor_date DROP NOT NULL,
      ADD COLUMN season_start_snapshot date, ADD COLUMN expected_harvest_snapshot date;
      CREATE FUNCTION season_snapshot_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF TG_TABLE_NAME='crop_cycle_plans' THEN
          IF to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD) THEN
            RAISE EXCEPTION 'Generated plan is immutable' USING ERRCODE='23514'; END IF;
        ELSIF (to_jsonb(NEW)-ARRAY['status','status_note','completed_at','completed_by','updated_at','updated_by'])
          IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','status_note','completed_at','completed_by','updated_at','updated_by']) THEN
          RAISE EXCEPTION 'Generated task snapshot is immutable' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER season_plan_snapshot BEFORE UPDATE ON crop_cycle_plans FOR EACH ROW EXECUTE FUNCTION season_snapshot_guard();
      CREATE TRIGGER season_task_snapshot BEFORE UPDATE ON crop_tasks FOR EACH ROW EXECUTE FUNCTION season_snapshot_guard();
      ALTER TABLE crop_tasks ADD CONSTRAINT phased_undated_task CHECK(phase IS NULL OR schedule_type IN
        ('days_after_season_start','days_before_planting','days_after_planting','days_before_harvest') OR due_date IS NULL);
    """)


def upgrade():
    # period_started_on already exists. No historical values or labels are inferred.
    op.execute('ALTER TABLE farm_crops ADD COLUMN expected_planting_on date')
    upgrade_planning()
    op.execute("""CREATE FUNCTION season_dates_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE perennial boolean;
      BEGIN
        IF TG_OP='UPDATE' AND ROW(NEW.period_started_on,NEW.expected_planting_on,NEW.expected_harvest_on,NEW.planted_on,NEW.crop_id)
          IS NOT DISTINCT FROM ROW(OLD.period_started_on,OLD.expected_planting_on,OLD.expected_harvest_on,OLD.planted_on,OLD.crop_id) THEN RETURN NEW; END IF;
        SELECT lifecycle_type='perennial' INTO perennial FROM crops WHERE crop_id=NEW.crop_id;
        IF NEW.period_started_on IS NOT NULL AND
          ((NEW.expected_harvest_on IS NOT NULL AND NEW.expected_harvest_on<=NEW.period_started_on)
          OR (NOT coalesce(perennial,false) AND coalesce(NEW.planted_on,NEW.expected_planting_on)<NEW.period_started_on)) THEN
          RAISE EXCEPTION 'Invalid season date order' USING ERRCODE='23514'; END IF;
        IF NEW.expected_planting_on IS NOT NULL AND NEW.expected_harvest_on<=NEW.expected_planting_on THEN
          RAISE EXCEPTION 'Expected harvest must follow expected planting' USING ERRCODE='23514'; END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER season_dates_guard BEFORE INSERT OR UPDATE ON farm_crops FOR EACH ROW EXECUTE FUNCTION season_dates_guard();""")


def downgrade():
    c = op.get_bind()
    if any(c.execute(text(q)).scalar() for q in (
        'SELECT EXISTS(SELECT 1 FROM farm_crops WHERE expected_planting_on IS NOT NULL OR (period_started_on IS NOT NULL AND perennial_planting_id IS NULL))',
        'SELECT EXISTS(SELECT 1 FROM sop_tasks WHERE phase IS NOT NULL)',
        'SELECT EXISTS(SELECT 1 FROM crop_tasks WHERE phase IS NOT NULL)',
        'SELECT EXISTS(SELECT 1 FROM crop_cycle_plans WHERE anchor_date IS NULL OR season_start_snapshot IS NOT NULL OR expected_harvest_snapshot IS NOT NULL)')):
        raise RuntimeError('Refusing to discard season planning history.')
    op.execute('DROP TRIGGER season_dates_guard ON farm_crops; DROP FUNCTION season_dates_guard(); ALTER TABLE farm_crops DROP COLUMN expected_planting_on')
    publication_guard(False)
    scheduling_constraints(False)
    op.execute('''DROP TRIGGER season_plan_snapshot ON crop_cycle_plans;
      DROP TRIGGER season_task_snapshot ON crop_tasks; DROP FUNCTION season_snapshot_guard();
      ALTER TABLE crop_tasks DROP CONSTRAINT IF EXISTS phased_undated_task, DROP COLUMN phase;
      ALTER TABLE sop_tasks DROP COLUMN phase;
      ALTER TABLE crop_cycle_plans DROP COLUMN season_start_snapshot,DROP COLUMN expected_harvest_snapshot,ALTER COLUMN anchor_date SET NOT NULL;''')
