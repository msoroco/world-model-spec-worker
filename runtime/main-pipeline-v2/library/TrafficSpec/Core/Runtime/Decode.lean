/-
  TrafficSpec.Core.Runtime.Decode
  Traces, readings and manifests from JSON: the adapter's output format, typed strictly. An absent
  or null key is `none`; a malformed value is a decode error, never `false`. This is the only
  place a string from outside becomes a typed value.

  Numbers decode exactly: a JSON number's mantissa and exponent become a rational, so a value
  written as `13.5` is 27/2 and not a float. Enumeration values are spelled as ATOMS.md spells them
  and decoded through the generated codecs.

  Trace document:
    { "scenes": [ { "t": <ms>, "subject": <track>?, "users": [...], "structures": [...],
                    "devices": [...], "occupancy_observed": true | [track...]?, "occupies": [[track, region]...]?,
                    "relations": [...]?, "env": {...}?, "assumptions": [[id, bool]...]?,
                    "links": [[old, new]...]? } ] }
  Field names follow the structures of World.lean in snake_case; see the decoders below.

  A formula, a term and an argument decode strictly from the JSON Export.lean writes: the
  decoder is that encoder's inverse, so a decoded formula exported again is the canonical form.
  `and` and `or` also read a list of more than two formulas, folded to the right
  (`[a, b, c]` is `a ∧ (b ∧ c)`); every other list form takes exactly its two elements.
-/
import Lean.Data.Json
import TrafficSpec.Core.Runtime.Manifest
import TrafficSpec.Core.Language.Rule

namespace TrafficSpec
namespace Decode
open Lean

abbrev D := Except String

def fail {α : Type} (path what : String) : D α := throw s!"{path}: {what}"

/-- The value under `k`, or none when absent or null. -/
def field? (j : Json) (k : String) : Option Json :=
  match j.getObjVal? k with
  | .ok .null => none
  | .ok v => some v
  | .error _ => none

/-- A JSON number as an exact rational. -/
def qOfNumber (n : JsonNumber) : Q :=
  Q.mk' n.mantissa (10 ^ n.exponent)

def num (path : String) (j : Json) : D Q :=
  match j with
  | .num n => pure (qOfNumber n)
  | _ => fail path "expected a number"
def nat (path : String) (j : Json) : D Nat :=
  match j.getNat? with | .ok n => pure n | .error _ => fail path "expected a natural"
def int (path : String) (j : Json) : D Int :=
  match j.getInt? with | .ok n => pure n | .error _ => fail path "expected an integer"
def bool (path : String) (j : Json) : D Bool :=
  match j with | .bool b => pure b | _ => fail path "expected a boolean"
def str (path : String) (j : Json) : D String :=
  match j with | .str s => pure s | _ => fail path "expected a string"
def arr (path : String) (j : Json) : D (List Json) :=
  match j with | .arr a => pure a.toList | _ => fail path "expected an array"
def vec (path : String) (j : Json) : D Vec := do
  match ← arr path j with
  | [x, y] => pure (← num (path ++ "[0]") x, ← num (path ++ "[1]") y)
  | _ => fail path "expected [x, y]"
def enum {α : Type} (ofString : String → Option α) (path : String) (j : Json) : D α := do
  let s ← str path j
  match ofString s with | some v => pure v | none => fail path s!"unknown value {s}"

/-- Optional field through a decoder. -/
def opt {α : Type} (j : Json) (path k : String) (dec : String → Json → D α) : D (Option α) :=
  match field? j k with
  | none => pure none
  | some v => (dec (path ++ "." ++ k) v).map some
def optList {α : Type} (j : Json) (path k : String) (dec : String → Json → D α) : D (Option (List α)) :=
  match field? j k with
  | none => pure none
  | some v => do
    let xs ← arr (path ++ "." ++ k) v
    ((xs.zip (List.range xs.length)).mapM fun (xi : Json × Nat) => dec s!"{path}.{k}[{xi.2}]" xi.1).map some
