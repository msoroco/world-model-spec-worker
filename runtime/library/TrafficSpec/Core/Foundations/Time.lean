/-
  TrafficSpec.Core.Foundations.Time
  Metric windows without a frame rate.

  Every observation carries a timestamp; a body also carries the path length it has travelled.
  A window is measured in one of the two: a duration of time, or a length of path travelled.
  Semantics are defined on the OBSERVED instants only; the one interpolation-free precondition is
  adequacy: a window of length d over a span is adequate when consecutive observations in the
  span are at most d/2 apart. An inadequate span yields `unknown`
  with the reason `samplingGap`, never a verdict invented between frames.

  Windows are computed for every instant of a trace at once: positions are monotone, so the
  window boundary moves one way and a two-pointer sweep with a range-maximum table over the gaps
  gives every window in O(n log n).

  There is no `next`, no rate and no frame count anywhere in the library.
-/
import TrafficSpec.Core.Foundations.Units

namespace TrafficSpec

/-- Milliseconds, monotone within a trace. -/
abbrev Timestamp := Int

/-- Which quantity a window is measured in. -/
inductive Measure
  | time | path
  deriving DecidableEq, Repr, Inhabited

/-- A window: a non-negative length in seconds (time) or metres (path). -/
structure Duration where
  measure : Measure
  length : Q
  deriving Repr

namespace Duration
def time (q : Q) : Duration := ⟨.time, q⟩
def path (q : Q) : Duration := ⟨.path, q⟩
end Duration

namespace Time

def ofTimestamp (t : Timestamp) : Q := Units.milliseconds t

/-- Consecutive gaps of a sorted list of positions (time or path). -/
def gaps : List Q → List Q
  | a :: b :: rest => Q.sub b a :: gaps (b :: rest)
  | _ => []

/-- Every consecutive gap in the span is at most `d / 2`. Vacuously true on one observation. -/
def adequate (d : Q) (span : List Q) : Bool :=
  (gaps span).all (fun g => Q.le g (Q.half d))

-- ---------------------------------------------------------------------------------------------
-- Range maximum over the gaps between consecutive observed positions (sparse table).
-- ---------------------------------------------------------------------------------------------
/-- `gapMax.query lo hi` is the largest gap `pos[k] - pos[k-1]` for `lo < k ≤ hi`, given that
    every position in `[lo, hi]` is observed. -/
structure GapMax where
  table : Array (Array Q)      -- table[k][j] = max of gaps[j .. j + 2^k)
  gapsArr : Array Q            -- gapsArr[k] = pos[k+1] - pos[k], or zero where a side is missing

namespace GapMax
def log2 (n : Nat) : Nat := if n ≤ 1 then 0 else 1 + log2 (n / 2)

def build (pos : Array (Option Q)) : GapMax :=
  let n := pos.size
  let g : Array Q := (Array.range (n - 1)).map fun k =>
    match pos[k]?, pos[k + 1]? with
    | some (some a), some (some b) => Q.sub b a
    | _, _ => Q.zero
  let levels := log2 (max 1 g.size) + 1
  let table := (List.range levels).foldl (fun (acc : Array (Array Q)) k =>
    if k == 0 then #[g]
    else
      let prev := acc[k - 1]!
      let half := 2 ^ (k - 1)
      let row := (Array.range (prev.size)).map fun j =>
        if j + half < prev.size then Q.max prev[j]! prev[j + half]! else prev[j]!
      acc.push row) #[]
  ⟨table, g⟩

/-- Largest gap among the observations `lo, …, hi` (`lo < hi`); zero for a single observation. -/
def query (m : GapMax) (lo hi : Nat) : Q :=
  if hi ≤ lo then Q.zero
  else
    let len := hi - lo                  -- gaps indices lo … hi-1
    let k := log2 len
    let row := m.table[k]!
    Q.max row[lo]! row[hi - 2 ^ k]!
end GapMax

-- ---------------------------------------------------------------------------------------------
-- Windows for every instant
-- ---------------------------------------------------------------------------------------------
/-- The window behind an instant: the oldest in-window index, whether the trace reaches back past
    the window (an observation precedes it, or the oldest is exactly `d` behind), and whether the
    observations inside are at most `d/2` apart. -/
structure Back where
  j0 : Nat
  covered : Bool
  adequate : Bool
  deriving Repr

