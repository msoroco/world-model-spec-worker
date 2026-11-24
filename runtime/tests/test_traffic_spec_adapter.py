"""Contract tests for observed facts, coordinate conversion and evidence honesty."""
import json
import math
import tempfile
import unittest
from pathlib import Path
from traffic_spec_adapter.adapter import rates, rounded, validate_scene, verify_join, signals, device_record, atom_ids, recorded_traffic_props, live_kinematics
from traffic_spec_adapter.geometry import body, static_map, xy, painted_map_objects, native_centre_lines


def core_fixture_library():
    root = Path(__file__).resolve().parents[1]
    exported = root/'library'
    return exported if exported.is_dir() else root.parent/'repo_prep/nevada_sydney/pipeline/traffic-spec-agent/library'


class AdapterTests(unittest.TestCase):
    def test_highway_arc_fold_uses_source_curvature_centre(self):
        from shapely.geometry import Polygon,Point
        xml='''<OpenDRIVE><road id="1" length="3.5707963267948966"><planView><geometry s="0" x="0" y="0" hdg="0" length="1"><line/></geometry><geometry s="1" x="1" y="0" hdg="0" length="1.5707963267948966"><arc curvature="1"/></geometry><geometry s="2.5707963267948966" x="2" y="1" hdg="1.5707963267948966" length="1"><line/></geometry></planView><lanes><laneSection s="0"><left><lane id="1" type="driving"><width sOffset="0" a="1.2" b="0" c="0" d="0"/></lane></left><right><lane id="-1" type="driving"><width sOffset="0" a="1.2" b="0" c="0" d="0"/></lane></right></laneSection></lanes></road></OpenDRIVE>'''
        with tempfile.TemporaryDirectory()as temp:
            path=Path(temp)/'road.xodr';path.write_text(xml);methods={}
            regions,_,_=static_map(path,public_way_roads=[1],partial=True,source_regions=methods)
            seam_xml=xml.replace('x="2" y="1"','x="2.0002" y="1"').replace('<width sOffset="0" a="1.2" b="0" c="0" d="0"/>','<width sOffset="0" a="1.2" b="0" c="0" d="0"/><width sOffset="1" a="1.20000000000001" b="0" c="0" d="0"/>')
            path.write_text(seam_xml);seam_methods={}
            seam_regions,_,_=static_map(path,public_way_roads=[1],partial=True,source_regions=seam_methods)
            seam_highway=next(r for r in seam_regions if r['kind']=='highway')
            self.assertTrue(Polygon(seam_highway['boundary']).is_valid)
            seam_method=seam_methods[seam_highway['id']]['highway_geometry_method']
            self.assertGreater(seam_method['max_source_seam_displacement_m'],.00019)
            self.assertLessEqual(seam_method['max_source_seam_displacement_m']+seam_method['max_chord_deviation_m'],.001)
            path.write_text(seam_xml.replace('x="2.0002"','x="2.002"'));large_methods={}
            static_map(path,public_way_roads=[1],partial=True,source_regions=large_methods)
            self.assertTrue(next(v for v in large_methods.values()if 'highway_geometry_method'in v)['highway_geometry_method']['unresolved_source_seams'])
        highway=next(r for r in regions if r['kind']=='highway');shape=Polygon(highway['boundary'])
        self.assertTrue(shape.is_valid);self.assertFalse(shape.interiors)
        self.assertTrue(shape.covers(Point(1,1)))
        self.assertFalse(shape.covers(Point(0,-2)))
        method=methods[highway['id']]['highway_geometry_method']
        self.assertGreater(method['fold_intervals'],0)
        self.assertLessEqual(method['max_chord_deviation_m'],.001)

    def test_retained_centre_line_repairs_source_bound_line_preserving_identity(self):
        from traffic_spec_adapter.geometry import retained_centre_line_fields
        xml='''<OpenDRIVE><road id="1" length="10"><planView><geometry s="0" x="0" y="0" hdg="0" length="10"><line/></geometry></planView><lanes><laneSection s="0"><left><lane id="1" type="driving"/></left><right><lane id="-1" type="driving"/></right></laneSection></lanes></road></OpenDRIVE>'''
        report={'inputs':{'map':{'sha256':'verified-map'}},'native_centre_lines':[
            {'region_id':42,'road_id':1,'section_id':0,'native_centerline':[[0,0],[10,0]]}]}
        region={'id':42,'kind':'centre_line','boundary':[[0,0],[5,0],[10,0]],'ways':[7]}
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'road.xodr';path.write_text(xml)
            fields=retained_centre_line_fields(path,[region],report,'verified-map')
            self.assertEqual(set(fields),{42})
            self.assertEqual(region['ways'],[7])
            from shapely.geometry import Polygon
            self.assertAlmostEqual(Polygon(fields[42]['boundary']).area,.1)
            self.assertEqual(fields[42]['_centre_line_source']['geometry_method']['total_width_m'],.01)
            report['native_centre_lines'][0]['method']='Native opposing driving-lane divider; directed increasing source s; <=2m sampling'
            region['boundary']=[[0,0],[5,0.0000001],[10,0]]
            projected=retained_centre_line_fields(path,[region],report,'verified-map')
            self.assertAlmostEqual(Polygon(projected[42]['boundary']).area,.1)
            report['native_centre_lines'][0].pop('method')
            measured=[[0,-.2],[10,-.2],[10,.2],[0,.2]]
            region['boundary']=measured
            self.assertEqual(retained_centre_line_fields(path,[region],report,'verified-map')[42]['boundary'],measured)
            preserved=retained_centre_line_fields(path,[region],report,'verified-map')[42]['_centre_line_source']
            self.assertEqual(preserved['method'],'retained_valid_area_outline')
            self.assertNotIn('geometry_method',preserved)
            with self.assertRaisesRegex(ValueError,'another map'):
                retained_centre_line_fields(path,[region],report,'wrong-map')
            region['boundary']=[[0,2],[10,2]]
            with self.assertRaisesRegex(ValueError,'differs from its source'):
                retained_centre_line_fields(path,[region],report,'verified-map')

    def test_native_centre_line_retains_offset_and_omits_one_way_road(self):
        xml='''<OpenDRIVE><road id="1" length="10"><planView><geometry s="0" x="0" y="0" hdg="0" length="10"><line/></geometry></planView><lanes><laneOffset s="0" a="2" b="0" c="0" d="0"/><laneSection s="0"><left><lane id="1" type="driving"/></left><center><lane id="0"><roadMark type="solid" color="yellow" width="0.12"/></lane></center><right><lane id="-1" type="driving"/></right></laneSection></lanes></road><road id="2" length="10"><planView><geometry s="0" x="0" y="20" hdg="0" length="10"><line/></geometry></planView><lanes><laneSection s="0"><right><lane id="-1" type="driving"/></right></laneSection></lanes></road></OpenDRIVE>'''
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'road.xodr';path.write_text(xml);lines=native_centre_lines(path)
        self.assertEqual(len(lines),1)
        self.assertEqual(lines[0]['source']['native_centerline'][0],[0.,2.])
        self.assertEqual(lines[0]['source']['native_centerline'][-1],[10.,2.])
        self.assertAlmostEqual(lines[0]['shape'].area,.1)
        self.assertEqual(lines[0]['source']['geometry_method']['total_width_m'],.01)
        self.assertEqual(lines[0]['source']['centre_road_marks'][0]['color'],'yellow')

    def test_native_stop_line_does_not_gain_an_invented_width(self):
        xml='<OpenDRIVE><road id="1"><planView><geometry s="0" x="0" y="0" hdg="0" length="20"><line/></geometry></planView><objects><object id="line" name="StopLine" s="5" t="-2" hdg="1.5707963267948966" length="4" width="0"/></objects></road></OpenDRIVE>'
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'road.xodr';path.write_text(xml);objects=painted_map_objects(path)
        line=objects[0]
        self.assertEqual(line['region']['kind'],'stop_line')
        self.assertEqual(line['shape'].geom_type,'LineString')
        self.assertEqual(line['shape'].area,0.)
        self.assertEqual(line['region']['position'],[5.,-2.])
        self.assertNotIn('boundary',line['region'])
        self.assertEqual(len(line['source']['native_centerline']),2)
        self.assertIn('thickness unobserved',line['source']['representation'])

    def test_verified_native_painted_line_uses_35cm_in_both_projection_paths(self):
        from traffic_spec_adapter.geometry import entrance_geometry_fields
        xml='<OpenDRIVE><road id="1"><planView><geometry s="0" x="0" y="0" hdg="0" length="20"><line/></geometry></planView><objects><object id="line" name="StopLine" s="5" t="-2" hdg="1.5707963267948966" length="4" width="0"/></objects></road></OpenDRIVE>'
        proof=[{'road_id':1,'object_id':'line','paint_verified':True,
                'reference_verified':True,'basis':'Verified recorded paint and exact native object identity',
                'evidence':{'review.json':'a'*64}}]
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'road.xodr';path.write_text(xml)
            self.assertNotIn('boundary',painted_map_objects(path)[0]['region'])
            observed=painted_map_objects(path,proof)[0]
            self.assertAlmostEqual(observed['shape'].area,1.4)
            self.assertEqual(observed['shape'].bounds,(4.825,-4.,5.175,0.))
            self.assertEqual(observed['source']['strip_method']['caps'],'flat')
            retained={'id':3,'kind':'stop_line','position':[5.,-2.],
                      'boundary':[[5.,-4.],[5.,0.]]}
            patch=entrance_geometry_fields(path,[retained],proof)[3]
            self.assertEqual(patch['boundary'],observed['region']['boundary'])
            self.assertNotIn('_unobserved_paint_boundary',patch)
            retained['boundary']=patch['boundary']
            repeated=entrance_geometry_fields(path,[retained],proof)[3]
            self.assertNotIn('boundary',repeated)
            self.assertNotIn('_unobserved_paint_boundary',repeated)
            # An independently observed 0.3 m outline takes precedence.
            retained['boundary']=[[4.85,-4.],[5.15,-4.],[5.15,0.],[4.85,0.]]
            self.assertNotIn('boundary',entrance_geometry_fields(path,[retained],proof)[3])
            with self.assertRaisesRegex(ValueError,'missing from source map'):
                painted_map_objects(path,[dict(proof[0],object_id='different')])

    def test_positive_native_paint_dimensions_remain_a_polygon(self):
        xml='<OpenDRIVE><road id="1"><planView><geometry s="0" x="0" y="0" hdg="0" length="20"><line/></geometry></planView><objects><object id="line" name="StopLine" s="5" t="-2" length="4" width="0.3"/></objects></road></OpenDRIVE>'
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'road.xodr';path.write_text(xml);line=painted_map_objects(path)[0]
        self.assertEqual(len(line['region']['boundary']),4)
        self.assertAlmostEqual(line['shape'].area,1.2)

    def test_explicit_native_outline_survives_zero_width_attribute(self):
        xml='''<OpenDRIVE><road id="1"><planView><geometry s="0" x="0" y="0" hdg="0" length="20"><line/></geometry></planView><objects><object id="line" name="StopLine" s="5" t="-2" width="0"><outline><cornerLocal u="-2" v="-0.2"/><cornerLocal u="2" v="-0.2"/><cornerLocal u="2" v="0.2"/><cornerLocal u="-2" v="0.2"/></outline></object></objects></road></OpenDRIVE>'''
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'road.xodr';path.write_text(xml)
            line=painted_map_objects(path)[0]
            self.assertEqual(line['source']['representation'],'polygon')
            self.assertAlmostEqual(line['shape'].area,1.6)
            self.assertEqual(len(line['region']['boundary']),4)
            path.write_text(xml.replace('<cornerLocal u="2" v="0.2"/><cornerLocal u="-2" v="0.2"/>',''))
            reference=painted_map_objects(path)[0]
            self.assertEqual(reference['shape'].geom_type,'LineString')
            self.assertNotIn('boundary',reference['region'])
            sampled=xml.replace('<cornerLocal u="2" v="-0.2"/>','<cornerLocal u="0" v="-0.199999999999"/><cornerLocal u="2" v="-0.2"/>').replace('<cornerLocal u="2" v="0.2"/><cornerLocal u="-2" v="0.2"/>','')
            path.write_text(sampled)
            reference=painted_map_objects(path)[0]
            self.assertEqual(reference['shape'].geom_type,'LineString')
            self.assertEqual(len(reference['source']['native_centerline']),3)
            path.write_text(xml.replace('u="2" v="-0.2"','u="2" v="0.2"').replace('u="2" v="0.2"/><cornerLocal u="-2"','u="2" v="-0.2"/><cornerLocal u="-2"'))
            with self.assertRaises(ValueError):painted_map_objects(path)

    def test_participant_motion_requires_original_live_acquisition(self):
        attrs={'carla_speed':5.,'carla_vel_x':3.,'carla_vel_y':4.,'carla_vel_z':0.}
        self.assertEqual(live_kinematics(attrs,'original_live_run'),{'speed':5.,'velocity':[3.,-4.]})
        self.assertEqual(live_kinematics(attrs,'recorder_replay'),{})
        self.assertEqual(live_kinematics(attrs,None),{})
        self.assertEqual(live_kinematics({},'original_live_run'),{})

    def test_reflection(self):
        self.assertEqual(xy([1,2,3]),[1,-2])

    def test_body_half_sizes_and_offset(self):
        points=[[x,y,z] for x in (3,7) for y in (1,3) for z in (0,2)]
        c,e,p=body(points,0)
        self.assertEqual(c,[5,-2]);self.assertEqual(e,[2,1,1]);self.assertEqual(p.area,8)

    def test_wrapped_heading_is_not_spin(self):
        self.assertEqual(rates([0,1,2],[179,-179,-177]),[-2,-2,-2])
        self.assertEqual(rates([0,1,2],[0,-10,-20]),[10,10,10])

    def test_gap_not_interpolated(self):
        self.assertIsNone(rates([0,.05,.1,2],[0,1,2,3])[-1])

    def test_observed_false_preserved(self):
        self.assertEqual(rounded({'lamp':False,'unknown':None}),{'lamp':False,'unknown':None})
        with self.assertRaises(ValueError):rounded(float('nan'))

    def test_dangling_occupancy_rejected(self):
        s={'subject':1,'users':[{'track':1}],'structures':[],'devices':[],'occupies':[[1,7]]}
        with self.assertRaises(ValueError):validate_scene(s)

    def test_duplicate_identity_rejected(self):
        s={'subject':1,'users':[{'track':1},{'track':1}],'structures':[],'devices':[]}
        with self.assertRaises(ValueError):validate_scene(s)

    def test_ambiguous_join_and_replay_speed_rejected(self):
        e={'original_frame':1,'actor_id':1,'recording_time_s':0,'replay_frame':10,'replay_simulation_time_s':2,
           'ego':{'speed_mps':1,'speed_provenance':'replay','position_m':[0,0,0]}}
        t={'frame':1,'time_s':0,'speed_mph':1/.44704,'position_m':[0,0,0]}
        f={'frame':10,'simulation_time':2}
        with self.assertRaises(ValueError):verify_join([e],[t],[f])
        e['ego']['speed_provenance']='synthetic_native_sample'
        with self.assertRaises(ValueError):verify_join([e],[t],[f])
        self.assertEqual(verify_join([e],[t],[f],diagnostic_fixture=True)[0][1],t)
        e['ego']['speed_provenance']='original_trace_actor_get_velocity'
        self.assertEqual(verify_join([e],[t],[f])[0][1],t)
        with self.assertRaises(ValueError):verify_join([e,e],[t],[f])

    def test_map_is_static_and_curvature_is_local(self):
        xml='''<OpenDRIVE><road id="1" length="20"><planView>
        <geometry s="0" x="0" y="0" hdg="0" length="10"><line/></geometry>
        <geometry s="10" x="10" y="0" hdg="0" length="10"><arc curvature="0.01"/></geometry>
        </planView><lanes><laneSection s="0"><right><lane id="-1" type="driving"><width sOffset="0" a="4" b="0" c="0" d="0"/></lane></right></laneSection></lanes></road></OpenDRIVE>'''
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'road.xodr';p.write_text(xml)
            regions,polys,keys=static_map(p)
        self.assertEqual(len(keys),1)
        self.assertNotIn('direction',regions[0]['lane'])
        self.assertEqual(len([r for r in regions if r['kind']=='roadway']),1)
        self.assertTrue(all('grade'not in r and'curvature'not in r for r in regions))
        self.assertTrue(all(p.is_valid for p in polys.values()))

    def test_complete_generated_map_distinguishes_no_marking_and_terminal_lane(self):
        xml='''<OpenDRIVE><road id="1" length="10"><planView><geometry s="0" x="0" y="0" hdg="0" length="10"><line/></geometry></planView><lanes><laneSection s="0"><right><lane id="-1" type="driving"><width sOffset="0" a="4" b="0" c="0" d="0"/></lane></right></laneSection></lanes></road></OpenDRIVE>'''
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'map.xodr';path.write_text(xml)
            known=static_map(path,complete_map=True)[0][0]['lane']
            unavailable=static_map(path)[0][0]['lane']
        self.assertEqual(known['marking_left'],['none','other'])
        self.assertEqual(known['marking_right'],['none','other'])
        self.assertEqual(known['leads_to'],[])
        self.assertNotIn('marking_left',unavailable)
        self.assertNotIn('leads_to',unavailable)

    def test_complete_native_lanes_require_bound_generated_map_and_capture_scope(self):
        from traffic_spec_adapter.inventory_observations import complete_generated_lanes
        digest='a'*64
        manifest={'map':'Carla/Maps/OpenDriveMap','complete_driving_lanes':True,'sources':{'road.xodr':digest}}
        facts={'map':manifest['map']}
        self.assertTrue(complete_generated_lanes(manifest,facts,digest))
        self.assertFalse(complete_generated_lanes(manifest,facts,'b'*64))
        self.assertFalse(complete_generated_lanes(manifest,{},digest))
        self.assertFalse(complete_generated_lanes(dict(manifest,complete_driving_lanes=False),facts,digest))
        self.assertFalse(complete_generated_lanes(dict(manifest,map='Town01'),facts,digest))

    def test_native_bicycle_surface_has_its_own_measured_region_and_highway_envelope(self):
        xml='''<OpenDRIVE><road id="1" length="10"><planView><geometry s="0" x="0" y="0" hdg="0" length="10"><line/></geometry></planView><lanes><laneSection s="0"><right><lane id="-1" type="driving"><width sOffset="0" a="4" b="0" c="0" d="0"/></lane><lane id="-2" type="biking"><width sOffset="0" a="2" b="0" c="0" d="0"/></lane></right></laneSection></lanes></road></OpenDRIVE>'''
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'map.xodr';path.write_text(xml)
            regions,polygons,_=static_map(path,include_non_driving=True,public_way_roads=[1])
        bike=next(r for r in regions if r['kind']=='bicycle_lane_or_path')
        highway=next(r for r in regions if r['kind']=='highway')
        roadway=next(r for r in regions if r['kind']=='roadway')
        self.assertEqual(polygons[bike['id']].bounds,(0,-6,10,-4))
        self.assertTrue(polygons[highway['id']].covers(polygons[bike['id']]))
        self.assertEqual(polygons[roadway['id']].intersection(polygons[bike['id']]).area,0)

    def test_crossing_native_edges_do_not_invent_a_highway_surface(self):
        xml='<OpenDRIVE><road id="1" length="10"><planView><geometry s="0" x="0" y="0" hdg="0" length="10"><line/></geometry></planView><lanes><laneSection s="0"><right><lane id="-1" type="driving"><width sOffset="0" a="4" b="-0.8" c="0" d="0"/></lane></right></laneSection></lanes></road></OpenDRIVE>'
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'map.xodr';path.write_text(xml)
            regions,polygons,_=static_map(path,public_way_roads=[1],partial=True)
        highway=next(r for r in regions if r['kind']=='highway')
        self.assertNotIn('boundary',highway)
        self.assertNotIn(highway['id'],polygons)

    def test_native_road_link_recovers_shared_strip_but_not_a_nearby_lane(self):
        lane='<lanes><laneSection s="0"><right><lane id="-1" type="driving"><width sOffset="0" a="4" b="0" c="0" d="0"/></lane></right></laneSection></lanes>'
        def road(ident,x,y,link=''):
            return f'<road id="{ident}" length="10">{link}<planView><geometry s="0" x="{x}" y="{y}" hdg="0" length="10"><line/></geometry></planView>{lane}</road>'
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'map.xodr'
            for offset,expected in [(0,True),(.1,False)]:
                path.write_text('<OpenDRIVE>'+road(1,0,0,'<link><successor elementType="road" elementId="2" contactPoint="start"/></link>')+road(2,10,offset)+'</OpenDRIVE>')
                regions,_,keys=static_map(path,complete_map=True);by_id={r['id']:r for r in regions}
                self.assertEqual('leads_to'in by_id[keys[(1,0,-1)]]['lane'],expected)
                if expected:self.assertEqual(by_id[keys[(1,0,-1)]]['lane']['leads_to'],[keys[(2,0,-1)]])

    def test_collapsed_strip_end_does_not_establish_an_inferred_lane_link(self):
        def road(ident,x,a,b,link=''):
            return f'''<road id="{ident}" length="10">{link}<planView><geometry s="0" x="{x}" y="0" hdg="0" length="10"><line/></geometry></planView><lanes><laneSection s="0"><right><lane id="-1" type="driving"><width sOffset="0" a="{a}" b="{b}" c="0" d="0"/></lane></right></laneSection></lanes></road>'''
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'map.xodr'
            path.write_text('<OpenDRIVE>'+road(1,0,4,-.4,'<link><successor elementType="road" elementId="2" contactPoint="start"/></link>')+road(2,10,0,.4)+'</OpenDRIVE>')
            regions,_,keys=static_map(path,complete_map=True)
        lane=next(r['lane']for r in regions if r['id']==keys[(1,0,-1)])
        self.assertNotIn('leads_to',lane)

    def test_marking_colour_and_compound_type_are_not_silently_discarded(self):
        from traffic_spec_adapter.geometry import lane_marking
        import xml.etree.ElementTree as ET
        source=ET.fromstring('<lane><roadMark sOffset="0" type="solid broken" color="red"/></lane>')
        self.assertEqual(lane_marking(source),['solid_broken','other'])
        self.assertIsNone(lane_marking(ET.fromstring('<lane><roadMark type="solid"/></lane>')))

    def test_native_junction_surface_and_lane_connections(self):
        lane='<lanes><laneSection s="0"><right><lane id="-1" type="driving"><width sOffset="0" a="4" b="0" c="0" d="0"/></lane></right></laneSection></lanes>'
        def road(ident,x,junction):
            return f'<road id="{ident}" junction="{junction}" length="20"><planView><geometry s="0" x="{x}" y="0" hdg="0" length="20"><line/></geometry></planView>{lane}</road>'
        xml='<OpenDRIVE>'+road(1,0,-1)+road(2,20,3)+'<junction id="3"><connection incomingRoad="1" connectingRoad="2" contactPoint="start"><laneLink from="-1" to="-1"/></connection></junction></OpenDRIVE>'
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'road.xodr';p.write_text(xml);notes=[]
            regions,polygons,keys=static_map(p,junctions=True,junction_report=notes)
        intersection=next(r for r in regions if r['kind']=='intersection')
        approach=next(r['lane'] for r in regions if r['id']==keys[(1,0,-1)])
        self.assertEqual(approach['enters_intersection'],intersection['id'])
        self.assertEqual(approach['leads_to'],[keys[(2,0,-1)]])
        self.assertEqual(polygons[intersection['id']].bounds,(20.,-4.,40.,0.))
        self.assertIn('not a painted stop line',notes[0]['scope'])

    def test_curved_lane_partition_preserves_surface_chain_and_references(self):
        import copy
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        from traffic_spec_adapter.geometry import lane_segments,project_lane_segments
        xml='''<OpenDRIVE><road id="1" length="8"><planView><geometry s="0" x="0" y="0" hdg="0" length="8"><arc curvature="0.05"/></geometry></planView><lanes><laneSection s="0"><right><lane id="-1" type="driving"><width sOffset="0" a="4" b="0" c="0" d="0"/></lane></right></laneSection></lanes></road></OpenDRIVE>'''
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'map.xodr';path.write_text(xml);sources={}
            regions,_,keys=static_map(path,source_regions=sources,complete_map=True)
        ident=keys[(1,0,-1)];lane=next(r for r in regions if r['id']==ident)
        lane['lane']['enters_intersection']=99
        scene={'structures':regions,'users':[{'track':7,'kin':{'position':[1,-2],'heading':[1,0],'extent':[.4,.4]}}],
            'devices':[{'id':8,'governs':[ident]}],'occupies':[[7,ident]],'occupancy_observed':[7]}
        fields={ident:{'lane':lane['lane'],'_lane_source':sources[ident]}}
        segments,issues=lane_segments(scene,fields)
        self.assertEqual(issues,[]);self.assertEqual(len(segments[ident]),4)
        pieces=[p for p,_ in segments[ident]]
        self.assertLess(unary_union([Polygon(p['boundary']) for p in pieces]).symmetric_difference(Polygon(lane['boundary'])).area,1e-8)
        self.assertEqual([p['lane']['enters_intersection'] for p in pieces],[99]*4)
        self.assertEqual([p['lane']['leads_to'] for p in pieces],[[p['id']] for p in pieces[1:]]+[[]])
        # Classifications and way membership may be established after compiling
        # the static partition; stale templates must not restore old unknowns.
        lane['ways']=[88]
        lane.pop('unobserved_kinds',None)
        for piece,_ in segments[ident]:piece['unobserved_kinds']=['crosswalk']
        # Independently established junction and other target kinds survive the
        # lane split; an approach never implicitly adds the destination junction.
        other_kinds=['intersection','roadway','one_way_roadway','shoulder',
                     'bicycle_lane_or_path','turn_lane','reserved_lane','centre_turn_lane']
        other_ids=list(range(99,99+len(other_kinds)))
        scene['structures'].extend({'id':i,'kind':kind}for i,kind in zip(other_ids,other_kinds))
        scene['devices'][0]['governs'].extend(other_ids)
        first=copy.deepcopy(scene);project_lane_segments(scene,segments)
        projected=[r for r in scene['structures'] if r['id'] in {p['id'] for p in pieces}]
        self.assertTrue(all(r.get('ways')==[88] and 'unobserved_kinds' not in r for r in projected))
        self.assertEqual(scene['devices'][0]['governs'],[p['id'] for p in pieces]+other_ids)
        self.assertEqual(scene['occupies'],[])
        self.assertEqual(scene['users'],first['users']);self.assertEqual(scene['occupancy_observed'],[])
        # The shared final pass, using exact source footprint, restores supported
        # partial pairs but cannot certify the other unresolved structures.
        from traffic_spec_adapter.occupancy import recompute
        recompute(scene,{7:Polygon([[.6,-2.4],[1.4,-2.4],[1.4,-1.6],[.6,-1.6]])},source_ids={r['id'] for r in scene['structures']})
        # Full final comparison also includes the overlapping native roadway2;
        # the retired partition-only computation omitted that supported pair.
        self.assertEqual(scene['occupies'],[[7,pieces[0]['id']],[7,2]])
        self.assertEqual(scene['occupancy_observed'],[])

    def test_lane_partition_never_guesses_a_scoped_intention_target(self):
        from traffic_spec_adapter.geometry import lane_segments
        scene={'structures':[{'id':1,'kind':'lane','lane':{},'boundary':[[0,0],[1,0],[1,1],[0,1]]}],
            'intents':[{'vehicle':7,'target':1,'values':[['int.left_turn',True]]}]}
        segments,issues=lane_segments(scene,{1:{'lane':{},'_lane_source':{'samples':[],'lane_id':-1}}})
        self.assertEqual(segments,{});self.assertIn('scoped intention',issues[0])

    def test_partition_entrance_uses_measured_line_without_inventing_paint_width(self):
        from traffic_spec_adapter.geometry import compile_lane_segments,project_lane_segments
        first={'id':1,'kind':'lane','boundary':[[0,0],[2,0],[2,-4],[0,-4]],'lane':{'direction':[1,0],'leads_to':[3]}}
        last={'id':3,'kind':'lane','boundary':[[2,0],[4,0],[4,-4],[2,-4]],'lane':{'direction':[1,0],'leads_to':[]}}
        segments={1:[(first,(0,2)),(last,(2,4))]}
        scene={'structures':[{'id':1,'kind':'lane','boundary':[[0,0],[4,0],[4,-4],[0,-4]]},
            {'id':2,'kind':'stop_line','position':[4,3],'entrance_of':[1]}],'users':[]}
        compiled=compile_lane_segments(segments,{2:{'_entrance_geometry':[[4,10],[4,-4]]}})
        project_lane_segments(scene,segments,compiled)
        entrance=next(r for r in scene['structures']if r['id']==2)
        self.assertEqual(entrance['entrance_of'],[3]);self.assertNotIn('boundary',entrance)

    def test_connector_stop_line_keeps_topology_binding_on_terminal_piece(self):
        from traffic_spec_adapter.geometry import compile_lane_segments,project_lane_segments
        first={'id':1,'kind':'lane','boundary':[[0,0],[2,0],[2,-4],[0,-4]],'lane':{'leads_to':[3]}}
        last={'id':3,'kind':'lane','boundary':[[2,0],[4,0],[4,-4],[2,-4]],'lane':{'leads_to':[4]}}
        segments={1:[(first,(0,2)),(last,(2,4))]}
        fields={1:{'_lane_source':{'road_id':10},'lane':{'leads_to':[4]}},
            4:{'_lane_source':{'road_id':20}},2:{'_entrance_geometry':[[5,0],[5,-4]],'_entrance_road':20}}
        def scene():return {'structures':[{'id':1,'kind':'lane','boundary':[[0,0],[4,0],[4,-4],[0,-4]]},
            {'id':2,'kind':'stop_line','position':[5,-2],'entrance_of':[1]},
            {'id':4,'kind':'lane','boundary':[[4,0],[8,0],[8,-4],[4,-4]]}],'users':[]}
        value=scene();project_lane_segments(value,segments,compile_lane_segments(segments,fields))
        self.assertEqual(next(r for r in value['structures']if r['id']==2)['entrance_of'],[3])
        fields[2]['_entrance_road']=30
        with self.assertRaisesRegex(ValueError,'does not meet'):
            project_lane_segments(scene(),segments,compile_lane_segments(segments,fields))

    def test_retained_sign_governance_cannot_join_by_position(self):
        from traffic_spec_adapter.adapter import repair_scene
        for kind in ('stop_sign', 'yield_sign', 'speed_limit_sign', 'regulatory_sign'):
            with self.subTest(kind=kind):
                scene = {'structures': [{'id': 5, 'kind': 'lane'}], 'users': [],
                         'devices': [{'id': 10, 'kind': kind, 'position': [1, 2]}]}
                packet = {'governance': {(1, 2): [(1, 0, -1)]}}
                repair_scene(scene, set(), packet, {}, {}, {(1, 0, -1): 5})
                self.assertNotIn('governs', scene['devices'][0])
                scene['devices'][0]['governs'] = [5]
                repair_scene(scene, set(), packet, {}, {}, {(1, 0, -1): 5})
                self.assertEqual(scene['devices'][0]['governs'], [5])

    def test_native_identity_match_ignores_exact_duplicate_vertices_without_mutation(self):
        import copy, warnings
        from traffic_spec_adapter.geometry import match_regions
        native = [{'id': 1, 'kind': 'lane', 'boundary': [[0,0],[2,0],[2,1],[0,1]]}]
        retained = [{'id': 7, 'kind': 'lane', 'boundary':
                     [[0,0],[2,0],[2,0],[2,1],[0,1],[0,1]]}]
        original = copy.deepcopy(retained)
        with warnings.catch_warnings():
            warnings.simplefilter('error', RuntimeWarning)
            self.assertEqual(match_regions(native, retained), {1:7})
        self.assertEqual(retained, original)
        retained.append(dict(retained[0], id=8))
        self.assertEqual(match_regions(native, retained), {})

    def test_scenario_geometry_checks_review_bytes_before_projection(self):
        import hashlib
        from traffic_spec_adapter.scenario_geometry import apply
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review = root/'review.json'
            review.write_text('{"face_confirmed":true}')
            proof = {'review': review.name, 'sha256': hashlib.sha256(review.read_bytes()).hexdigest()}
            (root/'scenario_geometry.json').write_text(json.dumps({
                'source': 'original construction', 'physical_verification': proof}))
            result = apply(root, [], {}, {})
            self.assertEqual(result['physical_verification_review'], proof)
            review.write_text('{"face_confirmed":false}')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                apply(root, [], {}, {})
            review.unlink()
            with self.assertRaisesRegex(ValueError, 'missing'):
                apply(root, [], {}, {})

    def test_scenario_geometry_review_cannot_escape_original_evidence(self):
        from traffic_spec_adapter.scenario_geometry import verification_review
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('../review.json', '/tmp/review.json'):
                with self.assertRaisesRegex(ValueError, 'relative review'):
                    verification_review(Path(tmp), {'review': name, 'sha256': '0'*64})
            with self.assertRaisesRegex(ValueError, 'relative review'):
                verification_review(Path(tmp), {'review': 'review.json'})

    def test_saved_geometry_review_requires_closed_source_and_matches_fresh_check(self):
        import hashlib
        from traffic_spec_adapter.scenario_geometry import verification_review, retained_review
        from traffic_spec_adapter.inventory_observations import Evidence
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root/'evidence'
            original.mkdir()
            review = original/'review.json'
            review.write_text('{"face_confirmed":true}')
            proof = {'review': review.name, 'sha256': hashlib.sha256(review.read_bytes()).hexdigest()}
            declaration = original/'scenario_geometry.json'
            declaration.write_text(json.dumps({'source': 'original', 'physical_verification': proof}))
            hashes = {'evidence/'+p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in (review, declaration)}
            inventory = root/'evidence-checksums.json'
            inventory.write_text(json.dumps(hashes))
            self.assertEqual(retained_review(Evidence(root)), verification_review(original, proof))
            hashes.pop('evidence/review.json')
            inventory.write_text(json.dumps(hashes))
            with self.assertRaisesRegex(ValueError, 'not bound'):
                retained_review(Evidence(root))

    def test_geometry_review_rejects_changed_declared_source(self):
        import hashlib
        from traffic_spec_adapter.scenario_geometry import verification_review
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'scene.py'
            source.write_text('original construction')
            review = root/'review.json'
            review.write_text(json.dumps({'sources': {
                source.name: hashlib.sha256(source.read_bytes()).hexdigest()}}))
            proof = {'review': review.name, 'sha256': hashlib.sha256(review.read_bytes()).hexdigest()}
            self.assertEqual(verification_review(root, proof), proof)
            source.write_text('altered construction')
            with self.assertRaisesRegex(ValueError, 'hash mismatch: scene.py'):
                verification_review(root, proof)

    def test_verified_zero_device_inventory_has_fresh_saved_parity(self):
        from traffic_spec_adapter.inventory_observations import STATIC_DEVICE_KINDS, static_inventory_observations
        from traffic_spec_adapter.atom_contract import required_coverage, gaps
        kinds = {kind: {'count': 0, 'basis': 'Verified complete original physical inventory'}
                 for kind in STATIC_DEVICE_KINDS}
        receipt = {'map_sha256': 'a'*64, 'kinds': kinds}
        atoms = {'dev.'+kind for kind in kinds} | {'dev.inoperative'}
        scene = {'devices': [], 'structures': [], 'users': []}
        records = static_inventory_observations(scene, receipt, 9, atoms)
        capability = {'atoms': {atom: 'exact' for atom in atoms}}
        fresh = required_coverage(atoms, capability, [scene],
                                  inventory_observations={k:[v] for k,v in records.items()})
        self.assertTrue(fresh['passed'])
        self.assertEqual(fresh['atoms']['dev.inoperative']['observation_status_counts'],
                         {'verified_absent': 1})
        limits = {}
        self.assertEqual(gaps(scene, atoms, capability=capability,
                              static_inventory=receipt, limitations=limits), [])
        self.assertEqual(limits, {})

    def test_empty_device_list_without_inventory_stays_unknown(self):
        from traffic_spec_adapter.atom_contract import required_coverage
        atoms = {'dev.regulatory_sign','dev.speed_limit_sign','dev.yield_sign','dev.lane_control_signal'}
        result = required_coverage(atoms, {'atoms': {a:'exact' for a in atoms}},
                                   [{'devices': [], 'structures': [], 'users': []}])
        self.assertEqual(set(result['missing']), atoms)

    def test_present_regulatory_device_inventory_does_not_supply_conditions(self):
        from traffic_spec_adapter.inventory_observations import static_inventory_observations
        from traffic_spec_adapter.atom_contract import required_coverage
        scene = {'devices': [{'id':1,'kind':'regulatory_sign','code':'one_way'}], 'structures': []}
        receipt = {'map_sha256':'a'*64, 'kinds': {'regulatory_sign': {
            'count':1, 'basis':'Complete observed physical sign inventory'}}}
        atoms = {'dev.regulatory_sign'}
        record = static_inventory_observations(scene, receipt, 9, atoms)
        kwargs = {'inventory_observations':{k:[v] for k,v in record.items()}}
        capability = {'atoms':{'dev.regulatory_sign':'exact'}}
        self.assertFalse(required_coverage(atoms,capability,[scene],**kwargs)['passed'])
        self.assertNotIn('conditions',scene['devices'][0])
        scene['devices'][0]['conditions'] = {}
        self.assertTrue(required_coverage(atoms,capability,[scene],**kwargs)['passed'])

    def test_zero_inventory_rejects_every_present_device_kind(self):
        from traffic_spec_adapter.inventory_observations import STATIC_DEVICE_KINDS, static_inventory_observations
        for kind in STATIC_DEVICE_KINDS:
            with self.subTest(kind=kind):
                receipt = {'map_sha256':'a'*64,'kinds':{kind:{'count':0,'basis':'Complete source inventory'}}}
                with self.assertRaisesRegex(ValueError,'contradicts'):
                    static_inventory_observations({'devices':[{'id':1,'kind':kind}], 'structures':[]},
                                                  receipt,9,{'dev.'+kind})

    def test_device_inventory_requires_hashed_non_map_acquisition_source(self):
        import hashlib
        from traffic_spec_adapter.inventory_observations import Evidence, retained_static_inventory
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original=root/'evidence';original.mkdir()
            road=original/'road.xodr';road.write_text('<OpenDRIVE/>')
            digest=hashlib.sha256(road.read_bytes()).hexdigest()
            receipt={'schema':'retained-static-inventory-v1','scope':'entire_recorded_map',
                     'constant_during_recording':True,'evidence':{'road.xodr':digest},
                     'map_sha256':digest,'kinds':{'yield_sign':{'count':0,'basis':'Physical source inventory'}}}
            hashes={'evidence/road.xodr':digest}
            (root/'evidence-checksums.json').write_text(json.dumps(hashes))
            with self.assertRaisesRegex(ValueError,'beyond the map'):
                retained_static_inventory(Evidence(root),receipt)
            physical=original/'physical-inventory.json'
            physical.write_text('{"devices":[],"complete":true,"scope":"entire_recorded_map"}')
            source_hash=hashlib.sha256(physical.read_bytes()).hexdigest()
            hashes['evidence/physical-inventory.json']=source_hash
            receipt['evidence'][physical.name]=source_hash
            (root/'evidence-checksums.json').write_text(json.dumps(hashes))
            self.assertEqual(retained_static_inventory(Evidence(root),receipt),receipt)

    def test_painted_stop_line_inventory_requires_bound_physical_reference_proof(self):
        from traffic_spec_adapter.inventory_observations import Evidence,retained_static_inventory
        from traffic_spec_adapter.adapter import sha
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original=root/'evidence';original.mkdir()
            (original/'road.xodr').write_text('<OpenDRIVE/>')
            (original/'paint-review.json').write_text('{"native_object_id":"line","paint_confirmed":true,"reference_confirmed":true}')
            sources={name:sha(original/name)for name in ('road.xodr','paint-review.json')}
            (root/'evidence-checksums.json').write_text(json.dumps({'evidence/'+n:h for n,h in sources.items()}))
            proof={'road_id':1,'object_id':'line','paint_verified':True,'reference_verified':True,
                   'basis':'Source-bound physical paint and native reference review',
                   'evidence':{'paint-review.json':sources['paint-review.json']}}
            receipt={'schema':'retained-static-inventory-v1','scope':'entire_recorded_map',
                     'constant_during_recording':True,'map_sha256':sources['road.xodr'],'evidence':sources,
                     'kinds':{'stop_line':{'count':1,'basis':'Complete source construction'}},
                     'painted_stop_line_bindings':[proof]}
            self.assertEqual(retained_static_inventory(Evidence(root),receipt),receipt)
            for patch in ({'paint_verified':False},{'reference_verified':False},
                          {'evidence':{'road.xodr':sources['road.xodr']}},
                          {'evidence':{'paint-review.json':'0'*64}}):
                receipt['painted_stop_line_bindings']=[dict(proof,**patch)]
                with self.assertRaisesRegex(ValueError,'Painted stop-line estimate'):
                    retained_static_inventory(Evidence(root),receipt)
            receipt['painted_stop_line_bindings']=[proof,proof]
            with self.assertRaisesRegex(ValueError,'unique native identity'):
                retained_static_inventory(Evidence(root),receipt)

    def test_verified_native_signal_absence_also_closes_operability_applicability(self):
        from traffic_spec_adapter.atom_contract import required_coverage
        capability={'atoms':{'dev.inoperative':'exact'}}
        inventory={'dev.traffic_signal':[{'status':'verified_absent'}]}
        self.assertTrue(required_coverage({'dev.inoperative'},capability,[{'devices':[]}],
                                          inventory_observations=inventory)['passed'])
        with self.assertRaisesRegex(ValueError,'contradicts'):
            required_coverage({'dev.inoperative'},capability,
                              [{'devices':[{'id':1,'kind':'traffic_signal'}]}],
                              inventory_observations=inventory)

    def test_way_membership_has_same_fresh_saved_observation_policy(self):
        from traffic_spec_adapter.atom_contract import required_coverage, gaps
        capability={'atoms':{'st.on_way':'exact'}}
        scene={'structures':[{'id':1,'kind':'highway'},
                             {'id':2,'kind':'lane','ways':[1]},
                             {'id':3,'kind':'one_way_roadway','ways':[1]}]}
        self.assertTrue(required_coverage({'st.on_way'},capability,[scene])['passed'])
        self.assertEqual(gaps(scene,{'st.on_way'},capability=capability),[])
        for kind in ('turn_lane','reserved_lane','centre_turn_lane','shoulder','bicycle_lane_or_path','intersection'):
            with self.subTest(kind=kind):
                region={'id':4,'kind':kind};scene['structures'].append(region)
                self.assertFalse(required_coverage({'st.on_way'},capability,[scene])['passed'])
                self.assertEqual(gaps(scene,{'st.on_way'},capability=capability),['st.on_way'])
                region['ways']=[]
                self.assertTrue(required_coverage({'st.on_way'},capability,[scene])['passed'])
                self.assertEqual(gaps(scene,{'st.on_way'},capability=capability),[])
                scene['structures'].pop()

    def test_native_speed_actor_value_and_governance(self):
        import networkx as nx
        graph=nx.MultiDiGraph()
        graph.add_node('speed',sem_class='traffic.speed_limit.30',carla_id=10,
                       landmark_value=30,landmark_unit='km/h',observed_governs=[[1,0,-1]])
        graph.add_node('lane',waypoint_road_id=1,waypoint_section_id=0,waypoint_lane_id=-1)
        graph.add_edge('speed','lane',dist_relationship='controlsTrafficOf')
        key,device=device_record('speed',graph.nodes['speed'],graph,{(1,0,-1):5})
        self.assertEqual(key,('actor','10'))
        self.assertAlmostEqual(device['speed_value'],30/3.6)
        self.assertNotIn('governs',device)  # No documented complete speed-sign lane API.

    def test_atom_inventory_does_not_include_primitives(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'splits/full/TrafficSpec/Core'
            (p/'Vocab/Ontology').mkdir(parents=True)
            (p/'Runtime').mkdir()
            (p/'Runtime/Decode.lean').write_text('-- fixture')
            (p/'Vocab/Ontology/Ids.lean').write_text('def atomIds : List String := ["kin.speed", "st.lane"]\ndef primitiveIds : List String := ["prim.heading_change"]')
            self.assertEqual(atom_ids(Path(d)),['kin.speed','st.lane'])

    def test_recorder_prop_position_has_no_invented_boundary(self):
        p=recorded_traffic_props('Frame 1 at 0 seconds\n Create 38: static.prop.streetbarrier (0) at (2808.97, -3028.97, 10)\nFrame 2 at 0.05 seconds')
        self.assertAlmostEqual(p[38]['position'][0],28.0897)
        self.assertAlmostEqual(p[38]['position'][1],30.2897)
        self.assertNotIn('boundary',p[38])

    def test_lamps_preserve_recorded_on_off_and_unknown(self):
        on=signals({'light_Brake':True,'light_Position':True,'light_Reverse':True,
                    'light_LeftBlinker':True,'light_RightBlinker':True,
                    'light_HighBeam':True,'light_LowBeam':False})
        self.assertEqual(on,{'brake_lamp':True,'position_lamp':True,
                             'reverse_lamp':True,'hazard':True,'headlamp':'high_beam'})
        self.assertEqual(signals({'brake':1.,'reverse':True}),{})
        self.assertEqual(signals({'light_Brake':False,'light_Reverse':False}),
                         {'brake_lamp':False,'reverse_lamp':False})
        self.assertEqual(signals({'light_HighBeam':False,'light_LowBeam':True}),
                         {'headlamp':'low_beam'})

    def test_measured_signal_off_is_preserved(self):
        lamps=signals({'light_Brake':False,'light_LeftBlinker':False,'light_RightBlinker':False})
        self.assertEqual(lamps,{'brake_lamp':False,'hazard':False,'turn_indicator':'off'})
        self.assertEqual(signals({'light_LeftBlinker':True,'light_RightBlinker':False})['turn_indicator'],'left')

    def test_device_governance_requires_real_edge(self):
        import networkx as nx
        g=nx.DiGraph()
        g.add_node('signal',sem_class='traffic.traffic_light',carla_id=99,vertex=[1,2],light_state='Red')
        g.add_node('lane',waypoint_road_id=1,waypoint_section_id=0,waypoint_lane_id=-1)
        g.add_edge('signal','lane',dist_relationship='mayAffect')
        key,d=device_record('signal',g.nodes['signal'],g,{(1,0,-1):7})
        self.assertNotIn('governs',d)
        g.edges['signal','lane']['dist_relationship']='controlsTrafficOf'
        _,d=device_record('signal',g.nodes['signal'],g,{(1,0,-1):7})
        self.assertNotIn('governs',d)
        g.nodes['signal']['observed_governs']=[[1,0,-1]]
        g.nodes['signal']['original_device_observation']={'actor_id':99,
            'blueprint':'traffic.traffic_light','affected_lanes':[[1,0,-1]]}
        _,d=device_record('signal',g.nodes['signal'],g,{(1,0,-1):7})
        self.assertEqual(d['governs'],[7]);self.assertEqual(d['indications'],['circular_red'])
        self.assertEqual(d['position'],[1,-2])

    def test_governance_merge_preserves_unknown_empty_and_positive(self):
        from traffic_spec_adapter.adapter import merge_device_governance
        value={}
        merge_device_governance(value,{})
        self.assertNotIn('governs',value)
        merge_device_governance(value,{'governs':[]})
        self.assertEqual(value['governs'],[])
        with self.assertRaisesRegex(ValueError, 'Conflicting complete'):
            merge_device_governance(value,{'governs':[4,2]})
        self.assertEqual(value['governs'],[])
        value={'governs':[4,2]}
        merge_device_governance(value,{})
        merge_device_governance(value,{'governs':[2,4]})
        self.assertEqual(value['governs'],[2,4])
        with self.assertRaisesRegex(ValueError, 'Conflicting complete'):
            merge_device_governance(value,{'governs':[2,3]})
        self.assertEqual(value['governs'],[2,4])

    def test_unverified_empty_native_governance_is_unknown(self):
        import networkx as nx
        graph=nx.DiGraph()
        graph.add_node('signal',sem_class='traffic.traffic_light',carla_id=99,
                       light_state='Red',observed_governs=[])
        _,device=device_record('signal',graph.nodes['signal'],graph,{})
        self.assertNotIn('governs',device)
        graph.nodes['signal']['original_device_observation']={'actor_id':99,
            'blueprint':'traffic.traffic_light','affected_lanes':[]}
        _,device=device_record('signal',graph.nodes['signal'],graph,{})
        self.assertNotIn('governs',device)
        del graph.nodes['signal']['observed_governs']
        _,device=device_record('signal',graph.nodes['signal'],graph,{})
        self.assertNotIn('governs',device)
        graph.nodes['signal']['observed_governs']=None
        _,device=device_record('signal',graph.nodes['signal'],graph,{})
        self.assertNotIn('governs',device)

    def test_unknown_geometry_fails_not_empty(self):
        from traffic_spec_adapter.geometry import reference
        import xml.etree.ElementTree as ET
        with self.assertRaises(ValueError):reference(ET.fromstring('<geometry s="0" x="0" y="0" hdg="0"><poly3/></geometry>'),0)

if __name__=='__main__':unittest.main()


class ManifestAvailabilityTests(unittest.TestCase):
    def test_source_capabilities_are_exhaustive_except_hand_signals(self):
        from unittest.mock import patch
        from traffic_spec_adapter import adapter
        library=core_fixture_library()
        atoms=adapter.manifest(library,acquisition_path='fresh')['atoms']
        self.assertNotIn('sig.hand_signal',atoms)
        self.assertEqual(set(atoms),set(adapter.atom_ids(library))-{'sig.hand_signal'})
        self.assertEqual(atoms['st.sight_distance'],'estimate:vehicle_reference_geometry')
        self.assertEqual(atoms['st.entrance_of'],'estimate:recorded_control_and_map_topology_join')
        with patch.object(adapter,'atom_ids',return_value=adapter.atom_ids(library)+['st.future_atom']):
            with self.assertRaisesRegex(ValueError,'lacks an explicit acquisition decision'):
                adapter.manifest(library,acquisition_path='fresh')


# Regression checks shared by production export and retained-trace reconstruction.
from traffic_spec_adapter.adapter import lamp_state, repair_scene, source_packets, yaw_estimates, preserve_inventory_unknown
from shared_manifest import link, verify
import hashlib
class OfflineRepairTests(unittest.TestCase):
    def test_native_mask_preserves_zero_and_hazard(self):
        self.assertEqual(lamp_state(0)['turn_indicator'], 'off')
        self.assertEqual(lamp_state(32)['turn_indicator'], 'left')
        self.assertEqual(lamp_state(16)['turn_indicator'], 'right')
        self.assertTrue(lamp_state(48)['hazard'])
        self.assertNotIn('turn_indicator', lamp_state(48))
        with self.assertRaises(ValueError):lamp_state(False)

    def test_missing_measurement_never_becomes_off(self):
        scene={'t':0,'subject':1,'users':[{'track':1,'sig':{'left_indicator_enabled':False}}]}
        repair_scene(scene,{'sig.turn_indicator'},{},{},{})
        self.assertNotIn('turn_indicator',scene['users'][0]['sig'])
        self.assertNotIn('left_indicator_enabled',scene['users'][0]['sig'])

    def test_hazard_does_not_retain_an_invented_turn_side(self):
        scene={'subject':1,'users':[{'track':1,'sig':{'turn_indicator':'left'}}]}
        repair_scene(scene,{'sig.turn_indicator'},{'ego_lamps':lamp_state(48)},{},{})
        self.assertNotIn('turn_indicator',scene['users'][0]['sig'])
        self.assertTrue(scene['users'][0]['sig']['hazard'])

    def test_brake_control_does_not_set_lamp(self):
        scene={'subject':1,'users':[{'track':1,'kin':{'service_brake':1},'sig':{'brake_lamp':False}}]}
        repair_scene(scene,{'sig.brake_lamp'},{},{},{})
        self.assertFalse(scene['users'][0]['sig']['brake_lamp'])

    def test_heading_rate_wraps_and_does_not_bridge_disappearance(self):
        import math
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'trace.json'
            def user(deg):return {'track':2,'kin':{'heading':[math.cos(math.radians(deg)),math.sin(math.radians(deg))]}}
            path.write_text(json.dumps({'scenes':[{'t':0,'users':[user(179)]},
                {'t':1000,'users':[user(-179)]},{'t':2000,'users':[]},
                {'t':3000,'users':[user(-170)]}]}))
            rates=yaw_estimates(path)
            self.assertAlmostEqual(rates[0][2],2)
            self.assertNotIn(2,rates.get(1,{}))
            self.assertNotIn(2,rates.get(3,{}))

    def test_current_decoder_rejects_ignored_typed_keys(self):
        from traffic_spec_adapter.trace_contract import validate
        library=core_fixture_library()
        scene={'t':0,'users':[{'track':1,'sig':{'left_indicator_enabled':False}}]}
        with self.assertRaisesRegex(ValueError,'ignored'):
            validate(scene,library)

    def test_retired_classes_do_not_invent_current_membership(self):
        from traffic_spec_adapter.classifications import project_user
        source={'track':1,'classes':['retired_source_category']}
        current=project_user(source,{'motor_vehicle','pedestrian'})
        self.assertIsNone(current['classes'])
        self.assertEqual(current['unobserved_classes'],['motor_vehicle','pedestrian'])
        self.assertNotIn('source_classifications',current)
        self.assertEqual(source['classes'],['retired_source_category'])

    def test_inventory_uncertainty_preserves_positive_objects(self):
        from traffic_spec_adapter.adapter import preserve_inventory_unknown
        scene={'structures':[{'id':1,'kind':'highway'},{'id':2,'kind':'roadway'}]}
        preserve_inventory_unknown(scene,['highway'],verified={1:['highway']})
        self.assertNotIn('unobserved_kinds',scene['structures'][0])
        self.assertIn('highway',scene['structures'][1]['unobserved_kinds'])

    def test_optional_relation_coverage_checks_actual_fields(self):
        from traffic_spec_adapter.atom_contract import gaps
        scene={'users':[],'structures':[{'id':1,'kind':'stop_line','entrance_of':[2]}],
               'devices':[{'id':3,'kind':'stop_sign','governs':[]}]}
        self.assertEqual(gaps(scene,{'st.entrance_of','dev.governs'}),[])
        del scene['structures'][0]['entrance_of']
        self.assertIn('st.entrance_of',gaps(scene,{'st.entrance_of'}))
        self.assertEqual(gaps({'structures':[],'devices':[]},{'st.entrance_of','dev.governs','dev.traffic_signal'}),[])

    def test_manifest_link_rejects_wrong_target_and_changed_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);case=root/'recordings/case';case.mkdir(parents=True)
            value={'source':'test','atoms':{'sig.turn_indicator':'exact'}}
            link(root,case,value)
            self.assertFalse((case/'manifest.json').readlink().is_absolute())
            digest=hashlib.sha256((case/'manifest.json').read_bytes()).hexdigest()
            verify(root,case,digest)
            with self.assertRaises(ValueError):link(root,case,{'source':'changed'})
            with self.assertRaises(ValueError):verify(root,case,'0'*64)
            other=root/'recordings/new';other.mkdir()
            link(root,other,{'source':'changed'})
            other_hash=hashlib.sha256((other/'manifest.json').read_bytes()).hexdigest()
            verify(root,other,other_hash)
            verify(root,case,digest)
            self.assertEqual(json.loads((root/'inputs/shared/manifest.json').read_text()),value)




