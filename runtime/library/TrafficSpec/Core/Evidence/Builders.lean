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
    (env : Env := {}) (assumptions : List (AsmId × Bool) := []) (intents : List DeclaredIntent := [])
    (facts : List DeclaredFact := []) : Scene :=
  { t := t
    subject := subject
    users := users
    structures := structures
    devices := devices
    occupancyObserved := users.map (·.track)
    occupies := occupies.getD (occupancyFromGeometry users structures)
    env := env
    assumptions := assumptions
    intents := intents
    facts := facts }

/-- A declared fact: `id` holds (`value`) of the road users `users`, in the order its meaning names
    them, and of the regions `regions`. -/
def fact (id : FactId) (users : List TrackId) (value : Bool) (regions : List RegionId := []) : DeclaredFact :=
  { id := id, users := users, regions := regions, value := value }
/-- The scene with these facts declared in it, besides those it has. -/
def withFacts (s : Scene) (fs : List DeclaredFact) : Scene := { s with facts := s.facts ++ fs }

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

/-- A manifest that observes every atom except the listed ids (for a `blind` witness), and supplies
    the declared facts `facts` lists (every one where it is `none`). -/
def manifest (absent : List String := []) (gap : Q := Q.zero) (facts : Option (List FactId) := none) : Manifest :=
  let full := Manifest.full "witness" gap
  { full with entries := full.entries.map (fun (id, c) => if absent.contains id then (id, .absent) else (id, c))
              facts := facts }

end Build

/-- A witness: a rule, a trace, the reading and manifest it assumes, the grounding it speaks
    about (binder ↦ track) and the episode verdict the plan declared over `window` (a closed range
    of timestamps; the whole trace when absent). A lookback window is truncated at the start of
    every finite trace, so a witness about a rule with one names the instants it speaks about.
    A witness is a test of the rule, not evidence about the law: it shows the formulas reach the
    verdict it names, on a scene its author built. A history-boundary witness (`boundary` names the
    history its trace lacks) shows that the rule stays unknown where the trace does not reach back
    far enough to decide it. -/
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
  boundary : String := ""
  setMembers : List Rule := []                -- the rules the rule-set operators range over here
  deriving Repr, Inhabited

namespace Scenario
/-- The operators that look back from the observation they judge, by the tag their truncation at the
    start of a trace carries: only these leave a history-boundary witness unknown. -/
def pastOps : List String :=
  ["since", "since_rise", "rises", "once", "holdsFor", "atLast", "count", "distance_while", "prim_heading_change",
   "heading_since", "duration_within"]

/-- The witness holds when the rule's episode verdict on its grounding has the expected tag, and
    the verdict is reached for the reason the witness is about: a `notApplicable` witness needs an
    instant at which every bound track is present (a track that never appears leaves any rule not
    engaged); an `unknown` witness must be unknown only for atoms its manifest masks, or declared
    facts it does not supply (an unbound
    variable, a truncated window or a missing parameter is a defect, not a masked observation),
    except that a history-boundary witness is unknown for a window truncated at the start of its
    trace, at least once, and otherwise only for masked atoms; a boundary is declared on an
    `unknown` witness only.
    The rules are evaluated with their concept calls expanded over `concepts`. The rule-set
    operators (`requiredBy`, `lawful`) range over the witness's own `setMembers`, never over the
    library, so a witness's verdict does not change as the library grows. A trace the
    admission rejects, or a region formal given a region no scene of the trace holds, fails. -/
