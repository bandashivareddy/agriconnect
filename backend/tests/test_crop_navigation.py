from test_crop_management import cm
from test_farm_ledger import block


def test_current_history_filter_before_pagination(cm):
    planned=cm.cycle();active=cm.cycle(status='active',planted_on='2026-01-01')
    harvested=cm.cycle(status='active',planted_on='2026-01-01');cancelled=cm.cycle()
    cm.ok('POST',f"/my/crop-cycles/{harvested['farm_crop_id']}/status",{'expected_status':'active','status':'harvested'})
    cm.ok('POST',f"/my/crop-cycles/{cancelled['farm_crop_id']}/status",{'expected_status':'planned','status':'cancelled','note':'Not planted'})
    current=cm.ok('GET','/my/crop-cycles?view=current');history=cm.ok('GET','/my/crop-cycles?view=history')
    assert {r['farm_crop_id'] for r in current}=={planned['farm_crop_id'],active['farm_crop_id']}
    assert {r['farm_crop_id'] for r in history}=={harvested['farm_crop_id'],cancelled['farm_crop_id']}
    assert cm.ok('GET','/my/crop-cycles?view=current&limit=1&offset=1')[0]['farm_crop_id']==planned['farm_crop_id']
    assert cm.ok('GET','/my/crop-cycles?view=history&limit=1&offset=1')[0]['farm_crop_id']==harvested['farm_crop_id']
    assert len(cm.ok('GET','/my/crop-cycles'))==4


def test_view_filters_preserve_ownership_and_status_filter(cm):
    cm.cycle();cm.cycle(status='active',planted_on='2026-01-01')
    assert len(cm.ok('GET','/my/crop-cycles?view=current&status=planned'))==1
    assert cm.ok('GET','/my/crop-cycles?view=history&status=planned')==[]
    assert cm.ok('GET','/my/crop-cycles?view=current',as_user=cm.other)==[]
    assert cm.call('GET','/my/crop-cycles?view=history',as_user=cm.provider).status_code==403
    assert cm.call('GET','/my/crop-cycles?view=unknown').status_code==422


def test_block_names_in_crop_cards_and_detail_optional(cm):
    b=block(cm);crop=cm.cycle(farm_block_id=b['farm_block_id']);plain=cm.cycle()
    detail=cm.ok('GET',f"/my/crop-cycles/{crop['farm_crop_id']}")
    assert detail['block_name']=='North block'
    listed={r['farm_crop_id']:r for r in cm.ok('GET','/my/crop-cycles?view=current')}
    assert listed[crop['farm_crop_id']]['block_name']=='North block'
    assert listed[plain['farm_crop_id']]['block_name'] is None
