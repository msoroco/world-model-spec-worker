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
    names an entity of that kind present in the same scene, and a sight-along-way entry names a
    highway; every track a link names appears in some scene;
  - a static map: the same structures in every scene, each identical at every appearance; every
    device that does not move (`Device.mobile`) in every scene; a device identical at every
    appearance outside its state (`Device.staticPart`);
  - valid geometry: a boundary has at least three vertices, all distinct (the first is not
    repeated at the end), a non-zero area and no self-intersection; an extent's half-length and
    half-width are positive; a path length is not negative; a heading is not the zero vector;
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
    else match r.structureKind with
      | some k => if (s.structure? r.id).map (·.kind) != some k then some s!"{at_ s}: {r.place} names region {r.id}, which is not a {k}" else none
      | none => none

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
-- Geometry
-- ---------------------------------------------------------------------------------------------
/-- Twice the signed area of a polygon (the shoelace sum). -/
def area2 (poly : List Vec) : Q :=
  (Geom.edges poly).foldl (fun acc (a, b) => Q.add acc (Geom.cross a b)) Q.zero

/-- Whether a polygon's boundary crosses or touches itself: two edges that are not neighbours
    meet, or two neighbouring edges fold back along one line. -/
def selfIntersects (poly : List Vec) : Bool :=
  let es := (Geom.edges poly).toArray
  let n := es.size
  (List.range n).any fun i => (List.range n).any fun j =>
    if j ≤ i then false
    else
      let (a, b) := es[i]!
      let (c, d) := es[j]!
      if j == i + 1 then Geom.orient a b d == 0 && Q.lt (Geom.dot (Geom.vsub b a) (Geom.vsub d c)) Q.zero
      else if i == 0 && j + 1 == n then Geom.orient c d b == 0 && Q.lt (Geom.dot (Geom.vsub d c) (Geom.vsub b a)) Q.zero
      else Geom.segmentsIntersect a b c d

/-- What is wrong with a boundary, or nothing. -/
def boundaryErrors (poly : List Vec) : List String :=
  if poly.length < 3 then ["has fewer than three vertices"]
  else if !(dups poly).isEmpty then ["repeats a vertex (the first vertex is not repeated at the end)"]
  else if Q.isZero (area2 poly) then ["has zero area"]
  else if selfIntersects poly then ["intersects itself"]
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
  checkReferences τ ++ staticMap τ ++ devices τ ++ geometry τ
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