def run (rules : List Rule) (sc : Scenario) (concepts : List Concept := []) : Except String Verdict := do
  let rules := rules.map (Concept.expandRule concepts)
  let r ← match rules.find? (·.id == sc.rule) with
    | some r => pure r
    | none => throw s!"{sc.name}: rule {sc.rule} is not registered"
  let S ← match Grounding.Setup.admit rules (maskTrace sc.manifest sc.trace) sc.reading sc.manifest.reidGap with
    | .ok S => pure { S with setRules := some (sc.setMembers.map (Concept.expandRule concepts)) }
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
  if !sc.boundary.isEmpty && sc.expected.tag != "unknown" then
    throw s!"{sc.name}: a history boundary is declared on a witness that expects {sc.expected.tag}, not unknown"
  if got.tag != sc.expected.tag then
    throw s!"{sc.name}: expected {sc.expected.tag}, got {got.tag} {(got.reasons.map UnknownReason.tag)}"
  match sc.expected with
  | .notApplicable =>
    if tl.present then pure got
    else throw s!"{sc.name}: not applicable, but no instant has every bound track present"
  | .unknown _ =>
    let absent := sc.manifest.absentIds
    let truncated := fun (w : UnknownReason) => match w with | .windowTruncated op => pastOps.contains op | _ => false
    let stray := got.reasons.filter fun w => match w with
      | .absentAtom n => !(atomIdOf n).any absent.contains
      | .factMissing id => sc.manifest.suppliesFact id
      | w => sc.boundary.isEmpty || !truncated w
    if !stray.isEmpty then
      throw s!"{sc.name}: unknown for {(stray.map UnknownReason.tag)}, not for an atom the manifest masks{if sc.boundary.isEmpty then "" else " or a window truncated at the trace start"}"
    else if !sc.boundary.isEmpty && !got.reasons.any truncated then
      throw s!"{sc.name}: a history-boundary witness, but no window is truncated at the trace start"
    else pure got
  | _ => pure got

/-- What a witness shows of case `k` of its rule, observation by observation within its window,
    on its grounding: the invariants it breaks and the controls it exercises. With whether the
    binders' classes hold, whether the rule is engaged, whether the case holds,
    whether the subject shows the case's conduct or act (`shown`), and the rule's verdict:
    - a defect where the case holds and the rule is not engaged; for a `requires` case, where it
      holds, the conduct is not shown and the rule is not violated (the case reaches beyond the
      duty: an exception, or a part of the obligation, that the case does not follow); for a
      `permits` case, where it holds, the act is shown and the rule is violated;
    - the control `positive` where the case holds and, for `requires`, the conduct is not shown and
      the rule is violated, for `permits`, the act is shown and the rule is compliant; `met` where
      a `requires` case holds, the conduct is shown and the rule is compliant; `outside` where the
      classes hold and the applicability does not (the case does not hold there); `exception`
      where the rule is engaged, the conduct is not shown, the rule is compliant and the case does
      not hold (an exception of the duty removes it, and the case follows).
    Observations at which any of these is unknown show nothing. These are control checks on the
    witnesses written, never a proof that the case equals the duty left after its exceptions on
    every trace. -/
def caseControls (rules : List Rule) (sc : Scenario) (concepts : List Concept) (k : Nat) : List String × List String :=
  let rules := rules.map (Concept.expandRule concepts)
  match rules.find? (·.id == sc.rule) with
  | none => ([], [])
  | some r =>
    match r.cases[k]?, Grounding.Setup.admit rules (maskTrace sc.manifest sc.trace) sc.reading sc.manifest.reidGap with
    | some c, .ok S0 =>
      let S := { S0 with setRules := some (sc.setMembers.map (Concept.expandRule concepts)) }
      let g : Grounding.Grounding := ⟨sc.grounding.map (fun (n, t) => (n, Grounding.canon S.cm t)), sc.regions⟩
      let ctx := S.ctx g.binding
      let sit := Rule.engagedAll { r with applicability := .tt } ctx
      let eng := r.engagedAll ctx
      let cv := (RuleSet.caseRule r c).engagedAll ctx
      let sh := Rule.evalRuleFormula ctx c.shown
      let vs := (Grounding.evaluate S r g).verdicts
      let rows := (List.range vs.size).filterMap fun i =>
        match vs[i]?, sit[i]?, eng[i]?, cv[i]?, sh[i]? with
        | some (t, v), some a, some e, some x, some y =>
          let inWin := match sc.window with | some (lo, hi) => lo ≤ t && t ≤ hi | none => true
          if inWin && a.v != .u && e.v != .u && x.v != .u && y.v != .u && v.tag != "unknown" then
            some (t, a.v == .t, e.v == .t, x.v == .t, y.v == .t, v.tag)
          else none
        | _, _, _, _, _ => none
      let req := match c.kind with | .requires _ => true | .permits => false
      let defects := rows.flatMap fun (t, _, e, x, y, v) =>
        (if x && !e then [s!"{sc.name} at {t}: case `{c.name}` holds where the rule is not engaged"] else []) ++
        (if req && x && !y && v != "violated" then
          [s!"{sc.name} at {t}: case `{c.name}` holds and the conduct is not shown, but the rule is {v}: the case reaches beyond the duty"] else []) ++
        (if !req && x && y && v == "violated" then
          [s!"{sc.name} at {t}: case `{c.name}` holds and the permitted act is shown, but the rule is violated"] else [])
      let controls := rows.flatMap fun (_, a, e, x, y, v) =>
        (if x && (if req then !y && v == "violated" else y && v == "compliant") then ["positive"] else []) ++
        (if req && x && y && v == "compliant" then ["met"] else []) ++
        (if a && !e then ["outside"] else []) ++
        (if e && !y && v == "compliant" && !x then ["exception"] else [])
      (defects, controls.eraseDups)
    | _, _ => ([], [])

