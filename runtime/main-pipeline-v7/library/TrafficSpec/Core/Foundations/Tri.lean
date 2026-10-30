/-
  TrafficSpec.Core.Foundations.Tri
  Three-valued truth (strong Kleene), fixed once for the whole library.

  `u` is "not observed on this source". The two laws that carry the library's guarantee that
  an unobserved atom never becomes compliance or violation:
    and f u = f   -- a definitely-false antecedent decides `notApplicable` even when the
                  -- obligation cannot be read
    and t u = u   -- one unobserved conjunct poisons the verdict instead of defaulting it
-/
namespace TrafficSpec

inductive Tri
  | t | f | u
  deriving DecidableEq, Repr, Inhabited

namespace Tri

def ofBool : Bool → Tri
  | true => .t
  | false => .f

def ofOption : Option Bool → Tri
  | some b => ofBool b
  | none => .u

def toOption : Tri → Option Bool
  | .t => some true
  | .f => some false
  | .u => none

def and : Tri → Tri → Tri
  | .f, _ => .f
  | _, .f => .f
  | .t, .t => .t
  | _, _ => .u

def or : Tri → Tri → Tri
  | .t, _ => .t
  | _, .t => .t
  | .f, .f => .f
  | _, _ => .u

def not : Tri → Tri
  | .t => .f
  | .f => .t
  | .u => .u

def implies (a b : Tri) : Tri := or (not a) b

/-- `t` and `f` are decided; `u` is not. -/
def decided : Tri → Bool
  | .u => false
  | _ => true

/-- Conjunction over a list: `t` on the empty list. -/
def all (xs : List Tri) : Tri := xs.foldl and .t

/-- Disjunction over a list: `f` on the empty list. -/
def any (xs : List Tri) : Tri := xs.foldl or .f

-- Laws. All by case analysis; they are what Tests/Tri.lean re-checks by `decide`.
theorem and_f_left (a : Tri) : and .f a = .f := rfl
theorem and_f_right (a : Tri) : and a .f = .f := by cases a <;> rfl
theorem and_t_left (a : Tri) : and .t a = a := by cases a <;> rfl
theorem and_t_right (a : Tri) : and a .t = a := by cases a <;> rfl
theorem and_t_u : and .t .u = .u := rfl
theorem and_comm (a b : Tri) : and a b = and b a := by cases a <;> cases b <;> rfl
theorem and_assoc (a b c : Tri) : and (and a b) c = and a (and b c) := by
  cases a <;> cases b <;> cases c <;> rfl
theorem or_t_left (a : Tri) : or .t a = .t := rfl
theorem or_t_right (a : Tri) : or a .t = .t := by cases a <;> rfl
theorem or_f_left (a : Tri) : or .f a = a := by cases a <;> rfl
theorem or_f_right (a : Tri) : or a .f = a := by cases a <;> rfl
theorem or_comm (a b : Tri) : or a b = or b a := by cases a <;> cases b <;> rfl
theorem or_assoc (a b c : Tri) : or (or a b) c = or a (or b c) := by
  cases a <;> cases b <;> cases c <;> rfl
theorem not_not (a : Tri) : not (not a) = a := by cases a <;> rfl
theorem not_and (a b : Tri) : not (and a b) = or (not a) (not b) := by
  cases a <;> cases b <;> rfl
theorem not_or (a b : Tri) : not (or a b) = and (not a) (not b) := by
  cases a <;> cases b <;> rfl
theorem ofOption_none : ofOption none = .u := rfl
theorem ofOption_toOption (a : Tri) : ofOption (toOption a) = a := by cases a <;> rfl
/-- The conjunction is unknown exactly when no conjunct is false and some conjunct is unknown. -/
theorem and_eq_u_iff (a b : Tri) : and a b = .u ↔ (a ≠ .f ∧ b ≠ .f ∧ (a = .u ∨ b = .u)) := by
  cases a <;> cases b <;> simp [and]

end Tri
end TrafficSpec
