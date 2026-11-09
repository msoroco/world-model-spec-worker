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
/-- The unit vector along `a`; `none` for the zero vector only. `a` is first divided by its larger
    absolute component, so the vector normalised has length between 1 and √2 whatever `a`'s scale,
    and then by that length taken to micrometres (`norm`). The result is the exact unit vector times
    a factor of at least 1 and below 1 + 2·10⁻⁶, and is exact where the scaled length is a whole
    number of micrometres (every axis-aligned direction). -/
def unit (a : Vec) : Option Vec :=
  let m := Q.max (Q.abs a.1) (Q.abs a.2)
  if Q.isZero m then none
  else
    let b := (Q.div a.1 m, Q.div a.2 m)
    let n := norm b
    some (Q.div b.1 n, Q.div b.2 n)
/-- Components of `v` in the frame of heading `h` (longitudinal, lateral); lateral positive = left.
    `h` is read as a direction (`unit`), whatever its length; `v` keeps its own. -/
def inFrame (h v : Vec) : Option (Q × Q) := do
  let u ← unit h
  pure (dot u v, cross u v)
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
/-- Every point of a polygon's boundary nearest a point: the nearest point of each edge whose
    distance is the least, so a tie keeps every equally near point whatever the vertex order. -/
def nearestPoints (p : Vec) (poly : List Vec) : List Vec :=
  match poly with
  | [] => []
  | [a] => [a]
  | _ =>
    let n := poly.length
    let cs := (List.range n).map fun i => segmentNearest p poly[i]! poly[(i + 1) % n]!
    match cs.map fun c => normSq (vsub p c) with
    | [] => []
    | d :: ds =>
      let m := ds.foldl Q.min d
      cs.filter fun c => Q.eq (normSq (vsub p c)) m
/-- The vector from the nearest point of polygon `p` to the nearest point of polygon `q`: zero when
    they share a point (`polygonsOverlap`), otherwise the shortest vector joining a vertex of one to
    the nearest point of the other's boundary, which for two convex polygons is the same for every
    nearest pair. `none` for an empty polygon. -/
def nearestOffset (p q : List Vec) : Option Vec :=
  if polygonsOverlap p q then some (Q.zero, Q.zero)
  else
    let fromP := p.filterMap fun c => (nearestPoint c q).map (vsub · c)
    let fromQ := q.filterMap fun c => (nearestPoint c p).map (vsub c ·)
    (fromP ++ fromQ).foldl (fun acc d => match acc with
      | none => some d
      | some e => if Q.lt (normSq d) (normSq e) then some d else some e) none
/-- The interval a polygon covers along the direction `u`, measured from `o`: (lowest, highest). -/
def span (u o : Vec) (poly : List Vec) : Option (Q × Q) :=
  match poly.map fun c => dot u (vsub c o) with
  | [] => none
  | x :: xs => some (xs.foldl Q.min x, xs.foldl Q.max x)
/-- Twice the signed area of a polygon (the shoelace sum). -/
def area2 (poly : List Vec) : Q :=
  (edges poly).foldl (fun acc (a, b) => Q.add acc (cross a b)) Q.zero
/-- Whether a polygon's boundary crosses or touches itself: two edges that are not neighbours
    meet, or two neighbouring edges fold back along one line. -/
def selfIntersects (poly : List Vec) : Bool :=
  let es := (edges poly).toArray
  let n := es.size
  (List.range n).any fun i => (List.range n).any fun j =>
    if j ≤ i then false
    else
      let (a, b) := es[i]!
      let (c, d) := es[j]!
      if j == i + 1 then orient a b d == 0 && Q.lt (dot (vsub b a) (vsub d c)) Q.zero
      else if i == 0 && j + 1 == n then orient c d b == 0 && Q.lt (dot (vsub d c) (vsub b a)) Q.zero
      else segmentsIntersect a b c d
/-- A simple polygon: at least three vertices, a non-zero area, and a boundary that neither crosses
    nor touches itself (a repeated vertex makes two edges that are not neighbours meet). -/
def simplePolygon (poly : List Vec) : Bool :=
  poly.length ≥ 3 && !Q.isZero (area2 poly) && !selfIntersects poly
/-- Whether a point lies on a polygon's boundary. Exact. -/
def onBoundary (p : Vec) (poly : List Vec) : Bool :=
  (edges poly).any fun (a, b) => orient a b p == 0 && withinBox p a b