/-- The external situation of a scene for road user `who`: the scene with `who`'s motion
    forgotten (its kinematics but its extent, the occupancy and the measured relations it is party
    to). Two witnesses with equal external situations at equal instants differ only in how `who`
    moves. -/
def externalOf (who : TrackId) (s : Scene) : String :=
  reprStr { s with users := s.users.map (fun (u : RoadUser) => if u.track == who then ({ u with kin := ({ extent := u.kin.extent } : Kin) } : RoadUser) else u),
                   occupies := s.occupies.filter (fun (p : TrackId × RegionId) => p.1 != who),
                   relations := s.relations.filter fun (m : MeasuredRelation) => m.a != who && m.b != who }

/-- Whether two traces have the same instants and, at each, the same external situation for `who`. -/
def sameExternal (who : TrackId) (a b : Trace) : Bool :=
  a.length == b.length && (a.zip b).all fun (x, y) => x.t == y.t && externalOf who x == externalOf who y

/-- Whether two traces have the same instants and, at each, the same scene but its devices. -/
def sameButDevices (a b : Trace) : Bool :=
  a.length == b.length && (a.zip b).all fun (x, y) => x.t == y.t && reprStr { x with devices := [] } == reprStr { y with devices := [] }

/-- The track the witness binds to its rule's subject binder. -/
def subjectTrack (rules : List Rule) (sc : Scenario) : Option TrackId :=
  (rules.find? (·.id == sc.rule)).bind fun r => r.binders.head?.bind fun b => sc.grounding.lookup b.name

/-- The speeds the trace observes of `who`, at every instant. -/
def speeds (who : TrackId) (τ : Trace) : List (Option Q) :=
  τ.map fun s => (s.users.find? (·.track == who)).bind (·.kin.speed)

/-- The witness's episode verdict on its grounding, with its members, as `run` computes it, and
    whether the case `k` holds at each observation (none where unknown). -/
def observe (rules : List Rule) (sc : Scenario) (concepts : List Concept) (k : Option Nat := none) :
    Option (Verdict × List (Option Bool)) :=
  let rules := rules.map (Concept.expandRule concepts)
  match rules.find? (·.id == sc.rule), Grounding.Setup.admit rules (maskTrace sc.manifest sc.trace) sc.reading sc.manifest.reidGap with
  | some r, .ok S0 =>
    let S := { S0 with setRules := some (sc.setMembers.map (Concept.expandRule concepts)) }
    let g : Grounding.Grounding := ⟨sc.grounding.map (fun (n, t) => (n, Grounding.canon S.cm t)), sc.regions⟩
    let ep := Grounding.episode ((Grounding.evaluate S r g).verdicts.toList.map (·.2))
    let cs : List (Option Bool) := match k.bind (r.cases[·]?) with
      | some c => ((RuleSet.caseRule r c).engagedAll (S.ctx g.binding)).toList.map fun x =>
          if x.v == .u then none else some (x.v == .t)
      | none => []
    some (ep, cs)
  | _, _ => none