def list {α : Type} (j : Json) (path k : String) (dec : String → Json → D α) : D (List α) :=
  (optList j path k dec).map (·.getD [])
def req {α : Type} (j : Json) (path k : String) (dec : String → Json → D α) : D α :=
  match field? j k with
  | none => fail (path ++ "." ++ k) "required"
  | some v => dec (path ++ "." ++ k) v

def pair {α β : Type} (da : String → Json → D α) (db : String → Json → D β) (path : String) (j : Json) : D (α × β) := do
  match ← arr path j with
  | [a, b] => pure (← da (path ++ "[0]") a, ← db (path ++ "[1]") b)
  | _ => fail path "expected a pair"

-- ---------------------------------------------------------------------------------------------
-- World
-- ---------------------------------------------------------------------------------------------
def kin (path : String) (j : Json) : D Kin := do
  pure { position := ← opt j path "position" vec
         heading := ← opt j path "heading" vec
         velocity := ← opt j path "velocity" vec
         speed := ← opt j path "speed" num
         accelLongitudinal := ← opt j path "accel_longitudinal" num
         yawRate := ← opt j path "yaw_rate" num
         extent := ← opt j path "extent" fun p v => do
           match ← arr p v with
           | [l, w, h] => pure (← num p l, ← num p w, ← num p h)
           | _ => fail p "expected [half_length, half_width, half_height]"
         steerAngle := ← opt j path "steer_angle" num
         engineRunning := ← opt j path "engine_running" bool
         parkingBrake := ← opt j path "parking_brake" bool
         gear := ← opt j path "gear" int
         throttle := ← opt j path "throttle" num
         serviceBrake := ← opt j path "service_brake" num
         pathLength := ← opt j path "path_length" num }

def posture (path : String) (j : Json) : D Posture := do
  pure { onSeat := ← opt j path "on_seat" bool
         handsOnControls := ← opt j path "hands_on_controls" nat
         standingOnDeck := ← opt j path "standing_on_deck" bool
         holdingAnotherVehicle := ← opt j path "holding_another_vehicle" bool
         stunt := ← opt j path "stunt" bool }

def warningLamp (path : String) (j : Json) : D WarningLamp := do
  pure { colour := ← req j path "colour" (enum LampColour.ofString)
         mode := ← req j path "mode" (enum LampMode.ofString)
         facing := ← req j path "facing" (enum Facing.ofString) }

def signals (path : String) (j : Json) : D Signals := do
  pure { turnIndicator := ← opt j path "turn_indicator" (enum TurnIndicatorState.ofString)
         brakeLamp := ← opt j path "brake_lamp" bool
         hazard := ← opt j path "hazard" bool
         headlamp := ← opt j path "headlamp" (enum HeadlampState.ofString)
         positionLamp := ← opt j path "position_lamp" bool
         reverseLamp := ← opt j path "reverse_lamp" bool
         warningLamps := ← optList j path "warning_lamps" warningLamp
         siren := ← opt j path "siren" bool
         horn := ← opt j path "horn" bool
         handSignal := ← opt j path "hand_signal" (enum HandSignal.ofString)
         doorsOpen := ← optList j path "doors_open" (enum DoorSide.ofString)
         compressionBrake := ← opt j path "compression_brake" bool }

def roadUser (path : String) (j : Json) : D RoadUser := do
  pure { track := ← req j path "track" nat
         classes := ← optList j path "classes" (enum RoadUserClass.ofString)
         unobservedClasses := ← list j path "unobserved_classes" (enum RoadUserClass.ofString)
         emergencyKind := ← opt j path "emergency_kind" (enum EmergencyKind.ofString)
         officialKind := ← opt j path "official_kind" (enum OfficialKind.ofString)
         eBikeClass := ← opt j path "e_bike_class" nat
         occupants := ← opt j path "occupants" nat
         posture := (← opt j path "posture" posture).getD {}
         kin := (← opt j path "kin" kin).getD {}
         sig := (← opt j path "sig" signals).getD {}
         sightAlongWay := ← optList j path "sight_along_way" (pair nat num) }