/-- The parameters `t` at which the line `p + t·u` meets the polygon's boundary: one per edge it
    crosses or touches, and both ends of an edge it runs along. `u` is not the zero vector. -/
def lineCrossings (p u : Vec) (poly : List Vec) : List Q :=
  (edges poly).flatMap fun (a, b) =>
    let d := vsub b a
    let w := vsub a p
    let den := cross u d
    if Q.isZero den then
      if Q.isZero (cross u w) then [Q.div (dot w u) (dot u u), Q.div (dot (vsub b p) u) (dot u u)] else []
    else
      let s := Q.div (cross w u) den
      if Q.le Q.zero s && Q.le s (Q.ofInt 1) then [Q.div (cross w d) den] else []
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
/-- Whether kind `a` refines kind `b`, reflexively and transitively. -/
def StructureKind.refines (a b : StructureKind) : Bool := a == b || a.ancestors.contains b

/-- Whether a source that cannot tell kind `m` (it is among `unobservedKinds`) leaves this structure's
    membership of `m`'s kinds open: always where `m` refines no kind other than an abstract one;
    otherwise only where the structure is labelled `m` or a kind `m` refines, since a structure of any
    other kind is known not to be one. -/
def Structure.maskApplies (st : Structure) (m : StructureKind) : Bool :=
  (m.parent?.filter (!·.isAbstract)).isNone || m.refines st.kind

/-- Whether a structure is of kind `k`: unknown where a kind the source cannot tell, applying to this
    structure, is `k` or a kind `k` refines (the label cannot be trusted for `k`); true where the
    structure's kind refines `k`; unknown where a kind the source cannot tell, applying to this
    structure, refines `k`; false otherwise. A parent never implies a kind refining it, two kinds
    refining one parent never imply each other, and a kind the source cannot tell never makes a known
    parent unknown. An abstract kind is the union of the kinds refining it: true where the structure
    is of one of them, unknown where it is of none and unknown for one, false otherwise. -/
def Structure.isOfKind (st : Structure) (k : StructureKind) : Option Bool :=
  let masked := st.unobservedKinds.filter st.maskApplies
  let concrete (k : StructureKind) : Option Bool :=
    if masked.any (k.refines ·) then none
    else if st.kind.refines k then some true
    else if masked.any (·.refines k) then none
    else some false
  if k.isAbstract then
    let vs := (StructureKind.all.filter (·.parent? == some k)).map concrete
    if vs.contains (some true) then some true else if vs.contains none then none else some false
  else concrete k

/-- Whether a region is of a kind (`Structure.isOfKind`); unknown for a region not in the scene. -/
def isKind (s : Scene) (r : RegionId) (k : StructureKind) : Option Bool :=
  (s.structure? r).bind (·.isOfKind k)

def st_highway (s : Scene) (r : RegionId) : Option Bool := isKind s r .highway
def st_travel_region (s : Scene) (r : RegionId) : Option Bool := isKind s r .travelRegion
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
def st_lane_enters (s : Scene) (r : RegionId) : Option RegionId := (st_lane_adjacency s r).bind (·.entersIntersection)
def st_on_way (s : Scene) (r : RegionId) : Option (List RegionId) := (s.structure? r).bind (·.ways)
/-- Whether line `l` marks carrier `a`'s entrance: decided where the line's entrances are observed,
    false for a region known to be neither a stop line nor a crosswalk, unknown otherwise. -/
def st_entrance_of (s : Scene) (l a : RegionId) : Option Bool :=
  (s.structure? l).bind fun st =>
    if st.entranceObserved then some (st.entranceOf.contains a)
    else match isKind s l .stopLine, isKind s l .crosswalk with
      | some false, some false => some false
      | _, _ => none
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
  let u ← Geom.unit h
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
/-- The regions present in the scene known to be of a kind (`Structure.isOfKind` true). -/
def regionsOfKind (s : Scene) (k : StructureKind) : List RegionId :=
  (s.structures.filter (·.isOfKind k == some true)).map (·.id)
/-- The regions a quantifier over a kind ranges over: those whose membership of the kind is not
    false (`Structure.isOfKind`), the known members and those that may be members. -/
