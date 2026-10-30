/-
  TrafficSpec.Core.Vocab.World
  The scene, as data. This is the adapter's output type and the only place a data source's
  honesty is recorded: every field a source might not observe is `Option`, and a source writes
  `none` for what it did not observe, never `false`.

  Rules never import this module. A rule reads the world only through `Atoms` (the bijection with
  ATOMS.md), so a rule can neither bypass an atom's contract nor read a field the ontology does
  not name. `Grounding`, `Builders` and `Decode` are the other readers.

  Identity: a `TrackId` is a source's track, not a persistent object. A re-identification across a
  track break is the adapter's claim, recorded in `Scene.links` (old track ↦ new track) and
  followed by the grounding within a bounded gap.

  Nothing in this file names a statute, a data source, a threshold or a rate.
-/
import TrafficSpec.Core.Foundations.Time
import TrafficSpec.Core.Foundations.Handles
import TrafficSpec.Core.Vocab.Ontology.RoadUser
import TrafficSpec.Core.Vocab.Ontology.Structure
import TrafficSpec.Core.Vocab.Ontology.Device
import TrafficSpec.Core.Vocab.Ontology.Signal

namespace TrafficSpec

/-- The sort of an entity: what a variable ranges over. -/
inductive EntityKind
  | track | region | device
  deriving Repr, DecidableEq, Inhabited

/-- A point or vector in the world frame, metres. -/
abbrev Vec := Q × Q

/-- Measurements on a body (world frame; SI units as exact rationals, see Units) and the inputs
    to a vehicle's controls, which an instrumented source observes on its own vehicle. -/
structure Kin where
  position : Option Vec := none          -- m
  heading : Option Vec := none           -- finite nonzero vector; unit length recommended
  velocity : Option Vec := none          -- m/s
  speed : Option Q := none               -- m/s
  accelLongitudinal : Option Q := none   -- m/s², signed along heading
  yawRate : Option Q := none             -- deg/s
  extent : Option (Q × Q × Q) := none    -- half-length, half-width, half-height, m
  steerAngle : Option Q := none          -- deg
  pathLength : Option Q := none          -- m since the start of the trace
  engineRunning : Option Bool := none    -- propulsion available
  parkingBrake : Option Bool := none     -- parking brake set
  gear : Option Int := none              -- negative reverse, zero neutral, positive forward
  throttle : Option Q := none            -- fraction of full travel applied
  serviceBrake : Option Q := none        -- fraction of full travel applied
  deriving Repr, Inhabited

/-- How a rider sits and holds the machine (ATOMS.md `ru.rider_posture`). -/
structure Posture where
  onSeat : Option Bool := none
  handsOnControls : Option Nat := none
  standingOnDeck : Option Bool := none
  holdingAnotherVehicle : Option Bool := none
  stunt : Option Bool := none
  deriving Repr, Inhabited

structure WarningLamp where
  colour : LampColour
  mode : LampMode
  facing : Facing
  deriving Repr, DecidableEq, Inhabited

/-- Signals a road user emits (the `sig.*` atoms). -/
structure Signals where
  turnIndicator : Option TurnIndicatorState := none
  brakeLamp : Option Bool := none
  hazard : Option Bool := none
  headlamp : Option HeadlampState := none
  positionLamp : Option Bool := none
  reverseLamp : Option Bool := none
  warningLamps : Option (List WarningLamp) := none
  siren : Option Bool := none
  horn : Option Bool := none
  handSignal : Option HandSignal := none
  doorsOpen : Option (List DoorSide) := none
  compressionBrake : Option Bool := none
  deriving Repr, Inhabited

/-- Source classifications retained verbatim during a versioned schema migration.
    These labels are provenance, not new legal atoms or aliases for current classes. -/
structure SourceClassifications where
  schema : String
  classes : Option (List String) := none
  unobservedClasses : Option (List String) := none
  deriving Repr, Inhabited

