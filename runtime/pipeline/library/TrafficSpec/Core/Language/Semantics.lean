/-
  TrafficSpec.Core.Language.Semantics
  The meaning of a formula over a trace: one three-valued result with reasons per instant.

  `evalAll` evaluates a formula bottom-up, each subformula once for the whole trace, so a formula
  costs O(|φ| · n log n) per binding: atoms map a scene function over the instants, the temporal
  operators are the single-pass operators of Temporal.lean, quantifiers evaluate their body once
  per region or device present anywhere in the trace. `eval c i φ` is the value at instant i.

  Atoms and derived concepts are dispatched by name to the definitions of Atoms.lean and
  Primitives.lean; a name the tables do not know, a wrong arity, a literal that spells no
  enumeration value or a variable of the wrong sort is `unknown (malformed …)`. The static check
  (RuleEval.check) finds every such defect from the syntax before any trace is read, so a checked
  rule reports at evaluation time only source absence, truncation, sampling gaps, undefined
  concept preconditions, division by zero and unknown compositions.

  Finite-trace policy — unobserved is unknown, never compliance:
  - `holdsFor` needs its whole window observed at adequate density, else unknown;
  - `within`/`untilWithin` are true on a witness, false only when the window is covered;
  - `eventually`/`until` carry the unobserved future, `since` the unobserved past, and `always`
    the unobserved future as unknown: on a finite trace `always φ` is false or unknown, never true.
    A rule's obligation is written for an instant; the sweep over instants (Grounding) is the
    "always".

  Rule composition is a callback, because the library of rules is defined above this file.
-/
import TrafficSpec.Core.Language.Formula
import TrafficSpec.Core.Vocab.Primitives
import TrafficSpec.Core.Vocab.Intentions

namespace TrafficSpec
namespace Semantics

open Primitives (DArg)
open Temporal

/-- Everything an evaluation needs: the indexed trace with its reading, the bindings, and how to
    evaluate another rule's obligation (`rule id map`) under a variable map, per instant. -/
structure SemCtx where
  d : Primitives.Ctx
  β : Binding := {}
  /-- Another rule's verdict per instant under a variable map: complied-with when `engaged` is
      false, engaged (classes and applicability) when true. -/
  compose : String → List (String × String) → Binding → Bool → Array R :=
    fun _ _ _ _ => #[]

namespace SemCtx
def n (c : SemCtx) : Nat := c.d.n
def scenes (c : SemCtx) : Array Scene := c.d.scenes
def bindVar (c : SemCtx) (v : String) (x : Val) : SemCtx := { c with β := c.β.bind v x }
def mk' (τ : Trace) (ρ : Reading) (β : Binding := {}) : SemCtx := { d := Primitives.Ctx.mk' τ ρ, β := β }
end SemCtx

-- ---------------------------------------------------------------------------------------------
-- Arguments
-- ---------------------------------------------------------------------------------------------
def resolve (β : Binding) : Arg → Except UnknownReason DArg
  | .var v =>
    match β.lookup v with
    | some (.track t) => .ok (.v t)
    | some (.region r) => .ok (.v r)
    | some (.device d) => .ok (.v d)
    | none => .error (.unboundVariable v)
  | .lit s => .ok (.s s)
  | .nat k => .ok (.n k)

def resolveAll (β : Binding) (args : List Arg) : Except UnknownReason (List DArg) := args.mapM (resolve β)

private def ent (a : DArg) : Except UnknownReason Nat :=
  match a with | .v t => .ok t | .n k => .ok k | .s _ => .error (.malformed "entity expected")
private def lit (a : DArg) : Except UnknownReason String :=
  match a with | .s s => .ok s | _ => .error (.malformed "literal expected")
private def enumLit {α : Type} (ofString : String → Option α) (a : DArg) : Except UnknownReason α := do
  let s ← lit a
  match ofString s with | some v => .ok v | none => .error (.malformed s)

private def b (o : Option Bool) (name : String) : R := R.ofOption o (.absentAtom name)
private def eqEnum {α : Type} [DecidableEq α] (o : Option α) (v : α) (name : String) : R :=
  b (o.map (· == v)) name
private def q (o : Option Q) (name : String) : QR :=
  match o with | some v => .ok v | none => .error (.absentAtom name)
private def qn (o : Option Nat) (name : String) : QR :=
  match o with | some v => .ok (Q.ofInt (Int.ofNat v)) | none => .error (.absentAtom name)
private def qz (o : Option Int) (name : String) : QR :=
  match o with | some v => .ok (Q.ofInt v) | none => .error (.absentAtom name)

def unknownAtom (n : String) : UnknownReason := .malformed s!"atom {n}"
def arity (n : String) : UnknownReason := .malformed s!"arity {n}"

