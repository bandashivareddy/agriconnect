from uuid import uuid4
from test_crop_management_concurrency import concurrent_cm
from test_field_work_concurrency import fc, race
from test_farm_ledger_concurrency import ledger
from test_crop_inputs_concurrency import catalogue


def test_concurrent_case_insensitive_crop_create(catalogue):
    c=catalogue;name='Catalogue '+uuid4().hex
    responses=race([lambda:c['call']('POST','/admin/crops',{'crop_name':name}),
                    lambda:c['call']('POST','/admin/crops',{'crop_name':name.upper()})])
    assert sorted(r.status_code for r in responses)==[201,409]