class ReconstructionTests(unittest.TestCase):
    def test_child_exclusion_uses_observed_nonpedestrian_not_missing_age(self):
        from traffic_spec_adapter.classifications import project_user
        known={'motor_vehicle','pedestrian','child'}
        vehicle={'track':1,'classes':['motor_vehicle'],'unobserved_classes':['child']}
        result=project_user(vehicle,known)
        self.assertNotIn('child',result['unobserved_classes'])
        self.assertEqual(vehicle['unobserved_classes'],['child'])
        walker={'track':2,'classes':['pedestrian'],'unobserved_classes':['child']}
        self.assertIn('child',project_user(walker,known)['unobserved_classes'])
        uncertain={'track':3,'classes':[],'unobserved_classes':['pedestrian','child']}
        self.assertIn('child',project_user(uncertain,known)['unobserved_classes'])
        unclassified={'track':4,'classes':None,'unobserved_classes':['child']}
        self.assertIn('child',project_user(unclassified,known)['unobserved_classes'])

    def test_geometry_match_ignores_winding_and_redundant_samples(self):
        from traffic_spec_adapter.geometry import match_regions
        native=[{'id':1,'kind':'lane','boundary':[[0,0],[2,0],[2,1],[0,1]]}]
        current=[{'id':7,'kind':'lane','boundary':[[2,1],[2,0],[1,0],[0,0],[0,1]]}]
        self.assertEqual(match_regions(native,current),{1:7})
        current.append(dict(current[0],id=8))
        self.assertEqual(match_regions(native,current),{})

    def test_numerically_collapsed_arc_edge_is_not_an_invalid_lane(self):
        from traffic_spec_adapter.geometry import clean_boundary
        from shapely.geometry import Polygon
        points=[[0,0],[1,0],[1,1],[1+1e-14,1],[0,1],[0,0]]
        result=clean_boundary(points)
        self.assertEqual(len(result),4)
        self.assertTrue(Polygon(result).is_valid)
        self.assertEqual(Polygon(result).area,1)

    def test_streaming_yaw_requires_contiguous_identity_and_time(self):
        from traffic_spec_adapter.adapter import heading_rate
        def scene(t,deg):return {'t':t,'users':[{'track':2,'kin':{'heading':[math.cos(math.radians(deg)),math.sin(math.radians(deg))]}}]}
        self.assertAlmostEqual(heading_rate(scene(0,179),scene(50,-179),scene(100,-177),2,50),40)
        self.assertIsNone(heading_rate(scene(0,0),scene(50,2),scene(200,4),2,50))
        self.assertIsNone(heading_rate({'t':0,'users':[]},scene(50,2),scene(100,4),2,50))

    def test_unchanged_reconstruction_does_not_write_a_trace(self):
        from traffic_spec_adapter.adapter import reconstruct
        from unittest.mock import patch
        library=core_fixture_library()
        scene={'t':0,'subject':1,'users':[{'track':1,'kin':{'speed':0,'path_length':0,'yaw_rate':0}}],
               'structures':[],'devices':[]}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);trace=root/'input.json';output=root/'output.json';trace.write_text(json.dumps({'scenes':[scene]}))
            with patch('traffic_spec_adapter.geometry.retained_map',return_value=({}, {}, [], {}, [])), \
                 patch('traffic_spec_adapter.entrance_associations.retained_associations',return_value=({},[])), \
                 patch('traffic_spec_adapter.adapter.source_packets',return_value={}):
                report=reconstruct(trace,root/'evidence',library,output)
            self.assertFalse(report['changed']);self.assertFalse(output.exists())


    def test_profile_only_reconstruction_writes_current_user_fields(self):
        from traffic_spec_adapter.adapter import reconstruct
        from unittest.mock import patch
        library=core_fixture_library()
        scene={'t':0,'subject':1,'users':[{'track':1,'kin':{'speed':0,'path_length':0,'yaw_rate':0,'heading':[1,0]}}],
               'structures':[],'devices':[]}
        def measured_profile(scene,source):
            scene['users'][0]['road_grade']=.08;scene['users'][0]['road_curvature']=0
            return [{'track':1,'grade':.08,'curvature':0,'reason':None}]
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);trace=root/'input.json';output=root/'output.json';trace.write_text(json.dumps({'scenes':[scene]}))
            with patch('traffic_spec_adapter.geometry.retained_map',return_value=({}, {}, [], {}, [])), \
                 patch('traffic_spec_adapter.entrance_associations.retained_associations',return_value=({},[])), \
                 patch('traffic_spec_adapter.adapter.source_packets',return_value={}), \
                 patch('traffic_spec_adapter.user_road_profile.project_source_profiles',side_effect=measured_profile):
                report=reconstruct(trace,root/'evidence',library,output)
            self.assertTrue(report['changed']);self.assertEqual(report['changes']['local_user_road_profiles'],1)
            self.assertEqual(json.loads(output.read_text())['scenes'][0]['users'][0]['road_grade'],.08)