/-- The paired controls of a case requiring a halt: three witnesses in the same external situation
    (`sameExternal` for the subject), the subject at rest throughout (`halt`), moving (`drive`), and
    moving more slowly than in `drive` (`creep`). The defects: the situations differ; `halt` has
    the subject moving, `drive` or `creep` never moving, `creep` not slower than `drive`; the case
    holds differently in the three (it would depend on the subject's own motion) or nowhere; the
    rule is violated in `halt`, or not violated in `drive` or in `creep` (a duty that slowing or
    yielding meets requires no stop). These are controls on three witnesses, not a proof over all
    traces. -/
def stopControls (rules : List Rule) (halt drive creep : Scenario) (concepts : List Concept) (k : Nat) : List String :=
  match subjectTrack rules halt with
  | none => ["the halt witness binds no subject"]
  | some who =>
    let moving := fun (sc : Scenario) => (speeds who sc.trace).any fun v => v.any (Q.lt Q.zero ·)
    let top := fun (sc : Scenario) => (speeds who sc.trace).foldl (fun a v => match v with | some q => if Q.lt a q then q else a | none => a) Q.zero
    let situation := (if sameExternal who halt.trace drive.trace && sameExternal who halt.trace creep.trace then []
      else ["the halt, drive and creep witnesses differ in more than the subject's motion"]) ++
      (if (speeds who halt.trace).all (· == some Q.zero) then [] else ["the subject is not at rest throughout the halt witness"]) ++
      (if moving drive && moving creep then [] else ["the subject does not move in the drive or the creep witness"]) ++
      (if Q.lt (top creep) (top drive) then [] else ["the creep witness is not slower than the drive witness"])
    match observe rules halt concepts (some k), observe rules drive concepts (some k), observe rules creep concepts (some k) with
    | some (vh, ch), some (vd, cd), some (vc, cc) =>
      situation ++
      (if ch == cd && ch == cc then [] else ["the case holds differently as the subject halts, drives or creeps: it depends on the subject's own motion"]) ++
      (if ch.any (· == some true) then [] else ["the case holds nowhere in the halt witness"]) ++
      (if vh.tag == "violated" then ["the rule is violated though the subject is at rest"] else []) ++
      (if vd.tag == "violated" then [] else [s!"driving in the same situation is {vd.tag}, not violated"]) ++
      (if vc.tag == "violated" then [] else [s!"creeping in the same situation is {vc.tag}, not violated: the duty is met short of a stop"])
    | _, _, _ => situation ++ ["a witness of the pair is not evaluated (its rule or its trace)"]

/-- The witness names of the paired controls of case `c`: halt, drive, creep. -/
def stopNames (c : RuleCase) : String × String × String :=
  (s!"stop_{c.name}_halt", s!"stop_{c.name}_drive", s!"stop_{c.name}_creep")

/-- The paired controls of a declared purpose, two witnesses: for `standingOrParking`, the same
    external situation with the subject at rest throughout (`a`, the rule violated) and moving
    (`b`, not violated); for `deviceInstruction`, the same scenes with the devices (`a`, the rule
    violated) and without any device (`b`, not violated). A rule whose verdict does not turn on
    standing, or on a device, fails them: a speed limit is not violated by standing, and is
    violated with no device present. Controls on two witnesses, not a proof. -/
def purposeControls (rules : List Rule) (a b : Scenario) (concepts : List Concept) (p : Purpose) : List String :=
  match subjectTrack rules a with
  | none => ["the first witness binds no subject"]
  | some who =>
    let situation := match p with
      | .standingOrParking =>
        (if sameExternal who a.trace b.trace then [] else ["the two witnesses differ in more than the subject's motion"]) ++
        (if (speeds who a.trace).all (· == some Q.zero) then [] else ["the subject is not at rest throughout the first witness"]) ++
        (if (speeds who b.trace).any (fun v => v.any (Q.lt Q.zero ·)) then [] else ["the subject does not move in the second witness"])
      | .deviceInstruction =>
        (if sameButDevices a.trace b.trace then [] else ["the two witnesses differ in more than their devices"]) ++
        (if a.trace.any (!·.devices.isEmpty) then [] else ["the first witness holds no device"]) ++
        (if b.trace.all (·.devices.isEmpty) then [] else ["the second witness holds a device"])
    match observe rules a concepts, observe rules b concepts with
    | some (va, _), some (vb, _) =>
      situation ++
      (if va.tag == "violated" then [] else [s!"the first witness is {va.tag}, not violated: the duty does not turn on {p}"]) ++
      (if vb.tag == "violated" then [s!"the second witness is violated: the duty is broken without {p}"] else [])
    | _, _ => situation ++ ["a witness of the pair is not evaluated (its rule or its trace)"]

/-- The witness names of the paired controls of purpose `p`. -/
def purposeNames : Purpose → String × String
  | .standingOrParking => ("purpose_standing_or_parking_halt", "purpose_standing_or_parking_move")
  | .deviceInstruction => ("purpose_device_instruction_on", "purpose_device_instruction_off")
end Scenario

end TrafficSpec
