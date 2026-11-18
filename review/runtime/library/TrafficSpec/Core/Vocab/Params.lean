/-
  TrafficSpec.Core.Vocab.Params
  Readings and operationalizations: every number the statute did not state.

  A rule NAMES a parameter; it never owns the value. The value lives in the run's reading, which
  the rule and the label both cite, so a standard is quantified exactly once and can be swept for
  sensitivity. A reading holds the parameter values and the legal aggregates; a rule holds its own
  `Operationalization`s, the records that give a judgement standard its concrete meaning: the
  standard's words, the atoms or concepts that bound it, the parameters, the convention
  the values come from, and whether the rule is a surrogate (the standard is the whole duty)
  rather than the law's own rule.

  No default values live here: a default in Core would be a threshold frozen before any law is seen.
-/
import TrafficSpec.Core.Foundations.Units

namespace TrafficSpec

abbrev ParamName := String

inductive PUnit'
  | metre | second | metrePerSecond | metrePerSecondSq | degree | degreePerSecond | perMetre | ratio | count
  deriving DecidableEq, Repr, Inhabited

structure ParamValue where
  name : ParamName
  value : Q
  unit : PUnit'
  deriving Repr, Inhabited

structure Operationalization where
  standard : String            -- the clause's words for the standard
  concepts : List String       -- the `drv.*` and atom ids that bound it (one standard may pair several)
  params : List ParamName      -- the parameters the bound uses
  convention : String          -- where the values come from
  surrogate : Bool := false    -- true when the standard is the whole duty
  deriving Repr, Inhabited

/-- A legal aggregate, keyed by its legal source (`<definition id>::<term>`, or `<law id>:<span>::<term>`
    for a law-local definition): the road-user classes (`ru.*` ids) its definition includes, and those
    it leaves unresolved. Every other class is excluded. An aggregate never lists another aggregate. -/
structure LegalAggregate where
  id : String
  included : List String := []
  unresolved : List String := []
  deriving Repr, Inhabited

structure Reading where
  params : List ParamValue := []
  aggregates : List LegalAggregate := []
  deriving Repr, Inhabited

namespace Reading
def param (ρ : Reading) (n : ParamName) : Option Q :=
  (ρ.params.find? (·.name == n)).map (·.value)
def paramUnit (ρ : Reading) (n : ParamName) : Option PUnit' :=
  (ρ.params.find? (·.name == n)).map (·.unit)
def has (ρ : Reading) (n : ParamName) : Bool := (ρ.param n).isSome
/-- The aggregate with this id. -/
def aggregate (ρ : Reading) (id : String) : Option LegalAggregate := ρ.aggregates.find? (·.id == id)
end Reading

end TrafficSpec