def marking (path : String) (j : Json) : D (MarkingType × MarkingColour) :=
  pair (enum MarkingType.ofString) (enum MarkingColour.ofString) path j

def laneInfo (path : String) (j : Json) : D LaneInfo := do
  pure { direction := ← opt j path "direction" vec
         leftNeighbour := ← opt j path "left" nat
         rightNeighbour := ← opt j path "right" nat
         ordinalFromLeft := ← opt j path "ordinal" nat
         countInDirection := ← opt j path "count" nat
         leadsTo := ← optList j path "leads_to" nat
         entersIntersection := ← opt j path "enters_intersection" nat
         markingLeft := ← opt j path "marking_left" marking
         markingRight := ← opt j path "marking_right" marking
         width := ← opt j path "width" num }

def structure' (path : String) (j : Json) : D Structure := do
  pure { id := ← req j path "id" nat
         kind := ← req j path "kind" (enum StructureKind.ofString)
         unobservedKinds := ← list j path "unobserved_kinds" (enum StructureKind.ofString)
         position := ← opt j path "position" vec
         boundary := ← optList j path "boundary" vec
         lane := ← opt j path "lane" laneInfo
         paved := ← opt j path "paved" bool
         opening := ← opt j path "opening" bool
         marked := ← opt j path "marked" bool
         curvature := ← opt j path "curvature" num
         grade := ← opt j path "grade" num
         sightDistance := ← opt j path "sight_distance" num
         ways := ← optList j path "ways" nat
         reservedClass := ← opt j path "reserved_class" (enum ReservedClass.ofString)
         turnSide := ← opt j path "turn_side" (enum TurnSide.ofString)
         parkingAngle := ← opt j path "parking_angle" num
         designation := ← opt j path "designation" (enum ParkingDesignation.ofString)
         curbKind := ← opt j path "curb_kind" (enum CurbZoneKind.ofString)
         curbColour := ← opt j path "curb_colour" (enum CurbColour.ofString)
         obstructionKind := ← opt j path "obstruction_kind" (enum ObstructionKind.ofString) }

def timeWindow (path : String) (j : Json) : D TimeWindow := do
  pure { weekdays := ← list j path "weekdays" nat
         calendarClass := ← opt j path "calendar_class" str
         startMinute := (← opt j path "start_minute" nat).getD 0
         endMinute := (← opt j path "end_minute" nat).getD 1440 }

def conditions (path : String) (j : Json) : D Conditions := do
  pure { windows := ← list j path "windows" timeWindow
         minOccupancy := ← opt j path "min_occupancy" nat
         durationLimit := ← opt j path "duration_limit" num
         vehicleClass := ← opt j path "vehicle_class" (enum RoadUserClass.ofString)
         whenChildrenPresent := (← opt j path "when_children_present" bool).getD false }

def device (path : String) (j : Json) : D Device := do
  pure { id := ← req j path "id" nat
         kind := ← req j path "kind" (enum DeviceKind.ofString)
         unobservedKinds := ← list j path "unobserved_kinds" (enum DeviceKind.ofString)
         position := ← opt j path "position" vec
         governs := ← list j path "governs" nat
         onTrack := ← opt j path "on_track" nat
         indications := ← optList j path "indications" (enum SignalIndication.ofString)
         uncovered := ← opt j path "uncovered" bool
         inoperative := ← opt j path "inoperative" bool
         pedState := ← opt j path "ped_state" (enum PedSignalState.ofString)
         countdown := ← opt j path "countdown" bool
         laneControl := ← opt j path "lane_control" (enum LaneControlState.ofString)
         flashing := ← opt j path "flashing" bool
         active := ← opt j path "active" bool
         speedValue := ← opt j path "speed_value" num
         speedKind := ← opt j path "speed_kind" (enum SpeedSignKind.ofString)
         code := ← opt j path "code" (enum SignCode.ofString)
         zoneKind := ← opt j path "zone_kind" (enum ZoneKind.ofString)
         isEnd := ← opt j path "is_end" bool
         conditions := ← opt j path "conditions" conditions
         railLights := ← opt j path "rail_lights" (enum RailLights.ofString)
         gate := ← opt j path "gate" (enum GateState.ofString)
         bell := ← opt j path "bell" bool
         humanRole := ← opt j path "human_role" (enum HumanRole.ofString)
         humanIndication := ← opt j path "human_indication" (enum HumanIndication.ofString)
         redFlashing := ← opt j path "red_flashing" bool
         amberFlashing := ← opt j path "amber_flashing" bool
         stopArm := ← opt j path "stop_arm" bool }

