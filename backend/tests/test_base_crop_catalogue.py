from uuid import uuid4
import pytest
from test_crop_management import cm


def test_admin_create_farmer_catalogue_and_metadata(cm):
    before=cm.sql('SELECT * FROM crops ORDER BY crop_id').all()
    name='New crop '+uuid4().hex
    crop=cm.ok('POST','/admin/crops',{'crop_name':'  '+name+'  '},cm.admin,201)
    assert crop['crop_name']==name and crop['lifecycle_type'] is None
    assert any(c['crop_id']==crop['crop_id'] for c in cm.ok('GET','/crops'))
    assert any(c['crop_id']==crop['crop_id'] for c in cm.ok('GET','/catalogue/crops?q='+name))
    metadata={'crop_group':'orchard','lifecycle_type':'perennial','harvest_pattern':'recurring'}
    saved=cm.ok('PUT',f"/admin/crops/{crop['crop_id']}/metadata",metadata,cm.admin)
    assert all(saved[k]==v for k,v in metadata.items())
    cycle=cm.cycle(crop_id=crop['crop_id'],status='active',planted_on='2020-01-01')
    p=cm.ok('POST',f"/my/crop-cycles/{cycle['farm_crop_id']}/enable-seasons",{'season':'2026','period_started_on':'2026-01-01'},code=201)
    assert p['crop_id']==crop['crop_id']
    assert before==cm.sql('SELECT * FROM crops WHERE crop_id<>:id ORDER BY crop_id',id=crop['crop_id']).all()


@pytest.mark.parametrize('variant',['same','case','spaces'])
def test_duplicate_crop(cm,variant):
    name='Catalogue '+uuid4().hex
    cm.ok('POST','/admin/crops',{'crop_name':name},cm.admin,201)
    duplicate=name.upper() if variant=='case' else '  '+name+'  ' if variant=='spaces' else name
    assert cm.call('POST','/admin/crops',{'crop_name':duplicate},cm.admin).status_code==409
    assert cm.sql('SELECT count(*) FROM crops WHERE lower(crop_name)=lower(:name)',name=name).scalar_one()==1


def test_create_authorization(cm,client):
    body={'crop_name':'Unauthorized '+uuid4().hex}
    assert client.post('/admin/crops',json=body).status_code==401
    for user in (cm.farmer,cm.other,cm.provider):
        assert cm.call('POST','/admin/crops',body,user).status_code==403
    cm.sql("INSERT INTO user_capabilities(user_id,capability) VALUES(:id,'admin')",id=cm.other['user_id'])
    cm.ok('POST','/admin/crops',body,cm.other,201)


@pytest.mark.parametrize('body',[{'crop_name':''},{'crop_name':'   '},{'crop_name':'x'*101},{'crop_name':'Valid','status':'active'},{'crop_name':'Valid','lifecycle_type':'perennial'}])
def test_invalid_create(cm,body):
    assert cm.call('POST','/admin/crops',body,cm.admin).status_code==422