class EvidenceReceiptTests(unittest.TestCase):
    def test_changed_derived_export_does_not_discard_bound_raw_map(self):
        from traffic_spec_adapter.inventory_observations import Evidence
        from batch_pipeline.completion import seal
        with tempfile.TemporaryDirectory() as temp:
            recording=Path(temp);original=recording/'evidence';original.mkdir()
            for name in ('road.xodr','trace.jsonl','frames.json','video.webm'):(original/name).write_text(name)
            derived=original/'traffic_spec';derived.mkdir();(derived/'trace.json').write_text('old')
            result={'trace_reference':'trace.jsonl','video_frame_map_reference':'frames.json','video_references':['video.webm']}
            (original/'result.json').write_text(json.dumps(result))
            seal(original,{'case_id':'c'})
            (derived/'trace.json').write_text('new derived trace')
            evidence=Evidence(recording)
            self.assertEqual(evidence.path('road.xodr'),original/'road.xodr')
            (original/'trace.jsonl').write_text('tampered')
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):evidence.path('trace.jsonl')


class UnknownMeasurementTests(unittest.TestCase):
    def test_null_lamps_stay_unknown_but_measured_mask_zero_is_off(self):
        self.assertEqual(signals({'light_Brake':None,'light_LeftBlinker':None,'light_RightBlinker':False}),{})
        self.assertEqual(signals({'vehicle_light_state':0})['turn_indicator'],'off')

    def test_unknown_indication_does_not_mean_definitely_not_red(self):
        scene={'users':[],'structures':[],'devices':[{'id':1,'kind':'traffic_signal','indications':['unknown']}]}
        repair_scene(scene,{'dev.traffic_signal'},{},{},{})
        self.assertNotIn('indications',scene['devices'][0])