-- ---------------------------------------------------------------------------------------------
-- Boolean atoms by name, on one scene. Class atoms (`ru_*`, `st_*`, `dev_*` kinds) are dispatched
-- through the generated codecs, so the table cannot drift from ATOMS.md; attribute atoms are listed.
-- ---------------------------------------------------------------------------------------------
def evalAtomE (s : Scene) (name : String) (args : List DArg) (ps : List Q) : Except UnknownReason R := do
  match name, args with
  -- road users
  | "ru_subject", [x] => pure (b (ru_subject s (← ent x)) name)
  | "ru_aggregate", [_, .s w] => .error (.parameterMissing s!"aggregate:{w}")   -- resolved with the reading in `evalAll`
  | "ru_rider_posture", [x, f] =>
    match f with
    | .s "on_seat" => pure (b (ru_rider_posture_on_seat s (← ent x)) name)
    | .s "standing_on_deck" => pure (b (ru_rider_posture_standing_on_deck s (← ent x)) name)
    | .s "holding_another_vehicle" => pure (b (ru_rider_posture_holding_another_vehicle s (← ent x)) name)
    | .s "stunt" => pure (b (ru_rider_posture_stunt s (← ent x)) name)
    | _ => .error (.malformed "posture field")
  | "ru_rider_posture_on_seat", [x] => pure (b (ru_rider_posture_on_seat s (← ent x)) name)
  | "ru_rider_posture_standing_on_deck", [x] => pure (b (ru_rider_posture_standing_on_deck s (← ent x)) name)
  | "ru_rider_posture_holding_another_vehicle", [x] => pure (b (ru_rider_posture_holding_another_vehicle s (← ent x)) name)
  | "ru_rider_posture_stunt", [x] => pure (b (ru_rider_posture_stunt s (← ent x)) name)
  | "ru_emergency_vehicle_kind", [x, k] => pure (eqEnum (ru_emergency_vehicle_kind s (← ent x)) (← enumLit EmergencyKind.ofString k) name)
  | "ru_official_vehicle_kind", [x, k] => pure (eqEnum (ru_official_vehicle_kind s (← ent x)) (← enumLit OfficialKind.ofString k) name)
  -- control state
  | "kin_engine_running", [x] => pure (b (kin_engine_running s (← ent x)) name)
  | "kin_parking_brake", [x] => pure (b (kin_parking_brake s (← ent x)) name)
  -- structure attributes
  | "st_road_edge_paved", [r] => pure (b (st_road_edge_paved s (← ent r)) name)
  | "st_shoulder_paved", [r] => pure (b (st_shoulder_paved s (← ent r)) name)
  | "st_median_or_divider_opening", [r] => pure (b (st_median_or_divider_opening s (← ent r)) name)
  | "st_crosswalk_marked", [r] => pure (b (st_crosswalk_marked s (← ent r)) name)
  | "st_reserved_lane_class", [r, k] => pure (eqEnum (st_reserved_lane_class s (← ent r)) (← enumLit ReservedClass.ofString k) name)
  | "st_turn_lane_side", [r, k] => pure (eqEnum (st_turn_lane_side s (← ent r)) (← enumLit TurnSide.ofString k) name)
  | "st_parking_space_designation", [r, k] => pure (eqEnum (st_parking_space_designation s (← ent r)) (← enumLit ParkingDesignation.ofString k) name)
  | "st_curb_zone_kind", [r, k] => pure (eqEnum (st_curb_zone_kind s (← ent r)) (← enumLit CurbZoneKind.ofString k) name)
  | "st_curb_zone_colour", [r, k] => pure (eqEnum (st_curb_zone_colour s (← ent r)) (← enumLit CurbColour.ofString k) name)
  | "st_obstruction_kind", [r, k] => pure (eqEnum (st_obstruction_kind s (← ent r)) (← enumLit ObstructionKind.ofString k) name)
  | "st_lane_adjacency", [r, sd, r'] =>
    match sd with
    | .s "left" => pure (b (st_lane_left_of s (← ent r) (← ent r')) name)
    | .s "right" => pure (b (st_lane_right_of s (← ent r) (← ent r')) name)
    | _ => .error (.malformed "side")
  | "st_lane_adjacency_left", [r, r'] => pure (b (st_lane_left_of s (← ent r) (← ent r')) name)
  | "st_lane_adjacency_right", [r, r'] => pure (b (st_lane_right_of s (← ent r) (← ent r')) name)
  | "st_lane_connectivity", [r, r'] => pure (b ((st_lane_connectivity s (← ent r)).map (·.contains (← ent r'))) name)
  | "st_entrance_of", [r, l] => pure (b ((st_entrance_of s (← ent r)).map (·.contains (← ent l))) name)
  | "st_lane_enters", [r, i] => pure (b ((st_lane_enters s (← ent r)).map (· == (← ent i))) name)
  | "st_on_way", [r, w] => pure (b ((st_on_way s (← ent r)).map (·.contains (← ent w))) name)
  | "st_lane_marking", [r, sd, t] =>
    match sd with
    | .s "left" => pure (eqEnum ((st_lane_marking_left s (← ent r)).map (·.1)) (← enumLit MarkingType.ofString t) name)
    | .s "right" => pure (eqEnum ((st_lane_marking_right s (← ent r)).map (·.1)) (← enumLit MarkingType.ofString t) name)
    | _ => .error (.malformed "side")
  | "st_lane_marking", [r, sd, t, col] =>
    let m ← match sd with
      | .s "left" => pure (st_lane_marking_left s (← ent r))
      | .s "right" => pure (st_lane_marking_right s (← ent r))
      | _ => .error (.malformed "side")
    pure (R.and (eqEnum (m.map (·.1)) (← enumLit MarkingType.ofString t) name)
                (eqEnum (m.map (·.2)) (← enumLit MarkingColour.ofString col) name))
  | "st_lane_marking_left", [r, t] => pure (eqEnum ((st_lane_marking_left s (← ent r)).map (·.1)) (← enumLit MarkingType.ofString t) name)
  | "st_lane_marking_right", [r, t] => pure (eqEnum ((st_lane_marking_right s (← ent r)).map (·.1)) (← enumLit MarkingType.ofString t) name)
  | "rel_occupies", [x, r] => pure (b (rel_occupies s (← ent x) (← ent r)) name)
  -- devices
  | "dev_traffic_signal_shows", [d, k] => pure (b (dev_traffic_signal_shows s (← ent d) (← enumLit SignalIndication.ofString k)) name)
  | "dev_traffic_signal_uncovered", [d] => pure (b (dev_traffic_signal_uncovered s (← ent d)) name)
  | "dev_pedestrian_signal_state", [d, k] => pure (eqEnum (dev_pedestrian_signal_state s (← ent d)) (← enumLit PedSignalState.ofString k) name)
  | "dev_pedestrian_signal_countdown", [d] => pure (b (dev_pedestrian_signal_countdown s (← ent d)) name)
  | "dev_lane_control_signal_state", [d, k] => pure (eqEnum (dev_lane_control_signal_state s (← ent d)) (← enumLit LaneControlState.ofString k) name)
  | "dev_speed_limit_beacon_flashing", [d] => pure (b (dev_speed_limit_beacon_flashing s (← ent d)) name)
  | "dev_crossing_warning_signal_active", [d] => pure (b (dev_crossing_warning_signal_active s (← ent d)) name)
  | "dev_speed_limit_sign_kind", [d, k] => pure (eqEnum (dev_speed_limit_sign_kind s (← ent d)) (← enumLit SpeedSignKind.ofString k) name)
  | "dev_regulatory_sign_code", [d, k] => pure (eqEnum (dev_regulatory_sign_code s (← ent d)) (← enumLit SignCode.ofString k) name)
  | "dev_zone_sign_kind", [d, k] => pure (eqEnum (dev_zone_sign_kind s (← ent d)) (← enumLit ZoneKind.ofString k) name)
  | "dev_zone_sign_end", [d] => pure (b (dev_zone_sign_end s (← ent d)) name)
  | "dev_railway_signal_or_gate_lights", [d, k] => pure (eqEnum (dev_railway_signal_or_gate_lights s (← ent d)) (← enumLit RailLights.ofString k) name)
  | "dev_railway_signal_or_gate_gate", [d, k] => pure (eqEnum (dev_railway_signal_or_gate_gate s (← ent d)) (← enumLit GateState.ofString k) name)
  | "dev_railway_signal_or_gate_bell", [d] => pure (b (dev_railway_signal_or_gate_bell s (← ent d)) name)
  | "dev_human_direction_role", [d, k] => pure (eqEnum (dev_human_direction_role s (← ent d)) (← enumLit HumanRole.ofString k) name)
  | "dev_human_direction_indication", [d, k] => pure (eqEnum (dev_human_direction_indication s (← ent d)) (← enumLit HumanIndication.ofString k) name)
  | "dev_school_bus_signal_on_track", [d, x] => pure (b ((dev_school_bus_signal_on_track s (← ent d)).map (· == (← ent x))) name)
  | "dev_school_bus_signal_red_flashing", [d] => pure (b (dev_school_bus_signal_red_flashing s (← ent d)) name)
  | "dev_school_bus_signal_amber_flashing", [d] => pure (b (dev_school_bus_signal_amber_flashing s (← ent d)) name)
  | "dev_school_bus_signal_stop_arm", [d] => pure (b (dev_school_bus_signal_stop_arm s (← ent d)) name)
  | "dev_governs", [d, r] => pure (b (dev_governs s (← ent d) (← ent r)) name)
  | "dev_inoperative", [d] => pure (b (dev_inoperative s (← ent d)) name)
  -- signals emitted
  | "sig_turn_indicator", [x, k] => pure (eqEnum (sig_turn_indicator s (← ent x)) (← enumLit TurnIndicatorState.ofString k) name)
  | "sig_brake_lamp", [x] => pure (b (sig_brake_lamp s (← ent x)) name)
  | "sig_hazard", [x] => pure (b (sig_hazard s (← ent x)) name)
  | "sig_headlamp", [x, k] => pure (eqEnum (sig_headlamp s (← ent x)) (← enumLit HeadlampState.ofString k) name)
  | "sig_position_lamp", [x] => pure (b (sig_position_lamp s (← ent x)) name)
  | "sig_reverse_lamp", [x] => pure (b (sig_reverse_lamp s (← ent x)) name)
  | "sig_warning_lamp", [x, col] => pure (b (sig_warning_lamp_colour s (← ent x) (← enumLit LampColour.ofString col)) name)
  | "sig_warning_lamp", [x, col, m] => pure (b (sig_warning_lamp_shows s (← ent x) (← enumLit LampColour.ofString col) (← enumLit LampMode.ofString m)) name)
  | "sig_siren", [x] => pure (b (sig_siren s (← ent x)) name)
  | "sig_horn", [x] => pure (b (sig_horn s (← ent x)) name)
  | "sig_hand_signal", [x, k] => pure (eqEnum (sig_hand_signal s (← ent x)) (← enumLit HandSignal.ofString k) name)
  | "sig_door_open", [x] => pure (b ((sig_door_open s (← ent x)).map (!·.isEmpty)) name)
  | "sig_door_open", [x, k] => pure (b (sig_door_open_side s (← ent x) (← enumLit DoorSide.ofString k)) name)
  | "sig_compression_brake", [x] => pure (b (sig_compression_brake s (← ent x)) name)
  -- environment
  | "env_darkness", [] => pure (b (env_darkness s) name)
  | "env_precipitation", [] => pure (b (env_precipitation s) name)
  | "env_wet_road", [] => pure (b (env_wet_road s) name)
  | "env_ice_or_snow", [] => pure (b (env_ice_or_snow s) name)
  -- relations
  | "rel_ahead_behind_in_lane", [a, a'] => pure (b (rel_ahead_behind_in_lane s (← ent a) (← ent a')) name)
  | "rel_ahead_in_lane", [a, a'] => pure (b (rel_ahead_in_lane s (← ent a) (← ent a')) name)
  | "rel_behind_in_lane", [a, a'] => pure (b (rel_behind_in_lane s (← ent a) (← ent a')) name)
  | "rel_oncoming", [a, a'] =>
    match ps with
    | [tol] => pure (b (rel_oncoming s (← ent a) (← ent a') tol) name)
    | _ => .error (.parameterMissing "rel_oncoming cosine tolerance")
  | "rel_same_direction", [a, a'] =>
    match ps with
    | [tol] => pure (b (rel_same_direction s (← ent a) (← ent a') tol) name)
    | _ => .error (.parameterMissing "rel_same_direction cosine tolerance")
  | "rel_bearing", [a, a', k] =>
    match k with
    | .s "ahead" => pure (b (rel_bearing_ahead s (← ent a) (← ent a')) name)
    | .s "behind" => pure (b (rel_bearing_behind s (← ent a) (← ent a')) name)
    | .s "left" => pure (b (rel_bearing_left s (← ent a) (← ent a')) name)
    | .s "right" => pure (b (rel_bearing_right s (← ent a) (← ent a')) name)
    | _ => .error (.malformed "bearing side")
  | "rel_contact", [a, a'] => pure (b (rel_contact s (← ent a) (← ent a')) name)
  | "rel_visible", [a, a'] => pure (b (rel_visible s (← ent a) (← ent a')) name)
  -- class atoms through the generated codecs
  | n, [x] =>
    if n.startsWith "ru_" then
      match RoadUserClass.ofString (n.drop 3).toString with
      | some k => pure (b ((s.user (← ent x)).bind fun u =>
          if u.unobservedClasses.contains k then none else u.classes.map (·.contains k)) n)
      | none => .error (unknownAtom n)
    else if n.startsWith "st_" then
      match StructureKind.ofString (n.drop 3).toString with
      | some k => pure (b (isKind s (← ent x) k) n)
      | none => .error (unknownAtom n)
    else if n.startsWith "dev_" then
      match DeviceKind.ofString (n.drop 4).toString with
      | some k => pure (b (devKind s (← ent x) k) n)
      | none => .error (unknownAtom n)
    else .error (unknownAtom n)
  | n, _ =>
    if n.startsWith "ru_" && (RoadUserClass.ofString (n.drop 3).toString).isSome then .error (arity n)
    else if n.startsWith "st_" && (StructureKind.ofString (n.drop 3).toString).isSome then .error (arity n)
    else if n.startsWith "dev_" && (DeviceKind.ofString (n.drop 4).toString).isSome then .error (arity n)
    else if boolAtomNames.contains n then .error (arity n)
    else .error (unknownAtom n)
where
  /-- The attribute atoms of the table above (for the arity/unknown distinction and the doctor). -/
  boolAtomNames : List String := [
    "ru_subject", "ru_aggregate", "ru_rider_posture", "ru_rider_posture_on_seat", "ru_rider_posture_standing_on_deck",
    "ru_rider_posture_holding_another_vehicle", "ru_rider_posture_stunt", "ru_emergency_vehicle_kind",
    "ru_official_vehicle_kind", "kin_engine_running", "kin_parking_brake",
    "st_road_edge_paved", "st_shoulder_paved", "st_median_or_divider_opening",
    "st_crosswalk_marked", "st_reserved_lane_class", "st_turn_lane_side", "st_parking_space_designation",
    "st_curb_zone_kind", "st_curb_zone_colour", "st_obstruction_kind", "st_lane_adjacency", "st_lane_adjacency_left",
    "st_lane_adjacency_right", "st_lane_connectivity", "st_lane_enters", "st_entrance_of", "st_on_way", "st_lane_marking", "st_lane_marking_left", "st_lane_marking_right",
    "rel_occupies", "dev_traffic_signal_shows", "dev_traffic_signal_uncovered", "dev_pedestrian_signal_state",
    "dev_pedestrian_signal_countdown", "dev_lane_control_signal_state", "dev_speed_limit_beacon_flashing",
    "dev_crossing_warning_signal_active", "dev_speed_limit_sign_kind", "dev_regulatory_sign_code",
    "dev_zone_sign_kind", "dev_zone_sign_end", "dev_railway_signal_or_gate_lights",
    "dev_railway_signal_or_gate_gate", "dev_railway_signal_or_gate_bell", "dev_human_direction_role",
    "dev_human_direction_indication", "dev_school_bus_signal_on_track", "dev_school_bus_signal_red_flashing",
    "dev_school_bus_signal_amber_flashing", "dev_school_bus_signal_stop_arm", "dev_governs", "dev_inoperative",
    "sig_turn_indicator", "sig_brake_lamp", "sig_hazard", "sig_headlamp", "sig_position_lamp",
    "sig_reverse_lamp", "sig_warning_lamp", "sig_siren", "sig_horn", "sig_hand_signal",
    "sig_door_open", "sig_compression_brake", "env_darkness", "env_precipitation", "env_wet_road",
    "env_ice_or_snow", "rel_ahead_behind_in_lane", "rel_ahead_in_lane", "rel_behind_in_lane", "rel_oncoming",
    "rel_same_direction", "rel_bearing", "rel_contact", "rel_visible"]

-- ---------------------------------------------------------------------------------------------
-- Measured atoms by name (quantity-valued), on one scene. Vector atoms take a component literal.
-- ---------------------------------------------------------------------------------------------
private def comp (v : Option Vec) (k : DArg) (name : String) : QR := do
  match k with
  | .s "x" => q (v.map (·.1)) name
  | .s "y" => q (v.map (·.2)) name
  | _ => .error (.malformed "component")

def evalMeasure (s : Scene) (name : String) (args : List DArg) : QR := do
  match name, args with
  | "kin_time", [] => .ok (Time.ofTimestamp (kin_time s))
  | "kin_position", [x, k] => comp (kin_position s (← ent x)) k name
  | "kin_heading", [x, k] => comp ((kin_heading s (← ent x)).bind Geom.unit) k name
  | "kin_velocity", [x, k] => comp (kin_velocity s (← ent x)) k name
  | "kin_speed", [x] => q (kin_speed s (← ent x)) name
  | "kin_accel_longitudinal", [x] => q (kin_accel_longitudinal s (← ent x)) name
  | "kin_yaw_rate", [x] => q (kin_yaw_rate s (← ent x)) name
  | "kin_extent", [x, k] =>
    let e := kin_extent s (← ent x)
    match k with   -- full extents: twice the half-extent
    | .s "length" => q (e.map fun (l, _, _) => Q.mul (Q.ofInt 2) l) name
    | .s "width" => q (e.map fun (_, w, _) => Q.mul (Q.ofInt 2) w) name
    | .s "height" => q (e.map fun (_, _, h) => Q.mul (Q.ofInt 2) h) name
    | _ => .error (.malformed "extent")
  | "kin_steer_angle", [x] => q (kin_steer_angle s (← ent x)) name
  | "kin_path_length", [x] => q (kin_path_length s (← ent x)) name
  | "kin_gear", [x] => qz (kin_gear s (← ent x)) name
  | "kin_throttle", [x] => q (kin_throttle s (← ent x)) name
  | "kin_service_brake", [x] => q (kin_service_brake s (← ent x)) name
  | "ru_occupant_count", [x] => qn (ru_occupant_count s (← ent x)) name
  | "ru_rider_posture_hands_on_controls", [x] => qn (ru_rider_posture_hands_on_controls s (← ent x)) name
  | "ru_electric_bicycle_class", [x] => qn (ru_electric_bicycle_class s (← ent x)) name
  | "st_lane_direction", [r, k] => comp (st_lane_direction s (← ent r)) k name
  | "st_lane_adjacency", [r, k] =>
    match k with
    | .s "ordinal" => qn (st_lane_adjacency_ordinal s (← ent r)) name
    | .s "count" => qn (st_lane_adjacency_count s (← ent r)) name
    | _ => .error (.malformed "adjacency field")
  | "st_lane_adjacency_ordinal", [r] => qn (st_lane_adjacency_ordinal s (← ent r)) name
  | "st_lane_adjacency_count", [r] => qn (st_lane_adjacency_count s (← ent r)) name
  | "st_lane_width", [r] => q (st_lane_width s (← ent r)) name
  | "st_curvature", [r] => q (st_curvature s (← ent r)) name
  | "st_grade", [r] => q (st_grade s (← ent r)) name
  | "st_sight_distance", [r] => q (st_sight_distance s (← ent r)) name
  | "st_sight_along_way", [x, w] => q (st_sight_along_way s (← ent x) (← ent w)) name
  | "st_parking_space_angle", [r] => q (st_parking_space_angle s (← ent r)) name
  | "st_region_geometry", [r, k] => comp (st_region_geometry_position s (← ent r)) k name
  | "st_region_geometry_distance", [x, r] => q (st_region_geometry_distance s (← ent x) (← ent r)) name
  | "dev_position", [d, k] => comp (dev_position s (← ent d)) k name
  | "dev_speed_limit_sign_value", [d] => q (dev_speed_limit_sign_value s (← ent d)) name
  | "env_visibility", [] => q (env_visibility s) name
  | "env_civil_time", [k] =>
    let ct := env_civil_time s
    match k with
    | .s "minute_of_day" => qn (ct.map (·.minuteOfDay)) name
    | .s "weekday" => qn (ct.map (·.weekday)) name
    | .s "month" => qn (ct.map (·.month)) name
    | .s "day" => qn (ct.map (·.day)) name
    | .s "year" => qn (ct.map (·.year)) name
    | _ => .error (.malformed "civil time field")
  | "rel_centre_distance", [a, a'] => q (rel_centre_distance s (← ent a) (← ent a')) name
  | "rel_surface_gap", [a, a'] => q (rel_surface_gap_min s (← ent a) (← ent a')) name
  | "rel_surface_gap", [a, a', k] =>
    match k with
    | .s "longitudinal" => q (rel_surface_gap_longitudinal s (← ent a) (← ent a')) name
    | .s "lateral" => q (rel_surface_gap_lateral s (← ent a) (← ent a')) name
    | .s "min" => q (rel_surface_gap_min s (← ent a) (← ent a')) name
    | _ => .error (.malformed "gap component")
  | "rel_longitudinal_overlap", [a, a'] => q (rel_longitudinal_overlap s (← ent a) (← ent a')) name
  | "rel_bearing", [a, a', k] => comp (rel_bearing s (← ent a) (← ent a')) k name
  | n, _ => if measureNames.contains n then .error (arity n) else .error (unknownAtom n)
where
  measureNames : List String := [
    "kin_time", "kin_position", "kin_heading", "kin_velocity", "kin_speed", "kin_accel_longitudinal",
    "kin_yaw_rate", "kin_extent", "kin_steer_angle", "kin_path_length", "kin_gear", "kin_throttle", "kin_service_brake", "ru_occupant_count",
    "ru_rider_posture_hands_on_controls", "ru_electric_bicycle_class", "st_lane_direction", "st_lane_adjacency",
    "st_lane_adjacency_ordinal", "st_lane_adjacency_count", "st_lane_width", "st_curvature", "st_grade",
    "st_sight_distance", "st_sight_along_way", "st_parking_space_angle", "st_region_geometry", "st_region_geometry_distance",
    "dev_position", "dev_speed_limit_sign_value", "env_visibility", "env_civil_time",
    "rel_centre_distance", "rel_surface_gap", "rel_longitudinal_overlap", "rel_bearing"]

/-- Whether a name is known to either table (the doctor holds this against `atomIds`). -/
def knowsAtom (n : String) : Bool :=
  let s : Scene := { t := 0 }
  let isUnknown : Except UnknownReason R → Bool
    | .error e => e == unknownAtom n
    | _ => false
  let isUnknownQ : QR → Bool
    | .error e => e == unknownAtom n
    | _ => false
  !(isUnknown (evalAtomE s n [] []) && isUnknownQ (evalMeasure s n []))

/-- The sort each entity argument of an atom must have (`none` marks a literal position): by
    family, with the mixed atoms listed. `none` for a name the tables do not know. -/
def atomArgSorts (name : String) : Option (List (Option EntityKind)) :=
  let t := some EntityKind.track; let r := some EntityKind.region; let d := some EntityKind.device
  match name with
  | "rel_occupies" => some [t, r]
  | "ru_aggregate" => some [t, none]
  | "dev_governs" => some [d, r]
  | "dev_school_bus_signal_on_track" => some [d, t]
  | "st_region_geometry_distance" | "st_sight_along_way" => some [t, r]
  | "st_lane_adjacency" => some [r, none, r]
  | "st_lane_adjacency_left" | "st_lane_adjacency_right" | "st_lane_connectivity" | "st_lane_enters" | "st_entrance_of" | "st_on_way" => some [r, r]
  | "st_lane_marking" => some [r, none, none, none]
  | "rel_oncoming" | "rel_same_direction" | "rel_ahead_behind_in_lane" | "rel_ahead_in_lane"
  | "rel_behind_in_lane" | "rel_contact" | "rel_visible" | "rel_centre_distance" | "rel_longitudinal_overlap" => some [t, t]
  | "rel_surface_gap" | "rel_bearing" => some [t, t, none]
  | n =>
    if !knowsAtom n then none
    else if n.startsWith "env_" || n == "kin_time" then some []
    else if n.startsWith "ru_" || n.startsWith "kin_" || n.startsWith "sig_" then some [t, none, none]
    else if n.startsWith "st_" then some [r, none, none]
    else if n.startsWith "dev_" then some [d, none, none]
    else none

/-- The Lean name of an ATOMS.md id or attribute path (`dev.traffic_signal.shows` ↦ `dev_traffic_signal_shows`). -/
def defName (id : String) : String := id.replace "." "_"

-- ---------------------------------------------------------------------------------------------
-- The evaluator: every subformula once, over the whole trace.
-- ---------------------------------------------------------------------------------------------
private def constU (n : Nat) (w : UnknownReason) : Array R := const n (R.u w)
private def constE (n : Nat) (w : UnknownReason) : Array QR := Array.replicate n (.error w)
private def liftA (n : Nat) (e : Except UnknownReason (Array R)) : Array R :=
  match e with | .ok a => a | .error w => constU n w
private def liftQ (n : Nat) (e : Except UnknownReason (Array QR)) : Array QR :=
  match e with | .ok a => a | .error w => constE n w
private def qzip (f : Q → Q → Q) (a b : Array QR) : Array QR :=
  Array.zipWith (fun x y => do pure (f (← x) (← y))) a b

/-- A term that names no instant: a literal, a parameter or arithmetic over those. Only such a
    term may parametrize an atom or a derived concept. -/
partial def Term.isConstant : Term → Bool
  | .lit _ _ | .param _ => true
  | .add a b | .sub a b | .mul a b | .div a b => Term.isConstant a && Term.isConstant b
  | .neg a | .abs a => Term.isConstant a
  | _ => false

/-- The single value of a constant term's per-instant array. -/
private def constOf (t : Term) (arr : Array QR) : Except UnknownReason Q := do
  if !Term.isConstant t then throw (.malformed "parameter is not a constant term")
  arr[0]?.getD (.error .outOfRange)

/-- The subject variable of a window: needed for path windows, irrelevant for time windows. -/
def subjectFor (β : Binding) (m : Measure) (v : String) : Except UnknownReason TrackId :=
  match m with
  | .time => .ok 0
  | .path => match β.track v with | some t => .ok t | none => .error (.unboundVariable v)

/-- Every region a quantifier over a kind ranges over in some scene of the trace: those of the
    kind, and those whose kind the source cannot tell. -/
def regionsOf (c : SemCtx) (k : StructureKind) : List RegionId :=
  (c.scenes.toList.flatMap fun s => regionCandidates s k).eraseDups
def devicesOf (c : SemCtx) (k : DeviceKind) : List DeviceId :=
  (c.scenes.toList.flatMap fun s => deviceCandidates s k).eraseDups
/-- At each instant, whether the region is of the kind: true, false, or unknown where the source
    cannot tell the kind. A quantifier conjoins it with its body, so a region the source cannot
    place in the kind makes the quantifier unknown, never decided by its absence. -/
def regionIsKind (c : SemCtx) (r : RegionId) (k : StructureKind) : Array R :=
  c.scenes.map fun s => R.ofOption (isKind s r k) (.absentAtom s!"st_{k}")
def deviceIsKind (c : SemCtx) (d : DeviceId) (k : DeviceKind) : Array R :=
  c.scenes.map fun s => R.ofOption (devKind s d k) (.absentAtom s!"dev_{k}")
/-- Every road user present in some scene of the trace. -/
def usersOf (c : SemCtx) : List TrackId :=
  (c.scenes.toList.flatMap (·.tracks)).eraseDups

/-- The kind a quantifier ranges over: a spelling of the ontology. A variable here is a concept's
    literal formal that no expansion filled. -/
private def regionKindOf (a : Arg) : Except UnknownReason StructureKind :=
  match a with
  | .lit s => match StructureKind.ofString s with | some k => .ok k | none => .error (.malformed s!"region kind {s}")
  | .var v => .error (.malformed s!"region kind `{v}` is a variable")
  | .nat _ => .error (.malformed "region kind")
private def deviceKindOf (a : Arg) : Except UnknownReason DeviceKind :=
  match a with
  | .lit s => match DeviceKind.ofString s with | some k => .ok k | none => .error (.malformed s!"device kind {s}")
  | .var v => .error (.malformed s!"device kind `{v}` is a variable")
  | .nat _ => .error (.malformed "device kind")

/-- φ where the precondition holds; undefined where it is false; the precondition's reasons where
    it is unknown. -/
private def definedWhenR (pre x : R) : R :=
  match pre.v with
  | .t => x
  | .f => R.u (.undefined "defined_when")
  | .u => ⟨.u, pre.why⟩

/-- A selection at one instant: the branch the guard picks; where the guard is unknown, the
    branches' common value, else unknown with the guard's reasons. -/
private def condAt (g : R) (a b : QR) : QR :=
  match g.v with
  | .t => a
  | .f => b
  | .u => match a, b with
    | .ok x, .ok y => if Q.eq x y then .ok x else .error (g.why.head?.getD (.malformed "cond"))
    | _, _ => .error (g.why.head?.getD (.malformed "cond"))

/-- An aggregate over the members present at one instant: unknown when a member's membership is
    unknown or a member's value is; `count` on an empty set is zero, the others are undefined. -/
private def aggregateAt (op : AggOp) (xs : List (R × QR)) : QR :=
  match xs.find? (fun (f, _) => f.v == .u) with
  | some (f, _) => .error (f.why.head?.getD (.malformed "aggregate"))
  | none =>
    let vals := xs.filterMap fun (f, q) => if f.v == .t then some q else none
    match op with
    | .count => .ok (Q.ofInt (Int.ofNat vals.length))
    | _ => do
      let qs ← vals.mapM fun q => q
      if qs.isEmpty then .error (.undefined "aggregate")
      else
        let sorted := qs.toArray.qsort (fun a b => Q.lt a b)
        match op with
        | .min => .ok sorted[0]!
        | .max => .ok sorted[sorted.size - 1]!
        | _ => .ok sorted[sorted.size / 2]!

/-- Membership of a road user in a legal aggregate at one scene: true when it carries an included
    class; unknown, with the observation's reason, when an included or unresolved class it might
    carry is unobserved; unknown as `aggregateUnresolved` when it carries a class the definition
    leaves unresolved; false otherwise. -/
def aggregateMembership (s : Scene) (t : TrackId) (a : LegalAggregate) : R :=
  let classes := fun (ids : List String) => ids.filterMap fun i => RoadUserClass.ofString (i.drop 3).toString
  match ru_aggregate s t (classes a.included) with
  | some true => R.t
  | none => R.u (.absentAtom "ru_aggregate")
  | some false =>
    match ru_aggregate s t (classes a.unresolved) with
    | some true => R.u (.aggregateUnresolved a.id)
    | some false => R.f
    | none => R.u (.absentAtom "ru_aggregate")

/-- Kleene aggregate at each instant over the evaluated members present in that scene. -/
private def perScene (c : SemCtx) (evaluated : List (Nat × Array R))
    (presentIn : Scene → Nat → Bool) (agg : List R → R) : Array R :=
  (Array.range c.n).map fun i =>
    let s := c.scenes[i]!
    agg (evaluated.filterMap fun (m, arr) => if presentIn s m then some arr[i]! else none)

mutual
  def evalTAll (c : SemCtx) : Term → Array QR
    | .lit v _ => Array.replicate c.n (.ok v)
    | .param p => Array.replicate c.n (match c.d.ρ.param p with | some v => .ok v | none => .error (.parameterMissing p))
    | .measure a args =>
      match resolveAll c.β args with
      | .error w => constE c.n w
      | .ok ds => c.scenes.map fun s => evalMeasure s a ds
    | .quantity concept args ps =>
      liftQ c.n do
        let vs ← constParams c ps
        Primitives.evalQ concept c.d (← resolveAll c.β args) vs
    | .distanceWhile subj φ =>
      match c.β.track subj with
      | none => constE c.n (.unboundVariable subj)
      | some x => Primitives.distanceWhile c.d x (evalAll c φ)
    | .sinceRise φ => sinceRiseAll c.d.times (evalAll c φ)
    | .aggregate op v φ t =>
      let members := (usersOf c).map fun u =>
        let c' := c.bindVar v (.track u)
        (u, evalAll c' φ, evalTAll c' t)
      (Array.range c.n).map fun i =>
        let s := c.scenes[i]!
        aggregateAt op (members.filterMap fun (u, fa, ta) => if s.tracks.contains u then some (fa[i]!, ta[i]!) else none)
    | .add a b' => qzip Q.add (evalTAll c a) (evalTAll c b')
    | .sub a b' => qzip Q.sub (evalTAll c a) (evalTAll c b')
    | .mul a b' => qzip Q.mul (evalTAll c a) (evalTAll c b')
    | .div a b' => Array.zipWith (fun x y => do
        let d ← y
        if Q.isZero d then .error (.divisionByZero "div") else pure (Q.div (← x) d)) (evalTAll c a) (evalTAll c b')
    | .neg a => (evalTAll c a).map (·.map Q.neg)
    | .abs a => (evalTAll c a).map (·.map Q.abs)
    | .cond φ a b' =>
      let g := evalAll c φ; let x := evalTAll c a; let y := evalTAll c b'
      (Array.range c.n).map fun i => condAt (g[i]?.getD (R.u .outOfRange)) (x[i]?.getD (.error .outOfRange)) (y[i]?.getD (.error .outOfRange))
  termination_by t => sizeOf t

  /-- Parameters of an atom or derived concept: constant terms, evaluated once. -/
  def constParams (c : SemCtx) : List Term → Except UnknownReason (List Q)
    | [] => .ok []
    | t :: rest => do
      let v ← constOf t (evalTAll c t)
      pure (v :: (← constParams c rest))
  termination_by ts => sizeOf ts

  def evalAll (c : SemCtx) : Formula → Array R
    | .tt => const c.n R.t
    | .ff => const c.n R.f
    | .atom name args ps =>
      liftA c.n do
        let vs ← constParams c ps
        let ds ← resolveAll c.β args
        if name == "ru_aggregate" then
          pure (match ds with
            | [.v t, .s id] =>
              match c.d.aggregateOverrides.find? (fun (x, a, _) => x == t && a == id) with
              | some (_, _, v) => const c.n (R.ofBool v)
              | none =>
                match c.d.ρ.aggregate id with
                | none => const c.n (R.u (.parameterMissing s!"aggregate:{id}"))
                | some a => c.scenes.map fun s => aggregateMembership s t a
            | _ => const c.n (R.u (.malformed "aggregate arguments")))
        else pure (c.scenes.map fun s => match evalAtomE s name ds vs with | .ok r => r | .error w => R.u w)
    | .cmp l op r => Array.zipWith (fun x y => match x, y with
        | .ok a, .ok b => R.ofBool (op.apply a b)
        | .error w, _ | _, .error w => R.u w) (evalTAll c l) (evalTAll c r)
    | .asm id => c.scenes.map fun s => R.ofOption (s.assumption id) (.assumptionMissing id)
    | .intent id who target =>
      match who, target with
      | .var a, .var b =>
        match c.β.lookup a, c.β.lookup b with
        | some (.track x), some (.region r) => c.scenes.map fun s => R.ofOption (s.intention id x r) (.intentionMissing id)
        | none, _ => constU c.n (.unboundVariable a)
        | _, none => constU c.n (.unboundVariable b)
        | _, _ => constU c.n (.malformed "intent: a track and a region expected")
      | _, _ => constU c.n (.malformed "intent: a track and a region expected")
    | .same a b =>
      match resolve c.β a, resolve c.β b with
      | .ok (.v i), .ok (.v j) => const c.n (R.ofBool (i == j))
      | .error w, _ | _, .error w => constU c.n w
      | _, _ => constU c.n (.malformed "same: entities expected")
    | .not φ => mapNot (evalAll c φ)
    | .and φ ψ => zipAnd (evalAll c φ) (evalAll c ψ)
    | .or φ ψ => zipOr (evalAll c φ) (evalAll c ψ)
    | .implies φ ψ => zipImplies (evalAll c φ) (evalAll c ψ)
    | .always φ => alwaysAll (evalAll c φ)
    | .eventually φ => eventuallyAll (evalAll c φ)
    | .until φ ψ => untilAll (evalAll c φ) (evalAll c ψ)
    | .since φ ψ => sinceAll (evalAll c φ) (evalAll c ψ)
    | .holdsFor m d subj φ =>
      liftA c.n do
        let x ← subjectFor c.β m subj
        let dv ← constOf d (evalTAll c d)
        pure (holdsForAll (Primitives.positions c.d m x) dv "holdsFor" (Primitives.missingPos m) (evalAll c φ))
    | .within m d subj φ =>
      liftA c.n do
        let x ← subjectFor c.β m subj
        let dv ← constOf d (evalTAll c d)
        pure (withinAll (Primitives.positions c.d m x) dv "within" (Primitives.missingPos m) (evalAll c φ))
    | .untilWithin m d subj φ ψ =>
      liftA c.n do
        let x ← subjectFor c.β m subj
        let dv ← constOf d (evalTAll c d)
        pure (untilWithinAll (Primitives.positions c.d m x) dv "untilWithin" (Primitives.missingPos m) (evalAll c φ) (evalAll c ψ))
    | .atLast m d subj ψ φ =>
      liftA c.n do
        let x ← subjectFor c.β m subj
        let dv ← constOf d (evalTAll c d)
        pure (atLastAll (Primitives.positions c.d m x) dv "atLast" (Primitives.missingPos m) (evalAll c ψ) (evalAll c φ))
    | .count edge sinceφ op k =>
      (countEdgesAll "count" (evalAll c edge) (evalAll c sinceφ)).map fun e => match e with
        | .error w => R.u w
        | .ok m => R.ofBool (op.apply (Q.ofInt (Int.ofNat m)) (Q.ofInt (Int.ofNat k)))
    | .rises φ => risesAll (evalAll c φ)
    | .definedWhen pre φ => Array.zipWith definedWhenR (evalAll c pre) (evalAll c φ)
    | .derived concept args ps =>
      liftA c.n do
        let vs ← constParams c ps
        Primitives.evalB concept c.d (← resolveAll c.β args) vs
    | .rule id map =>
      let arr := c.compose id map c.β false
      if arr.size = c.n then arr else constU c.n (.compositionUnknown id)
    | .ruleApplies id map =>
      let arr := c.compose id map c.β true
      if arr.size = c.n then arr else constU c.n (.compositionUnknown id)
    | .existsUser v φ =>
      perScene c ((usersOf c).map fun t => (t, evalAll (c.bindVar v (.track t)) φ))
        (fun s t => s.tracks.contains t) R.any
    | .forallUser v φ =>
      perScene c ((usersOf c).map fun t => (t, evalAll (c.bindVar v (.track t)) φ))
        (fun s t => s.tracks.contains t) R.all
    | .existsRegion k v φ =>
      match regionKindOf k with
      | .error w => constU c.n w
      | .ok kd => perScene c ((regionsOf c kd).map fun r =>
            (r, Array.zipWith R.and (regionIsKind c r kd) (evalAll (c.bindVar v (.region r)) φ)))
          (fun s r => (s.structure? r).isSome) R.any
    | .forallRegion k v φ =>
      match regionKindOf k with
      | .error w => constU c.n w
      | .ok kd => perScene c ((regionsOf c kd).map fun r =>
            (r, Array.zipWith R.implies (regionIsKind c r kd) (evalAll (c.bindVar v (.region r)) φ)))
          (fun s r => (s.structure? r).isSome) R.all
    | .existsDevice k v φ =>
      match deviceKindOf k with
      | .error w => constU c.n w
      | .ok kd => perScene c ((devicesOf c kd).map fun d =>
            (d, Array.zipWith R.and (deviceIsKind c d kd) (evalAll (c.bindVar v (.device d)) φ)))
          (fun s d => (s.device d).isSome) R.any
    | .forallDevice k v φ =>
      match deviceKindOf k with
      | .error w => constU c.n w
      | .ok kd => perScene c ((devicesOf c kd).map fun d =>
            (d, Array.zipWith R.implies (deviceIsKind c d kd) (evalAll (c.bindVar v (.device d)) φ)))
          (fun s d => (s.device d).isSome) R.all
  termination_by φ => sizeOf φ
end

/-- The value of a formula at instant `i`. -/
def eval (c : SemCtx) (i : Nat) (φ : Formula) : R := (evalAll c φ)[i]?.getD (R.u .outOfRange)
def evalTri (c : SemCtx) (i : Nat) (φ : Formula) : Tri := (eval c i φ).v

-- ---------------------------------------------------------------------------------------------
-- Unfolding lemmas: the connectives are the pointwise three-valued operations of Unknown.lean.
-- ---------------------------------------------------------------------------------------------
section Lemmas
variable (c : SemCtx) (φ ψ : Formula)

theorem evalAll_tt : evalAll c .tt = const c.n R.t := by rw [evalAll]
theorem evalAll_ff : evalAll c .ff = const c.n R.f := by rw [evalAll]
theorem evalAll_not : evalAll c (.not φ) = (evalAll c φ).map R.not := by rw [evalAll]; rfl
theorem evalAll_and : evalAll c (.and φ ψ) = Array.zipWith R.and (evalAll c φ) (evalAll c ψ) := by rw [evalAll]; rfl
theorem evalAll_or : evalAll c (.or φ ψ) = Array.zipWith R.or (evalAll c φ) (evalAll c ψ) := by rw [evalAll]; rfl
theorem evalAll_implies : evalAll c (.implies φ ψ) = Array.zipWith R.implies (evalAll c φ) (evalAll c ψ) := by rw [evalAll]; rfl
theorem evalAll_always : evalAll c (.always φ) = alwaysAll (evalAll c φ) := by rw [evalAll]
theorem evalAll_eventually : evalAll c (.eventually φ) = eventuallyAll (evalAll c φ) := by rw [evalAll]
theorem evalAll_until : evalAll c (.until φ ψ) = untilAll (evalAll c φ) (evalAll c ψ) := by rw [evalAll]
theorem evalAll_since : evalAll c (.since φ ψ) = sinceAll (evalAll c φ) (evalAll c ψ) := by rw [evalAll]
theorem evalAll_rule (id : String) (map : List (String × String)) (h : (c.compose id map c.β false).size = c.n) :
    evalAll c (.rule id map) = c.compose id map c.β false := by rw [evalAll]; simp [h]
theorem evalAll_ruleApplies (id : String) (map : List (String × String)) (h : (c.compose id map c.β true).size = c.n) :
    evalAll c (.ruleApplies id map) = c.compose id map c.β true := by rw [evalAll]; simp [h]

/-- Unknown is absorbing for `not`, pointwise. -/
theorem eval_not_u (i : Nat) (h : (eval c i φ).v = .u) (hi : i < (evalAll c φ).size) : (eval c i (.not φ)).v = .u := by
  unfold eval at *
  rw [evalAll_not, Array.getElem?_map]
  simp only [Array.getElem?_eq_getElem hi, Option.map_some, Option.getD_some, R.not_v] at *
  rw [h]; rfl
end Lemmas

end Semantics
end TrafficSpec
