/-
  TrafficSpec.Core.Foundations.Temporal
  The temporal operators over a whole trace at once: every operator maps per-instant arrays to a
  per-instant array in one pass (or one pass plus O(1) window queries), so a formula costs
  O(|φ| · n log n) per grounding. Semantics and Derived both use these; nothing here knows what
  a formula or a road user is.

  Finite-trace policy: the unobserved past and future are unknown (`windowTruncated`), never a
  verdict. A lookback window must be covered and adequately sampled; a lookahead window is true
  on a witness, false only when covered.
-/
import TrafficSpec.Core.Foundations.Time
import TrafficSpec.Core.Foundations.Unknown

namespace TrafficSpec
namespace Temporal

def const (n : Nat) (r : R) : Array R := Array.replicate n r
def truncated (op : String) : R := R.u (.windowTruncated op)

-- pointwise connectives
def zipAnd (a b : Array R) : Array R := Array.zipWith R.and a b
def zipOr (a b : Array R) : Array R := Array.zipWith R.or a b
def zipImplies (a b : Array R) : Array R := Array.zipWith R.implies a b
def mapNot (a : Array R) : Array R := a.map R.not
def allOf (n : Nat) (xs : List (Array R)) : Array R := xs.foldl zipAnd (const n R.t)
def anyOf (n : Nat) (xs : List (Array R)) : Array R := xs.foldl zipOr (const n R.f)

-- ---------------------------------------------------------------------------------------------
-- Unbounded operators: one backward or forward pass with the unobserved tail as unknown.
-- ---------------------------------------------------------------------------------------------
private def backward (tail : R) (step : R → R → R) (vals : Array R) : Array R :=
  let n := vals.size
  ((List.range n).reverse.foldl (fun (acc : Array R × R) i =>
    let r := step vals[i]! acc.2
    (acc.1.set! i r, r)) (Array.replicate n tail, tail)).1

private def forward (head : R) (step : R → R → R) (vals : Array R) : Array R :=
  let n := vals.size
  ((List.range n).foldl (fun (acc : Array R × R) i =>
    let r := step vals[i]! acc.2
    (acc.1.set! i r, r)) (Array.replicate n head, head)).1

/-- `always φ`: φ here and at every later observation, and the unobserved future. -/
def alwaysAll (φ : Array R) : Array R := backward (truncated "always") R.and φ
/-- `eventually φ`: φ here or later, or the unobserved future. -/
def eventuallyAll (φ : Array R) : Array R := backward (truncated "eventually") R.or φ
/-- Strong until: `ψ ∨ (φ ∧ until')`, the unobserved future as the tail. -/
def untilAll (φ ψ : Array R) : Array R :=
  let n := ψ.size
  ((List.range n).reverse.foldl (fun (acc : Array R × R) i =>
    let r := R.or ψ[i]! (R.and φ[i]! acc.2)
    (acc.1.set! i r, r)) (Array.replicate n (truncated "until"), truncated "until")).1
/-- Since: `ψ ∨ (φ ∧ since')`, the unobserved past as the head. -/
def sinceAll (φ ψ : Array R) : Array R :=
  let n := ψ.size
  ((List.range n).foldl (fun (acc : Array R × R) i =>
    let r := R.or ψ[i]! (R.and φ[i]! acc.2)
    (acc.1.set! i r, r)) (Array.replicate n (truncated "since"), truncated "since")).1
/-- `once φ`: φ here or at some earlier observation, or the unobserved past. -/
def onceAll (φ : Array R) : Array R := forward (truncated "once") (fun v acc => R.or v acc) φ
/-- φ at the previous observation (`first` at the trace start). -/
def prevAll (first : R) (φ : Array R) : Array R :=
  (Array.range φ.size).map fun i => if i = 0 then first else φ[i - 1]!

-- ---------------------------------------------------------------------------------------------
-- Metric windows: positions per instant (time or path), a length d, per-instant values.
-- ---------------------------------------------------------------------------------------------
/-- φ at every observation in the window of length `d` behind each instant. Unknown where the
    window is not covered, not adequately sampled, or a position inside it is missing. -/
def holdsForAll (pos : Array (Option Q)) (d : Q) (op : String) (missing : UnknownReason) (φ : Array R) : Array R :=
  let wins := Time.backWindows pos d
  let agg := RangeAgg.build φ
  (Array.range φ.size).map fun i =>
    match wins[i]! with
    | none => R.u missing
    | some w =>
      if !w.covered then truncated op
      else if !w.adequate then R.u (.samplingGap op)
      else agg.all w.j0 i

/-- The value of φ at the latest observation `j` in `[j0, i]` at which ψ held: unknown where ψ is
    unknown at an observation later than any at which it held; none where ψ held nowhere in the range. -/