class MeasuredSidecarTests(unittest.TestCase):
    def test_sidecar_uses_native_mask_and_actor_identity_not_labels(self):
        from unittest.mock import patch
        from traffic_spec_adapter.inventory_observations import Evidence
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);original=root/'evidence';original.mkdir()
            raw=original/'vehicle_turn_signal_history.jsonl'
            raw.write_text(json.dumps({'time_s':.05,'value':{'ego':{'actor_id':7,'lamp_bits':0},'command':'left'}})+'\n')
            (root/'evidence-checksums.json').write_text(json.dumps({'evidence/'+raw.name:hashlib.sha256(raw.read_bytes()).hexdigest()}))
            packets=source_packets(Evidence(root),read_graphs=False)
            scene={'t':50,'subject':7,'users':[{'track':7}], 'structures':[], 'devices':[]}
            repair_scene(scene,{'sig.turn_indicator'},packets[50],{},{})
            self.assertEqual(scene['users'][0]['sig']['turn_indicator'],'off')


class ConflictingMeasurementTests(unittest.TestCase):
    def test_conflicting_same_frame_lamps_remain_unknown(self):
        scene={'subject':1,'users':[{'track':1,'sig':{'turn_indicator':'left'}}], 'structures':[], 'devices':[]}
        packet={'ego_lamps':{'turn_indicator':'left'},'lamp_sources':[{'track':1,'lamps':{'turn_indicator':'off'}}]}
        repair_scene(scene,{'sig.turn_indicator'},packet,{},{})
        self.assertNotIn('turn_indicator',scene['users'][0]['sig'])


