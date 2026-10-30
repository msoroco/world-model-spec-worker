/-
  TrafficSpec.Core.Vocab.Primitives
  What the formula language cannot express, each a geometric computation with no legal word in it:
  a heading change integrated over a window, the closest approach of two bodies under constant
  velocities, the structured matching of a sign's legend. One definition per `prim.*` id of the
  ontology, named `prim_name`, computed over the whole trace from atoms only, parameters as
  arguments with no default.

  A concept (a pipeline node) is written over atoms and primitives in the formula language and
  expanded before evaluation; nothing else computes a manoeuvre here. `Ctx` is the trace indexed
  for evaluation, shared with Semantics.lean.
-/
import TrafficSpec.Core.Vocab.Atoms
import TrafficSpec.Core.Vocab.Params
import TrafficSpec.Core.Foundations.Temporal

namespace TrafficSpec
namespace Primitives
open Temporal

/-- The trace indexed for evaluation, with the run's reading. `aggregateOverrides` fixes the
    membership of a track in an aggregate to a value, for the sensitivity of a verdict to that
    membership; it is empty in every evaluation that judges a trace. -/
structure Ctx where
  scenes : Array Scene
  times : Array Q
  ρ : Reading
  aggregateOverrides : List (TrackId × String × Bool) := []

def Ctx.mk' (τ : Trace) (ρ : Reading) : Ctx :=
  { scenes := τ.toArray, times := (τ.map fun s => Time.ofTimestamp s.t).toArray, ρ := ρ }
def Ctx.n (c : Ctx) : Nat := c.scenes.size

/-- An argument as the dispatcher receives it: a resolved entity id (tracks, regions and devices
    are all `Nat`), an enumeration spelling, or a natural. -/
inductive DArg
  | v (id : Nat)
  | s (lit : String)
  | n (nat : Nat)
  deriving Repr, DecidableEq

-- ---------------------------------------------------------------------------------------------
-- Lifting scene functions over the trace; positions for windows
-- ---------------------------------------------------------------------------------------------
def each (c : Ctx) (f : Scene → R) : Array R := c.scenes.map f
def eachQ (c : Ctx) (f : Scene → QR) : Array QR := c.scenes.map f
def timePos (c : Ctx) : Array (Option Q) := c.times.map some
def pathPos (c : Ctx) (x : TrackId) : Array (Option Q) := c.scenes.map (kin_path_length · x)
def positions (c : Ctx) (m : Measure) (x : TrackId) : Array (Option Q) :=
  match m with | .time => timePos c | .path => pathPos c x
def missingPos (m : Measure) : UnknownReason :=
  match m with | .time => .outOfRange | .path => .absentAtom "kin_path_length"

def bAtom (o : Option Bool) (name : String) : R := R.ofOption o (.absentAtom name)
def qAtom (o : Option Q) (name : String) : QR :=
  match o with | some q => .ok q | none => .error (.absentAtom name)
-- ---------------------------------------------------------------------------------------------
-- Scene-level helpers over atoms
-- ---------------------------------------------------------------------------------------------
/-- Heading change (degrees, left positive) integrated over the back window of length w:
    prefix sums of yaw rate × interval, one window query per instant. -/
def yawChange (c : Ctx) (x : TrackId) (w : Q) : Array (Except UnknownReason Q) :=
  let n := c.n
  -- sums[i] = Σ_{k ≤ i} ω_k (t_k − t_{k−1}); a missing yaw rate contributes nothing and is tracked
  let sums := (List.range n).foldl (fun (acc : Array Q) i =>
    let prev := if i = 0 then Q.zero else acc[i - 1]!
    let dt := if i = 0 then Q.zero else Q.sub c.times[i]! c.times[i - 1]!
    acc.push (match kin_yaw_rate c.scenes[i]! x with
      | some ω => Q.add prev (Q.mul ω dt)
      | none => prev)) #[]
  -- lastMissing[i] = latest index ≤ i with a missing yaw rate (n when none)
  let lastMissing := (List.range n).foldl (fun (acc : Array Nat) i =>
    acc.push (if (kin_yaw_rate c.scenes[i]! x).isNone then i else (if i = 0 then n else acc[i - 1]!))) #[]
  let wins := Time.backWindows (timePos c) w
  (Array.range n).map fun i =>
    match wins[i]! with
    | none => .error .outOfRange
    | some win =>
      if !win.covered then .error (.windowTruncated "prim_heading_change")
      else if !win.adequate then .error (.samplingGap "prim_heading_change")
      else
        let lm := lastMissing[i]!
        if lm ≠ n && lm > win.j0 then .error (.absentAtom "kin_yaw_rate")
        else .ok (Q.sub sums[i]! sums[win.j0]!)