/-- The window ahead of an instant, symmetrically. -/
structure Fwd where
  jl : Nat
  covered : Bool
  adequate : Bool
  deriving Repr

/-- Index of the earliest missing position at or after `i`, per instant (size n+1; `n` when none). -/
private def nextMissing (pos : Array (Option Q)) : Array Nat :=
  let n := pos.size
  (List.range n).reverse.foldl (fun (acc : Array Nat) i =>
    let v := if (pos[i]?).getD none |>.isNone then i else acc[i + 1]!
    acc.set! i v) (Array.replicate (n + 1) n)

/-- Every back window of length `d`. `none` where the instant's own position or a position inside
    its window is missing (a gap the adequacy test could not see). Covered means an observed
    position precedes the window, or its oldest observation is exactly `d` behind. -/
def backWindows (pos : Array (Option Q)) (d : Q) : Array (Option Back) :=
  let n := pos.size
  let gm := GapMax.build pos
  let nm := nextMissing pos
  -- observedBefore[j]: some position at an index < j is observed
  let observedBefore : Array Bool := (List.range n).foldl (fun (acc : Array Bool) j =>
    acc.push (acc[j]! || (pos[j]!).isSome)) #[false]
  let step (st : Nat × Array (Option Back)) (i : Nat) : Nat × Array (Option Back) :=
    let (j0, out) := st
    match pos[i]! with
    | none => (j0, out.push none)
    | some pi =>
      -- advance the oldest index while its position is observed and more than d behind
      let rec adv (j : Nat) (fuel : Nat) : Nat :=
        match fuel with
        | 0 => j
        | fuel + 1 =>
          if j ≥ i then j
          else match pos[j]! with
            | some pj => if Q.gt (Q.sub pi pj) d then adv (j + 1) fuel else j
            | none => adv (j + 1) fuel
      let j0' := adv j0 (i + 1 - j0)
      -- a missing position between j0' and i makes the window unknown
      if nm[j0']! ≤ i then (j0', out.push none)
      else
        let p0 := (pos[j0']!).getD pi
        let covered := observedBefore[j0']! || Q.ge (Q.sub pi p0) d
        let adequate := Q.le (gm.query j0' i) (Q.half d)
        (j0', out.push (some ⟨j0', covered, adequate⟩))
  ((List.range n).foldl step (0, Array.mkEmpty n)).2

/-- Every forward window of length `d`, by the same sweep run backwards. -/
def forwardWindows (pos : Array (Option Q)) (d : Q) : Array (Option Fwd) :=
  let n := pos.size
  let gm := GapMax.build pos
  -- observedFrom[j]: some position at an index ≥ j is observed (size n+1; false at n)
  let observedFrom : Array Bool := (List.range n).reverse.foldl (fun (acc : Array Bool) j =>
    acc.set! j (acc[j + 1]! || (pos[j]!).isSome)) (Array.replicate (n + 1) false)
  -- index of the latest missing position at or before i (n when none), per instant
  let lastMissing : Array Nat := (List.range n).foldl (fun (acc : Array Nat) i =>
    let v := if (pos[i]!).isNone then i else (if i = 0 then n else acc[i - 1]!)
    acc.push v) (Array.mkEmpty n)
  let step (st : Nat × List (Option Fwd)) (i : Nat) : Nat × List (Option Fwd) :=
    let (jl, out) := st
    match pos[i]! with
    | none => (jl, none :: out)
    | some pi =>
      let rec adv (j : Nat) (fuel : Nat) : Nat :=
        match fuel with
        | 0 => j
        | fuel + 1 =>
          if j ≤ i then j
          else match pos[j]! with
            | some pj => if Q.gt (Q.sub pj pi) d then adv (j - 1) fuel else j
            | none => adv (j - 1) fuel
      let jl' := adv jl (jl + 1 - i)
      let lm := lastMissing[jl']!
      if lm ≠ n && lm ≥ i then (jl', none :: out)
      else
        let pl := (pos[jl']!).getD pi
        let covered := observedFrom[jl' + 1]! || Q.ge (Q.sub pl pi) d
        let adequate := Q.le (gm.query i jl') (Q.half d)
        (jl', (some ⟨jl', covered, adequate⟩) :: out)
  (((List.range n).reverse).foldl step (n - 1, [])).2.toArray

end Time
end TrafficSpec