class OperabilityProjectionTests(unittest.TestCase):
    def test_valid_indication_excludes_inoperability_but_darkness_does_not_supply_it(self):
        from traffic_spec_adapter.adapter import project_operability
        devices=[{'kind':'traffic_signal','indications':['circular_red']},
                 {'kind':'traffic_signal','indications':['dark'],'inoperative':True},
                 {'kind':'traffic_signal','inoperative':False}]
        project_operability(devices)
        self.assertIs(devices[0]['inoperative'],False)
        self.assertNotIn('inoperative',devices[1]);self.assertNotIn('inoperative',devices[2])

class OriginalMotionConventionTests(unittest.TestCase):
    def test_planar_speed_does_not_hide_raw_vertical_velocity(self):
        from traffic_spec_adapter.adapter import measured_kinematics, live_kinematics
        raw={'velocity_mps':[3.,4.,12.]}
        self.assertEqual(measured_kinematics(raw), {'velocity':[3.,-4.], 'speed':5.})
        self.assertEqual(raw['velocity_mps'],[3.,4.,12.])
        self.assertEqual(live_kinematics({'carla_vel_x':3.,'carla_vel_y':4.,
            'carla_vel_z':12.,'carla_speed':13.}, 'original_live_run'), measured_kinematics(raw))
        self.assertEqual(measured_kinematics({'speed_mps':13.}), {})

    def test_horizontal_acceleration_and_explicit_zero(self):
        from traffic_spec_adapter.adapter import measured_kinematics
        from traffic_spec_adapter.acceleration import METHOD
        raw={'acceleration_mps2':[1.,2.,3.], 'forward_vector':[.6,0.,.8],
             'accel_longitudinal_mps2':3., 'velocity_mps':[-5.,0.,0.]}
        self.assertAlmostEqual(measured_kinematics(raw)['accel_longitudinal'],1.)
        self.assertEqual(measured_kinematics({'velocity_mps':[0,0,0],
            'accel_longitudinal_mps2':0, 'acceleration_method':METHOD})['accel_longitudinal'],0)
        self.assertEqual(measured_kinematics(dict(raw,forward_vector=[2,0,0]))['accel_longitudinal'],1.)
        for patch in [{'forward_vector':[0,0,0]},
                      {'accel_longitudinal_mps2':-3,'acceleration_method':METHOD},
                      {'velocity_mps':[1,float('nan'),0]}]:
            with self.subTest(patch=patch):
                with self.assertRaises(ValueError):measured_kinematics(dict(raw,**patch))

    def test_saved_acceleration_and_speed_share_the_original_projection(self):
        from traffic_spec_adapter.adapter import measured_kinematics,index_motion,audit_motion
        raw={'actor_id':7,'velocity_mps':[3,4,12], 'acceleration_mps2':[2,3,4],
             'forward_vector':[1,0,0], 'accel_longitudinal_mps2':2}
        packet={}; index_motion(packet,raw,'original_frame')
        scene={'users':[{'track':7,'kin':{'velocity':[3,-4],'speed':13}}]}
        changes,_=audit_motion(scene,packet)
        self.assertTrue(changes)
        self.assertEqual(scene['users'][0]['kin'], measured_kinematics(raw))
        scene['users'][0]['kin']['velocity']=[4,-3]
        with self.assertRaises(ValueError):audit_motion(scene,packet)

