/-
  TrafficSpec.Core.Foundations.Units
  Exact quantities.

  A statute states feet, inches, miles and miles per hour; another states metres and
  kilometres per hour; a scene states metres and metres per second. None of these convert
  to a common INTEGER unit exactly (a kilometre per hour is 5/18 of a metre per second), so
  quantities are exact rationals over SI base units: metre, second, metre per second,
  metre per second squared, degree. No `Float` anywhere; comparison is by cross-multiplication.

  This is the only file where a unit of law meets a unit of measurement. A rule may write a
  number only as the argument of one of the constructors below (the gate enforces this), so a
  threshold in a rule and the same threshold in a label cannot round differently.
-/
namespace TrafficSpec

/-- An exact rational `num / den` with `den > 0`, kept in lowest terms by `mk'`; `Q.eq` is
    equality by value for the rare unreduced literal. -/
structure Q where
  num : Int
  den : Nat
  den_pos : den > 0 := by decide
  deriving Repr

namespace Q

/-- Structural equality (same numerator and denominator); `Q.eq` is equality by value. -/
instance : DecidableEq Q := fun a b =>
  if h : a.num = b.num ∧ a.den = b.den then
    isTrue (by
      obtain ⟨n₁, d₁, p₁⟩ := a
      obtain ⟨n₂, d₂, p₂⟩ := b
      obtain ⟨h1, h2⟩ := h
      simp only at h1 h2
      subst h1; subst h2; rfl)
  else isFalse (by intro e; subst e; exact h ⟨rfl, rfl⟩)

def ofInt (n : Int) : Q := ⟨n, 1, by decide⟩
def zero : Q := ofInt 0
instance : Inhabited Q := ⟨zero⟩

/-- `a / b` in lowest terms for a positive natural `b`; a zero `b` is treated as one so the value
    stays total. Reducing here keeps chained products and sums from growing without bound. -/
def mk' (a : Int) (b : Nat) : Q :=
  if h : b > 0 then
    let g := Nat.gcd a.natAbs b
    have hg : 0 < g := Nat.gcd_pos_of_pos_right _ h
    ⟨a / (g : Int), b / g, Nat.div_pos (Nat.le_of_dvd h (Nat.gcd_dvd_right _ _)) hg⟩
  else ⟨a, 1, by decide⟩

def le (a b : Q) : Bool := a.num * (b.den : Int) ≤ b.num * (a.den : Int)
def lt (a b : Q) : Bool := a.num * (b.den : Int) < b.num * (a.den : Int)
def eq (a b : Q) : Bool := a.num * (b.den : Int) = b.num * (a.den : Int)
def ge (a b : Q) : Bool := le b a
def gt (a b : Q) : Bool := lt b a

def add (a b : Q) : Q := mk' (a.num * b.den + b.num * a.den) (a.den * b.den)
def sub (a b : Q) : Q := mk' (a.num * b.den - b.num * a.den) (a.den * b.den)
def mul (a b : Q) : Q := mk' (a.num * b.num) (a.den * b.den)
def neg (a : Q) : Q := ⟨-a.num, a.den, a.den_pos⟩
def abs (a : Q) : Q := ⟨if a.num < 0 then -a.num else a.num, a.den, a.den_pos⟩
/-- `a / b`; division by zero yields zero (the callers guard it and report `unknown`). -/
def div (a b : Q) : Q :=
  if b.num = 0 then zero
  else if b.num > 0 then mk' (a.num * b.den) (a.den * b.num.toNat)
  else mk' (-(a.num * b.den)) (a.den * (-b.num).toNat)
def half (a : Q) : Q := mk' a.num (a.den * 2)
def min (a b : Q) : Q := if le a b then a else b
def max (a b : Q) : Q := if le a b then b else a
def isZero (a : Q) : Bool := a.num = 0
def isNonneg (a : Q) : Bool := a.num ≥ 0

instance : Add Q := ⟨add⟩
instance : Sub Q := ⟨sub⟩
instance : Mul Q := ⟨mul⟩
instance : Neg Q := ⟨neg⟩

end Q

/-- Integer square root (floor), by Newton's iteration from `n` with fuel; exact for all `n`. -/
def isqrtAux : Nat → Nat → Nat → Nat
  | 0, _, x => x
  | fuel + 1, n, x =>
    if x = 0 then 0
    else
      let y := (x + n / x) / 2
      if y ≥ x then x else isqrtAux fuel n y

def isqrt (n : Nat) : Nat := if n < 2 then n else isqrtAux 256 n n

theorem isqrt_zero : isqrt 0 = 0 := rfl
theorem isqrt_one : isqrt 1 = 1 := rfl

namespace Units

-- Lengths (metres).
def metres (n : Int) : Q := Q.ofInt n
def centimetres (n : Int) : Q := Q.mk' n 100
def millimetres (n : Int) : Q := Q.mk' n 1000
/-- Micrometres: the integer unit adapters use for measured lengths. -/
def micrometres (n : Int) : Q := Q.mk' n 1000000
def kilometres (n : Int) : Q := Q.ofInt (n * 1000)
def inches (n : Int) : Q := Q.mk' (n * 254) 10000          -- 25.4 mm exactly
def feet (n : Int) : Q := Q.mk' (n * 3048) 10000           -- 304.8 mm exactly
def yards (n : Int) : Q := Q.mk' (n * 9144) 10000
def miles (n : Int) : Q := Q.mk' (n * 1609344) 1000        -- 1609.344 m exactly

-- Durations (seconds).
def seconds (n : Int) : Q := Q.ofInt n
def milliseconds (n : Int) : Q := Q.mk' n 1000
def minutes (n : Int) : Q := Q.ofInt (n * 60)
def hours (n : Int) : Q := Q.ofInt (n * 3600)

-- Speeds (metres per second).
def metresPerSecond (n : Int) : Q := Q.ofInt n
/-- Micrometres per second: the integer unit adapters use for measured speeds. -/
def micrometresPerSecond (n : Int) : Q := Q.mk' n 1000000
def kmh (n : Int) : Q := Q.mk' (n * 1000) 3600              -- exactly 5/18 m/s per km/h
def mph (n : Int) : Q := Q.mk' (n * 44704) 100000           -- 0.44704 m/s exactly

-- Curvatures (per metre).
def perMetre (n : Int) : Q := Q.ofInt n

-- Accelerations (metres per second squared).
def metresPerSecondSq (n : Int) : Q := Q.ofInt n
def micrometresPerSecondSq (n : Int) : Q := Q.mk' n 1000000

-- Angles (degrees) and rates (degrees per second).
def degrees (n : Int) : Q := Q.ofInt n
def millidegrees (n : Int) : Q := Q.mk' n 1000

-- Dimensionless.
def ratio (a : Int) (b : Nat) : Q := Q.mk' a b
def percent (n : Int) : Q := Q.mk' n 100

end Units
end TrafficSpec
