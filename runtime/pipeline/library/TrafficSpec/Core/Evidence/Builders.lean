/-
  TrafficSpec.Core.Evidence.Builders
  Scenarios for witnesses and tests: a scene and a trace from a few named quantities, padding by
  timestamp, masking under a manifest, and the `Scenario` a witness file declares.

  A witness must be indistinguishable from adapter output to an atom, so everything here goes
  through the `World` constructors and nothing else. Reachable from `Witness/**` and `Tests/**`
  only: a rule that could build its own evidence proves nothing.

  No default magnitude lives here — every extent, speed and distance is an argument the witness
  writes through a `Units` constructor.
-/
import TrafficSpec.Core.Runtime.Monitor

namespace TrafficSpec
namespace Build

/-- Cardinal unit headings in the world frame (+x east, +y north). -/
def east : Vec := (Q.ofInt 1, Q.zero)
def west : Vec := (Q.ofInt (-1), Q.zero)
def north : Vec := (Q.zero, Q.ofInt 1)
def south : Vec := (Q.zero, Q.ofInt (-1))

def scale (h : Vec) (k : Q) : Vec := (Q.mul h.1 k, Q.mul h.2 k)

/-- A road user with position, heading and speed; velocity follows the heading, path length
    is the caller's (cumulative) figure, extents are half-length/half-width/half-height. -/
def user (track : TrackId) (classes : List RoadUserClass) (pos : Vec) (heading : Vec) (speed : Q)
    (halfExtent : Q × Q × Q) (pathLength : Option Q := none) : RoadUser :=
  { track := track
    classes := some classes
    kin := { position := some pos
             heading := some heading
             velocity := some (scale heading speed)
             speed := some speed
             extent := some halfExtent
             pathLength := pathLength } }

/-- A road user of which only the position (and classes) was observed. -/
def sparseUser (track : TrackId) (classes : List RoadUserClass) (pos : Vec) : RoadUser :=
  { track := track, classes := some classes, kin := { position := some pos } }

def withSignals (u : RoadUser) (f : Signals → Signals) : RoadUser := { u with sig := f u.sig }
def withKin (u : RoadUser) (f : Kin → Kin) : RoadUser := { u with kin := f u.kin }
/-- A measured relation from `a` to `b`, with the measured fields the source supplies. -/
def relation (a b : TrackId) (f : MeasuredRelation → MeasuredRelation := id) : MeasuredRelation := f { a := a, b := b }
def withRelations (s : Scene) (rs : List MeasuredRelation) : Scene := { s with relations := rs }

/-- A region of a kind with a polygon boundary. -/
def region (id : RegionId) (kind : StructureKind) (boundary : List Vec) : Structure :=
  { id := id, kind := kind, boundary := some boundary }