class CommonProjectionTests(unittest.TestCase):
    def test_observed_signals_are_exported_without_law_dependencies(self):
        scene={'subject':1,'users':[{'track':1}], 'structures':[], 'devices':[]}
        repair_scene(scene,set(),{'ego_lamps':{'turn_indicator':'off','brake_lamp':False}}, {}, {})
        self.assertEqual(scene['users'][0]['sig'], {'turn_indicator':'off','brake_lamp':False})

    def test_pedestrian_equipment_and_complete_lane_markings(self):
        from traffic_spec_adapter.atom_contract import observed
        scene={'users':[{'track':1,'classes':['pedestrian']}], 'structures':[]}
        self.assertTrue(observed(scene,'sig.headlamp','exact'))
        self.assertTrue(observed(scene,'kin.steer_angle','exact'))
        self.assertFalse(observed(scene,'kin.velocity','exact'))
        scene['structures']=[{'id':1,'kind':'lane','lane':{'marking_left':['none','white']}}]
        self.assertFalse(observed(scene,'st.lane_marking','exact'))
        scene['structures'][0]['lane']['marking_right']=['none','white']
        self.assertTrue(observed(scene,'st.lane_marking','exact'))

class RuntimeRequirementTests(unittest.TestCase):
    def test_unknown_requirement_names_fail_with_producer_location(self):
        from unittest.mock import patch
        from traffic_spec_adapter.atom_contract import validate_required_atoms
        with patch('traffic_spec_adapter.adapter.atom_ids',return_value=['kin.speed']):
            validate_required_atoms(['kin.speed'],'fixture','valid-report')
            for atom in ('ru.animal','drv.wrong_way'):
                with self.assertRaisesRegex(ValueError,'producer-report'):
                    validate_required_atoms([atom],'fixture','producer-report')

