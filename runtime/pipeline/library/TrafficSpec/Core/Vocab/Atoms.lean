/-
  TrafficSpec.Core.Vocab.Atoms
  The bijection with the atoms of ATOMS.md: exactly one definition per atom id, named `family_name`,
  each reading one field of `World` and nothing else. Attribute accessors of an atom carry the
  atom's name plus a suffix (`dev_traffic_signal_shows`, `ru_rider_posture_on_seat`).

  Rules of this file, held by the doctor:
  - every `\`family.name\`` in ATOMS.md has exactly one `def family_name` here and vice versa;
  - no thresholds, no comparisons against constants, no temporal lookback: a threshold is a rule's
    or a derived concept's business;
  - the `rel_*` atoms may compute geometry from kinematics, because their contract says they are
    "computed from kinematics; listed because a source may supply them measured" — a measured
    value, when the source gives one, is preferred; `rel_visible` reads a measured value only.

  Every atom is three-valued: `none` is "not observed on this source".
-/
import TrafficSpec.Core.Vocab.World
import TrafficSpec.Core.Vocab.Assumptions

namespace TrafficSpec

-- ---------------------------------------------------------------------------------------------
-- Geometry helpers for the `rel_*` atoms (exact rationals; the one square root is an integer
-- square root at micrometre resolution).
-- ---------------------------------------------------------------------------------------------
namespace Geom
def vsub (a b : Vec) : Vec := (Q.sub a.1 b.1, Q.sub a.2 b.2)
def vadd (a b : Vec) : Vec := (Q.add a.1 b.1, Q.add a.2 b.2)
def dot (a b : Vec) : Q := Q.add (Q.mul a.1 b.1) (Q.mul a.2 b.2)
/-- 2-D cross product `a × b`; positive when `b` is to the left of `a`. -/
def cross (a b : Vec) : Q := Q.sub (Q.mul a.1 b.2) (Q.mul a.2 b.1)
def normSq (a : Vec) : Q := dot a a
/-- Square root of a non-negative quantity in metres, floored to micrometres. -/
def sqrtMicro (q : Q) : Q :=
  if q.num ≤ 0 then Q.zero
  else
    let scaled : Int := (q.num * 1000000000000) / (q.den : Int)   -- µm²
    Units.micrometres (Int.ofNat (isqrt scaled.toNat))
def norm (a : Vec) : Q := sqrtMicro (normSq a)
/-- Components of `v` in the frame of heading `h` (longitudinal, lateral); lateral positive = left. -/
def inFrame (h v : Vec) : Option (Q × Q) :=
  let n := norm h
  if Q.isZero n then none
  else some (Q.div (dot h v) n, Q.div (cross h v) n)
/-- The unit vector along `a`; `none` for the zero vector. -/
def unit (a : Vec) : Option Vec :=
  let n := norm a
  if Q.isZero n then none else some (Q.div a.1 n, Q.div a.2 n)
/-- Distance from a point to a segment. -/
def segmentDistance (p a b : Vec) : Q :=
  let ab := vsub b a
  let ap := vsub p a
  let l2 := normSq ab
  if Q.isZero l2 then norm ap
  else
    let t := Q.max Q.zero (Q.min (Q.ofInt 1) (Q.div (dot ap ab) l2))
    norm (vsub p (vadd a (Q.mul t ab.1, Q.mul t ab.2)))
/-- Whether a point lies inside a polygon (ray casting), for footprint-in-region tests. -/
def inPolygon (p : Vec) (poly : List Vec) : Bool :=
  let n := poly.length
  if n < 3 then false
  else
    let edges := (List.range n).map fun i => (poly[i]!, poly[(i + 1) % n]!)
    let crossings := edges.filter fun (a, b) =>
      let (ax, ay) := a; let (bx, by_) := b
      ((Q.le ay p.2) != (Q.le by_ p.2)) &&
        -- x-intersection of the edge with the horizontal line through p, compared with p.x
        (let dy := Q.sub by_ ay
         !Q.isZero dy &&
         Q.lt p.1 (Q.add ax (Q.div (Q.mul (Q.sub p.2 ay) (Q.sub bx ax)) dy)))
    crossings.length % 2 == 1
/-- The sign of `(b − a) × (c − a)`: 1 when `c` is to the left of `ab`, −1 to its right, 0 on its line. -/
def orient (a b c : Vec) : Int :=
  let k := (cross (vsub b a) (vsub c a)).num
  if k > 0 then 1 else if k < 0 then -1 else 0
/-- Whether `p` lies on the closed segment `ab`, given that it lies on its line. -/
def withinBox (p a b : Vec) : Bool :=
  Q.le (Q.min a.1 b.1) p.1 && Q.le p.1 (Q.max a.1 b.1) && Q.le (Q.min a.2 b.2) p.2 && Q.le p.2 (Q.max a.2 b.2)
/-- Whether the closed segments `ab` and `cd` share a point, touching and collinear overlap included. -/
def segmentsIntersect (a b c d : Vec) : Bool :=
  let o1 := orient a b c; let o2 := orient a b d; let o3 := orient c d a; let o4 := orient c d b
  (o1 * o2 < 0 && o3 * o4 < 0) || (o1 == 0 && withinBox c a b) || (o2 == 0 && withinBox d a b)
    || (o3 == 0 && withinBox a c d) || (o4 == 0 && withinBox b c d)