structure RoadUser where
  track : TrackId
  sourceClassifications : Option SourceClassifications := none
  classes : Option (List RoadUserClass) := none   -- a user may be several (a school bus is a bus)
  /-- Classes the source cannot tell for this user: membership in them is unknown, not false. -/
  unobservedClasses : List RoadUserClass := []
  emergencyKind : Option EmergencyKind := none
  officialKind : Option OfficialKind := none
  eBikeClass : Option Nat := none
  occupants : Option Nat := none
  posture : Posture := {}
  kin : Kin := {}
  sig : Signals := {}
  sightAlongWay : Option (List (RegionId × Q)) := none   -- per way, m
  deriving Repr, Inhabited

/-- Lane attributes (ATOMS.md `st.lane_*`). -/
structure LaneInfo where
  direction : Option Vec := none
  leftNeighbour : Option RegionId := none
  rightNeighbour : Option RegionId := none
  ordinalFromLeft : Option Nat := none
  countInDirection : Option Nat := none
  leadsTo : Option (List RegionId) := none
  entersIntersection : Option RegionId := none   -- the intersection this lane is an approach to
  markingLeft : Option (MarkingType × MarkingColour) := none
  markingRight : Option (MarkingType × MarkingColour) := none
  width : Option Q := none
  deriving Repr, Inhabited

/-- A piece of road structure. `kind` says which structure atom it is; the typed attributes
    are those ATOMS.md lists for that kind, `none` when not observed. -/
structure Structure where
  id : RegionId
  kind : StructureKind
  /-- Kinds the source cannot tell for this region: whether it is one of them is unknown, not false. -/
  unobservedKinds : List StructureKind := []
  position : Option Vec := none             -- reference point (point-like structures)
  boundary : Option (List Vec) := none      -- polygon, for regions
  entranceOf : Option (List RegionId) := none -- stop line/crosswalk entrance associations
  lane : Option LaneInfo := none
  paved : Option Bool := none
  opening : Option Bool := none
  marked : Option Bool := none
  curvature : Option Q := none              -- 1/m
  grade : Option Q := none                  -- ratio
  sightDistance : Option Q := none          -- m
  ways : Option (List RegionId) := none     -- the highway regions it lies on
  reservedClass : Option ReservedClass := none
  turnSide : Option TurnSide := none
  parkingAngle : Option Q := none           -- deg
  designation : Option ParkingDesignation := none
  curbKind : Option CurbZoneKind := none
  curbColour : Option CurbColour := none
  obstructionKind : Option ObstructionKind := none
  deriving Repr, Inhabited

/-- Local calendar time of an observation (ATOMS.md `env.civil_time`). -/
structure CivilTime where
  year : Nat
  month : Nat
  day : Nat
  weekday : Nat        -- 0 = Monday … 6 = Sunday
  minuteOfDay : Nat    -- 0 … 1439
  deriving Repr, DecidableEq, Inhabited

/-- One window of a sign's conditions: on the listed weekdays (or a calendar class the reading
    supplies as an assumption), from `startMinute` to `endMinute` of the day. -/
structure TimeWindow where
  weekdays : List Nat := []
  calendarClass : Option AsmId := none
  startMinute : Nat := 0
  endMinute : Nat := 1440
  deriving Repr, Inhabited

/-- A structured reading of a sign's legend (ATOMS.md `dev.zone_sign` **conditions**). -/
structure Conditions where
  windows : List TimeWindow := []
  minOccupancy : Option Nat := none
  durationLimit : Option Q := none          -- s
  vehicleClass : Option RoadUserClass := none
  whenChildrenPresent : Bool := false
  deriving Repr, Inhabited