class BoundClassificationTests(unittest.TestCase):
    known={'motor_vehicle','motorcycle','moped','bicycle','pedestrian','child','bus','truck','taxicab'}
    def test_native_car_clears_only_source_resolved_masks(self):
        from traffic_spec_adapter.classifications import classify,project_user
        evidence={'blueprint':'vehicle.fixture','blueprint_attributes':{'base_type':'car'}}
        positive,unknown=classify(evidence['blueprint'],evidence['blueprint_attributes'],self.known)
        self.assertEqual(positive,['motor_vehicle']);self.assertEqual(unknown,['taxicab'])
        user={'track':1,'classes':None,'unobserved_classes':sorted(self.known)}
        result=project_user(user,self.known,evidence)
        self.assertEqual(result['classes'],positive);self.assertEqual(result['unobserved_classes'],unknown)
        self.assertIsNone(user['classes'])
    def test_unknown_vehicle_and_name_substrings_do_not_establish_categories(self):
        from traffic_spec_adapter.classifications import classify
        positive,unknown=classify('vehicle.contains_motorcycle_or_bicycle',{},self.known)
        self.assertEqual(positive,[])
        self.assertIn('motor_vehicle',unknown);self.assertIn('bicycle',unknown)
        self.assertNotIn('pedestrian',unknown);self.assertNotIn('child',unknown)
    def test_separate_two_wheeler_and_bus_classes(self):
        from traffic_spec_adapter.classifications import classify
        self.assertEqual(classify('vehicle.fixture',{'base_type':'bicycle'},self.known)[0],['bicycle'])
        positive,unknown=classify('vehicle.fixture',{'base_type':'motorcycle'},self.known)
        self.assertEqual(positive,['motorcycle']);self.assertIn('moped',unknown)
        self.assertEqual(classify('vehicle.fixture',{'base_type':'bus'},self.known)[0],['bus','motor_vehicle'])
    def test_walker_age_and_service_role_need_their_own_evidence(self):
        from traffic_spec_adapter.classifications import classify
        positive,unknown=classify('walker.pedestrian.0001',{},self.known)
        self.assertEqual(positive,['pedestrian']);self.assertIn('child',unknown);self.assertNotIn('taxicab',unknown)
        positive,unknown=classify('walker.pedestrian.0001',{'age':'child'},self.known)
        self.assertIn('child',positive);self.assertNotIn('child',unknown)
    def test_conflicting_original_identity_is_rejected(self):
        from traffic_spec_adapter.adapter import index_motion
        packet={};index_motion(packet,{'actor_id':1,'blueprint':'vehicle.a'},'first')
        with self.assertRaises(ValueError):index_motion(packet,{'actor_id':1,'blueprint':'vehicle.b'},'second')