/-- An axis-aligned rectangular region from two corners. -/
def rect (id : RegionId) (kind : StructureKind) (x0 y0 x1 y1 : Q) : Structure :=
  region id kind [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
/-- A lane with its direction and neighbours. -/
def lane (id : RegionId) (boundary : List Vec) (direction : Vec)
    (left right : Option RegionId := none) (ordinal count : Option Nat := none)
    (leadsTo : Option (List RegionId) := none) (enters : Option RegionId := none) : Structure :=
  { id := id
    kind := .lane
    boundary := some boundary
    lane := some { direction := some direction, leftNeighbour := left, rightNeighbour := right,
                   ordinalFromLeft := ordinal, countInDirection := count, leadsTo := leadsTo,
                   entersIntersection := enters } }
def point (id : RegionId) (kind : StructureKind) (pos : Vec) : Structure :=
  { id := id, kind := kind, position := some pos }

def device (id : DeviceId) (kind : DeviceKind) (governs : List RegionId) (pos : Option Vec := none) : Device :=
  { id := id, kind := kind, governs := governs, position := pos }
def signal (id : DeviceId) (governs : List RegionId) (shows : List SignalIndication) : Device :=
  { device id .trafficSignal governs with indications := some shows }
def sign (id : DeviceId) (kind : DeviceKind) (governs : List RegionId) : Device := device id kind governs
def speedLimit (id : DeviceId) (governs : List RegionId) (value : Q) (kind : SpeedSignKind) : Device :=
  { device id .speedLimitSign governs with speedValue := some value, speedKind := some kind }
def zoneSign (id : DeviceId) (governs : List RegionId) (kind : ZoneKind) (isEnd : Bool)
    (conditions : Option Conditions := none) : Device :=
  { device id .zoneSign governs with zoneKind := some kind, isEnd := some isEnd, conditions := conditions }

/-- Occupancy from the geometry: every user inside every region whose boundary contains its position. -/
def occupancyFromGeometry (users : List RoadUser) (structures : List Structure) : List (TrackId × RegionId) :=
  users.flatMap fun u =>
    match u.kin.position with
    | none => []
    | some p => structures.filterMap fun st =>
      match st.boundary with
      | some poly => if Geom.inPolygon p poly then some (u.track, st.id) else none
      | none => none

/-- A scene; occupancy is derived from geometry unless given. -/
def scene (t : Timestamp) (subject : Option TrackId) (users : List RoadUser) (structures : List Structure)
    (devices : List Device) (occupies : Option (List (TrackId × RegionId)) := none)
    (env : Env := {}) (assumptions : List (AsmId × Bool) := []) (intents : List DeclaredIntent := []) : Scene :=
  { t := t
    subject := subject
    users := users
    structures := structures
    devices := devices
    occupancyObserved := users.map (·.track)
    occupies := occupies.getD (occupancyFromGeometry users structures)
    env := env
    assumptions := assumptions
    intents := intents }

/-- A trace from a scene generator over instants `t0, t0 + dt, …` (`dt` in seconds). -/
def trace (n : Nat) (t0 : Timestamp) (dt : Q) (f : Nat → Timestamp → Scene) : Trace :=
  (List.range n).map fun k =>
    let t : Timestamp := t0 + (Q.mul (Q.ofInt (Int.ofNat k)) (Q.mul dt (Q.ofInt 1000))).num /
      (Q.mul dt (Q.ofInt 1000)).den
    f k t

/-- Repeat the first and last scenes for `before`/`after` seconds at spacing `dt`, so that windows
    at the ends of the interesting part are covered rather than truncated. -/
def pad (τ : Trace) (before after dt : Q) : Trace :=
  match τ.head?, τ.getLast? with
  | some first, some last =>
    let step : Timestamp := (Q.mul dt (Q.ofInt 1000)).num / (Q.mul dt (Q.ofInt 1000)).den
    let nb := ((Q.div before dt).num / (Q.div before dt).den).toNat
    let na := ((Q.div after dt).num / (Q.div after dt).den).toNat
    let pre := (List.range nb).reverse.map fun k => { first with t := first.t - step * (k + 1) }
    let post := (List.range na).map fun k => { last with t := last.t + step * (k + 1) }
    pre ++ τ ++ post
  | _, _ => τ

def masked (m : Manifest) (τ : Trace) : Trace := maskTrace m τ

/-- A manifest that observes every atom except the listed ids (for a `blind` witness). -/
def manifest (absent : List String := []) (gap : Q := Q.zero) : Manifest :=
  let full := Manifest.full "witness" gap
  { full with entries := full.entries.map fun (id, c) => if absent.contains id then (id, .absent) else (id, c) }

end Build

/-- A witness: a rule, a trace, the reading and manifest it assumes, the grounding it speaks
    about (binder ↦ track) and the episode verdict the plan declared over `window` (a closed range
    of timestamps; the whole trace when absent). A lookback window is truncated at the start of
    every finite trace, so a witness about a rule with one names the instants it speaks about.
    A witness is a test of the rule, not evidence about the law: it shows the formulas reach the
    verdict it names, on a scene its author built. -/
structure Scenario where
  name : String
  rule : String
  trace : Trace
  reading : Reading
  manifest : Manifest
  grounding : List (String × TrackId)
  regions : List (String × RegionId) := []   -- an instance's region formals, each a region of the trace
  expected : Verdict
  window : Option (Timestamp × Timestamp) := none
  deriving Repr, Inhabited

namespace Scenario
/-- The witness holds when the rule's episode verdict on its grounding has the expected tag, and
    the verdict is reached for the reason the witness is about: a `notApplicable` witness needs an
    instant at which every bound track is present (a track that never appears leaves any rule not
    engaged); an `unknown` witness must be unknown only for atoms its manifest masks (an unbound
    variable, a truncated window or a missing parameter is a defect, not a masked observation).
    The rules are evaluated with their concept calls expanded over `concepts`. A trace the
    admission rejects, or a region formal given a region no scene of the trace holds, fails. -/
def run (rules : List Rule) (sc : Scenario) (concepts : List Concept := []) : Except String Verdict := do
  let rules := rules.map (Concept.expandRule concepts)
  let r ← match rules.find? (·.id == sc.rule) with
    | some r => pure r
    | none => throw s!"{sc.name}: rule {sc.rule} is not registered"
  let S ← match Grounding.Setup.admit rules (maskTrace sc.manifest sc.trace) sc.reading sc.manifest.reidGap with
    | .ok S => pure S
    | .error ds => throw s!"{sc.name}: the trace is not admitted: {"; ".intercalate ds}"
  for (n, reg) in sc.regions do
    if !(sc.trace.any fun s => (s.structure? reg).isSome) then
      throw s!"{sc.name}: region formal `{n}` is region {reg}, which is no structure of the trace"
  let g : Grounding.Grounding := ⟨sc.grounding.map (fun (n, t) => (n, Grounding.canon S.cm t)), sc.regions⟩
  let tl := Grounding.evaluate S r g
  let rows := tl.verdicts.toList.filter fun (t, _) =>
    match sc.window with
    | some (a, b) => a ≤ t && t ≤ b
    | none => true
  let got := Grounding.episode (rows.map (·.2))
  if got.tag != sc.expected.tag then
    throw s!"{sc.name}: expected {sc.expected.tag}, got {got.tag} {(got.reasons.map UnknownReason.tag)}"
  match sc.expected with
  | .notApplicable =>
    if tl.present then pure got
    else throw s!"{sc.name}: not applicable, but no instant has every bound track present"
  | .unknown _ =>
    let absent := sc.manifest.absentIds
    let stray := got.reasons.filter fun w => match w with
      | .absentAtom n => !(atomIdOf n).any absent.contains
      | _ => true
    if stray.isEmpty then pure got
    else throw s!"{sc.name}: unknown for {(stray.map UnknownReason.tag)}, not for an atom the manifest masks"
  | _ => pure got
end Scenario

end TrafficSpec
