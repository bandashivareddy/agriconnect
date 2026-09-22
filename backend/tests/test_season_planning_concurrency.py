from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from test_crop_management_concurrency import concurrent_cm
from test_field_work_concurrency import race


def configured(cm):
    cm['ok']('PATCH',f"/admin/sop-tasks/{cm['task']['sop_task_id']}",{'phase':'pre_season','schedule_type':'days_after_season_start'})
    cm['ok']('POST',f"/admin/sop-versions/{cm['version']['sop_version_id']}/publish")
    base=f"/my/crop-cycles/{cm['cycle']['farm_crop_id']}"
    cm['ok']('PATCH',base,{'period_started_on':'2025-12-01'})
    return base,{'sop_version_id':cm['version']['sop_version_id']}


def test_season_plan_generation_race(concurrent_cm):
    cm=concurrent_cm; base,body=configured(cm)
    results=race([lambda:cm['client'].post(base+'/plan',json=body) for _ in range(2)])
    assert sorted(r.status_code for r in results)==[200,201]
    assert results[0].json()['plan_id']==results[1].json()['plan_id']
    assert len(results[0].json()['tasks'])==1


def test_generation_and_date_correction_race(concurrent_cm):
    cm=concurrent_cm; base,body=configured(cm)
    results=race([lambda:cm['client'].post(base+'/plan',json=body),lambda:cm['client'].patch(base,json={'period_started_on':'2025-11-01'})])
    assert [r.status_code for r in results]==[201,200]
    p=results[0].json()
    assert p['tasks'][0]['due_date']==p['season_start_snapshot']
    assert p['season_start_snapshot'] in ('2025-12-01','2025-11-01')


def test_populated_season_downgrade_refused(concurrent_cm):
    cm=concurrent_cm; configured(cm)
    path=Path(__file__).resolve().parents[1]/'alembic/versions/d8a327b3f596_season_planning.py'
    spec=spec_from_file_location('season_downgrade',path); m=module_from_spec(spec); spec.loader.exec_module(m)
    with cm['engine'].begin() as c, Operations.context(MigrationContext.configure(c)):
        with pytest.raises(RuntimeError,match='Refusing'):
            m.downgrade()