class EstimatedStripTests(unittest.TestCase):
    def test_distinct_widths_flat_caps_and_normalization(self):
        from traffic_spec_adapter.geometry import strip_polygon,normalized_polygon
        from shapely.geometry import Polygon
        for width in (.01,.35):
            boundary,method=strip_polygon([[0,0],[5,0],[10,0]],width)
            self.assertAlmostEqual(Polygon(boundary).area,10*width)
            self.assertEqual(Polygon(boundary).bounds,(0,-width/2,10,width/2))
            self.assertEqual(method['half_width_m'],width/2)
        self.assertEqual(normalized_polygon([[0,0],[1,0],[1,1],[0,0]]),[[0,0],[1,0],[1,1]])
    def test_crossings_and_invalid_polygons_are_not_hull_repaired(self):
        from traffic_spec_adapter.geometry import strip_polygon,normalized_polygon
        with self.assertRaises(ValueError):strip_polygon([[0,0],[1,1],[0,1],[1,0]],.01)
        with self.assertRaises(ValueError):normalized_polygon([[0,0],[1,1],[0,1],[1,0]])

    def test_zero_native_width_does_not_erase_retained_area_outline(self):
        from traffic_spec_adapter.geometry import entrance_geometry_fields
        xml='<OpenDRIVE><road id="1"><planView><geometry s="0" x="0" y="0" hdg="0" length="20"><line/></geometry></planView><objects><object id="line" name="StopLine" s="5" t="-2" length="4" width="0"/></objects></road></OpenDRIVE>'
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'road.xodr';path.write_text(xml)
            region={'id':1,'kind':'stop_line','position':[5,-2],
                    'boundary':[[3,-2.15],[7,-2.15],[7,-1.85],[3,-1.85]]}
            fields=entrance_geometry_fields(path,[region])
            self.assertNotIn('_unobserved_paint_boundary',fields[1])
            region['boundary']=[[3,-2],[7,-2]]
            self.assertTrue(entrance_geometry_fields(path,[region])[1]['_unobserved_paint_boundary'])

class AnalyticCentrelineSamplingTests(unittest.TestCase):
    def test_curved_divider_samples_to_declared_geometric_error(self):
        xml='<OpenDRIVE><road id="1" length="1"><planView><geometry s="0" x="0" y="0" hdg="0" length="1"><arc curvature="0.5"/></geometry></planView><lanes><laneSection s="0"><left><lane id="1" type="driving"/></left><right><lane id="-1" type="driving"/></right></laneSection></lanes></road></OpenDRIVE>'
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'road.xodr';path.write_text(xml)
            value=native_centre_lines(path)[0]
        method=value['source']['geometry_method']
        self.assertGreater(len(value['source']['native_centerline']),2)
        self.assertLessEqual(method['max_reference_deviation_m'],method['reference_deviation_budget_m'])
        self.assertTrue(value['shape'].is_valid)
        self.assertEqual(method['total_width_m'],.01)

class JunctionIdentityTests(unittest.TestCase):
    def test_source_component_canonicalization_preserves_referenced_id(self):
        from traffic_spec_adapter.geometry import canonical_junctions
        from traffic_spec_adapter.roadways import apply_replacements
        boundary=[[0,0],[2,0],[2,2],[0,2]]
        regions=[{'id':19,'kind':'intersection','boundary':boundary},
                 {'id':26,'kind':'intersection','boundary':boundary[2:]+boundary[:2]}]
        native=[dict(regions[0],id=100)];sources={100:{'junction_id':10,'component':0}}
        bindings=[{'region':i,'junction_id':10,'component':0,'map_sha256':'map'} for i in (19,26)]
        replacements=canonical_junctions(regions,native,sources,bindings,'map',preferred={26})
        self.assertEqual(replacements,{19:26})
        scene={'structures':regions,'users':[],'devices':[{'id':1,'governs':[19,26]}],
               'occupies':[[7,19],[7,26]],'intents':[{'vehicle':7,'target':19}]}
        result=apply_replacements(scene,replacements,[19])
        self.assertEqual(result['occupies'],[[7,26]])
        self.assertEqual(result['devices'][0]['governs'],[26])
        self.assertEqual(result['intents'][0]['target'],26)
        self.assertEqual(canonical_junctions(regions,native,sources,[],'map'),{})
    def test_equal_xy_distinct_components_are_not_merged_and_cycles_fail(self):
        from traffic_spec_adapter.geometry import canonical_junctions
        from traffic_spec_adapter.compatibility import remap_regions
        regions=[{'id':i,'kind':'intersection','boundary':[[0,0],[2,0],[2,2],[0,2]]} for i in (1,2)]
        sources={1:{'junction_id':10,'component':0},2:{'junction_id':11,'component':0}}
        bindings=[{'region':i,'junction_id':9+i,'component':0,'map_sha256':'map'} for i in (1,2)]
        self.assertEqual(canonical_junctions(regions,regions,sources,bindings,'map'),{})
        for replacements in ({1:2,2:1},{1:99}):
            with self.assertRaises(ValueError):remap_regions({'structures':regions},replacements)

class CoverageScopeTests(unittest.TestCase):
    def test_zero_inventory_subject_scope_and_unsupported_are_distinct(self):
        from collections import Counter
        from traffic_spec_adapter.atom_contract import gaps
        scene={'subject':1,'users':[{'track':1,'kin':{'path_length':0}}, {'track':2,'kin':{}}],
               'structures':[],'devices':[]}
        capability={'atoms':{'kin.path_length':'subject','st.bicycle_lane_or_path':'exact',
                    'dev.lane_control_signal':'exact','dev.human_direction':'absent','dev.stop_sign':'exact'}}
        inventory={'kinds':{'bicycle_lane_or_path':{'count':0},'lane_control_signal':{'count':0}}}
        limits=Counter()
        self.assertEqual(gaps(scene,set(capability['atoms']),capability=capability,
                              static_inventory=inventory,limitations=limits),[])
        self.assertEqual(limits,{'dev.human_direction:unsupported_by_source':1,'dev.stop_sign:unknown_inventory':1})
        self.assertIn('st.bicycle_lane_or_path',gaps(scene,{'st.bicycle_lane_or_path'},capability=capability))
        scene['structures']=[{'id':1,'kind':'bicycle_lane_or_path'}]
        with self.assertRaises(ValueError):gaps(scene,{'st.bicycle_lane_or_path'},static_inventory=inventory)

class LaneEntryApplicabilityTests(unittest.TestCase):
    def test_nonapproach_requires_proof_and_unknown_is_a_processing_limit(self):
        from collections import Counter
        from traffic_spec_adapter.atom_contract import gaps
        scene={'structures':[{'id':1,'kind':'lane','lane':{}},
                             {'id':2,'kind':'lane','lane':{'enters_intersection':10}}]}
        limits=Counter()
        self.assertEqual(gaps(scene,{'st.lane_enters'},lane_entry_applicability={1:False,2:True},limitations=limits),[])
        self.assertFalse(limits)
        self.assertEqual(gaps(scene,{'st.lane_enters'},lane_entry_applicability={},limitations=limits),[])
        self.assertEqual(limits,{'st.lane_enters:unknown_applicability':1})
        scene['structures'][1]['lane'].clear()
        self.assertEqual(gaps(scene,{'st.lane_enters'},lane_entry_applicability={1:False,2:True}),['st.lane_enters'])