/-- The edges of a polygon, the last vertex closing to the first. -/
def edges (poly : List Vec) : List (Vec × Vec) :=
  let n := poly.length
  (List.range n).map fun i => (poly[i]!, poly[(i + 1) % n]!)
/-- Whether two polygons share a point as closed sets: an edge of one meets an edge of the other
    (touching counts), or one lies inside the other. Exact. -/
def polygonsOverlap (p q : List Vec) : Bool :=
  (edges p).any (fun (a, b) => (edges q).any fun (c, d) => segmentsIntersect a b c d)
    || p.any (inPolygon · q) || q.any (inPolygon · p)
/-- Distance from a point to a polygon's boundary: zero inside, the nearest edge outside. -/
def polygonDistance (p : Vec) (poly : List Vec) : Option Q :=
  match poly with
  | [] => none
  | [a] => some (norm (vsub p a))
  | _ =>
    if inPolygon p poly then some Q.zero
    else
      let n := poly.length
      let ds := (List.range n).map fun i => segmentDistance p poly[i]! poly[(i + 1) % n]!
      ds.foldl (fun acc d => match acc with | none => some d | some a => some (Q.min a d)) none
/-- The point of a segment nearest a point. -/
def segmentNearest (p a b : Vec) : Vec :=
  let ab := vsub b a
  let l2 := normSq ab
  if Q.isZero l2 then a
  else
    let t := Q.max Q.zero (Q.min (Q.ofInt 1) (Q.div (dot (vsub p a) ab) l2))
    vadd a (Q.mul t ab.1, Q.mul t ab.2)
/-- The point of a polygon's boundary nearest a point. -/
def nearestPoint (p : Vec) (poly : List Vec) : Option Vec :=
  match poly with
  | [] => none
  | [a] => some a
  | _ =>
    let n := poly.length
    let cs := (List.range n).map fun i => segmentNearest p poly[i]! poly[(i + 1) % n]!
    cs.foldl (fun acc c => match acc with
      | none => some c
      | some b => if Q.lt (normSq (vsub p c)) (normSq (vsub p b)) then some c else some b) none
end Geom

-- ---------------------------------------------------------------------------------------------
-- Road users
-- ---------------------------------------------------------------------------------------------
private def hasClass (s : Scene) (x : TrackId) (c : RoadUserClass) : Option Bool :=
  (s.user x).bind fun u => if u.unobservedClasses.contains c then none else u.classes.map (·.contains c)

def ru_motor_vehicle (s : Scene) (x : TrackId) : Option Bool := hasClass s x .motorVehicle
def ru_motorcycle (s : Scene) (x : TrackId) : Option Bool := hasClass s x .motorcycle
def ru_moped (s : Scene) (x : TrackId) : Option Bool := hasClass s x .moped
def ru_bus (s : Scene) (x : TrackId) : Option Bool := hasClass s x .bus
def ru_transit_bus (s : Scene) (x : TrackId) : Option Bool := hasClass s x .transitBus
def ru_school_bus (s : Scene) (x : TrackId) : Option Bool := hasClass s x .schoolBus
def ru_taxicab (s : Scene) (x : TrackId) : Option Bool := hasClass s x .taxicab
def ru_tour_bus_or_limousine (s : Scene) (x : TrackId) : Option Bool := hasClass s x .tourBusOrLimousine
def ru_truck (s : Scene) (x : TrackId) : Option Bool := hasClass s x .truck
def ru_commercial_motor_vehicle (s : Scene) (x : TrackId) : Option Bool := hasClass s x .commercialMotorVehicle
def ru_trailer_or_combination (s : Scene) (x : TrackId) : Option Bool := hasClass s x .trailerOrCombination
def ru_bicycle (s : Scene) (x : TrackId) : Option Bool := hasClass s x .bicycle
def ru_electric_bicycle (s : Scene) (x : TrackId) : Option Bool := hasClass s x .electricBicycle
def ru_electric_scooter (s : Scene) (x : TrackId) : Option Bool := hasClass s x .electricScooter
def ru_pedestrian (s : Scene) (x : TrackId) : Option Bool := hasClass s x .pedestrian
def ru_pedestrian_with_white_cane_or_guide_animal (s : Scene) (x : TrackId) : Option Bool := hasClass s x .pedestrianWithWhiteCaneOrGuideAnimal
def ru_child (s : Scene) (x : TrackId) : Option Bool := hasClass s x .child
def ru_emergency_vehicle (s : Scene) (x : TrackId) : Option Bool := hasClass s x .emergencyVehicle
def ru_fire_apparatus (s : Scene) (x : TrackId) : Option Bool := hasClass s x .fireApparatus
def ru_official_vehicle (s : Scene) (x : TrackId) : Option Bool := hasClass s x .officialVehicle
def ru_rail_vehicle (s : Scene) (x : TrackId) : Option Bool := hasClass s x .railVehicle

def ru_subject (s : Scene) (x : TrackId) : Option Bool := s.subject.map (· == x)
/-- Whether the road user carries one of the listed classes: true when it carries one; unknown when
    none holds and a listed class is unobserved (or the classes were not observed at all); false
    otherwise. A legal aggregate's membership is read through it, once for the classes its
    definition includes and once for those it leaves unresolved. -/