private def atLastAt (ψ φ : Array R) (j0 i : Nat) : Option R :=
  (List.range (i + 1 - j0)).foldl (fun (acc : Option R) k =>
    match acc with
    | some r => some r
    | none =>
      let j := i - k
      match ψ[j]!.v with
      | .t => some φ[j]!
      | .u => some ⟨.u, ψ[j]!.why⟩
      | .f => none) none

/-- φ at the last observation in the window of length `d` behind each instant at which ψ held.
    Unknown where a position is missing, where ψ is unknown later than any observation at which it
    held, where the window is not adequately sampled (an unobserved later instant could be the last
    one at which ψ held), and where ψ held nowhere in a window that is not covered; false where ψ
    held nowhere in a covered, adequately sampled window. -/
def atLastAll (pos : Array (Option Q)) (d : Q) (op : String) (missing : UnknownReason) (ψ φ : Array R) : Array R :=
  let wins := Time.backWindows pos d
  (Array.range φ.size).map fun i =>
    match wins[i]! with
    | none => R.u missing
    | some w =>
      match atLastAt ψ φ w.j0 i with
      | some r => if !w.adequate then R.u (.samplingGap op) else r
      | none => if !w.covered then truncated op else if !w.adequate then R.u (.samplingGap op) else R.f

/-- φ at some observation in the window of length `d` ahead: true on a witness, false only when
    the window is covered, unknown when it runs off the trace. -/
def withinAll (pos : Array (Option Q)) (d : Q) (op : String) (missing : UnknownReason) (φ : Array R) : Array R :=
  let wins := Time.forwardWindows pos d
  let agg := RangeAgg.build φ
  (Array.range φ.size).map fun i =>
    match wins[i]! with
    | none => R.u missing
    | some w =>
      if !w.adequate then R.u (.samplingGap op)
      else
        let a := agg.any i w.jl
        if w.covered then a else R.or a (truncated op)

/-- Smallest `k ≥ i` whose value satisfies `p` (size when none), per instant. -/
def nextWhere (vals : Array R) (p : Tri → Bool) : Array Nat :=
  let n := vals.size
  (List.range n).reverse.foldl (fun (acc : Array Nat) i =>
    acc.set! i (if p vals[i]!.v then i else acc[i + 1]!)) (Array.replicate (n + 1) n)

/-- Strong until restricted to the window ahead: ∃ j in the window, ψ at j and φ at every
    observation from here to just before j; the unobserved remainder counts as unknown unless φ
    already failed. -/
def untilWithinAll (pos : Array (Option Q)) (d : Q) (op : String) (missing : UnknownReason) (φ ψ : Array R) : Array R :=
  let wins := Time.forwardWindows pos d
  let aggφ := RangeAgg.build φ
  let aggψ := RangeAgg.build ψ
  let firstψ := nextWhere ψ (· = .t)
  let firstφf := nextWhere φ (· = .f)
  (Array.range φ.size).map fun i =>
    match wins[i]! with
    | none => R.u missing
    | some w =>
      if !w.adequate then R.u (.samplingGap op)
      else
        let b := firstψ[i]!
        -- φ at every observation from i up to, not including, b (empty when b = i)
        let φBefore (b : Nat) : R := if b ≤ i then R.t else aggφ.all i (b - 1)
        let witnessed : R :=
          if b ≤ w.jl && (φBefore b).v = .t then R.t
          else
            -- false only if every candidate fails: ψ false up to the first φ failure (or the window end)
            let a := firstφf[i]!
            let hi := min a w.jl
            let ψany := aggψ.any i hi
            if ψany.v = .f then R.f
            else
              let why := (if ψany.v = .u then ψany.why else []) ++
                (if b ≤ w.jl then (φBefore b).why else [])
              ⟨.u, if why.isEmpty then [.windowTruncated op] else why⟩
        if w.covered then witnessed
        else R.or witnessed (R.and (truncated op) (aggφ.all i w.jl))

-- ---------------------------------------------------------------------------------------------
-- Runs and counts
-- ---------------------------------------------------------------------------------------------
/-- The first instant of the latest run of true values ending at the latest true instant ≤ i:
    "since φ became true". `none` before any true; an error where an unknown value hides the
    run's start, and `windowTruncated op` where the run reaches the trace start (it may have
    begun before the recording). -/
def runStartAll (op : String) (vals : Array R) : Array (Except UnknownReason (Option Nat)) :=
  let n := vals.size
  ((List.range n).foldl (fun (acc : Array (Except UnknownReason (Option Nat)) × Except UnknownReason (Option Nat)) i =>
    let v := vals[i]!
    let st : Except UnknownReason (Option Nat) :=
      match v.v with
      | .t =>
        if i = 0 then .error (.windowTruncated op)
        else match vals[i - 1]!.v with
          | .t => acc.2
          | .f => .ok (some i)
          | .u => .error (vals[i - 1]!.why.head?.getD (.malformed op))
      | .f => acc.2
      | .u => .error (v.why.head?.getD (.malformed op))
    (acc.1.push st, st)) (Array.mkEmpty n, .ok none)).1