def civilTime (path : String) (j : Json) : D CivilTime := do
  pure { year := ← req j path "year" nat
         month := ← req j path "month" nat
         day := ← req j path "day" nat
         weekday := ← req j path "weekday" nat
         minuteOfDay := ← req j path "minute_of_day" nat }

def env (path : String) (j : Json) : D Env := do
  pure { darkness := ← opt j path "darkness" bool
         precipitation := ← opt j path "precipitation" bool
         wetRoad := ← opt j path "wet_road" bool
         iceOrSnow := ← opt j path "ice_or_snow" bool
         visibility := ← opt j path "visibility" num
         civilTime := ← opt j path "civil_time" civilTime }

def relation (path : String) (j : Json) : D MeasuredRelation := do
  pure { a := ← req j path "a" nat
         b := ← req j path "b" nat
         centreDistance := ← opt j path "centre_distance" num
         surfaceGap := ← opt j path "surface_gap" (pair num num)
         aAheadOfB := ← opt j path "a_ahead_of_b" bool
         longitudinalOverlap := ← opt j path "longitudinal_overlap" num
         oncoming := ← opt j path "oncoming" bool
         sameDirection := ← opt j path "same_direction" bool
         bearing := ← opt j path "bearing" vec
         contact := ← opt j path "contact" bool
         visible := ← opt j path "visible" bool }

def scene (path : String) (j : Json) : D Scene := do
  let users ← list j path "users" roadUser
  pure { t := ← req j path "t" int
         subject := ← opt j path "subject" nat
         users := users
         structures := ← list j path "structures" structure'
         devices := ← list j path "devices" device
         occupancyObserved := ← (do
           match field? j "occupancy_observed" with
           | none => pure []
           | some (.bool true) => pure (users.map (·.track))
           | some (.bool false) => pure []
           | some v => arr (path ++ ".occupancy_observed") v >>= fun xs => xs.mapM (nat (path ++ ".occupancy_observed")))
         occupies := ← list j path "occupies" (pair nat nat)
         relations := ← list j path "relations" relation
         env := (← opt j path "env" env).getD {}
         assumptions := ← list j path "assumptions" (pair str bool)
         links := ← list j path "links" (pair nat nat) }

def trace (j : Json) : D Trace := do
  let τ ← list j "trace" "scenes" scene
  if τ.isEmpty then fail "trace.scenes" "empty"
  else if !Trace.monotone τ then fail "trace.scenes" "timestamps not strictly increasing"
  else pure τ

-- ---------------------------------------------------------------------------------------------
-- Reading and manifest
-- ---------------------------------------------------------------------------------------------
/-- A unit as a reading spells it, with the factor that takes a value in it to the Core unit
    (metres, seconds, m/s, m/s², degrees). A reading may state a distance in feet or a speed in
    miles per hour; the rule sees the Core unit. -/