def ru_aggregate (s : Scene) (x : TrackId) (members : List RoadUserClass) : Option Bool :=
  (s.user x).bind fun u =>
    let has : List (Option Bool) := members.map fun c =>
      if u.unobservedClasses.contains c then none else u.classes.map (·.contains c)
    if has.any (· == some true) then some true
    else if has.any (·.isNone) then none
    else some false
def ru_occupant_count (s : Scene) (x : TrackId) : Option Nat := (s.user x).bind (·.occupants)
def ru_rider_posture (s : Scene) (x : TrackId) : Option Posture := (s.user x).map (·.posture)
def ru_rider_posture_on_seat (s : Scene) (x : TrackId) : Option Bool := (s.user x).bind (·.posture.onSeat)
def ru_rider_posture_hands_on_controls (s : Scene) (x : TrackId) : Option Nat := (s.user x).bind (·.posture.handsOnControls)
def ru_rider_posture_standing_on_deck (s : Scene) (x : TrackId) : Option Bool := (s.user x).bind (·.posture.standingOnDeck)
def ru_rider_posture_holding_another_vehicle (s : Scene) (x : TrackId) : Option Bool := (s.user x).bind (·.posture.holdingAnotherVehicle)
def ru_rider_posture_stunt (s : Scene) (x : TrackId) : Option Bool := (s.user x).bind (·.posture.stunt)
def ru_emergency_vehicle_kind (s : Scene) (x : TrackId) : Option EmergencyKind := (s.user x).bind (·.emergencyKind)
def ru_official_vehicle_kind (s : Scene) (x : TrackId) : Option OfficialKind := (s.user x).bind (·.officialKind)
def ru_electric_bicycle_class (s : Scene) (x : TrackId) : Option Nat := (s.user x).bind (·.eBikeClass)

-- ---------------------------------------------------------------------------------------------
-- Kinematics
-- ---------------------------------------------------------------------------------------------
def kin_time (s : Scene) : Timestamp := s.t
def kin_position (s : Scene) (x : TrackId) : Option Vec := (s.user x).bind (·.kin.position)
def kin_heading (s : Scene) (x : TrackId) : Option Vec := (s.user x).bind (·.kin.heading)
def kin_velocity (s : Scene) (x : TrackId) : Option Vec := (s.user x).bind (·.kin.velocity)
def kin_speed (s : Scene) (x : TrackId) : Option Q := (s.user x).bind (·.kin.speed)
def kin_accel_longitudinal (s : Scene) (x : TrackId) : Option Q := (s.user x).bind (·.kin.accelLongitudinal)
def kin_yaw_rate (s : Scene) (x : TrackId) : Option Q := (s.user x).bind (·.kin.yawRate)
def kin_extent (s : Scene) (x : TrackId) : Option (Q × Q × Q) := (s.user x).bind (·.kin.extent)
def kin_steer_angle (s : Scene) (x : TrackId) : Option Q := (s.user x).bind (·.kin.steerAngle)
def kin_path_length (s : Scene) (x : TrackId) : Option Q := (s.user x).bind (·.kin.pathLength)
def kin_engine_running (s : Scene) (x : TrackId) : Option Bool := (s.user x).bind (·.kin.engineRunning)
def kin_parking_brake (s : Scene) (x : TrackId) : Option Bool := (s.user x).bind (·.kin.parkingBrake)
def kin_gear (s : Scene) (x : TrackId) : Option Int := (s.user x).bind (·.kin.gear)
def kin_throttle (s : Scene) (x : TrackId) : Option Q := (s.user x).bind (·.kin.throttle)
def kin_service_brake (s : Scene) (x : TrackId) : Option Q := (s.user x).bind (·.kin.serviceBrake)

-- ---------------------------------------------------------------------------------------------
-- Road structure and occupancy
-- ---------------------------------------------------------------------------------------------
/-- Specific structure kinds also satisfy their parent kind. -/
def structureRefines (actual requested : StructureKind) : Bool :=
  actual == requested || match actual, requested with
  | .turnLane, .lane | .reservedLane, .lane | .centreTurnLane, .lane => true
  | .oneWayRoadway, .roadway => true
  | _, _ => false

/-- Whether a region is of a kind: unknown where the source cannot tell that kind. -/
def isKind (s : Scene) (r : RegionId) (k : StructureKind) : Option Bool :=
  (s.structure? r).bind fun st =>
    if structureRefines st.kind k then some true
    else if st.unobservedKinds.any (structureRefines k) then none else some false

def st_highway (s : Scene) (r : RegionId) : Option Bool := isKind s r .highway
def st_roadway (s : Scene) (r : RegionId) : Option Bool := isKind s r .roadway
def st_lane (s : Scene) (r : RegionId) : Option Bool := isKind s r .lane
def st_lane_direction (s : Scene) (r : RegionId) : Option Vec := (s.structure? r).bind (·.lane) |>.bind (·.direction)
def st_lane_adjacency (s : Scene) (r : RegionId) : Option LaneInfo := (s.structure? r).bind (·.lane)
def st_lane_adjacency_left (s : Scene) (r : RegionId) : Option RegionId := (st_lane_adjacency s r).bind (·.leftNeighbour)
def st_lane_adjacency_right (s : Scene) (r : RegionId) : Option RegionId := (st_lane_adjacency s r).bind (·.rightNeighbour)
def st_lane_adjacency_ordinal (s : Scene) (r : RegionId) : Option Nat := (st_lane_adjacency s r).bind (·.ordinalFromLeft)
def st_lane_adjacency_count (s : Scene) (r : RegionId) : Option Nat := (st_lane_adjacency s r).bind (·.countInDirection)
/-- Whether `r'` is lane `r`'s neighbour of the same direction on its left: decided false for every
    `r'` where `r` is first from the left, unknown where neither the neighbour nor the lane's place
    is observed. -/