/-- Path length over which `holds` has held continuously up to each instant: zero where it does
    not hold, unknown where it is unknown, where the path length is missing, or where the run
    reaches the trace start. -/
def distanceWhileAll (pathPos : Array (Option Q)) (holds : Array R) : Array QR :=
  let starts := runStartAll "distance_while" holds
  (Array.range holds.size).map fun i =>
    match holds[i]!.v with
    | .f => .ok Q.zero
    | .u => .error (holds[i]!.why.head?.getD (.malformed "distance_while"))
    | .t =>
      match starts[i]! with
      | .error e => .error e
      | .ok none => .error (.windowTruncated "distance_while")
      | .ok (some j) =>
        match pathPos[i]!, pathPos[j]! with
        | some pi, some pj => .ok (Q.sub pi pj)
        | _, _ => .error (.absentAtom "kin_path_length")

/-- Rising edges of `edge` since the start of the latest run of `sinceφ`, per instant. -/
def countEdgesAll (op : String) (edge sinceφ : Array R) : Array (Except UnknownReason Nat) :=
  let n := edge.size
  let starts := runStartAll op sinceφ
  -- edge k: true when edge[k] = t and edge[k-1] = f; unknown when either is unknown
  let edgeVal : Array (Except UnknownReason Bool) := (Array.range n).map fun k =>
    if k = 0 then .ok false
    else match edge[k]!.v, edge[k - 1]!.v with
      | .u, _ => .error (edge[k]!.why.head?.getD (.malformed "count"))
      | _, .u => .error (edge[k - 1]!.why.head?.getD (.malformed "count"))
      | .t, .f => .ok true
      | _, _ => .ok false
  let prefT := (List.range n).foldl (fun (acc : Array Nat) k =>
    acc.push (acc[k]! + (match edgeVal[k]! with | .ok true => 1 | _ => 0))) #[0]
  let prefU := (List.range n).foldl (fun (acc : Array Nat) k =>
    acc.push (acc[k]! + (match edgeVal[k]! with | .error _ => 1 | _ => 0))) #[0]
  let nextU := (List.range n).reverse.foldl (fun (acc : Array Nat) k =>
    acc.set! k (match edgeVal[k]! with | .error _ => k | _ => acc[k + 1]!)) (Array.replicate (n + 1) n)
  (Array.range n).map fun i =>
    match starts[i]! with
    | .error e => .error e
    | .ok none => .error (.windowTruncated op)
    | .ok (some j) =>
      -- edges at k ∈ (j, i]
      if prefU[i + 1]! - prefU[j + 1]! > 0 then
        match edgeVal[nextU[j + 1]!]! with | .error e => .error e | _ => .error (.malformed op)
      else .ok (prefT[i + 1]! - prefT[j + 1]!)

/-- φ true here and false at the previous observation: unknown at the first observation (the
    previous one is unobserved) and where either value is unknown. -/
def risesAll (φ : Array R) : Array R :=
  (Array.range φ.size).map fun i =>
    if i = 0 then truncated "rises"
    else match φ[i]!.v, φ[i - 1]!.v with
      | .u, _ => φ[i]!
      | _, .u => φ[i - 1]!
      | .t, .f => R.t
      | _, _ => R.f

/-- Seconds since φ last became true: from the start of the latest run of true values; unknown
    where that run reaches the trace start or none is observed. -/
def sinceRiseAll (times : Array Q) (φ : Array R) : Array QR :=
  let starts := runStartAll "since_rise" φ
  (Array.range φ.size).map fun i =>
    match starts[i]! with
    | .error e => .error e
    | .ok none => .error (.windowTruncated "since_rise")
    | .ok (some j) => .ok (Q.sub times[i]! times[j]!)

/-- First instant ≤ i at which `vals` is true; an error if an unknown precedes it. A first true at
    index 0 is an upper bound on the true onset, which the caller must treat as such. -/
def firstTrueAll (vals : Array R) : Array (Except UnknownReason (Option Nat)) :=
  let n := vals.size
  ((List.range n).foldl (fun (acc : Array (Except UnknownReason (Option Nat)) × Except UnknownReason (Option Nat)) i =>
    let st : Except UnknownReason (Option Nat) :=
      match acc.2 with
      | .ok (some j) => .ok (some j)
      | .error e => .error e
      | .ok none =>
        match vals[i]!.v with
        | .t => .ok (some i)
        | .f => .ok none
        | .u => .error (vals[i]!.why.head?.getD (.malformed "first"))
    (acc.1.push st, st)) (Array.mkEmpty n, .ok none)).1

end Temporal
end TrafficSpec