def regionCandidates (s : Scene) (k : StructureKind) : List RegionId :=
  (s.structures.filter (·.isOfKind k != some false)).map (·.id)

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

/-- The gap between the two bodies: the vector from the nearest point of `a`'s footprint to the
    nearest point of `b`'s, each footprint read with its own heading and extent, given as its
    lengths along and across `a`'s heading (longitudinal, lateral). Neither is ever negative; both
    are zero exactly when the footprints touch or overlap. `none` when either footprint is not
    observed, and when a supplied gap has a negative component. -/
def rel_surface_gap (s : Scene) (a b : TrackId) : Option (Q × Q) :=
  match (s.relation a b).bind (·.surfaceGap) with
  | some g => if Q.isNonneg g.1 && Q.isNonneg g.2 then some g else none
  | none => do
    let fa ← footprint s a
    let fb ← footprint s b
    let d ← Geom.nearestOffset fa fb
    let ha ← kin_heading s a
    let (lon, lat) ← Geom.inFrame ha d
    pure (Q.abs lon, Q.abs lat)
def rel_surface_gap_longitudinal (s : Scene) (a b : TrackId) : Option Q := (rel_surface_gap s a b).map (·.1)
def rel_surface_gap_lateral (s : Scene) (a b : TrackId) : Option Q := (rel_surface_gap s a b).map (·.2)
/-- The distance between the nearest points of the two bodies, the gap's length: zero on contact
    or overlap, never negative. -/
def rel_surface_gap_distance (s : Scene) (a b : TrackId) : Option Q := (rel_surface_gap s a b).map Geom.norm

/-- `a` and `b` share a lane and `a` is ahead of `b` along `a`'s heading. The lane is any region both
    occupy that is of kind lane (`Structure.isOfKind`): unknown when `a` is ahead and no shared region
    is known to be a lane but one may be. -/
def rel_ahead_behind_in_lane (s : Scene) (a b : TrackId) : Option Bool :=
  match (s.relation a b).bind (·.aAheadOfB) with
  | some v => some v
  | none => do
    let ra ← rel_occupies_regions s a
    let rb ← rel_occupies_regions s b
    let (lon, _) ← relFrame s a b
    if !Q.lt lon Q.zero then some false
    else
      let shared := (s.structures.filter fun st => ra.contains st.id && rb.contains st.id).map (·.isOfKind .lane)
      if shared.contains (some true) then some true
      else if shared.contains none then none
      else some false
def rel_ahead_in_lane (s : Scene) (a b : TrackId) : Option Bool := rel_ahead_behind_in_lane s a b
def rel_behind_in_lane (s : Scene) (a b : TrackId) : Option Bool := rel_ahead_behind_in_lane s b a

/-- Signed overlap of the two footprints along `a`'s heading, each read with its own heading and
    extent: the length their projections on that axis share, positive when the bodies are side by
    side, otherwise the gap between the projections negated. A projection: it reads nothing across
    the axis, so a positive value is no contact and a negative one no distance between the bodies. -/
def rel_longitudinal_overlap (s : Scene) (a b : TrackId) : Option Q :=
  match (s.relation a b).bind (·.longitudinalOverlap) with
  | some v => some v
  | none => do
    let pa ← kin_position s a
    let ha ← kin_heading s a
    let u ← Geom.unit ha
    let fa ← footprint s a
    let fb ← footprint s b
    let (loA, hiA) ← Geom.span u pa fa
    let (loB, hiB) ← Geom.span u pa fb
    pure (Q.sub (Q.min hiA hiB) (Q.max loA loB))

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
    let ua ← Geom.unit ha
    let ub ← Geom.unit hb
    let closing := Q.lt (Geom.dot (Geom.vsub pb pa) (Geom.vsub vb va)) Q.zero
    pure (Q.lt (Geom.dot ua ub) (Q.neg cosTol) && closing)

/-- Headings aligned (cosine above `cosTol`). -/
def rel_same_direction (s : Scene) (a b : TrackId) (cosTol : Q) : Option Bool :=
  match (s.relation a b).bind (·.sameDirection) with
  | some v => some v
  | none => do
    let ha ← kin_heading s a
    let hb ← kin_heading s b
    let ua ← Geom.unit ha
    let ub ← Geom.unit hb
    pure (Q.gt (Geom.dot ua ub) cosTol)

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