def st_lane_left_of (s : Scene) (r r' : RegionId) : Option Bool :=
  match st_lane_adjacency_left s r with
  | some n => some (n == r')
  | none => if st_lane_adjacency_ordinal s r == some 1 then some false else none
/-- Whether `r'` is lane `r`'s neighbour of the same direction on its right: decided false for every
    `r'` where `r` is last of the lanes in its direction. -/
def st_lane_right_of (s : Scene) (r r' : RegionId) : Option Bool :=
  match st_lane_adjacency_right s r with
  | some n => some (n == r')
  | none =>
    match st_lane_adjacency_ordinal s r, st_lane_adjacency_count s r with
    | some o, some n => if o == n then some false else none
    | _, _ => none
def st_lane_connectivity (s : Scene) (r : RegionId) : Option (List RegionId) := (st_lane_adjacency s r).bind (·.leadsTo)
def st_entrance_of (s : Scene) (r : RegionId) : Option (List RegionId) := (s.structure? r).bind (·.entranceOf)

def st_lane_enters (s : Scene) (r : RegionId) : Option RegionId := (st_lane_adjacency s r).bind (·.entersIntersection)
def st_on_way (s : Scene) (r : RegionId) : Option (List RegionId) := (s.structure? r).bind (·.ways)
def st_lane_marking (s : Scene) (r : RegionId) : Option ((Option (MarkingType × MarkingColour)) × (Option (MarkingType × MarkingColour))) :=
  (st_lane_adjacency s r).map fun l => (l.markingLeft, l.markingRight)
def st_lane_marking_left (s : Scene) (r : RegionId) : Option (MarkingType × MarkingColour) := (st_lane_adjacency s r).bind (·.markingLeft)
def st_lane_marking_right (s : Scene) (r : RegionId) : Option (MarkingType × MarkingColour) := (st_lane_adjacency s r).bind (·.markingRight)
def st_lane_width (s : Scene) (r : RegionId) : Option Q := (st_lane_adjacency s r).bind (·.width)
def st_centre_line (s : Scene) (r : RegionId) : Option Bool := isKind s r .centreLine
def st_road_edge (s : Scene) (r : RegionId) : Option Bool := isKind s r .roadEdge
def st_road_edge_paved (s : Scene) (r : RegionId) : Option Bool := (s.structure? r).bind (·.paved)
def st_shoulder (s : Scene) (r : RegionId) : Option Bool := isKind s r .shoulder
def st_shoulder_paved (s : Scene) (r : RegionId) : Option Bool := (s.structure? r).bind (·.paved)
def st_sidewalk (s : Scene) (r : RegionId) : Option Bool := isKind s r .sidewalk
def st_median_or_divider (s : Scene) (r : RegionId) : Option Bool := isKind s r .medianOrDivider
def st_median_or_divider_opening (s : Scene) (r : RegionId) : Option Bool := (s.structure? r).bind (·.opening)
def st_one_way_roadway (s : Scene) (r : RegionId) : Option Bool := isKind s r .oneWayRoadway
def st_intersection (s : Scene) (r : RegionId) : Option Bool := isKind s r .intersection
def st_crosswalk (s : Scene) (r : RegionId) : Option Bool := isKind s r .crosswalk
def st_crosswalk_marked (s : Scene) (r : RegionId) : Option Bool := (s.structure? r).bind (·.marked)
def st_stop_line (s : Scene) (r : RegionId) : Option Bool := isKind s r .stopLine
def st_driveway_or_alley_entrance (s : Scene) (r : RegionId) : Option Bool := isKind s r .drivewayOrAlleyEntrance
def st_alley (s : Scene) (r : RegionId) : Option Bool := isKind s r .alley
/-- Horizontal curvature as a magnitude (1/m, never negative): a bend to either hand has the same value. -/
def st_curvature (s : Scene) (r : RegionId) : Option Q := (s.structure? r).bind (·.curvature) |>.map Q.abs
def st_grade (s : Scene) (r : RegionId) : Option Q := (s.structure? r).bind (·.grade)
def st_crest (s : Scene) (r : RegionId) : Option Bool := isKind s r .crest
def st_sight_distance (s : Scene) (r : RegionId) : Option Q := (s.structure? r).bind (·.sightDistance)
def st_sight_along_way (s : Scene) (x : TrackId) (w : RegionId) : Option Q :=
  (s.user x).bind fun u => u.sightAlongWay.bind fun ws => (ws.find? (·.1 == w)).map (·.2)
def st_railway_crossing (s : Scene) (r : RegionId) : Option Bool := isKind s r .railwayCrossing
def st_controlled_access (s : Scene) (r : RegionId) : Option Bool := isKind s r .controlledAccess
def st_elevated_structure (s : Scene) (r : RegionId) : Option Bool := isKind s r .elevatedStructure
def st_bicycle_lane_or_path (s : Scene) (r : RegionId) : Option Bool := isKind s r .bicycleLaneOrPath
def st_reserved_lane (s : Scene) (r : RegionId) : Option Bool := isKind s r .reservedLane
def st_reserved_lane_class (s : Scene) (r : RegionId) : Option ReservedClass := (s.structure? r).bind (·.reservedClass)
def st_centre_turn_lane (s : Scene) (r : RegionId) : Option Bool := isKind s r .centreTurnLane
def st_turn_lane (s : Scene) (r : RegionId) : Option Bool := isKind s r .turnLane
def st_turn_lane_side (s : Scene) (r : RegionId) : Option TurnSide := (s.structure? r).bind (·.turnSide)
def st_parking_space (s : Scene) (r : RegionId) : Option Bool := isKind s r .parkingSpace
def st_parking_space_angle (s : Scene) (r : RegionId) : Option Q := (s.structure? r).bind (·.parkingAngle)
def st_parking_space_designation (s : Scene) (r : RegionId) : Option ParkingDesignation := (s.structure? r).bind (·.designation)
def st_curb_zone (s : Scene) (r : RegionId) : Option Bool := isKind s r .curbZone
def st_curb_zone_kind (s : Scene) (r : RegionId) : Option CurbZoneKind := (s.structure? r).bind (·.curbKind)
def st_curb_zone_colour (s : Scene) (r : RegionId) : Option CurbColour := (s.structure? r).bind (·.curbColour)
def st_transit_stop (s : Scene) (r : RegionId) : Option Bool := isKind s r .transitStop
def st_safety_zone (s : Scene) (r : RegionId) : Option Bool := isKind s r .safetyZone
def st_pedestrian_grade_separation (s : Scene) (r : RegionId) : Option Bool := isKind s r .pedestrianGradeSeparation
def st_fire_hydrant (s : Scene) (r : RegionId) : Option Bool := isKind s r .fireHydrant
def st_fire_station_entrance (s : Scene) (r : RegionId) : Option Bool := isKind s r .fireStationEntrance
def st_roundabout (s : Scene) (r : RegionId) : Option Bool := isKind s r .roundabout
def st_obstruction (s : Scene) (r : RegionId) : Option Bool := isKind s r .obstruction
def st_obstruction_kind (s : Scene) (r : RegionId) : Option ObstructionKind := (s.structure? r).bind (·.obstructionKind)
/-- Geometry accessors every structure atom shares: the reference point and the boundary polygon. -/
def st_region_geometry (s : Scene) (r : RegionId) : Option (Option Vec × Option (List Vec)) :=
  (s.structure? r).map fun st => (st.position, st.boundary)
def st_region_geometry_position (s : Scene) (r : RegionId) : Option Vec := (s.structure? r).bind (·.position)
def st_region_geometry_boundary (s : Scene) (r : RegionId) : Option (List Vec) := (s.structure? r).bind (·.boundary)
/-- The rectangle a road user's body covers on the ground, from its position, heading and
    half-extents; `none` when one of them is not observed. -/
def footprint (s : Scene) (x : TrackId) : Option (List Vec) := do
  let p ← kin_position s x
  let h ← kin_heading s x
  let (hl, hw, _) ← kin_extent s x
  let n := Geom.norm h
  if Q.isZero n then none
  else
    let u := (Q.div h.1 n, Q.div h.2 n)
    let v := (Q.neg u.2, u.1)
    let corner (a b : Q) : Vec := Geom.vadd p (Q.add (Q.mul a u.1) (Q.mul b v.1), Q.add (Q.mul a u.2) (Q.mul b v.2))
    pure [corner hl hw, corner hl (Q.neg hw), corner (Q.neg hl) (Q.neg hw), corner (Q.neg hl) hw]

/-- Ground distance from a road user's body to a region: zero when the footprint overlaps the
    boundary, otherwise the nearest approach between the two outlines. Without a footprint (no
    extent or heading observed) the reference point is used; a point-like structure is measured
    to its reference point. -/
def st_region_geometry_distance (s : Scene) (x : TrackId) (r : RegionId) : Option Q := do
  let p ← kin_position s x
  match st_region_geometry_boundary s r, footprint s x with
  | some poly, some fp =>
    if Geom.polygonsOverlap fp poly then some Q.zero
    else
      let ds := fp.filterMap (Geom.polygonDistance · poly) ++ poly.filterMap (Geom.polygonDistance · fp)
      ds.foldl (fun acc d => match acc with | none => some d | some a => some (Q.min a d)) none
  | some poly, none => Geom.polygonDistance p poly
  | none, fp =>
    let c ← st_region_geometry_position s r
    match fp with
    | some poly => Geom.polygonDistance c poly
    | none => some (Geom.norm (Geom.vsub c p))
/-- The regions of a kind present in the scene. -/
def regionsOfKind (s : Scene) (k : StructureKind) : List RegionId :=
  (s.structures.filter (·.kind == k)).map (·.id)
/-- The regions a quantifier over a kind ranges over: those of the kind, and those whose kind the
    source cannot tell, which may be of it. -/
def regionCandidates (s : Scene) (k : StructureKind) : List RegionId :=
  (s.structures.filter fun st => st.kind == k || st.unobservedKinds.contains k).map (·.id)

def rel_occupies (s : Scene) (x : TrackId) (r : RegionId) : Option Bool :=
  if s.occupancyObserved.contains x then some (s.occupies.contains (x, r)) else none
/-- Every region the road user occupies, when its occupancy was observed. -/
def rel_occupies_regions (s : Scene) (x : TrackId) : Option (List RegionId) :=
  if s.occupancyObserved.contains x then some ((s.occupies.filter (·.1 == x)).map (·.2)) else none

-- ---------------------------------------------------------------------------------------------
-- Control devices
-- ---------------------------------------------------------------------------------------------
/-- Whether a device is of a kind: unknown where the source cannot tell that kind. -/
def devKind (s : Scene) (d : DeviceId) (k : DeviceKind) : Option Bool :=
  (s.device d).bind fun dv => if dv.unobservedKinds.contains k then none else some (dv.kind == k)

def dev_traffic_signal (s : Scene) (d : DeviceId) : Option Bool := devKind s d .trafficSignal
def dev_traffic_signal_indications (s : Scene) (d : DeviceId) : Option (List SignalIndication) := (s.device d).bind (·.indications)
def dev_traffic_signal_shows (s : Scene) (d : DeviceId) (i : SignalIndication) : Option Bool :=
  (dev_traffic_signal_indications s d).map (·.contains i)
def dev_traffic_signal_uncovered (s : Scene) (d : DeviceId) : Option Bool := (s.device d).bind (·.uncovered)
def dev_pedestrian_signal (s : Scene) (d : DeviceId) : Option Bool := devKind s d .pedestrianSignal
def dev_pedestrian_signal_state (s : Scene) (d : DeviceId) : Option PedSignalState := (s.device d).bind (·.pedState)
def dev_pedestrian_signal_countdown (s : Scene) (d : DeviceId) : Option Bool := (s.device d).bind (·.countdown)
def dev_lane_control_signal (s : Scene) (d : DeviceId) : Option Bool := devKind s d .laneControlSignal
def dev_lane_control_signal_state (s : Scene) (d : DeviceId) : Option LaneControlState := (s.device d).bind (·.laneControl)
def dev_speed_limit_beacon (s : Scene) (d : DeviceId) : Option Bool := devKind s d .speedLimitBeacon
def dev_speed_limit_beacon_flashing (s : Scene) (d : DeviceId) : Option Bool := (s.device d).bind (·.flashing)
def dev_crossing_warning_signal (s : Scene) (d : DeviceId) : Option Bool := devKind s d .crossingWarningSignal
def dev_crossing_warning_signal_active (s : Scene) (d : DeviceId) : Option Bool := (s.device d).bind (·.active)
def dev_stop_sign (s : Scene) (d : DeviceId) : Option Bool := devKind s d .stopSign
def dev_yield_sign (s : Scene) (d : DeviceId) : Option Bool := devKind s d .yieldSign
def dev_speed_limit_sign (s : Scene) (d : DeviceId) : Option Bool := devKind s d .speedLimitSign
def dev_speed_limit_sign_value (s : Scene) (d : DeviceId) : Option Q := (s.device d).bind (·.speedValue)
def dev_speed_limit_sign_kind (s : Scene) (d : DeviceId) : Option SpeedSignKind := (s.device d).bind (·.speedKind)
def dev_regulatory_sign (s : Scene) (d : DeviceId) : Option Bool := devKind s d .regulatorySign
def dev_regulatory_sign_code (s : Scene) (d : DeviceId) : Option SignCode := (s.device d).bind (·.code)
def dev_regulatory_sign_conditions (s : Scene) (d : DeviceId) : Option Conditions := (s.device d).bind (·.conditions)
def dev_zone_sign (s : Scene) (d : DeviceId) : Option Bool := devKind s d .zoneSign
def dev_zone_sign_kind (s : Scene) (d : DeviceId) : Option ZoneKind := (s.device d).bind (·.zoneKind)
def dev_zone_sign_end (s : Scene) (d : DeviceId) : Option Bool := (s.device d).bind (·.isEnd)
def dev_zone_sign_conditions (s : Scene) (d : DeviceId) : Option Conditions := (s.device d).bind (·.conditions)
def dev_railway_signal_or_gate (s : Scene) (d : DeviceId) : Option Bool := devKind s d .railwaySignalOrGate
def dev_railway_signal_or_gate_lights (s : Scene) (d : DeviceId) : Option RailLights := (s.device d).bind (·.railLights)
def dev_railway_signal_or_gate_gate (s : Scene) (d : DeviceId) : Option GateState := (s.device d).bind (·.gate)
def dev_railway_signal_or_gate_bell (s : Scene) (d : DeviceId) : Option Bool := (s.device d).bind (·.bell)
def dev_temporary_traffic_control (s : Scene) (d : DeviceId) : Option Bool := devKind s d .temporaryTrafficControl
def dev_human_direction (s : Scene) (d : DeviceId) : Option Bool := devKind s d .humanDirection
def dev_human_direction_role (s : Scene) (d : DeviceId) : Option HumanRole := (s.device d).bind (·.humanRole)
def dev_human_direction_indication (s : Scene) (d : DeviceId) : Option HumanIndication := (s.device d).bind (·.humanIndication)
def dev_school_bus_signal (s : Scene) (d : DeviceId) : Option Bool := devKind s d .schoolBusSignal
def dev_school_bus_signal_on_track (s : Scene) (d : DeviceId) : Option TrackId := (s.device d).bind (·.onTrack)
def dev_school_bus_signal_red_flashing (s : Scene) (d : DeviceId) : Option Bool := (s.device d).bind (·.redFlashing)
def dev_school_bus_signal_amber_flashing (s : Scene) (d : DeviceId) : Option Bool := (s.device d).bind (·.amberFlashing)
def dev_school_bus_signal_stop_arm (s : Scene) (d : DeviceId) : Option Bool := (s.device d).bind (·.stopArm)
def dev_governs (s : Scene) (d : DeviceId) (r : RegionId) : Option Bool :=
  (s.device d).bind fun dv => if dv.governsObserved then some (dv.governs.contains r) else none
def dev_governs_regions (s : Scene) (d : DeviceId) : Option (List RegionId) :=
  (s.device d).bind fun dv => if dv.governsObserved then some dv.governs else none
def dev_position (s : Scene) (d : DeviceId) : Option Vec := (s.device d).bind (·.position)
def dev_inoperative (s : Scene) (d : DeviceId) : Option Bool := (s.device d).bind (·.inoperative)
/-- The devices of a kind present in the scene. -/
def devicesOfKind (s : Scene) (k : DeviceKind) : List DeviceId :=
  (s.devices.filter (·.kind == k)).map (·.id)
/-- The devices a quantifier over a kind ranges over: those of the kind, and those whose kind the
    source cannot tell, which may be of it. -/
def deviceCandidates (s : Scene) (k : DeviceKind) : List DeviceId :=
  (s.devices.filter fun d => d.kind == k || d.unobservedKinds.contains k).map (·.id)

-- ---------------------------------------------------------------------------------------------
-- Signals emitted by road users
-- ---------------------------------------------------------------------------------------------
def sig_turn_indicator (s : Scene) (x : TrackId) : Option TurnIndicatorState := (s.user x).bind (·.sig.turnIndicator)
def sig_brake_lamp (s : Scene) (x : TrackId) : Option Bool := (s.user x).bind (·.sig.brakeLamp)
def sig_hazard (s : Scene) (x : TrackId) : Option Bool := (s.user x).bind (·.sig.hazard)
def sig_headlamp (s : Scene) (x : TrackId) : Option HeadlampState := (s.user x).bind (·.sig.headlamp)
def sig_position_lamp (s : Scene) (x : TrackId) : Option Bool := (s.user x).bind (·.sig.positionLamp)
def sig_reverse_lamp (s : Scene) (x : TrackId) : Option Bool := (s.user x).bind (·.sig.reverseLamp)
def sig_warning_lamp (s : Scene) (x : TrackId) : Option (List WarningLamp) := (s.user x).bind (·.sig.warningLamps)
/-- A warning lamp of the given colour lit, in any mode or facing. -/
def sig_warning_lamp_colour (s : Scene) (x : TrackId) (c : LampColour) : Option Bool :=
  (sig_warning_lamp s x).map (·.any (·.colour == c))
def sig_warning_lamp_shows (s : Scene) (x : TrackId) (c : LampColour) (m : LampMode) : Option Bool :=
  (sig_warning_lamp s x).map (·.any fun l => l.colour == c && l.mode == m)
def sig_siren (s : Scene) (x : TrackId) : Option Bool := (s.user x).bind (·.sig.siren)
def sig_horn (s : Scene) (x : TrackId) : Option Bool := (s.user x).bind (·.sig.horn)
def sig_hand_signal (s : Scene) (x : TrackId) : Option HandSignal := (s.user x).bind (·.sig.handSignal)
def sig_door_open (s : Scene) (x : TrackId) : Option (List DoorSide) := (s.user x).bind (·.sig.doorsOpen)
def sig_door_open_side (s : Scene) (x : TrackId) (side : DoorSide) : Option Bool := (sig_door_open s x).map (·.contains side)
def sig_compression_brake (s : Scene) (x : TrackId) : Option Bool := (s.user x).bind (·.sig.compressionBrake)

-- ---------------------------------------------------------------------------------------------
-- Environment
-- ---------------------------------------------------------------------------------------------
def env_darkness (s : Scene) : Option Bool := s.env.darkness
def env_precipitation (s : Scene) : Option Bool := s.env.precipitation
def env_wet_road (s : Scene) : Option Bool := s.env.wetRoad
def env_ice_or_snow (s : Scene) : Option Bool := s.env.iceOrSnow
def env_visibility (s : Scene) : Option Q := s.env.visibility
def env_civil_time (s : Scene) : Option CivilTime := s.env.civilTime

-- ---------------------------------------------------------------------------------------------
-- Relations between road users. Measured where the source supplies them, otherwise computed
-- from kinematics. `none` when a needed kinematic is missing.
-- ---------------------------------------------------------------------------------------------
def rel_centre_distance (s : Scene) (a b : TrackId) : Option Q :=
  match (s.relation a b).bind (·.centreDistance) with
  | some d => some d
  | none => do
    let pa ← kin_position s a
    let pb ← kin_position s b
    pure (Geom.norm (Geom.vsub pb pa))

/-- Components of `b`'s position relative to `a` in `a`'s heading frame (longitudinal, lateral). -/
private def relFrame (s : Scene) (a b : TrackId) : Option (Q × Q) := do
  let pa ← kin_position s a
  let pb ← kin_position s b
  let ha ← kin_heading s a
  Geom.inFrame ha (Geom.vsub pb pa)

/-- Longitudinal and lateral clearance between the two bodies in `a`'s frame, approximating each
    body by its extent along `a`'s axes; negative means overlap along that axis. -/
def rel_surface_gap (s : Scene) (a b : TrackId) : Option (Q × Q) :=
  match (s.relation a b).bind (·.surfaceGap) with
  | some g => some g
  | none => do
    let (lon, lat) ← relFrame s a b
    let (la, wa, _) ← kin_extent s a
    let (lb, wb, _) ← kin_extent s b
    pure (Q.sub (Q.abs lon) (Q.add la lb), Q.sub (Q.abs lat) (Q.add wa wb))
def rel_surface_gap_longitudinal (s : Scene) (a b : TrackId) : Option Q := (rel_surface_gap s a b).map (·.1)
def rel_surface_gap_lateral (s : Scene) (a b : TrackId) : Option Q := (rel_surface_gap s a b).map (·.2)
/-- The smaller of the two clearances, as a scalar gap. -/
def rel_surface_gap_min (s : Scene) (a b : TrackId) : Option Q := (rel_surface_gap s a b).map fun g => Q.min g.1 g.2

/-- `a` and `b` share a lane and `a` is ahead of `b` along `a`'s heading. -/
def rel_ahead_behind_in_lane (s : Scene) (a b : TrackId) : Option Bool :=
  match (s.relation a b).bind (·.aAheadOfB) with
  | some v => some v
  | none => do
    let ra ← rel_occupies_regions s a
    let rb ← rel_occupies_regions s b
    let lanes := regionsOfKind s .lane
    let shared := lanes.any fun l => ra.contains l && rb.contains l
    let (lon, _) ← relFrame s a b
    pure (shared && Q.lt lon Q.zero)
def rel_ahead_in_lane (s : Scene) (a b : TrackId) : Option Bool := rel_ahead_behind_in_lane s a b
def rel_behind_in_lane (s : Scene) (a b : TrackId) : Option Bool := rel_ahead_behind_in_lane s b a

/-- Signed overlap of the two bodies along `a`'s axis: positive when side by side. -/
def rel_longitudinal_overlap (s : Scene) (a b : TrackId) : Option Q :=
  match (s.relation a b).bind (·.longitudinalOverlap) with
  | some v => some v
  | none => do
    let (lon, _) ← relFrame s a b
    let (la, _, _) ← kin_extent s a
    let (lb, _, _) ← kin_extent s b
    pure (Q.sub (Q.add la lb) (Q.abs lon))

/-- Headings opposed (cosine below `-cosTol`) and the distance decreasing. -/
def rel_oncoming (s : Scene) (a b : TrackId) (cosTol : Q) : Option Bool :=
  match (s.relation a b).bind (·.oncoming) with
  | some v => some v
  | none => do
    let ha ← kin_heading s a
    let hb ← kin_heading s b
    let pa ← kin_position s a
    let pb ← kin_position s b
    let va ← kin_velocity s a
    let vb ← kin_velocity s b
    let na := Geom.norm ha; let nb := Geom.norm hb
    if Q.isZero na || Q.isZero nb then none
    else
      let cosθ := Q.div (Geom.dot ha hb) (Q.mul na nb)
      let closing := Q.lt (Geom.dot (Geom.vsub pb pa) (Geom.vsub vb va)) Q.zero
      pure (Q.lt cosθ (Q.neg cosTol) && closing)

/-- Headings aligned (cosine above `cosTol`). -/
def rel_same_direction (s : Scene) (a b : TrackId) (cosTol : Q) : Option Bool :=
  match (s.relation a b).bind (·.sameDirection) with
  | some v => some v
  | none => do
    let ha ← kin_heading s a
    let hb ← kin_heading s b
    let na := Geom.norm ha; let nb := Geom.norm hb
    if Q.isZero na || Q.isZero nb then none
    else pure (Q.gt (Q.div (Geom.dot ha hb) (Q.mul na nb)) cosTol)

/-- `b` relative to `a` in `a`'s frame: (longitudinal, lateral), lateral positive to the left. -/
def rel_bearing (s : Scene) (a b : TrackId) : Option Vec :=
  match (s.relation a b).bind (·.bearing) with
  | some v => some v
  | none => relFrame s a b
def rel_bearing_right (s : Scene) (a b : TrackId) : Option Bool := (rel_bearing s a b).map fun v => Q.lt v.2 Q.zero
def rel_bearing_left (s : Scene) (a b : TrackId) : Option Bool := (rel_bearing s a b).map fun v => Q.gt v.2 Q.zero
def rel_bearing_ahead (s : Scene) (a b : TrackId) : Option Bool := (rel_bearing s a b).map fun v => Q.gt v.1 Q.zero
def rel_bearing_behind (s : Scene) (a b : TrackId) : Option Bool := (rel_bearing s a b).map fun v => Q.lt v.1 Q.zero

/-- The bodies touch or overlap. -/
def rel_contact (s : Scene) (a b : TrackId) : Option Bool :=
  match (s.relation a b).bind (·.contact) with
  | some v => some v
  | none => (rel_surface_gap s a b).map fun g => Q.le g.1 Q.zero && Q.le g.2 Q.zero

/-- `b` is in `a`'s line of sight, as the source tested it; never computed. -/
def rel_visible (s : Scene) (a b : TrackId) : Option Bool := (s.relation a b).bind (·.visible)

end TrafficSpec