def unit (path : String) (j : Json) : D (PUnit' × Q) := do
  match ← str path j with
  | "m" | "metre" => pure (.metre, Q.ofInt 1)
  | "ft" | "foot" | "feet" => pure (.metre, Units.feet 1)
  | "in" | "inch" | "inches" => pure (.metre, Units.inches 1)
  | "yd" | "yard" => pure (.metre, Units.yards 1)
  | "mi" | "mile" | "miles" => pure (.metre, Units.miles 1)
  | "km" => pure (.metre, Units.kilometres 1)
  | "s" | "second" | "seconds" => pure (.second, Q.ofInt 1)
  | "ms" => pure (.second, Units.milliseconds 1)
  | "min" | "minute" | "minutes" => pure (.second, Units.minutes 1)
  | "h" | "hour" | "hours" => pure (.second, Units.hours 1)
  | "m/s" | "metre_per_second" => pure (.metrePerSecond, Q.ofInt 1)
  | "mph" | "mi/h" => pure (.metrePerSecond, Units.mph 1)
  | "km/h" | "kph" => pure (.metrePerSecond, Units.kmh 1)
  | "m/s2" | "m/s^2" | "metre_per_second_sq" => pure (.metrePerSecondSq, Q.ofInt 1)
  | "deg" | "degree" | "degrees" => pure (.degree, Q.ofInt 1)
  | "deg/s" | "degree_per_second" => pure (.degreePerSecond, Q.ofInt 1)
  | "1/m" | "per_metre" => pure (.perMetre, Q.ofInt 1)
  | "ratio" => pure (.ratio, Q.ofInt 1)
  | "count" => pure (.count, Q.ofInt 1)
  | s => fail path s!"unknown unit {s}"

def paramValue (path : String) (j : Json) : D ParamValue := do
  let (u, k) ← req j path "unit" unit
  pure { name := ← req j path "name" str, value := Q.mul (← req j path "value" num) k, unit := u }
def aggregate (path : String) (j : Json) : D LegalAggregate := do
  pure { id := ← req j path "id" str
         included := ← list j path "included" str
         unresolved := ← list j path "unresolved" str }
def reading (j : Json) : D Reading := do
  pure { params := ← list j "reading" "params" paramValue
         aggregates := ← list j "reading" "aggregates" aggregate }

def capability (path : String) (j : Json) : D Capability := do
  match ← str path j with
  | "exact" => pure .exact
  | "absent" => pure .absent
  | "subject" => pure .subject
  | s => if s.startsWith "estimate:" then pure (.estimate ((s.drop 9).toString))
         else fail path s!"unknown capability {s}"
/-- `{ "source": ..., "reid_gap": <seconds>?, "atoms": { "<atom id>": "exact"|"estimate:<class>"|"absent"|"subject", ... } }` -/
def manifest (j : Json) : D Manifest := do
  let atoms ← match field? j "atoms" with
    | some (.obj kvs) => kvs.toArray.toList.mapM fun (k, v) => do pure (k, ← capability s!"manifest.atoms.{k}" v)
    | some _ => fail "manifest.atoms" "expected an object"
    | none => fail "manifest.atoms" "required"
  pure { source := ← req j "manifest" "source" str
         entries := atoms
         reidGap := (← opt j "manifest" "reid_gap" num).getD Q.zero }

-- ---------------------------------------------------------------------------------------------
-- Formulas: the inverse of Export's encoders, strict. An object must carry exactly the keys of one
-- constructor; a missing or extra key, a wrong array length, a null, a malformed rational or a zero
-- denominator is an error, never a default.
-- ---------------------------------------------------------------------------------------------
/-- The keys of a JSON object. -/
def keysOf (path : String) (j : Json) : D (List String) :=
  match j with
  | .obj kvs => pure (kvs.toArray.toList.map (·.1))
  | _ => fail path "expected an object"

/-- The value under `k`: present and not null. -/
def need (path : String) (j : Json) (k : String) : D Json :=
  match j.getObjVal? k with
  | .ok .null => fail (path ++ "." ++ k) "unexpected null"
  | .ok v => pure v
  | .error _ => fail (path ++ "." ++ k) "required"

/-- Exactly `n` elements, each decoded. -/
def exactly {α : Type} (n : Nat) (dec : String → Json → D α) (path : String) (j : Json) : D (List α) := do
  let xs ← arr path j
  if xs.length != n then fail path s!"expected {n} elements, found {xs.length}"
  else (xs.zip (List.range xs.length)).mapM fun (x, i) => dec s!"{path}[{i}]" x

def elems {α : Type} (dec : String → Json → D α) (path : String) (j : Json) : D (List α) := do
  let xs ← arr path j
  (xs.zip (List.range xs.length)).mapM fun (x, i) => dec s!"{path}[{i}]" x

def strictNat (path : String) (j : Json) : D Nat :=
  match j with
  | .num n => if n.exponent == 0 && n.mantissa ≥ 0 then pure n.mantissa.toNat else fail path "expected a natural"
  | _ => fail path "expected a natural"
def strictInt (path : String) (j : Json) : D Int :=
  match j with
  | .num n => if n.exponent == 0 then pure n.mantissa else fail path "expected an integer"
  | _ => fail path "expected an integer"

def rational (path : String) (j : Json) : D Q := do
  let ks ← keysOf path j
  if !(ks.length == 2 && ks.contains "num" && ks.contains "den") then fail path "a rational is {\"num\", \"den\"}"
  else
    let n ← strictInt (path ++ ".num") (← need path j "num")
    let d ← strictNat (path ++ ".den") (← need path j "den")
    if d == 0 then fail (path ++ ".den") "zero denominator" else pure (Q.mk' n d)

def cmpOp (path : String) (j : Json) : D CmpOp := do
  match ← str path j with
  | "lt" => pure .lt | "le" => pure .le | "eq" => pure .eq | "ge" => pure .ge | "gt" => pure .gt
  | s => fail path s!"unknown comparison {s}"
def measureOf (path : String) (j : Json) : D Measure := do
  match ← str path j with
  | "time" => pure .time | "path" => pure .path
  | s => fail path s!"unknown window measure {s}"
def literalUnit (path : String) (j : Json) : D PUnit' := do
  match ← str path j with
  | "metre" => pure .metre | "second" => pure .second | "metre_per_second" => pure .metrePerSecond
  | "metre_per_second_sq" => pure .metrePerSecondSq | "degree" => pure .degree
  | "degree_per_second" => pure .degreePerSecond | "per_metre" => pure .perMetre | "ratio" => pure .ratio
  | "count" => pure .count
  | s => fail path s!"unknown unit {s}"
def aggOp (path : String) (j : Json) : D AggOp := do
  match ← str path j with
  | "min" => pure .min | "max" => pure .max | "median" => pure .median | "count" => pure .count
  | s => fail path s!"unknown aggregate {s}"

def arg (path : String) (j : Json) : D Arg := do
  match ← keysOf path j with
  | ["var"] => return .var (← need path j "var" >>= str (path ++ ".var"))
  | ["lit"] => return .lit (← need path j "lit" >>= str (path ++ ".lit"))
  | ["nat"] => return .nat (← need path j "nat" >>= strictNat (path ++ ".nat"))
  | ks => fail path s!"an argument is one of var, lit, nat; found keys {ks}"

/-- The key set of an object is exactly `want`. -/
private def keyed (ks want : List String) : Bool := ks.length == want.length && want.all ks.contains

/-- The two elements of a decoded pair. -/
def pair2 {α : Type} (path : String) (xs : List α) : D (α × α) :=
  match xs with
  | [a, b] => pure (a, b)
  | _ => fail path "expected two elements"

/-- `x₁ ∘ (x₂ ∘ (… ∘ xₙ))`: a list of operands joined to the right by `f`. -/
def joinRight (f : Formula → Formula → Formula) : Formula → List Formula → Formula
  | a, [] => a
  | a, b :: rest => f a (joinRight f b rest)

/-- An object of strings, as pairs. -/
def strMap (path : String) (j : Json) : D (List (String × String)) :=
  match j with
  | .obj kvs => kvs.toArray.toList.mapM fun (k, v) => do pure (k, ← str (path ++ "." ++ k) v)
  | _ => fail path "expected an object"

mutual
  partial def term (path : String) (j : Json) : D Term := do
    let ks ← keysOf path j
    let at_ := fun (k : String) => path ++ "." ++ k
    let sub := fun (k : String) => need path j k >>= term (at_ k)
    let two := fun (k : String) => need path j k >>= exactly 2 term (at_ k) >>= fun xs => pair2 (at_ k) xs
    if keyed ks ["lit", "unit"] then
      return .lit (← need path j "lit" >>= rational (at_ "lit")) (← need path j "unit" >>= literalUnit (at_ "unit"))
    if keyed ks ["param"] then return .param (← need path j "param" >>= str (at_ "param"))
    if keyed ks ["measure", "args"] then
      return .measure (← need path j "measure" >>= str (at_ "measure")) (← need path j "args" >>= elems arg (at_ "args"))
    if keyed ks ["quantity", "args", "params"] then
      return .quantity (← need path j "quantity" >>= str (at_ "quantity")) (← need path j "args" >>= elems arg (at_ "args"))
        (← need path j "params" >>= elems term (at_ "params"))
    if keyed ks ["distance_while", "holds"] then
      return .distanceWhile (← need path j "distance_while" >>= str (at_ "distance_while")) (← need path j "holds" >>= formula (at_ "holds"))
    if keyed ks ["since_rise"] then return .sinceRise (← need path j "since_rise" >>= formula (at_ "since_rise"))
    if keyed ks ["aggregate", "var", "where", "of"] then
      return .aggregate (← need path j "aggregate" >>= aggOp (at_ "aggregate")) (← need path j "var" >>= str (at_ "var"))
        (← need path j "where" >>= formula (at_ "where")) (← sub "of")
    if keyed ks ["add"] then let ab ← two "add"; return .add ab.1 ab.2
    if keyed ks ["sub"] then let ab ← two "sub"; return .sub ab.1 ab.2
    if keyed ks ["mul"] then let ab ← two "mul"; return .mul ab.1 ab.2
    if keyed ks ["div"] then let ab ← two "div"; return .div ab.1 ab.2
    if keyed ks ["neg"] then return .neg (← sub "neg")
    if keyed ks ["abs"] then return .abs (← sub "abs")
    if keyed ks ["cond", "then", "else"] then
      return .cond (← need path j "cond" >>= formula (at_ "cond")) (← sub "then") (← sub "else")
    fail path s!"no term has exactly the keys {ks}"

  partial def formula (path : String) (j : Json) : D Formula := do
    if j == Json.str "tt" then return .tt
    if j == Json.str "ff" then return .ff
    let ks ← keysOf path j
    let at_ := fun (k : String) => path ++ "." ++ k
    let sub := fun (k : String) => need path j k >>= formula (at_ k)
    let two := fun (k : String) => need path j k >>= exactly 2 formula (at_ k) >>= fun xs => pair2 (at_ k) xs
    let many := fun (k : String) => do
      let xs ← need path j k >>= elems formula (at_ k)
      match xs with
      | a :: b :: rest => pure (a, b :: rest)
      | _ => fail (at_ k) s!"expected at least 2 elements, found {xs.length}"
    let s := fun (k : String) => need path j k >>= str (at_ k)
    let len := fun (_ : Unit) => need path j "length" >>= term (at_ "length")
    let kind := fun (k : String) => need path j k >>= arg (at_ k)
    let args := fun (_ : Unit) => need path j "args" >>= elems arg (at_ "args")
    let params := fun (_ : Unit) => need path j "params" >>= elems term (at_ "params")
    let mapOf := fun (k : String) => need path j k >>= strMap (at_ k)
    let win := fun (k : String) => need path j k >>= measureOf (at_ k)
    if keyed ks ["atom", "args", "params"] then return .atom (← s "atom") (← args ()) (← params ())
    if keyed ks ["cmp", "lhs", "rhs"] then
      return .cmp (← need path j "lhs" >>= term (at_ "lhs")) (← need path j "cmp" >>= cmpOp (at_ "cmp")) (← need path j "rhs" >>= term (at_ "rhs"))
    if keyed ks ["asm"] then return .asm (← s "asm")
    if keyed ks ["same"] then
      let ab ← need path j "same" >>= exactly 2 arg (at_ "same") >>= pair2 (at_ "same")
      return .same ab.1 ab.2
    if keyed ks ["not"] then return .not (← sub "not")
    if keyed ks ["and"] then let xs ← many "and"; return joinRight .and xs.1 xs.2
    if keyed ks ["or"] then let xs ← many "or"; return joinRight .or xs.1 xs.2
    if keyed ks ["implies"] then let ab ← two "implies"; return .implies ab.1 ab.2
    if keyed ks ["always"] then return .always (← sub "always")
    if keyed ks ["eventually"] then return .eventually (← sub "eventually")
    if keyed ks ["until"] then let ab ← two "until"; return .until ab.1 ab.2
    if keyed ks ["since"] then let ab ← two "since"; return .since ab.1 ab.2
    if keyed ks ["holds_for", "length", "subject", "body"] then
      return .holdsFor (← win "holds_for") (← len ()) (← s "subject") (← sub "body")
    if keyed ks ["within", "length", "subject", "body"] then
      return .within (← win "within") (← len ()) (← s "subject") (← sub "body")
    if keyed ks ["until_within", "length", "subject", "hold", "reach"] then
      return .untilWithin (← win "until_within") (← len ()) (← s "subject") (← sub "hold") (← sub "reach")
    if keyed ks ["at_last", "length", "subject", "when", "body"] then
      return .atLast (← win "at_last") (← len ()) (← s "subject") (← sub "when") (← sub "body")
    if keyed ks ["count", "since", "op", "n"] then
      return .count (← sub "count") (← sub "since") (← need path j "op" >>= cmpOp (at_ "op")) (← need path j "n" >>= strictNat (at_ "n"))
    if keyed ks ["rises"] then return .rises (← sub "rises")
    if keyed ks ["defined_when", "body"] then return .definedWhen (← sub "defined_when") (← sub "body")
    if keyed ks ["derived", "args", "params"] then return .derived (← s "derived") (← args ()) (← params ())
    if keyed ks ["rule", "map"] then return .rule (← s "rule") (← mapOf "map")
    if keyed ks ["rule_applies", "map"] then return .ruleApplies (← s "rule_applies") (← mapOf "map")
    if keyed ks ["exists_user", "body"] then return .existsUser (← s "exists_user") (← sub "body")
    if keyed ks ["forall_user", "body"] then return .forallUser (← s "forall_user") (← sub "body")
    if keyed ks ["exists_region", "var", "body"] then return .existsRegion (← kind "exists_region") (← s "var") (← sub "body")
    if keyed ks ["forall_region", "var", "body"] then return .forallRegion (← kind "forall_region") (← s "var") (← sub "body")
    if keyed ks ["exists_device", "var", "body"] then return .existsDevice (← kind "exists_device") (← s "var") (← sub "body")
    if keyed ks ["forall_device", "var", "body"] then return .forallDevice (← kind "forall_device") (← s "var") (← sub "body")
    fail path s!"no formula has exactly the keys {ks}"
end

/-- A case's entities: `{name: {"kind": "track" | "region" | "device", "id": n}}`. -/
def entities (path : String) (j : Json) : D (List (String × Val)) := do
  match j with
  | .obj kvs => kvs.toArray.toList.mapM fun (name, v) => do
      let p := path ++ "." ++ name
      let ks ← keysOf p v
      if !keyed ks ["kind", "id"] then fail p "an entity is {\"kind\", \"id\"}"
      else
        let id ← strictNat (p ++ ".id") (← need p v "id")
        match ← str (p ++ ".kind") (← need p v "kind") with
        | "track" => pure (name, .track id)
        | "region" => pure (name, .region id)
        | "device" => pure (name, .device id)
        | k => fail (p ++ ".kind") s!"unknown entity kind {k}"
  | _ => fail path "expected an object"

def parse {α : Type} (dec : Json → D α) (text : String) : D α := do
  dec (← Json.parse text)

end Decode
end TrafficSpec
