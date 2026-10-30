/-
  TrafficSpec.Core.Runtime.Identity
  Which track continues which: the links a source claims (`Scene.links`, old ↦ new), accepted
  when the new track first appears after the old one was last seen, within the manifest's
  re-identification gap, and the canonical (root) identity each track has through them.

  It reads only the scenes, their track ids and the gap, so the admission of a trace and its
  grounding both use it.
-/
import TrafficSpec.Core.Foundations.Time
import TrafficSpec.Core.Vocab.World

namespace TrafficSpec
namespace Grounding

def firstSeen (τ : Array Scene) (t : TrackId) : Option Nat :=
  (List.range τ.size).find? fun i => τ[i]!.tracks.contains t
def lastSeen (τ : Array Scene) (t : TrackId) : Option Nat :=
  ((List.range τ.size).reverse).find? fun i => τ[i]!.tracks.contains t

/-- A link old ↦ new is accepted when `new` first appears after `old` was last seen, within `gap`. -/
def acceptedLinks (τ : Array Scene) (gap : Q) : List (TrackId × TrackId) :=
  (τ.toList.flatMap (·.links)).eraseDups.filter fun (old, new) =>
    match lastSeen τ old, firstSeen τ new with
    | some lo, some fn =>
      fn > lo && Q.le (Q.sub (Time.ofTimestamp τ[fn]!.t) (Time.ofTimestamp τ[lo]!.t)) gap
    | _, _ => false

/-- The canonical (root) track of every track, following accepted links backwards. -/
def canonMap (τ : Array Scene) (gap : Q) : List (TrackId × TrackId) :=
  let links := acceptedLinks τ gap
  let tracks := (τ.toList.flatMap (·.tracks)).eraseDups
  let rec root (t : TrackId) (fuel : Nat) : TrackId :=
    match fuel with
    | 0 => t
    | fuel + 1 =>
      match links.find? (·.2 == t) with
      | some (old, _) => root old fuel
      | none => t
  tracks.map fun t => (t, root t (links.length + 1))

def canon (cm : List (TrackId × TrackId)) (t : TrackId) : TrackId :=
  ((cm.find? (·.1 == t)).map (·.2)).getD t

end Grounding
end TrafficSpec