structure Device where
  id : DeviceId
  kind : DeviceKind
  /-- Kinds the source cannot tell for this device: whether it is one of them is unknown, not false. -/
  unobservedKinds : List DeviceKind := []
  position : Option Vec := none
  governs : List RegionId := []
  /-- Whether the source observes which regions the device governs; where it does not, `governs`
      is empty and no region is decidedly governed or not. -/
  governsObserved : Bool := true
  onTrack : Option TrackId := none                  -- a device carried by a road user (school bus)
  indications : Option (List SignalIndication) := none
  uncovered : Option Bool := none
  inoperative : Option Bool := none
  pedState : Option PedSignalState := none
  countdown : Option Bool := none
  laneControl : Option LaneControlState := none
  flashing : Option Bool := none
  active : Option Bool := none
  speedValue : Option Q := none                     -- m/s
  speedKind : Option SpeedSignKind := none
  code : Option SignCode := none
  zoneKind : Option ZoneKind := none
  isEnd : Option Bool := none
  conditions : Option Conditions := none
  railLights : Option RailLights := none
  gate : Option GateState := none
  bell : Option Bool := none
  humanRole : Option HumanRole := none
  humanIndication : Option HumanIndication := none
  redFlashing : Option Bool := none
  amberFlashing : Option Bool := none
  stopArm : Option Bool := none
  deriving Repr, Inhabited

structure Env where
  darkness : Option Bool := none
  precipitation : Option Bool := none
  wetRoad : Option Bool := none
  iceOrSnow : Option Bool := none
  visibility : Option Q := none              -- m
  civilTime : Option CivilTime := none
  deriving Repr, Inhabited

/-- A relation a source supplies measured rather than derived; `visible` is only ever supplied. -/
structure MeasuredRelation where
  a : TrackId
  b : TrackId
  centreDistance : Option Q := none
  surfaceGap : Option (Q × Q) := none        -- longitudinal, lateral, in a's frame
  aAheadOfB : Option Bool := none
  longitudinalOverlap : Option Q := none
  oncoming : Option Bool := none
  sameDirection : Option Bool := none
  bearing : Option Vec := none               -- b relative to a, in a's frame (long, lat)
  contact : Option Bool := none
  visible : Option Bool := none              -- b in a's line of sight
  deriving Repr, Inhabited

/-- A source's declaration current at a scene for one road user at one target region: each id
    listed true or false, an id the declaration does not decide left out. -/
structure DeclaredIntent where
  vehicle : TrackId
  target : RegionId
  values : List (IntId × Bool)
  deriving Repr, Inhabited

structure Scene where
  t : Timestamp
  subject : Option TrackId := none
  users : List RoadUser := []
  structures : List Structure := []
  devices : List Device := []
  /-- The tracks whose occupancy was observed: for them every region not listed in `occupies` is
      not occupied; for any other track `rel.occupies` is unknown. -/
  occupancyObserved : List TrackId := []
  occupies : List (TrackId × RegionId) := []
  relations : List MeasuredRelation := []
  env : Env := {}
  assumptions : List (AsmId × Bool) := []
  intents : List DeclaredIntent := []
  links : List (TrackId × TrackId) := []
  deriving Repr, Inhabited

/-- A trace: scenes in strictly increasing time. -/
abbrev Trace := List Scene

namespace Scene
def user (s : Scene) (x : TrackId) : Option RoadUser := s.users.find? (·.track == x)
def structure? (s : Scene) (r : RegionId) : Option Structure := s.structures.find? (·.id == r)
def device (s : Scene) (d : DeviceId) : Option Device := s.devices.find? (·.id == d)
def relation (s : Scene) (a b : TrackId) : Option MeasuredRelation :=
  s.relations.find? (fun m => m.a == a && m.b == b)
def tracks (s : Scene) : List TrackId := s.users.map (·.track)
end Scene

-- ---------------------------------------------------------------------------------------------
-- Projections a trace check reads, so that it names no field of these records itself. A field a
-- split may omit is named on a line of its own.
-- ---------------------------------------------------------------------------------------------
/-- A reference a scene makes to an entity: where it is written, the kind of entity it names, the
    id, and the structure kind that entity must have when the field requires one. -/
