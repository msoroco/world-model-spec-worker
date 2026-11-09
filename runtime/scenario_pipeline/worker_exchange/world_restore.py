"""Restore an operator-owned world. No allocation or server lifecycle operations."""
import hashlib,math

def fields(obj):
    return {k:getattr(obj,k) for k in dir(obj) if not k.startswith('_') and isinstance(getattr(obj,k),(bool,int,float,str,type(None)))}
def snapshot(client):
    world=client.get_world();mapping=world.get_map();name=mapping.name
    maps=client.get_available_maps()
    packaged=next((p for p in maps if p==name),None)
    return {'name':name,'packaged':packaged,'opendrive':mapping.to_opendrive(),
            'settings':world.get_settings(),'weather':world.get_weather()}
def equal(actual,expected):
    if isinstance(expected,float):return isinstance(actual,(int,float)) and math.isclose(actual,expected,rel_tol=1e-6,abs_tol=1e-6)
    return actual==expected

def restore(client,saved):
    if saved['packaged'] is not None:client.load_world(saved['packaged'])
    else:client.generate_opendrive_world(saved['opendrive'])
    world=client.get_world();world.apply_settings(saved['settings']);world.set_weather(saved['weather'])
    actual=world.get_map().to_opendrive()
    if actual!=saved['opendrive']:raise ValueError('Restored OpenDRIVE readback differs')
    for key,obj in [('settings',world.get_settings()),('weather',world.get_weather())]:
        current=fields(obj)
        if any(not equal(current.get(k),v) for k,v in fields(saved[key]).items()):raise ValueError('Restored '+key+' readback differs')
    return {'restored':True,'map':world.get_map().name,'opendrive_sha256':hashlib.sha256(actual.encode()).hexdigest(),'settings':fields(world.get_settings()),'weather':fields(world.get_weather())}
