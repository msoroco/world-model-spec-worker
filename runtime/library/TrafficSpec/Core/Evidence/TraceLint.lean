/-
  TrafficSpec.Core.Evidence.TraceLint
  The admission check of a trace written by hand (a reviewer's counterexample), before any rule is
  run on it. It reads the trace and, for the witness check, a grounding, a case's entities and one
  timestamp: no law, rule, formula, contract or reading parameter. Every check is exact, in
  rational arithmetic, with no tolerance: a written trace has no measurement noise, and its author
  is shown these rules. Traces a source records are never held to it.

  `checkTrace` requires:
  - identity: track, region and device ids unique within a scene; at most one measured relation
    per ordered pair of tracks within a scene; every reference a scene makes (`Scene.references`)
    names an entity of that kind present in the same scene, a sight-along-way entry names a
    highway, and an `entrance_of` entry names a lane, a roadway, a shoulder or a bicycle lane or
    path, or a kind refining one (`StructureKind.entranceCarriers`); every track a link names
    appears in some scene;
  - a static map: the same structures in every scene, each identical at every appearance; every
    device that does not move (`Device.mobile`) in every scene; a device identical at every
    appearance outside its state (`Device.staticPart`);
  - one representation of direction and control: a designated direction (`lane.direction`) is
    carried only by a structure a vehicle travels in (`directionKinds`: a lane, reserved lane,
    turn lane, bicycle lane or path, roadway, one-way roadway or shoulder; a centre turn lane
    carries none), and is not the zero vector; each carrier stands on its own, and carriers that
    overlap or cross may carry different directions. A device whose control is observed governs
    only the travel regions whose traffic it controls, or an intersection, read as control of the
    junction itself (`governedKinds`); never a highway, a controlled-access region or a region no
    vehicle travels in. Only a lane, a roadway, a shoulder or a bicycle lane or path, or a kind
    refining one, carries the intersection it is an approach to (`lane.enters_intersection`); a
    roadway, one-way roadway, shoulder or bicycle lane or path that carries one is a directed
    approach segment entering that one intersection, which the check cannot see, and a whole
    two-way roadway or bicycle path carries none. Only a stop line or a crosswalk
    lists the carriers whose entrance it marks (`entrance_of`). A place no carrier covers has no
    designated direction, a device whose `governs` is not written has no observed control, and a
    line whose `entrance_of` is not written has no observed entrances; none is filled in;
  - valid geometry: a boundary has at least three vertices, all distinct (the first is not
    repeated at the end), a non-zero area and no self-intersection; an extent's half-length and
    half-width are positive; a path length is not negative; a heading is not the zero vector; a
    supplied relation's `surface_gap` has no negative component (each is a distance between the
    bodies' nearest points, zero on contact or overlap);
  - geometric occupancy: a track whose occupancy is observed has a position, a heading and an
    extent, and in a scene with such a track every structure has a valid boundary, because a
    pair absent from `occupies` is read as not occupied. The pairs of such a track are not
    written by hand: `completeOccupancy` derives them, the pair (track, structure) exactly when
    the track's footprint (`footprint`) and the structure's boundary overlap as closed sets
    (`Geom.polygonsOverlap`), so touching counts and a body on the line between two lanes
    occupies both;
  - path length: between consecutive observations of a track's path length it never decreases,
    and its increase is at least the straight-line distance between the two positions;
  - heading against yaw rate: where a track's heading is the same direction at two consecutive
    scenes (parallel and not opposed, whatever the vectors' lengths), the yaw rate integrated
    between them, ω (t₁ − t₀) with the later sample's rate held over the interval before it, is a
    whole number of turns (a multiple of 360°).
  `checkReferences` is the identity part alone. A witness trace is held to the whole check, after
  `completeOccupancy`, as a reviewer's trace is.
  `checkWitness` requires that `at` is the timestamp of a scene, and that every grounded track and
  every entity of the case, with its declared kind, is present in that scene.

  Each message names the scene by its timestamp, the entity and the field.
-/
import TrafficSpec.Core.Vocab.Atoms
import TrafficSpec.Core.Language.Formula

namespace TrafficSpec
namespace TraceLint

private def dups {α : Type} [BEq α] (xs : List α) : List α :=
  (xs.filter fun x => xs.count x > 1).eraseDups
private def at_ (s : Scene) : String := s!"scene t={s.t}"
private def qs (q : Q) : String := if q.den == 1 then s!"{q.num}" else s!"{q.num}/{q.den}"
private def kindName : EntityKind → String
  | .track => "track" | .region => "region" | .device => "device"
private def reprStr {α : Type} [Repr α] (x : α) : String := toString (repr x)
private def orList (ks : List StructureKind) : String :=
  match ks.reverse with
  | [] => ""
  | [k] => k.toString
  | k :: rest => s!"{", ".intercalate (rest.reverse.map (·.toString))} or {k}"

/-- Whether an entity of this kind and id is present in the scene. -/
def present (s : Scene) (k : EntityKind) (id : Nat) : Bool :=
  match k with
  | .track => s.tracks.contains id
  | .region => (s.structure? id).isSome
  | .device => (s.device id).isSome

-- ---------------------------------------------------------------------------------------------
-- Identity and references
-- ---------------------------------------------------------------------------------------------
private def identity (s : Scene) : List String :=
  (dups s.tracks).map (fun t => s!"{at_ s}: track {t} appears more than once in users")
  ++ (dups (s.structures.map (·.id))).map (fun r => s!"{at_ s}: structure id {r} appears more than once")
  ++ (dups (s.devices.map (·.id))).map (fun d => s!"{at_ s}: device id {d} appears more than once")
  ++ (dups (s.relations.map fun m => (m.a, m.b))).map (fun (a, b) => s!"{at_ s}: more than one relation for the ordered pair ({a}, {b})")
  ++ s.references.filterMap fun r =>
    if !present s r.kind r.id then
      some s!"{at_ s}: {r.place} names {kindName r.kind} {r.id}, which is not in this scene"
    else if r.structureKinds.isEmpty then none
    else if (s.structure? r.id).map (fun st => r.structureKinds.any (st.kind.refines ·)) == some true then none
    else some s!"{at_ s}: {r.place} names region {r.id}, which is not a {orList r.structureKinds}"

private def links (τ : Trace) : List String :=
  let all := (τ.flatMap (·.tracks)).eraseDups
  τ.flatMap fun s => s.links.flatMap fun (a, b) =>
    ([a, b].filter (!all.contains ·)).map fun t => s!"{at_ s}: links names track {t}, which appears in no scene"

-- ---------------------------------------------------------------------------------------------
-- The static map and the devices
-- ---------------------------------------------------------------------------------------------
private def staticMap (τ : Trace) : List String :=
  match τ with
  | [] => []
  | s0 :: _ =>
    let ids0 := s0.structures.map (·.id)
    let first := fun (r : RegionId) => τ.findSome? (·.structure? r)
    τ.flatMap fun s =>
      let ids := s.structures.map (·.id)
      (ids0.filter (!ids.contains ·)).map (fun r => s!"{at_ s}: structure {r} is missing; the map is the same in every scene")
      ++ (ids.filter (!ids0.contains ·)).map (fun r => s!"{at_ s}: structure {r} is not in the first scene; the map is the same in every scene")
      ++ s.structures.filterMap fun st => match first st.id with
        | some st0 => if reprStr st0 != reprStr st then some s!"{at_ s}: structure {st.id} differs from its first appearance; every field of a structure is the same in every scene" else none
        | none => none

private def devices (τ : Trace) : List String :=
  let ids := (τ.flatMap fun s => s.devices.map (·.id)).eraseDups
  let first := fun (d : DeviceId) => τ.findSome? (·.device d)
  τ.flatMap fun s =>
    (ids.filterMap fun d => match first d with
      | some dv => if !dv.mobile && (s.device d).isNone then some s!"{at_ s}: device {d} is missing; a device that does not move is in every scene" else none
      | none => none)
    ++ s.devices.filterMap fun dv => match first dv.id with
      | some d0 =>
        if reprStr d0.staticPart != reprStr dv.staticPart then
          some s!"{at_ s}: device {dv.id} differs from its first appearance in a field that is not its state (its state is {String.intercalate ", " Device.stateFields}{if d0.mobile then ", position" else ""})"
        else none
      | none => none

-- ---------------------------------------------------------------------------------------------
-- Representation: where a designated direction and a device's control are written
-- ---------------------------------------------------------------------------------------------
/-- The structure kinds a vehicle travels in that may carry a designated direction. A centre turn
    lane, shared by both directions, carries none. -/
def directionKinds : List StructureKind :=
  [.lane, .reservedLane, .turnLane, .bicycleLaneOrPath, .roadway, .oneWayRoadway, .shoulder]

/-- The structure kinds a device may govern: the kinds refining the travel region, the regions
    whose traffic it controls and an intersection, read as control of the junction itself and of
    nothing else. -/
def governedKinds : List StructureKind :=
  StructureKind.all.filter fun k => !k.isAbstract && k.refines .travelRegion

/-- The structure kinds that mark a carrier's entrance into an intersection. -/
def entranceKinds : List StructureKind := [.stopLine, .crosswalk]

/-- The structure kinds that carry an entrance into an intersection: those of
    `StructureKind.entranceCarriers` and every kind refining one of them. -/
def carrierKinds : List StructureKind :=
  StructureKind.all.filter fun k => StructureKind.entranceCarriers.any (k.refines ·)

/-- The kinds a region may have at each region argument of an atom or primitive, keyed by its Lean
    name and the argument's index in its full argument list: `some ks` where the field the name reads
    there is carried by, or may name, only a region whose kind is in `ks` (the lists this check and
    `Scene.references` hold the field to); `none` where a region of any kind may stand there. A class
    atom `st_<kind>` reads the label every region has and is `none`. -/
def regionArgKinds : List ((String × Nat) × Option (List StructureKind)) :=
  let refining := fun (ks : List StructureKind) => StructureKind.all.filter fun k => ks.any (k.refines ·)
  [(("st_lane_enters", 0), some carrierKinds),
   (("st_entrance_of", 0), some entranceKinds),
   (("st_entrance_of", 1), some (refining StructureKind.entranceCarriers)),
   (("st_lane_direction", 0), some directionKinds),
   (("dev_governs", 1), some governedKinds),
   (("st_sight_along_way", 1), some (refining StructureKind.sightWays)),
   (("prim_region_offset_along", 2), some directionKinds)]
  ++ ([("st_lane_enters", 1), ("rel_occupies", 1), ("st_road_edge_paved", 0), ("st_shoulder_paved", 0),
       ("st_median_or_divider_opening", 0), ("st_crosswalk_marked", 0), ("st_reserved_lane_class", 0),
       ("st_turn_lane_side", 0), ("st_parking_space_designation", 0), ("st_curb_zone_kind", 0),
       ("st_curb_zone_colour", 0), ("st_obstruction_kind", 0), ("st_lane_adjacency", 0), ("st_lane_adjacency", 2),
       ("st_lane_adjacency_left", 0), ("st_lane_adjacency_left", 1), ("st_lane_adjacency_right", 0),
       ("st_lane_adjacency_right", 1), ("st_lane_connectivity", 0), ("st_lane_connectivity", 1), ("st_on_way", 0),
       ("st_on_way", 1), ("st_lane_marking", 0), ("st_lane_marking_left", 0), ("st_lane_marking_right", 0),
       ("st_lane_adjacency_ordinal", 0), ("st_lane_adjacency_count", 0), ("st_lane_width", 0), ("st_curvature", 0),
       ("st_grade", 0), ("st_sight_distance", 0), ("st_parking_space_angle", 0), ("st_region_geometry", 0),
       ("st_region_geometry_distance", 1), ("prim_region_lateral_offset", 1), ("prim_region_offset_along", 1)]
      ++ StructureKind.all.map fun k => (s!"st_{k}", 0)).map (·, none)

private def representation (τ : Trace) : List String :=
  let firstStructure := fun (r : RegionId) => τ.findSome? fun s => (s.structure? r).map fun _ => s.t
  let firstDevice := fun (d : DeviceId) => τ.findSome? fun s => (s.device d).map fun _ => s.t
  τ.flatMap fun s =>
    (s.structures.flatMap fun st =>
      -- the map is static, so each structure is reported once, at its first appearance
      if firstStructure st.id != some s.t then []
      else match st.lane.bind (·.direction) with
        | none => []
        | some v =>
          (if directionKinds.contains st.kind then []
           else [s!"{at_ s}: structure {st.id} ({st.kind.toString}) carries lane.direction; only a lane, reserved lane, turn lane, bicycle lane or path, roadway, one-way roadway or shoulder does"])
          ++ (if Q.isZero v.1 && Q.isZero v.2 then [s!"{at_ s}: structure {st.id} lane.direction is the zero vector"] else []))
    ++ (s.structures.filterMap fun st =>
      if firstStructure st.id != some s.t || (st.lane.bind (·.entersIntersection)).isNone || carrierKinds.contains st.kind then none
      else some s!"{at_ s}: structure {st.id} ({st.kind.toString}) carries lane.enters_intersection; only a lane, a roadway, a shoulder or a bicycle lane or path, or a kind refining one, enters an intersection as an approach")
    ++ (s.structures.filterMap fun st =>
      if firstStructure st.id != some s.t || !st.entranceObserved || entranceKinds.contains st.kind then none
      else some s!"{at_ s}: structure {st.id} ({st.kind.toString}) carries entrance_of; only a stop line or a crosswalk marks an entrance")
    ++ s.devices.flatMap fun dv =>
      if firstDevice dv.id != some s.t || !dv.governsObserved then []
      else dv.governs.filterMap fun r => match s.structure? r with
        | some st =>
          if governedKinds.contains st.kind then none
          else some s!"{at_ s}: device {dv.id} governs structure {r} ({st.kind.toString}); a device governs the travel regions whose traffic it controls (a lane, reserved lane, turn lane, centre turn lane, bicycle lane or path, roadway, one-way roadway or shoulder) or an intersection"
        | none => none

-- ---------------------------------------------------------------------------------------------
-- Geometry
-- ---------------------------------------------------------------------------------------------
/-- What is wrong with a boundary, or nothing. -/
def boundaryErrors (poly : List Vec) : List String :=
  if poly.length < 3 then ["has fewer than three vertices"]
  else if !(dups poly).isEmpty then ["repeats a vertex (the first vertex is not repeated at the end)"]
  else if Q.isZero (Geom.area2 poly) then ["has zero area"]
  else if Geom.selfIntersects poly then ["intersects itself"]
  else []

private def geometry (τ : Trace) : List String :=
  let firstOf := fun (r : RegionId) => τ.findSome? fun s => (s.structure? r).map fun _ => s
  τ.flatMap fun s =>
    (s.structures.filterMap fun st =>
      -- a structure is static, so its boundary is reported once, at its first appearance
      if (firstOf st.id).map (·.t) != some s.t then none
      else match st_region_geometry_boundary s st.id with
        | some poly => match boundaryErrors poly with
          | [] => none
          | e :: _ => some s!"{at_ s}: the boundary of structure {st.id} {e}"
        | none => none)
    ++ (s.relations.filterMap fun m => match m.surfaceGap with
      | some (lon, lat) =>
        if Q.lt lon Q.zero || Q.lt lat Q.zero then
          some s!"{at_ s}: relation ({m.a}, {m.b}) surface_gap ({qs lon}, {qs lat}) has a negative component; each component is a distance between the bodies' nearest points, along and across a's heading, zero on contact or overlap"
        else none
      | none => none)
    ++ s.tracks.flatMap fun x =>
      (match kin_extent s x with
       | some (l, w, _) => if Q.le l Q.zero || Q.le w Q.zero then [s!"{at_ s}: track {x} extent: the half-length and the half-width must be positive"] else []
       | none => [])
      ++ (match kin_path_length s x with
       | some p => if Q.lt p Q.zero then [s!"{at_ s}: track {x} path_length {qs p} is negative"] else []
       | none => [])
      ++ (match kin_heading s x with
       | some h => if Q.isZero h.1 && Q.isZero h.2 then [s!"{at_ s}: track {x} heading is the zero vector"] else []
       | none => [])

-- ---------------------------------------------------------------------------------------------
-- Occupancy, path length, heading against yaw rate
-- ---------------------------------------------------------------------------------------------
/-- The trace with the occupancy of every observed track derived from the geometry: in each scene,
    for a track in `occupancy_observed` whose footprint is defined, `occupies` holds the pair
    (track, structure) exactly when the footprint and the structure's valid boundary overlap as
    closed sets; what the trace listed for that track is replaced, every other pair kept. -/
def completeOccupancy (τ : Trace) : Trace :=
  τ.map fun s =>
    let derived := (s.occupancyObserved.filter (s.tracks.contains ·)).eraseDups.filter (footprint s · |>.isSome)
    let kept := s.occupies.filter fun (t, _) => !derived.contains t
    let made := derived.flatMap fun t => match footprint s t with
      | none => []
      | some fp => s.structures.filterMap fun st => match st_region_geometry_boundary s st.id with
        | some poly => if (boundaryErrors poly).isEmpty && Geom.polygonsOverlap fp poly then some (t, st.id) else none
        | none => none
    { s with occupies := kept ++ made }

private def occupancy (s : Scene) : List String :=
  let obs := (s.occupancyObserved.filter (s.tracks.contains ·)).eraseDups
  if obs.isEmpty then []
  else
    let bodies := obs.filterMap fun t =>
      if (footprint s t).isNone then
        some s!"{at_ s}: track {t} is in occupancy_observed but lacks a position, a non-zero heading or an extent, so its footprint is undefined"
      else none
    let unbounded := s.structures.filterMap fun st =>
      if (st_region_geometry_boundary s st.id).isNone then
        some s!"{at_ s}: structure {st.id} has no boundary; where occupancy is observed every structure needs one, since a pair left out of occupies is read as not occupied"
      else none
    bodies ++ unbounded

private def pathLength (τ : Trace) : List String :=
  let tracks := (τ.flatMap (·.tracks)).eraseDups
  tracks.flatMap fun x =>
    let obs := τ.filterMap fun s => (kin_path_length s x).map fun p => (s, p, kin_position s x)
    (obs.zip (obs.drop 1)).flatMap fun ((s0, p0, q0), (s1, p1, q1)) =>
      let inc := Q.sub p1 p0
      if Q.lt inc Q.zero then [s!"{at_ s1}: track {x} path_length {qs p1} is less than {qs p0} at t={s0.t}; it never decreases"]
      else match q0, q1 with
        | some a, some b =>
          if Q.lt (Q.mul inc inc) (Geom.normSq (Geom.vsub b a)) then
            [s!"{at_ s1}: track {x} path_length grows by {qs inc} m since t={s0.t}, less than the straight-line distance between its two positions"]
          else []
        | _, _ => []

/-- Whether two non-zero headings are the same direction: parallel and not opposed. -/
def sameDirection (a b : Vec) : Bool := Q.isZero (Geom.cross a b) && Q.gt (Geom.dot a b) Q.zero

/-- Whether an angle in degrees is a whole number of turns. -/
def wholeTurns (deg : Q) : Bool := deg.num % (360 * (deg.den : Int)) == 0

private def yaw (τ : Trace) : List String :=
  (τ.zip (τ.drop 1)).flatMap fun (s0, s1) =>
    s1.tracks.filterMap fun x =>
      match kin_heading s0 x, kin_heading s1 x, kin_yaw_rate s1 x with
      | some h0, some h1, some ω =>
        if !sameDirection h0 h1 then none
        else
          let turn := Q.mul ω (Q.sub (Time.ofTimestamp s1.t) (Time.ofTimestamp s0.t))
          if wholeTurns turn then none
          else some s!"{at_ s1}: track {x} keeps the heading it had at t={s0.t}, but its yaw rate turns it {qs turn}° over the interval (the rate at a scene is held over the interval before it)"
      | _, _, _ => none

/-- The identity and reference defects of a trace: what no adapter output can contain, whoever
    wrote it. Empty for a trace that passes. -/
def checkReferences (τ : Trace) : List String :=
  τ.flatMap identity ++ links τ

/-- Every inconsistency of a written trace. Empty for a trace that passes. -/
def checkTrace (τ : Trace) : List String :=
  checkReferences τ ++ staticMap τ ++ devices τ ++ representation τ ++ geometry τ
    ++ τ.flatMap occupancy ++ pathLength τ ++ yaw τ

/-- Every defect of the witness instant: `at` is a scene's timestamp, and every grounded track and
    every entity of the case, with its declared kind, is present in that scene. -/
def checkWitness (τ : Trace) (grounding : List (String × TrackId)) (entities : List (String × Val)) (at_ms : Timestamp) : List String :=
  match τ.find? (·.t == at_ms) with
  | none => [s!"at {at_ms} is not the timestamp of any scene"]
  | some s =>
    (grounding.filterMap fun (b, t) =>
      if s.tracks.contains t then none else some s!"scene t={at_ms}: binder {b} is grounded to track {t}, which is not in this scene")
    ++ entities.filterMap fun (n, v) =>
      if present s v.kind (match v with | .track t => t | .region r => r | .device d => d) then none
      else some s!"scene t={at_ms}: entity {n} is {kindName v.kind} {match v with | .track t => t | .region r => r | .device d => d}, which is not in this scene"

end TraceLint
end TrafficSpec
