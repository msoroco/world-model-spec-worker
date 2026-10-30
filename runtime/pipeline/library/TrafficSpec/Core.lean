/-
  TrafficSpec.Core — the frozen core, in five layers; a file imports only from its own layer and
  the layers above it in this list.
  Foundations: three-valued logic with reasons, units, time, the temporal operators, the handles
    that name tracks, regions, devices and assumptions.
  Vocab: the ontology enumerations, the world, the atoms, assumptions, parameters, primitives.
  Language: formulas and their semantics, rules, concepts, the static check, export.
  Runtime: grounding, manifests, the monitor, decoding.
  Evidence: builders and adequacy for the witnesses; the lint of a written trace and the
    certificate of a reviewer's case.
-/
import TrafficSpec.Core.Foundations.Tri
import TrafficSpec.Core.Foundations.Units
import TrafficSpec.Core.Foundations.Time
import TrafficSpec.Core.Foundations.Handles
import TrafficSpec.Core.Foundations.Unknown
import TrafficSpec.Core.Foundations.Temporal
import TrafficSpec.Core.Vocab.Ontology.Ids
import TrafficSpec.Core.Vocab.Ontology.RoadUser
import TrafficSpec.Core.Vocab.Ontology.Structure
import TrafficSpec.Core.Vocab.Ontology.Device
import TrafficSpec.Core.Vocab.Ontology.Signal
import TrafficSpec.Core.Vocab.Ontology.Dimensions
import TrafficSpec.Core.Vocab.World
import TrafficSpec.Core.Vocab.Assumptions
import TrafficSpec.Core.Vocab.Intentions
import TrafficSpec.Core.Vocab.Params
import TrafficSpec.Core.Vocab.Atoms
import TrafficSpec.Core.Vocab.Primitives
import TrafficSpec.Core.Language.Formula
import TrafficSpec.Core.Language.Semantics
import TrafficSpec.Core.Language.Rule
import TrafficSpec.Core.Language.Concept
import TrafficSpec.Core.Language.RuleEval
import TrafficSpec.Core.Language.Export
import TrafficSpec.Core.Runtime.Identity
import TrafficSpec.Core.Runtime.Admission
import TrafficSpec.Core.Runtime.Grounding
import TrafficSpec.Core.Runtime.Manifest
import TrafficSpec.Core.Runtime.Monitor
import TrafficSpec.Core.Runtime.Decode
import TrafficSpec.Core.Evidence.Builders
import TrafficSpec.Core.Evidence.Adequacy
import TrafficSpec.Core.Evidence.TraceLint
import TrafficSpec.Core.Evidence.Certificate
