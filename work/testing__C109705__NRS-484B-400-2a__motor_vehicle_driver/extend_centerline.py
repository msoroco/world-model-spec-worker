import importlib.util,json,pathlib,copy,xml.etree.ElementTree as ET
P=pathlib.Path(__file__).with_name('package_builder.py');m=importlib.util.spec_from_file_location('b',P);b=importlib.util.module_from_spec(m);m.loader.exec_module(b);ROOT=b.ROOT
for aid in json.load(open(ROOT/'partitions/demo-test-01.json'))['assignment_ids'][:2]:
 p=ROOT/'work'/aid/'package-spec.json';s=json.load(open(p))
 if len(s['cases'])>2:continue
 original=copy.deepcopy(s['cases']);s['runner']=s['runner'].replace("'two_way':True", "'centerline_definition':cfg.get('centerline_definition','marked'),'road_edges_width_m':14,'two_way':True")
 s['analysis']=s['analysis'].replace("return {'two_way':bool(road['two_way'])", "return {'centerline_definition':road.get('centerline_definition','marked'),'road_edges_width_m':road.get('road_edges_width_m',14),'two_way':bool(road['two_way'])")
 for c in s['cases']:c['config']['centerline_definition']='marked';c['fixture']['road_geometry.json']['centerline_definition']='marked';c['fixture']['road_geometry.json']['road_edges_width_m']=14
 for c in original:
  c['name']='imaginary_'+c['name'];c['config']['centerline_definition']='imaginary_equidistant';c['fixture']['road_geometry.json']['centerline_definition']='imaginary_equidistant';c['fixture']['road_geometry.json']['road_edges_width_m']=14
  t=ET.fromstring((ROOT/'references/v6-capability'/aid/'scene.xodr').read_text())
  for center in t.findall('.//center/lane'):
   for mark in list(center.findall('roadMark')):center.remove(mark)
  c['scene']=ET.tostring(t,encoding='unicode');s['cases'].append(c)
 comp=copy.deepcopy(s['comparisons'][0]);comp['comparison_id']='imaginary_'+comp['comparison_id'];comp['cases']=['imaginary_'+x for x in comp['cases']];comp['fixed_conditions'].append('No marked centerline; equidistant road edge reference fixed');s['comparisons'].append(comp)
 branch=copy.deepcopy(s['branches'][0]);branch['name']='imaginary-'+branch['name'];branch['cases']=['imaginary_'+x for x in branch['cases']];branch['comparison_ids']=['imaginary_'+x for x in branch['comparison_ids']];s['branches'].append(branch)
 b.write(p,s);b.build(s)
