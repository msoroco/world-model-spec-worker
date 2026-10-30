/-
  TrafficSpec.Core.Runtime.Manifest
  What a source can observe: a capability per atom id, complete over ATOMS.md (`subject` is an atom
  observed for the subject track alone, as an instrumented vehicle reports its own controls); a mask
  that blanks every field of an absent atom, and of a subject-only atom on every other road user,
  before evaluation; and `support`, the first and most honest number
  a source gets — which rules it can be judged against at all, computed from the rules' syntax
  before any frame is read.

  The same rules run on a simulator, on an annotated dataset and on perception over video; the
  only thing that differs is what each can see, and that difference is a declared input here.
  For the perception stage the manifest is the interface the other way round: the list of atoms
  its programs must deliver, with the error class each is allowed.
-/
import TrafficSpec.Core.Language.Rule
import TrafficSpec.Core.Language.Semantics
import TrafficSpec.Core.Vocab.Ontology.Ids

namespace TrafficSpec

inductive Capability
  | exact
  | estimate (errorClass : String)
  | absent
  | subject
  deriving Repr, DecidableEq, Inhabited

structure Manifest where
  source : String
  entries : List (String × Capability)     -- atom id in ATOMS.md form ↦ capability
  /-- Retired source capabilities retained for provenance; never current observation support. -/
  sourceEntries : List (String × Capability) := []
  /-- The longest tracker break the source's re-identification links may bridge (seconds). -/
  reidGap : Q := Q.zero
  deriving Repr, Inhabited

namespace Manifest
/-- An atom the manifest does not list is absent: silence is not a capability. -/
def capability (m : Manifest) (id : String) : Capability :=
  ((m.entries.find? (·.1 == id)).map (·.2)).getD .absent
def observes (m : Manifest) (id : String) : Bool := m.capability id != .absent
/-- Complete: every atom id of ATOMS.md has an entry, and no entry names anything else. -/
def complete (m : Manifest) : Bool :=
  atomIds.all (fun id => (m.entries.find? (·.1 == id)).isSome) &&
  m.entries.all (fun e => atomIds.contains e.1)
def absentIds (m : Manifest) : List String := atomIds.filter fun id => !m.observes id
/-- The atoms observed for the subject track only. -/
def subjectIds (m : Manifest) : List String := atomIds.filter fun id => m.capability id == .subject
/-- A manifest that observes everything exactly (the simulator's, and the tests'). -/
def full (source : String) (gap : Q := Q.zero) : Manifest :=
  { source := source, entries := atomIds.map fun id => (id, .exact), reidGap := gap }
end Manifest

-- ---------------------------------------------------------------------------------------------
-- From Lean names back to atom ids
-- ---------------------------------------------------------------------------------------------
/-- The atom id a Lean name reads: the longest id whose `defName` is a prefix of the name
    (`dev_traffic_signal_shows` ↦ `dev.traffic_signal`), with the relation aliases spelled out. -/
def atomIdOf (name : String) : Option String :=
  let n := match name with
    | "rel_ahead_in_lane" | "rel_behind_in_lane" => "rel_ahead_behind_in_lane"
    | other => other
  let cands := atomIds.filter fun id =>
    let d := Semantics.defName id
    n == d || n.startsWith (d ++ "_")
  cands.foldl (fun acc id => match acc with
    | none => some id
    | some a => if id.length > a.length then some id else some a) none

/-- The atom ids a formula list reads, through atoms and primitives (a concept call is expanded first). -/
def formulaAtomIds (fs : List Formula) : List String :=
  ((fs.flatMap Formula.atoms).flatMap fun n =>
    if n.startsWith "prim_" then (Primitives.reads n).filterMap atomIdOf
    else (atomIdOf n).toList).eraseDups

/-- The atom ids a rule reads, through its atoms, its primitives and, transitively, the
    rules it composes. -/
def Rule.atomIds (rules : List Rule) (r : Rule) : List String :=
  let rec go (fuel : Nat) (seen : List String) (r : Rule) : List String :=
    match fuel with
    | 0 => formulaAtomIds r.formulas
    | fuel + 1 =>
      formulaAtomIds r.formulas ++ (r.composes.flatMap fun id =>
        if seen.contains id then [] else
        match rules.find? (·.id == id) with
        | some r' => go fuel (id :: seen) r'
        | none => [])
  (go rules.length [r.id] r).eraseDups

inductive Support
  | supported
  | partially (absent : List String)      -- some atoms unobserved: verdicts may be unknown
  | unsupported (absent : List String)    -- the obligation reads nothing the source observes
  deriving Repr, DecidableEq, Inhabited