-- ---------------------------------------------------------------------------------------------
-- The primitives
-- ---------------------------------------------------------------------------------------------
/-- minute m of the day lies in the window [start, end), wrapping past midnight when end ≤ start. -/
def inWindow (w : TimeWindow) (m : Nat) : Bool :=
  if w.startMinute < w.endMinute then w.startMinute ≤ m && m < w.endMinute
  else m ≥ w.startMinute || m < w.endMinute

private def hasClassOpt (s : Scene) (x : TrackId) (k : RoadUserClass) : Option Bool :=
  (s.user x).bind fun u => if u.unobservedClasses.contains k then none else u.classes.map (·.contains k)

private def vecAtom (o : Option Vec) (name : String) : Except UnknownReason Vec :=
  match o with | some v => .ok v | none => .error (.absentAtom name)

/-- Under constant velocities, the time of closest approach of the two centres and the centre
    distance then; `none` when the paths do not approach within `[0, horizon]`. -/
private def closestApproach (s : Scene) (a b : TrackId) (horizon : Q) : Except UnknownReason (Option (Q × Q)) := do
  let pa ← vecAtom (kin_position s a) "kin_position"
  let pb ← vecAtom (kin_position s b) "kin_position"
  let va ← vecAtom (kin_velocity s a) "kin_velocity"
  let vb ← vecAtom (kin_velocity s b) "kin_velocity"
  let r := Geom.vsub pb pa
  let v := Geom.vsub vb va
  let vv := Geom.dot v v
  if Q.isZero vv then pure none
  else
    let tstar := Q.neg (Q.div (Geom.dot r v) vv)
    if Q.lt tstar Q.zero || Q.gt tstar horizon then pure none
    else pure (some (tstar, Geom.norm (Geom.vadd r (Q.mul tstar v.1, Q.mul tstar v.2))))

/-- Signed heading change (degrees, left positive) over the back window w, integrated from the yaw
    rate; unknown where the window is truncated, sparsely sampled or a yaw rate is missing. -/
def prim_heading_change (c : Ctx) (x : TrackId) (w : Q) : Array QR :=
  (yawChange c x w).map fun e => match e with
    | .error r => .error (match r with
        | .windowTruncated _ => .windowTruncated "prim_heading_change"
        | .samplingGap _ => .samplingGap "prim_heading_change"
        | other => other)
    | .ok Δ => .ok Δ

/-- The centres approach each other within the horizon. -/
def prim_closest_approach_within (c : Ctx) (a b : TrackId) (horizon : Q) : Array R :=
  each c fun s => match closestApproach s a b horizon with
    | .error w => R.u w
    | .ok o => R.ofBool o.isSome

/-- The time of closest approach; undefined when the centres do not approach within the horizon. -/
def prim_closest_approach_time (c : Ctx) (a b : TrackId) (horizon : Q) : Array QR :=
  eachQ c fun s => do
    match ← closestApproach s a b horizon with
    | some (t, _) => pure t
    | none => throw (.undefined "prim_closest_approach_time")

/-- The centre distance at closest approach; undefined when the centres do not approach within the horizon. -/
def prim_closest_approach_distance (c : Ctx) (a b : TrackId) (horizon : Q) : Array QR :=
  eachQ c fun s => do
    match ← closestApproach s a b horizon with
    | some (_, dist) => pure dist
    | none => throw (.undefined "prim_closest_approach_distance")

/-- The legend conditions of device d hold now for road user x: a time window on a listed day (or a
    calendar class the scene declares), any occupancy or class condition, children present. -/
def prim_conditions_hold (c : Ctx) (d : DeviceId) (x : TrackId) : Array R :=
  each c fun s =>
    let conds := match dev_zone_sign_conditions s d with
      | some cd => some cd
      | none => dev_regulatory_sign_conditions s d
    R.bindOpt conds (.absentAtom "dev_zone_sign_conditions") fun cd =>
      let timeOk : R :=
        if cd.windows.isEmpty then R.t
        else R.bindOpt (env_civil_time s) (.absentAtom "env_civil_time") fun ct =>
          R.any (cd.windows.map fun w =>
            let dayOk : R := match w.calendarClass with
              | some cls => R.ofOption (s.assumption cls) (.assumptionMissing cls)
              | none => R.ofBool (w.weekdays.isEmpty || w.weekdays.contains ct.weekday)
            R.and dayOk (R.ofBool (inWindow w ct.minuteOfDay)))
      let occOk : R := match cd.minOccupancy with
        | none => R.t
        | some n => bAtom ((ru_occupant_count s x).map (· ≥ n)) "ru_occupant_count"
      let clsOk : R := match cd.vehicleClass with
        | none => R.t
        | some k => bAtom (hasClassOpt s x k) "ru_class"
      let childOk : R :=
        if cd.whenChildrenPresent then R.any (s.tracks.map fun y => bAtom (ru_child s y) "ru_child") else R.t
      R.and (R.and timeOk occOk) (R.and clsOk childOk)

