/-
  TrafficSpec.Core.Foundations.Handles
  The identifiers by which a scene, a formula and a reason for unknown name a road user's track,
  a region, a device, an assumption, a declared intention and a declared fact.
-/
namespace TrafficSpec

abbrev TrackId := Nat
abbrev RegionId := Nat
abbrev DeviceId := Nat
abbrev AsmId := String
abbrev IntId := String
abbrev FactId := String

end TrafficSpec