def Support.tag : Support → String
  | .supported => "supported"
  | .partially _ => "partial"
  | .unsupported _ => "unsupported"
def Support.absent : Support → List String
  | .supported => []
  | .partially a | .unsupported a => a

/-- Support from syntax alone, closed over the rules a rule composes. Unsupported when every atom
    the obligation reads is absent (the rule could never decide), or a binder's class can never be
    established, or a composed rule is itself unsupported. -/
def support (rules : List Rule) (r : Rule) (m : Manifest) : Support :=
  -- the clock is every source's: a window over time reads it, and no manifest declares it absent
  let absentOf (fs : List Formula) : List String × Nat :=
    let ids := (formulaAtomIds fs).filter (· != "kin.time")
    (ids.filter fun id => !m.observes id, ids.length)
  let (oblAbsent, oblTotal) := absentOf [r.obligation]
  let clsDead := r.binders.any fun b =>
    let (a, n) := absentOf [b.cls]
    n > 0 && a.length == n
  let composedDead := (r.composes.filterMap fun id => rules.find? (·.id == id)).any fun r' =>
    let (a, n) := absentOf [r'.obligation]
    n > 0 && a.length == n
  let allAbsent := (Rule.atomIds rules r).filter fun id => !m.observes id
  if allAbsent.isEmpty then .supported
  else if clsDead || composedDead || (oblTotal > 0 && oblAbsent.length == oblTotal) then .unsupported allAbsent
  else .partially allAbsent

-- ---------------------------------------------------------------------------------------------
-- Masking: a scene as the source would have produced it
-- ---------------------------------------------------------------------------------------------
namespace Mask
def user (id : String) (u : RoadUser) : RoadUser :=
  match id with
  | "ru.subject" => u
  | "ru.occupant_count" => { u with occupants := none }
  | "ru.rider_posture" => { u with posture := {} }
  | "kin.position" => { u with kin := { u.kin with position := none } }
  | "kin.heading" => { u with kin := { u.kin with heading := none } }
  | "kin.velocity" => { u with kin := { u.kin with velocity := none } }
  | "kin.speed" => { u with kin := { u.kin with speed := none } }
  | "kin.accel_longitudinal" => { u with kin := { u.kin with accelLongitudinal := none } }
  | "kin.yaw_rate" => { u with kin := { u.kin with yawRate := none } }
  | "kin.extent" => { u with kin := { u.kin with extent := none } }
  | "kin.steer_angle" => { u with kin := { u.kin with steerAngle := none } }
  | "kin.path_length" => { u with kin := { u.kin with pathLength := none } }
  | "kin.engine_running" => { u with kin := { u.kin with engineRunning := none } }
  | "kin.parking_brake" => { u with kin := { u.kin with parkingBrake := none } }
  | "kin.gear" => { u with kin := { u.kin with gear := none } }
  | "kin.throttle" => { u with kin := { u.kin with throttle := none } }
  | "kin.service_brake" => { u with kin := { u.kin with serviceBrake := none } }
  | "sig.turn_indicator" => { u with sig := { u.sig with turnIndicator := none } }
  | "sig.brake_lamp" => { u with sig := { u.sig with brakeLamp := none } }
  | "sig.hazard" => { u with sig := { u.sig with hazard := none } }
  | "sig.headlamp" => { u with sig := { u.sig with headlamp := none } }
  | "sig.position_lamp" => { u with sig := { u.sig with positionLamp := none } }
  | "sig.reverse_lamp" => { u with sig := { u.sig with reverseLamp := none } }
  | "sig.warning_lamp" => { u with sig := { u.sig with warningLamps := none } }
  | "sig.siren" => { u with sig := { u.sig with siren := none } }
  | "sig.horn" => { u with sig := { u.sig with horn := none } }
  | "sig.hand_signal" => { u with sig := { u.sig with handSignal := none } }
  | "ru.aggregate" => { u with classes := none }   -- the source classifies nothing: every member unknown
  | "sig.door_open" => { u with sig := { u.sig with doorsOpen := none } }
  | "sig.compression_brake" => { u with sig := { u.sig with compressionBrake := none } }
  | "st.sight_along_way" => { u with sightAlongWay := none }
  | _ =>
    -- a class atom: the source cannot tell this class, so no user is known to have or lack it,
    -- nor the attribute the class carries
    match RoadUserClass.ofString ((id.drop 3).toString) with
    | some k =>
      let u := { u with classes := u.classes.map (·.filter (· != k)), unobservedClasses := k :: u.unobservedClasses }
      match k with
      | .emergencyVehicle => { u with emergencyKind := none }
      | .officialVehicle => { u with officialKind := none }
      | .electricBicycle => { u with eBikeClass := none }
      | _ => u
    | none => u

def structure' (id : String) (st : Structure) : Option Structure :=
  match id with
  | "st.lane_direction" => some { st with lane := st.lane.map fun l => { l with direction := none } }
  | "st.lane_adjacency" => some { st with lane := st.lane.map fun l =>
      { l with leftNeighbour := none, rightNeighbour := none, ordinalFromLeft := none, countInDirection := none } }
  | "st.lane_connectivity" => some { st with lane := st.lane.map fun l => { l with leadsTo := none } }
  | "st.entrance_of" => some { st with entranceOf := none }
  | "st.lane_enters" => some { st with lane := st.lane.map fun l => { l with entersIntersection := none } }
  | "st.lane_marking" => some { st with lane := st.lane.map fun l => { l with markingLeft := none, markingRight := none } }
  | "st.lane_width" => some { st with lane := st.lane.map fun l => { l with width := none } }
  | "st.curvature" => some { st with curvature := none }
  | "st.grade" => some { st with grade := none }
  | "st.sight_distance" => some { st with sightDistance := none }
  | "st.on_way" => some { st with ways := none }
  | "st.region_geometry" => some { st with position := none, boundary := none }
  | _ =>
    -- a kind atom: the source cannot tell this kind, so no region is known to be or not be one
    match StructureKind.ofString ((id.drop 3).toString) with
    | some k => some { st with unobservedKinds := k :: st.unobservedKinds }
    | none => some st

def device (id : String) (d : Device) : Option Device :=
  match id with
  | "dev.governs" => some { d with governs := [], governsObserved := false }
  | "dev.position" => some { d with position := none }
  | "dev.inoperative" => some { d with inoperative := none }
  | _ =>
    -- a kind atom: the source cannot tell this kind, so no device is known to be or not be one
    match DeviceKind.ofString ((id.drop 4).toString) with
    | some k => some { d with unobservedKinds := k :: d.unobservedKinds }
    | none => some d

def env (id : String) (e : Env) : Env :=
  match id with
  | "env.darkness" => { e with darkness := none }
  | "env.precipitation" => { e with precipitation := none }
  | "env.wet_road" => { e with wetRoad := none }
  | "env.ice_or_snow" => { e with iceOrSnow := none }
  | "env.visibility" => { e with visibility := none }
  | "env.civil_time" => { e with civilTime := none }
  | _ => e

def relation (id : String) (m : MeasuredRelation) : MeasuredRelation :=
  match id with
  | "rel.centre_distance" => { m with centreDistance := none }
  | "rel.surface_gap" => { m with surfaceGap := none }
  | "rel.ahead_behind_in_lane" => { m with aAheadOfB := none }
  | "rel.longitudinal_overlap" => { m with longitudinalOverlap := none }
  | "rel.oncoming" => { m with oncoming := none }
  | "rel.same_direction" => { m with sameDirection := none }
  | "rel.bearing" => { m with bearing := none }
  | "rel.contact" => { m with contact := none }
  | "rel.visible" => { m with visible := none }
  | _ => m

/-- Blank one atom in a scene. The computed relations are blanked through the kinematics they
    would be computed from only when the source lacks those too; a measured value is dropped. -/
def scene (id : String) (s : Scene) : Scene :=
  match id with
  | "ru.subject" => { s with subject := none }
  | "rel.occupies" => { s with occupancyObserved := [], occupies := [] }
  | "kin.time" => s
  | _ =>
    { s with users := s.users.map (user id)
             structures := s.structures.filterMap (structure' id)
             devices := s.devices.filterMap (device id)
             env := env id s.env
             relations := s.relations.map (relation id) }

/-- Blank one atom on every road user but the subject, and in every measured relation not taken
    from the subject: what a source that instruments the subject's vehicle alone can say. -/
def sceneExceptSubject (id : String) (s : Scene) : Scene :=
  { s with users := s.users.map fun u => if s.subject == some u.track then u else user id u
           relations := s.relations.map fun m => if s.subject == some m.a then m else relation id m }
end Mask

/-- The scene as the source would have produced it: every absent atom blanked, every subject-only
    atom blanked on everyone but the subject. -/
def mask (m : Manifest) (s : Scene) : Scene :=
  let s := m.absentIds.foldl (fun acc id => Mask.scene id acc) s
  m.subjectIds.foldl (fun acc id => Mask.sceneExceptSubject id acc) s
def maskTrace (m : Manifest) (τ : Trace) : Trace := τ.map (mask m)

end TrafficSpec