structure Reference where
  place : String
  kind : EntityKind
  id : Nat
  structureKind : Option StructureKind := none
  deriving Repr, Inhabited

namespace Structure
/-- The regions a structure's own fields name: its lane's neighbours, successors and intersection,
    and the ways it lies on. -/
def references (st : Structure) : List Reference :=
  let at_ := fun (f : String) => s!"structure {st.id} {f}"
  (st.lane.bind (·.leftNeighbour)).toList.map (fun r => { place := at_ "lane.left", kind := .region, id := r })
  ++ (st.lane.bind (·.rightNeighbour)).toList.map (fun r => { place := at_ "lane.right", kind := .region, id := r })
  ++ ((st.lane.bind (·.leadsTo)).getD []).map (fun r => { place := at_ "lane.leads_to", kind := .region, id := r })
  ++ (st.lane.bind (·.entersIntersection)).toList.map (fun r => { place := at_ "lane.enters_intersection", kind := .region, id := r })
  ++ (st.entranceOf.getD []).map (fun r => { place := at_ "entrance_of", kind := .region, id := r, structureKind := some .lane })
  ++ (st.ways.getD []).map (fun r => { place := at_ "ways", kind := .region, id := r })
end Structure

namespace Scene
/-- Every reference the scene makes to an entity, each of which must be present in the scene. -/
def references (s : Scene) : List Reference :=
  (s.subject.toList.map fun t => { place := "subject", kind := .track, id := t })
  ++ (s.occupies.flatMap fun (t, r) => [{ place := "occupies", kind := .track, id := t }, { place := "occupies", kind := .region, id := r }])
  ++ (s.occupancyObserved.map fun t => { place := "occupancy_observed", kind := .track, id := t })
  ++ (s.relations.flatMap fun m => [{ place := "relations[].a", kind := .track, id := m.a }, { place := "relations[].b", kind := .track, id := m.b }])
  ++ (s.devices.flatMap fun d => d.governs.map fun r => { place := s!"device {d.id} governs", kind := .region, id := r })
  ++ (s.devices.flatMap fun d => d.onTrack.toList.map fun t => { place := s!"device {d.id} on_track", kind := .track, id := t })
  ++ (s.structures.flatMap Structure.references)
  ++ (s.users.flatMap fun u => (u.sightAlongWay.getD []).map fun (w, _) =>
       { place := s!"user {u.track} sight_along_way", kind := .region, id := w, structureKind := some .highway })
end Scene

namespace Device
/-- The fields of a device that may change between scenes: the state it displays or senses (JSON keys). -/
def stateFields : List String := [
  "indications",
  "uncovered",
  "inoperative",
  "ped_state",
  "countdown",
  "lane_control",
  "flashing",
  "active",
  "rail_lights",
  "gate",
  "bell",
  "human_indication",
  "red_flashing",
  "amber_flashing",
  "stop_arm"
  ]

/-- A device that moves: one carried by a road user, or a person directing traffic. Its position is
    state too. -/
def mobile (d : Device) : Bool :=
  d.kind == .humanDirection
  || d.onTrack.isSome

/-- The device without its state: what is the same at every appearance of the device. -/
def staticPart (d : Device) : Device :=
  { d with
    position := if d.mobile then none else d.position
    indications := none
    uncovered := none
    inoperative := none
    pedState := none
    countdown := none
    laneControl := none
    flashing := none
    active := none
    railLights := none
    gate := none
    bell := none
    humanIndication := none
    redFlashing := none
    amberFlashing := none
    stopArm := none
    }
end Device

namespace Trace
def timestamps (τ : Trace) : List Timestamp := τ.map (·.t)
def monotone (τ : Trace) : Bool :=
  match τ with
  | a :: b :: rest => a.t < b.t && monotone (b :: rest)
  | _ => true
end Trace

end TrafficSpec