/-- The signed lateral offset of region r from road user x (m, left positive): the component,
    perpendicular to x's heading, of the vector from x's reference point to the nearest point of
    r's boundary; zero where the reference point lies inside r. -/
def prim_region_lateral_offset (c : Ctx) (x : TrackId) (r : RegionId) : Array QR :=
  eachQ c fun s => do
    let some p := kin_position s x | throw (.absentAtom "kin_position")
    let some h := kin_heading s x | throw (.absentAtom "kin_heading")
    let some poly := st_region_geometry_boundary s r | throw (.absentAtom "st_region_geometry")
    if Geom.inPolygon p poly then pure Q.zero
    else
      let some q := Geom.nearestPoint p poly | throw (.absentAtom "st_region_geometry")
      let some (_, lat) := Geom.inFrame h (Geom.vsub q p) | throw (.absentAtom "kin_heading")
      pure lat

/-- Path length over which `holds` has held continuously up to each instant (`Term.distanceWhile`). -/
def distanceWhile (c : Ctx) (x : TrackId) (holds : Array R) : Array QR :=
  Temporal.distanceWhileAll (pathPos c x) holds

-- ---------------------------------------------------------------------------------------------
-- Tables and dispatch by name
-- ---------------------------------------------------------------------------------------------
/-- Every `prim_*` definition of this file. The doctor holds this against `primitiveIds`. -/
def primitiveNames : List String :=
  ["prim_heading_change", "prim_closest_approach_within", "prim_closest_approach_time",
   "prim_closest_approach_distance", "prim_conditions_hold", "prim_region_lateral_offset"]

/-- The atoms each primitive reads (Lean names of Atoms.lean); Manifest.lean turns a primitive
    into the atoms a source must observe. -/
def reads (n : String) : List String :=
  match n with
  | "prim_heading_change" => ["kin_yaw_rate"]
  | "prim_closest_approach_within" | "prim_closest_approach_time" | "prim_closest_approach_distance" => ["kin_position", "kin_velocity"]
  | "prim_conditions_hold" => ["dev_zone_sign", "dev_regulatory_sign", "env_civil_time", "ru_occupant_count", "ru_child"]
  | "prim_region_lateral_offset" => ["kin_position", "kin_heading", "st_region_geometry"]
  | _ => []

/-- The sort each entity argument of a primitive must have (`none` marks a literal or natural
    position). The static check holds variables to these. -/
def argSorts (name : String) : Option (List (Option EntityKind)) :=
  let t := some EntityKind.track
  match name with
  | "prim_heading_change" => some [t]
  | "prim_closest_approach_within" | "prim_closest_approach_time" | "prim_closest_approach_distance" => some [t, t]
  | "prim_conditions_hold" => some [some EntityKind.device, t]
  | "prim_region_lateral_offset" => some [t, some EntityKind.region]
  | _ => none

private def tid (a : DArg) : Except UnknownReason TrackId :=
  match a with | .v t => .ok t | .n n => .ok n | _ => .error (.malformed "entity")

/-- A name no primitive carries: a concept call that no expansion replaced, or a misspelling. -/
private def unknownName (n : String) : UnknownReason :=
  if primitiveNames.contains n then .malformed s!"arity {n}" else .malformed s!"concept {n}"

/-- Boolean primitives by name. Unlisted names and wrong arities are `malformed`. -/
def evalB (name : String) (c : Ctx) (args : List DArg) (ps : List Q) : Except UnknownReason (Array R) :=
  match name, args, ps with
  | "prim_closest_approach_within", [a, b], [h] => do pure (prim_closest_approach_within c (← tid a) (← tid b) h)
  | "prim_conditions_hold", [d, x], [] => do pure (prim_conditions_hold c (← tid d) (← tid x))
  | n, _, _ => .error (unknownName n)

/-- Quantity-valued primitives by name. -/
def evalQ (name : String) (c : Ctx) (args : List DArg) (ps : List Q) : Except UnknownReason (Array QR) :=
  match name, args, ps with
  | "prim_heading_change", [x], [w] => do pure (prim_heading_change c (← tid x) w)
  | "prim_closest_approach_time", [a, b], [h] => do pure (prim_closest_approach_time c (← tid a) (← tid b) h)
  | "prim_closest_approach_distance", [a, b], [h] => do pure (prim_closest_approach_distance c (← tid a) (← tid b) h)
  | "prim_region_lateral_offset", [x, r], [] => do pure (prim_region_lateral_offset c (← tid x) (← tid r))
  | n, _, _ => .error (unknownName n)

end Primitives
end TrafficSpec
