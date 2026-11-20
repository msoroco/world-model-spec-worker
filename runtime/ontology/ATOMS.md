# Traffic-law ontology — atoms

Status: frozen. Changed only by an explicit ontology change, never by a rule and never by an
agent.

## What an atom is

An **atom** is an element of the road world that traffic law refers to without defining it
further and that a data source can observe: a class of road user, a quantity of motion, a piece
of road structure, a control device and its state, a signal a road user emits, a condition of the
environment, or a relation between two road users. Each atom has a **semantic contract** — what
it denotes physically, its unit and its reference frame, and, where the meaning invites
confusion, what it is **not a stand-in for**. The contract is independent of any data source and
of any statute.

A standard of judgement ("safe", "reasonable", "practicable") is **not** an atom: nothing in a
scene is a reasonableness. §8 says how a rule gives such a standard a concrete meaning.

## The termination rule

This file is the whole termination rule. It has six clauses; every session and every check of the
pipeline works within them, and nothing else adds to or bypasses them.

1. **Closed set.** A rule reads the world only through the atoms of §1–§7, the primitives of
   §10, and the concepts the pipeline has accepted (§9). An element a clause needs that none of
   these carries is an ontology change request, filed as a gap; it is never approximated by
   another atom, and it is never absorbed as a residue on a span that decides when the rule
   applies. A residue records only what the obligation side says and the rule does not capture.
2. **Contract-bound.** An atom expresses only what its contract says. The "not a stand-in for"
   clauses are part of the contract; using an atom for what its contract excludes is a semantic
   error, whatever the data source happens to make convenient.
3. **Defined once.** A concept — a manoeuvre, a state of motion, a road configuration — is a
   node of the pipeline: a contract and a body over atoms, primitives and other concepts, accepted
   like a rule, called by id and never rebuilt inline. A primitive (§10) is a computation the
   formula language cannot express, defined once in Core with its parameters exposed. A rule
   instantiates parameters; it never redefines either.
4. **A judgement standard is operationalized, never read.** A clause element that is a standard
   of judgement is bounded, in the plan, by concepts and primitives with parameters the reading
   sets, and the bound is recorded as an *operationalization claim* that names the standard,
   the concepts, the parameters and the convention their values come from. A rule that leaves a
   standard unoperationalized is not a rule; a rule whose only content is an operationalized
   standard is a **surrogate** and is marked as one.
5. **Legal region classes are assumptions.** Categories a jurisdiction defines administratively
   (a district, an area class, a calendar or clock condition, a legal designation of a highway)
   enter a formalization only as reading assumptions declared per map or per trace, never as
   atoms a rule reads from a scene.
6. **Unobserved is unknown.** Every atom is three-valued when observed — true, false, or *not
   observed on this source* — as declared by that source's capability manifest. A rule built on
   an unobserved atom reports `unknown`, never compliance and never violation.

**How atoms are reached from a clause.** Mapping the elements of a clause onto atoms is the
planning session's work — the linguistic half of autoformalization. Each planned node records
its mappings as *grounding claims* (`elements`: clause element → atoms, with a justification that
cites the contracts) and its *operationalization claims* (§8). The harness validates them before
any rule is written: every atom named exists here; the same element maps to the same atoms in
every node of the run, so a contradiction is rejected; and the run's mapping index, which the
harness derives from the accepted nodes, is what the validator checks each later mapping against
and what the planner is shown. No agent writes a shared file, and nothing about a corpus is decided
before the run that formalizes it.

This file says nothing about which law refers to which atom and nothing about how any data
source produces one. Which atoms a source can observe is declared at run time by that source's
**capability manifest**, one capability per atom: `exact`, `estimate` (with a named error
class), `absent`, or `subject` — observed for the subject track only, as an instrumented vehicle
or a simulator reports its own controls and its own line of sight and nobody else's. Under
`subject` a read of the atom for any other road user is unknown.

**Scope column.** `general` marks an element of the ordinary road vocabulary. `local` marks an
element that exists because the target jurisdiction's own vehicle taxonomy or device catalogue
names it; its contract still describes what is physically observed, and a source that has no such
thing declares it `absent`. The flag is information for the manifest author and the planner, not
a permission: local atoms are atoms.

Identifier scheme: `family.name`. Families: `ru` road user, `kin` kinematics, `st` road
structure, `dev` control device, `sig` emitted signal, `env` environment, `rel` relation between
road users. Derived concepts use `drv`. Where an atom carries an attribute (a state, a kind, a
colour), the attribute's values are listed in the contract; an attribute value not listed is an
ontology change request.

## 1. Road users (`ru`) — class atoms on an entity

| id | contract | scope |
|---|---|---|
| `ru.motor_vehicle` | a self-propelled vehicle other than a rail vehicle; excludes the powered two-wheelers a jurisdiction classes separately below, and the cycles and scooters it classes apart from motor vehicles (bicycles, electric bicycles, electric scooters) **Not a stand-in for:** "vehicle" as a legal aggregate — which classes count as a vehicle is declared by the reading | general |
| `ru.motorcycle` | motor vehicle on two or three wheels ridden astride, including three-wheeled variants, equipped with a seat or saddle for its rider. Legal classification: the source lists this class for a road user only where it confirms that the road user is a motorcycle under NRS 484A.135 (the pipeline trusts that classification) | local |
| `ru.trimobile` | a motor vehicle with handlebars and a saddle seat, designed to travel with three wheels in contact with the ground, at least one of them power driven. Legal classification: the source lists this class for a road user only where it confirms that the road user is a trimobile under NRS 486.057, and lists it for every road user it so confirms, marking the class unobserved where it cannot decide (the pipeline trusts that classification); it lists `ru.motorcycle` as well only where it confirms that the vehicle is a motorcycle under NRS 484A.135, and neither class implies the other **Not a stand-in for:** a motorcycle with a sidecar — it is no trimobile, though it may travel on three wheels | local |
| `ru.moped` | a low-power two- or three-wheeler with a small engine or motor. Legal classification: the source lists this class for a road user only where it confirms that the road user is a moped under NRS 484A.125 and under NRS 486.038, and lists it for every road user it so confirms, marking the class unobserved where it cannot decide (the pipeline trusts that classification and measures no engine output, displacement or speed) | local |
| `ru.bus` | a bus: a motor vehicle designed to carry many passengers. Legal classification: the source lists this class for a road user only where it confirms that the road user is a bus under NRS 484A.030 (the pipeline trusts that classification) | local |
| `ru.transit_bus` | bus in public transit service, identifiable by its livery or route display; it lists `ru.bus` as well only where it confirms that the vehicle is a bus under NRS 484A.030, and neither class implies the other | general |
| `ru.school_bus` | bus designated for carrying school children, with the jurisdiction's markings. Legal classification: the source lists this class for a road user only where it confirms that the road user is a school bus under NRS 484A.230 (the pipeline trusts that classification); it lists `ru.bus` as well only where it confirms that the vehicle is a bus under NRS 484A.030, and neither class implies the other | local |
| `ru.taxicab` | a taxicab: a passenger vehicle for hire, identifiable by its markings. Legal classification: the source lists this class for a road user only where it confirms that the road user is a taxicab under NRS 484A.270 (the pipeline trusts that classification; the markings describe the class and are no evidence of the passenger count or the charge that definition states) | local |
| `ru.tour_or_shuttle_bus` | a bus in tour or shuttle service, identifiable by its livery. Legal classification: the source lists this class for a road user only where it confirms that the road user is a tour bus or shuttle bus under LVMC 11.02.150 (the pipeline trusts that classification); it lists `ru.bus` as well only where it confirms that the vehicle is a bus under NRS 484A.030, and neither class implies the other **Not a stand-in for:** a transit bus on a public route (`ru.transit_bus`), or a limousine (`ru.limousine`) | local |
| `ru.limousine` | a lengthened passenger vehicle for hire, identifiable by its body and its livery **Not a stand-in for:** a taxicab (`ru.taxicab`), or a tour or shuttle bus (`ru.tour_or_shuttle_bus`) | local |
| `ru.truck` | motor vehicle for carrying goods, with a body built for that purpose. Legal classification: the source lists this class for a road user only where it confirms that the road user is a truck under NRS 484A.305, and lists it for every road user it so confirms, marking the class unobserved where it cannot decide (the pipeline trusts that classification) | local |
| `ru.commercial_motor_vehicle` | vehicle over the jurisdiction's commercial mass class or marked as commercially licensed | general |
| `ru.trailer` | a vehicle without motive power of its own, built to be drawn by another (a trailer or a semitrailer), tracked by the source as a road user of its own **Not a stand-in for:** the vehicle drawing it, or a drawing vehicle and what it draws tracked as one body (`ru.vehicle_combination`) | general |
| `ru.vehicle_combination` | a drawing vehicle together with the vehicle or vehicles it draws (a truck tractor and a semitrailer, a car and a trailer), tracked by the source as one body **Not a stand-in for:** either unit tracked on its own — a drawn unit is `ru.trailer`, the drawing vehicle keeps its own class | general |
| `ru.bicycle` | a human-powered wheeled vehicle ridden by a person. Legal classification: the source lists this class for a road user only where it confirms that the road user is a bicycle under NRS 484A.025, and lists it for every road user it so confirms, marking the class unobserved where it cannot decide (the pipeline trusts that classification and measures no wheel size or wheel count) | local |
| `ru.electric_bicycle` | an electric bicycle. Legal classification: the source lists this class for a road user only where it confirms that the road user is an electric bicycle under NRS 484B.017 (to which NRS 484A.081 ascribes the term's meaning), and lists it for every road user it so confirms, marking the class unobserved where it cannot decide (the pipeline trusts that classification and asks for no measurement of motor power, speed or pedals); **class** attribute as that definition labels it **Not a stand-in for:** a bicycle without a motor, a moped or a motor vehicle — how the class enters a law is that law's words, as its definitions state them | local |
| `ru.electric_scooter` | a standing or seated electric scooter with handlebars. Legal classification: the source lists this class for a road user only where it confirms that the road user is an electric scooter under NRS 484B.018, under NRS 484A.082 and under NRS 482.0295, and lists it for every road user it so confirms, marking the class unobserved where it cannot decide (the pipeline trusts that classification and measures no weight or speed) | local |
| `ru.pedestrian` | a person on foot, in a wheelchair, or on a device the jurisdiction treats as on foot. Legal classification: the source lists this class for a road user only where it confirms that the road user is a pedestrian under NRS 484A.165, and lists it for every road user it so confirms, whatever other class it lists for the same road user (a person in a motorized wheelchair carries this class with any other), marking the class unobserved where it cannot decide (the pipeline trusts that classification and measures nothing of the wheelchair or the device) **Not a stand-in for:** a person on a bicycle or scooter | local |
| `ru.pedestrian_with_white_cane_or_guide_animal` | pedestrian carrying a white or white-and-red cane, accompanied by a guide animal, or led by another person | general |
| `ru.child` | pedestrian who is visibly a child | general |
| `ru.emergency_vehicle` | an authorized emergency vehicle: a vehicle of a class the jurisdiction designates as emergency, which the source declares only where it confirms that the vehicle is equipped with the warning lamps and the siren the jurisdiction requires of such a vehicle (the pipeline trusts that declaration and checks no evidence of the equipment); legal classification: the source lists this class for a road user only where it confirms, by the vehicle's designated class and that equipment, that it is an authorized emergency vehicle under NRS 484A.020, and lists it for every vehicle it so confirms, marking the class unobserved where it cannot decide; **kind** ∈ {police, fire, ambulance, other} **Not a stand-in for:** a warning lamp or a siren in use now, a response to an emergency now, or an official duty being performed now — the class carries the vehicle's fixed identity and the equipment its contract names, and never shows any of them | local |
| `ru.fire_apparatus` | a fire-fighting vehicle (a sub-kind of `ru.emergency_vehicle` that law names on its own) | general |
| `ru.official_vehicle` | a vehicle in official or contracted road service, identifiable by livery or equipment; **kind** ∈ {tow, utility, highway_maintenance, incident_management, regulatory_agency, coroner, armored_car, municipal, postal, other} **Not a stand-in for:** an emergency vehicle | general (kinds `incident_management`, `regulatory_agency`, `armored_car`: local) |
| `ru.tow_car` | a motor vehicle built or equipped for towing or for roadside assistance — with a crane, a hoist, a tow bar, a towline or a dolly — identifiable by that equipment **Not a stand-in for:** a vehicle in official or contracted towing service (`ru.official_vehicle` kind `tow`) — this class is the equipment, not the service; or a vehicle drawing a trailer (`ru.vehicle_combination`) | general |
| `ru.rail_vehicle` | a train, tram, streetcar or other device used only on fixed rails | general |
| `ru.occupant_count` | the number of persons in or on a vehicle (an integer attribute of a road user) **Not a stand-in for:** a person arriving at or leaving a vehicle — a change in the count is not the count | general |
| `ru.unladen_mass` | the mass of a vehicle as built and equipped for the road, without its load, its occupants or a vehicle it draws, as the source records it (a registration or a manufacturer's figure, never weighed in the scene); a vehicle combination's is the sum of its units' **Not a stand-in for:** the vehicle's mass with its present load, or its size (`kin.extent`) — a large vehicle may be light and a small one heavy | general |
| `ru.disabled` | the vehicle cannot move under its own power (broken down, wrecked, without fuel or charge), as the source records it: a physical state at the observation, unknown where the source does not record it, never presumed **Not a stand-in for:** a halted vehicle, one showing hazard lamps (`sig.hazard`) or one whose engine is off (`kin.engine_running`) — none of them shows that the vehicle cannot move; or a vehicle used by a person with a disability, or a space designated for one (`st.parking_space` **designation**) | general |
| `ru.rider_posture` | how a rider sits and holds the machine: **on_seat**, **hands_on_controls** (count), **standing_on_deck**, **holding_another_vehicle**, **stunt** (a wheel off the ground, a person on the handlebars). The fields are independent of one another, and **hands_on_controls** is a count **Not a stand-in for:** a manoeuvre, or an arm signal, which is `sig.hand_signal` | general |
| `ru.subject` | the road user whose conduct a rule judges (the ego) | general |
| `ru.aggregate` | membership of a legal aggregate: the atom's literal argument is an aggregate id, `<definition id>::<term>` for the posted definition that applies, or `<law id>:<span>::<term>` for a definition the law itself makes, and the run's reading classifies every road-user class under that id by the definition's words as included, excluded (the definition leaves it out), covered (the definition admits its members only as members of named included classes, which a road user carries beside it, so its own label adds no membership evidence) or unresolved; true when the user carries an included class, unknown when no included class holds and the user carries an unresolved class or an included or unresolved class it might carry is unobserved, false otherwise: a covered or excluded class decides nothing **Not a stand-in for:** a named road-user class for which the applicable definitions and the run's representation decisions permit its own class atom — that class's own atom; an admitted aggregate stays an aggregate even when it contains only one class; a relational role such as who drives or controls a vehicle — never membership; nor a role defined by an observable manoeuvre, such as overtaking — that role is a derived concept | general |

Legal aggregate words ("vehicle", "traffic") are carried by `ru.aggregate` with the definition-scoped
id as its argument, never the word: which classes the posted definition counts under that id is
derived from its words and recorded in the reading, never expanded into a class list by a rule.
"Driver" is no aggregate: it names who controls a vehicle, a relational role read as the section on
what is not an atom states. Where words make a rule turn on an emergency vehicle's response to an emergency, it is read from a
declared fact; where they ask for its warning lamps or siren in use, from those signals in the trace;
the class shows neither.

## 2. Kinematics and control state (`kin`) — measurements on any road user, and the inputs to a vehicle's controls

| id | contract | unit / frame | scope |
|---|---|---|---|
| `kin.time` | instant of observation of a scene | ms, monotone within a trace | general |
| `kin.position` | position of the body's reference point | m, world frame (map or local) | general |
| `kin.heading` | direction the body points; a formula reads it normalised: divided by its larger absolute component, then by its length taken to a micrometre, so the vector read is the unit vector times a factor of at least 1 and below 1 + 2·10⁻⁶ (exactly the unit vector where that scaled length is a whole number of micrometres, as for an axis-aligned direction); a zero vector reads unknown | unit vector, world frame | general |
| `kin.velocity` | velocity vector | m/s, world frame | general |
| `kin.speed` | magnitude of velocity | m/s | general |
| `kin.accel_longitudinal` | acceleration along heading, signed **Not a stand-in for:** speed | m/s² | general |
| `kin.yaw_rate` | rate of change of heading, positive when the heading turns to the left (counter-clockwise) **Not a stand-in for:** road curvature — a vehicle yaws on a straight road whenever it manoeuvres | deg/s | general |
| `kin.extent` | the body's size along its axes about the reference point: a trace writes the half-length, half-width and half-height; a formula reads the full length, width and height, twice each | m | general |
| `kin.steer_angle` | front-wheel steering angle **Not a stand-in for:** road geometry, a turn, a lane change or any other manoeuvre — a steering input is not a path and not a road | deg | general |
| `kin.path_length` | distance travelled along the body's path since the start of the trace, monotone | m | general |
| `kin.engine_running` | the vehicle's engine or motor is running, so that propulsion is available **Not a stand-in for:** motion or a halt — a vehicle stands with its engine running and rolls with it stopped | — | general |
| `kin.parking_brake` | the parking brake (hand brake) is set **Not a stand-in for:** the service brake (`kin.service_brake`) or the brake lamp (`sig.brake_lamp`) — a set parking brake lights no lamp and a pressed pedal sets no parking brake | — | general |
| `kin.gear` | the gear selected: negative for reverse, zero for neutral, positive for a forward gear **Not a stand-in for:** the direction of motion — a vehicle in a forward gear rolls backwards on a grade; backing is read from kinematics | gear number, signed | general |
| `kin.throttle` | the accelerator input, as the fraction of its full travel that is applied **Not a stand-in for:** acceleration (`kin.accel_longitudinal`) — the input is what the driver does, the acceleration is what the body does | ratio | general |
| `kin.service_brake` | the service brake (foot brake) input, as the fraction of its full travel that is applied **Not a stand-in for:** deceleration or the brake lamp — the lamp is what other road users see, the input is what the driver does | ratio | general |

The control-state atoms are observed on an instrumented vehicle — a simulator's own vehicle, a
vehicle with a data recorder.

## 3. Road structure (`st`) — map-level atoms and occupancy

A kind whose contract ends in **Refines:** names the kind it refines: every region of the refining kind is also a region of the kind it refines, and of every kind that one refines. A parent never implies a refining kind, and two kinds refining one parent never imply each other. Refinement is not lying on a way (`st.on_way`): a region that lies on another is not thereby of its kind. Where a source cannot tell a refining kind, only the regions it labels with a kind that refining kind refines are unknown members of it; a region of any other kind is known not to be one. A kind whose contract begins with **Abstract.** is the union of the kinds that refine it, and only a quantifier or a formula reads it: no region is labelled with it, no source declares it a kind it cannot tell, it refines no kind, and a region is of it exactly when it is of a kind that refines it (unknown where that is unknown for one of them and true for none). An abstract parent is no parent for what a source cannot tell: a kind whose parent is abstract is treated, where a source cannot tell it, as a kind that refines none.

| id | contract | scope |
|---|---|---|
| `st.highway` | the entire public way between its boundary lines, including sidewalks and shoulders **Not a stand-in for:** the roadway | general |
| `st.travel_region` | **Abstract.** the union of the kinds a device can govern (`dev.governs`): a lane and the kinds that refine it, a bicycle lane or path, a roadway and the kinds that refine it, a shoulder, or an intersection; a region is a travel region exactly when it is of one of them **Not a stand-in for:** the extent of a highway (`st.highway`, `st.on_way`) — a sidewalk, a crosswalk, a stop line or the way as a whole is no travel region; travel along or across a way, which the road user's motion and the region's direction state, never the kind of the region occupied; or which entry into an intersection a region is (`st.lane_enters`, `st.entrance_of`) | general |
| `st.roadway` | the part of a highway improved for vehicular traffic, excluding shoulder; separate roadways of a divided highway are separate **Not a stand-in for:** the sidewalk — 'not on the roadway' includes shoulder, verge and parking bays **Refines:** `st.travel_region` | general |
| `st.lane` | a longitudinal strip of roadway for one line of vehicles **Not a stand-in for:** a half of the roadway or a lateral position within a lane — lane membership is not an offset from the edge, and lane ordinal equals roadway half only on a two-lane road **Refines:** `st.travel_region` | general |
| `st.lane_direction` | direction of travel designated for a structure a vehicle travels in — a lane, reserved lane, turn lane, bicycle lane or path, or a roadway, one-way roadway or shoulder; a centre turn lane carries none. The direction is local to its carrier (a bend or a loop is written as segments), carriers that overlap or cross may carry different directions, and a place no carrier covers has none (unknown). It is written at any length; a formula reads it normalised: divided by its larger absolute component, then by its length taken to a micrometre, so the vector read is the unit vector times a factor of at least 1 and below 1 + 2·10⁻⁶ (exactly the unit vector where that scaled length is a whole number of micrometres, as for an axis-aligned direction); a zero vector reads unknown | general |
| `st.lane_adjacency` | left / right neighbouring lane of the same direction; lane ordinal within the carriageway and the count of lanes in that direction; ordinal 1 is the leftmost lane, looking along the lane's direction **Not a stand-in for:** the marking between two lanes | general |
| `st.lane_connectivity` | which lane a lane leads into | general |
| `st.lane_enters` | relation: the intersection region a directed approach carrier runs into at its entrance end — the carrier is an approach to that intersection. A carrier is a lane or a kind refining it, or a roadway, one-way roadway, shoulder or bicycle lane or path that the source records as a directed approach segment: the stretch one direction of travel uses to reach one junction, its entrance end at that junction. A bicycle lane or path stays its own kind, not a lane, and a mark or a device's governance on it does not pass to an adjacent lane, nor theirs to it.  Writing the relation on a roadway, one-way roadway, shoulder or bicycle lane or path asserts that it is such a segment: a whole two-way roadway or bicycle path, with an end at each junction, carries none, and which junction it is an approach to stays unknown. A carrier enters one intersection at most. The relation is entry topology: it is decided where the source records it, whether or not the carrier's direction (`st.lane_direction`) is observed. It is the source's record, never inferred from distance, overlap or a road user's velocity, and a carrier never takes the entrance of a carrier it overlaps. **Which carrier a road user approaches through:** a road user's approach to an intersection is a carrier it occupies (`rel.occupies`) whose entrance end is that intersection, and the mark that governs that approach is one the source records as marking that carrier (`st.entrance_of`). The intersection is fixed by the event the rule reads (the intersection entered, or the one the words name), never by the road user's velocity or heading, by distance or by overlap. A road user occupying one such carrier approaches through it whatever its motion: forward, at rest, backing, or with its velocity or heading unobserved. Overlapping carriers that enter different intersections are told apart by the intersection, not by motion. Where it occupies several carriers entering the same intersection, the duty is owed through each of them: it is met where it is met through every one, violated where it is violated through any, and unknown otherwise (a mark's association unobserved on one carrier leaves that carrier unknown); a rule never picks the carrier that favours the road user. Travel against a carrier's direction does not change which intersection the carrier enters, and reaching a carrier's far (exit) end is no entry through it **Not a stand-in for:** the lane a lane leads into (`st.lane_connectivity`), the subject's presence in the intersection (`rel.occupies`), or the region a device governs (`dev.governs`) — a device governs a lane and the lane enters an intersection; which intersection a device controls is read through both, or directly where the device governs the intersection | general |
| `st.on_way` | relation: the public way (a `highway` region) a structure region lies on — a lane, roadway, shoulder, crosswalk, stop line, median or any other part of it; an intersection lies on every way that meets there **Not a stand-in for:** nearness to a way (`st.region_geometry`), or the lane a lane leads into (`st.lane_connectivity`) | general |
| `st.entrance_of` | relation: the carrier whose entrance into an intersection a stop line or a crosswalk marks — exactly that carrier's entrance, the line or crossing a vehicle approaching through that carrier halts at or before, and not a line near the carrier or on its way. The carriers are those `st.lane_enters` admits: a lane or a kind refining it, or a roadway, one-way roadway, shoulder or bicycle lane or path recorded as a directed approach segment; the intersection is the one that carrier enters, so a rule reads both relations on the same carrier. One line may mark several carriers (several lanes, or lanes and a segment or a bicycle lane beside them), and a carrier may have a stop line and a crosswalk. Where the source observes a line's entrances its list is complete, and the line marks no carrier it does not list; where it does not, which carriers the line marks is unknown, never "no line for this carrier". The association is the source's record, never inferred from distance, overlap or a road user's velocity; a carrier never takes the line, nor the governance of a device (`dev.governs`), of a carrier it overlaps. No region other than a stop line or a crosswalk marks an entrance **Not a stand-in for:** distance to the line (`st.region_geometry`), or the way the line lies on (`st.on_way`) | general |
| `st.lane_marking` | per side of a lane: **type** ∈ {none, broken, solid, double_solid, solid_broken, dotted, curb}, **colour** ∈ {white, yellow, other} | general |
| `st.centre_line` | the marking, or the geometric centre, dividing the two directions of a two-way roadway | general |
| `st.road_edge` | curb or edge of the roadway; **paved** attribute for the surface beyond it | general |
| `st.shoulder` | the part of the highway beside the roadway not intended for vehicular traffic; **paved** attribute **Refines:** `st.travel_region` | general |
| `st.sidewalk` | area for pedestrians between roadway and property line **Not a stand-in for:** a crosswalk | general |
| `st.median_or_divider` | physical barrier or dividing section between roadways; **opening** attribute where a crossover exists | general |
| `st.one_way_roadway` | roadway on which traffic is restricted to one direction **Refines:** `st.roadway` | general |
| `st.intersection` | the region where two roadways meet, bounded by the prolongation of their edges; a junction where an alley meets another way (a street, road, highway or alley) is no intersection but a `st.driveway_or_alley_entrance` **Not a stand-in for:** a crosswalk or a stop line — a stop before the crossing is earlier than a stop before the intersection **Refines:** `st.travel_region` | general |
| `st.crosswalk` | marked crossing, or the unmarked prolongation of sidewalks at an intersection (`st.intersection`); **marked** attribute | general |
| `st.stop_line` | the transverse line marking where vehicles halt for a device | general |
| `st.driveway_or_alley_entrance` | the place where a driveway, a private road, an alley or another entrance to abutting property meets the highway; **kind** ∈ {driveway, private_road, alley, property}: a driveway serving one property, a private road serving several, an alley (`st.alley`), or an entrance into abutting property (a lot, a garage, a parking area) that is none of these; **private** attribute: the way or property the entrance leads into is private, false where it is public, as the source records it; where the source does not record it, whether it is private is unknown, never read from the kind **Not a stand-in for:** an intersection (`st.intersection`) — an entrance is no junction of two roadways; the alley itself (`st.alley`) — the entrance is where it meets the highway; or whether a kind is private — an alley or a private road may be either, and only the **private** attribute says | general |
| `st.alley` | a narrow way within a block serving the rear of properties | general |
| `st.curvature` | horizontal curvature of the roadway at a road user's position, one value per road user at each observation, as a magnitude (1/m, never negative): a bend to either hand has the same value. Where the road user's position, or the roadway it lies on, cannot be determined uniquely, the source gives no value and the curvature is unknown **Not a stand-in for:** the road user's own turning (`kin.yaw_rate`) — the curvature is the road's, whatever path the road user takes on it | general |
| `st.grade` | longitudinal slope of the roadway at a road user's position, along the road user's heading (`kin.heading`), one value per road user at each observation: the rise per unit of horizontal distance, positive where the road rises in the direction the road user faces, negative where it falls (ratio, unit 1). Where the road user's heading is not observed the grade is unknown; where its position, or the roadway it lies on, cannot be determined uniquely, the source gives no value and the grade is unknown **Not a stand-in for:** the place of a crest (`st.crest`) — the slope where a road user is says nothing of a crest ahead of it | general |
| `st.crest` | the place on a roadway's longitudinal profile where the slope changes from rising to falling in the direction of travel, carried as a region with a reference point and a boundary, so the ground distance from a road user to it is read through `st.region_geometry` **Not a stand-in for:** the slope where a road user is (`st.grade`), the view a crest restricts (`st.sight_distance`), or a horizontal bend (`st.curvature`) | general |
| `st.sight_distance` | the distance along the road within which a vehicle at a point and another vehicle on the road could see each other, from the eye of either driver to the body of the other vehicle at the height convention the source declares: both the view of approaching traffic from that point and its being seen by drivers approaching it, whether or not any road user is there **Not a stand-in for:** whether an actual road user saw, or could see, another at an observation (`rel.visible`), or the clarity of the air (`env.visibility`) | general |
| `st.sight_along_way` | the distance along a way — a highway, or a railway track (`st.railway_track`) — in each direction from the point of that way nearest a road user (on a railway track, from the level crossing of that track nearest the road user), within which another vehicle on that way, a rail vehicle on a track, could be seen from the road user's eye at the observation, at the height convention the source declares; the smaller of the two directions; m **Not a stand-in for:** the sight distance of the place the road user is at (`st.sight_distance`), whether an actual road user or train is seen (`rel.visible`), or the view of the crossing itself — a clear view along the track in both directions is this atom, the crossing's place is `st.region_geometry` | general |
| `st.railway_crossing` | level crossing of a railway with the roadway, and its nearest rail | general |
| `st.railway_track` | the track of a railway or a street railway as a region: the outline of its outermost rails, along its length on, beside or across the highway; **kind** ∈ {railroad, streetcar} **Not a stand-in for:** a level crossing (`st.railway_crossing`) — the track runs on beyond the place where it crosses the roadway; or a rail vehicle on it (`ru.rail_vehicle`) — a track is there whether or not a train is | general |
| `st.controlled_access` | a highway with access only at designated points, and its entrance and exit lanes | general |
| `st.elevated_structure` | bridge, viaduct or tunnel carrying the roadway | general |
| `st.bicycle_lane_or_path` | lane or separate path reserved for bicycles and the devices a jurisdiction groups with them **Refines:** `st.travel_region` | general |
| `st.reserved_lane` | lane reserved for a class of vehicles; **class** ∈ {high_occupancy, bus, heavy_vehicle, other} **Refines:** `st.lane` | general (class `high_occupancy` with occupancy and hours conditions: local) |
| `st.centre_turn_lane` | a single centre lane used only for turning by traffic in both directions **Refines:** `st.lane` | local |
| `st.turn_lane` | a lane designated only for turning; **side** ∈ {left, right} **Refines:** `st.lane` | general |
| `st.parking_space` | marked bay for standing or parking; **angle** attribute; **designation** ∈ {general, disabled, disabled_side_lift, access_aisle, municipal, charging}; **angle_marking** attribute: true where the source confirms that the space's markings are an official marking indicating the angle of parking, false where it confirms that they are not, unknown where it does not record it; **axis** attribute: the undirected direction of the space's long axis as its stall lines mark it, taken from those lines and never from a parked vehicle, a design default or a template; a direction and its opposite are the same axis and either may be written, and the reading is already undirected: of the two, the one whose second (y) component is positive, or, where that component is zero, whose first (x) component is positive; it is written at any length and read normalised as `st.lane_direction` is, a zero vector reading unknown **Not a stand-in for:** whether the markings are an official marking indicating the angle of parking — the space's outline or geometry, its **angle** and its **axis** never show it, only **angle_marking** does; the **axis** is read as the angle of parking the markings indicate only where **angle_marking** is true | general |
| `st.curb_zone` | a signed or marked length of curb; **kind** ∈ {passenger_loading, freight_loading, tour_bus_loading, restricted_parking, bus_stop, taxicab_stand, fire_lane, no_stopping, no_parking}; **colour** ∈ {red, yellow, white, blue, gray, none} where the curb itself is painted | general (curb colour code and kind `tour_bus_loading`: local) |
| `st.transit_stop` | a bus stop, bench, shelter or platform for public transport passengers | general |
| `st.safety_zone` | an area within the highway marked off for pedestrians only | general |
| `st.pedestrian_grade_separation` | a pedestrian tunnel or overpass at a point on the highway | general |
| `st.fire_hydrant` | a fire hydrant beside the roadway | general |
| `st.fire_station_entrance` | the driveway entrance of a fire station | general |
| `st.roundabout` | a rotary intersection: its central island, its circulatory roadway and its entry and exit approaches | general |
| `st.lane_width` | width of a lane at a point | general |
| `st.region_geometry` | the reference point and the boundary polygon of a structure region in the world frame, and the ground distance from a road user's body outline to it (zero when they overlap); where the outline is not recorded, every such distance is unknown **Not a stand-in for:** occupancy — a footprint inside a boundary is `rel.occupies`, which a source may observe without geometry | general |
| `st.obstruction` | a physical object on or beside the roadway that is not a road user; **kind** ∈ {debris, excavation, hose, barrier, stalled_vehicle_wreckage, sidewalk_fixture, mail_drop_box, sidewalk_elevator_or_chute, other}, a `sidewalk_elevator_or_chute` being a freight lift or chute opening in the sidewalk; **protected** attribute, for a hose: a cover or a bridge is laid over it so that a vehicle passes over the cover and not the hose, false where the hose lies bare, unknown where the source does not record it **Not a stand-in for:** a road user, or a temporary traffic control device (`dev.temporary_traffic_control`); nor is a hose's being protected read from its kind — only the **protected** attribute says | general |
| `st.impassable_section` | a section of a sidewalk, or of the ground beside a roadway where a pedestrian would walk, that a pedestrian cannot traverse on foot (missing, broken, closed or too narrow), as the source records it, as a region **Not a stand-in for:** an obstruction (`st.obstruction`) — no object need be there, and an object on a sidewalk does not by itself make the section impassable; or the absence of a sidewalk — a place with no sidewalk mapped is not thereby impassable | general |
| `rel.occupies` | a road user's footprint overlaps a lane / region (roadway, shoulder, sidewalk, intersection, crosswalk, stop line, safety zone, bicycle lane, median, alley, curb zone, controlled-access lane, structure) | general |

## 4. Control devices (`dev`) — class, state, position, governance

| id | contract | scope |
|---|---|---|
| `dev.traffic_signal` | a signal head; **state** ∈ {circular_green, circular_yellow, circular_red, green_arrow(dir), yellow_arrow(dir), red_arrow(dir), flashing_yellow_arrow(dir), flashing_red, flashing_yellow, dark, unknown} with dir ∈ {left, right, straight, u_turn}; several states may be displayed at once; **uncovered** attribute for an installed head whose faces are not covered | general (state `flashing_yellow_arrow`: local) |
| `dev.pedestrian_signal` | a pedestrian head; **state** ∈ {walk, dont_walk_flashing, dont_walk_steady, dark}; **countdown** attribute when a timer is displayed | general (countdown semantics: local) |
| `dev.lane_control_signal` | an overhead per-lane signal; **state** ∈ {green_down_arrow, red_x, yellow_x, yellow_arrow(dir), dark} | local |
| `dev.speed_limit_beacon` | a pair or more of yellow lamps mounted with a speed sign, flashing alternately when the sign's limit is in effect; **flashing** attribute | local |
| `dev.crossing_warning_signal` | a signal device at a pedestrian or school crossing that warns of persons crossing; **active** attribute | general |
| `dev.stop_sign` | regulatory sign requiring a full halt | general |
| `dev.yield_sign` | regulatory sign requiring yielding without a mandatory halt | general |
| `dev.speed_limit_sign` | sign stating a maximum or minimum speed, with value and unit; **kind** ∈ {maximum, minimum, structure_maximum, zone} | general |
| `dev.regulatory_sign` | a point regulation by catalogue **code**, with the same structured **conditions** attribute as `dev.zone_sign`, read as that row says (unconditional when empty, unknown when absent), where the sign states hours, days, a duration or a class: no_left_turn, no_right_turn, no_u_turn, no_straight, one_way, keep_right, do_not_enter, wrong_way, no_stopping, no_standing, no_parking, angle_parking, lane_use_arrow, turn_course_marker, right_turn_only, entrance, exit, closed_to_traffic, exempt_crossing, abandoned_crossing, shoulder_use_permitted, bicycles_prohibited, bicycle_ebike_escooter_prohibited, pedestrians_prohibited, nonmotorized_prohibited, motor_vehicles_prohibited, truck_route, no_trucks, lamps_on, parking_permitted; **legend_angle** attribute, on an `angle_parking` sign: the angle of parking its legend states, in degrees, or `none` where the source confirms that the legend states no angle; where the source does not record it, which angle the legend states is unknown, never `none` **Not a stand-in for:** a manoeuvre or a road feature — a prohibition sign is a condition, a warning sign is not the hazard it warns of, and a sign is not a signal; a `lamps_on` sign directs the lamps of the vehicles in the regions it governs to be lit, and is not the lamps being lit (`sig.headlamp`); a `parking_permitted` sign permits parking in the regions it governs, under its conditions, and is not the absence of a prohibition — where no such sign governs, nothing is permitted by it; a `bicycle_ebike_escooter_prohibited` sign prohibits riding a bicycle, an electric bicycle or an electric scooter (`ru.bicycle`, `ru.electric_bicycle`, `ru.electric_scooter`), exactly these three classes and no other, and a `bicycles_prohibited` sign concerns bicycles alone | general (`shoulder_use_permitted`, `exempt_crossing`, `truck_route`: local) |
| `dev.zone_sign` | a sign that begins or ends a signed zone along the road; **kind** ∈ {school, school_crossing, pedestrian_safety, temporary_traffic_control, no_passing, high_occupancy_lane, heavy_vehicle_lane, speed_zone, narrow_highway, hazardous_place, parking_restricted, trail}; **end** attribute; **conditions** attribute: a structured reading of the sign's legend — a list of time windows (a set of weekdays or a calendar class such as school days, a start and an end time of day), a minimum occupancy, a duration limit, a vehicle class, or a "when children present" flag; a legend read with no restriction is the empty set (unconditional), a legend not read is absent (every condition unknown); a formula reads the duration limit, of this sign's or a regulatory sign's conditions, as the measure `dev_zone_sign_duration_limit` (s), unknown where the legend is not read or states no duration **Not a stand-in for:** whether the condition holds now — that is `prim.conditions_hold` | general (kinds `school_crossing`, `pedestrian_safety`, `high_occupancy_lane`: local) |
| `dev.railway_signal_or_gate` | the devices at a level crossing; **lights** ∈ {flashing, dark}; **gate** ∈ {up, lowering, down, raising, none}; **bell** attribute | general |
| `dev.temporary_traffic_control` | cones, barricades, temporary signs and flashers marking works, a closure or an obstruction | general |
| `dev.human_direction` | a person directing traffic and the direction given; **role** ∈ {police_officer, flagger, school_crossing_guard, railroad_flagger, fire_official}, a `fire_official` being the fire department official in command at the scene of a fire; **indication** ∈ {stop, proceed, slow, turn(dir)} **Not a stand-in for:** a permission or a consent the role may give — what was directed is the **indication**, and a role is never read as another (a fire official is no police officer) | general |
| `dev.school_bus_signal` | the school bus's own devices; **red_flashing**, **amber_flashing**, **stop_arm** attributes | general |
| `dev.governs` | relation: the travel regions whose traffic the device controls — a lane, reserved lane, turn lane, centre turn lane, bicycle lane or path, roadway, one-way roadway or shoulder — or an intersection, read as control of the junction itself and of nothing else (no closure to the lanes that enter it); never a highway, a controlled-access region or a region no vehicle travels in. Unknown where the source does not observe what a device governs. A source may list only the carriers a device governs and never the intersection, so control of an intersection is read through a governed carrier that enters it (`st.lane_enters`); a rule reads a device's governance of the intersection itself only beside that reading, never in its place **Not a stand-in for:** a position — the region a device governs is not where a halt is required | general |
| `dev.governs_sidewalk` | relation: the sidewalk regions (`st.sidewalk`) a regulatory sign (`dev.regulatory_sign`) whose code is a riding prohibition (`bicycles_prohibited`, `bicycle_ebike_escooter_prohibited`) governs, as the source records it for that sign; recorded only for such a sign and only of a sidewalk. Where the source records the sidewalks a sign governs, its record is complete and the sign governs no sidewalk it leaves out; where it does not record them, whether the sign governs a sidewalk is unknown. Never inferred from the sign's position, from distance, or from the travel regions the sign governs (`dev.governs`) **Not a stand-in for:** `dev.governs` — a sign's control of the traffic of travel regions; or nearness — a sidewalk beside a sign is not thereby governed by it | general |
| `dev.governs_parking_space` | relation: the parking spaces (`st.parking_space`) an `angle_parking` regulatory sign (`dev.regulatory_sign`) governs, as the source records it for that sign; recorded only for such a sign and only of a parking space. Where the source records the parking spaces a sign governs, its record is complete and the sign governs no space it leaves out; where it does not record them, whether the sign governs a space is unknown. Never inferred from the sign's position, from distance, or from the travel regions the sign governs (`dev.governs`) **Not a stand-in for:** `dev.governs` — a sign's control of the traffic of travel regions; or nearness — a space beside a sign is not thereby governed by it | general |
| `dev.position` | location of the device head / sign face **Not a stand-in for:** a stop line or a crossing — the distance to a signal head is a different quantity from the distance to the line or region | general |
| `dev.inoperative` | a signal head installed and uncovered but showing no valid indication | general |

## 5. Signals emitted by road users (`sig`)

| id | contract | scope |
|---|---|---|
| `sig.turn_indicator` | the turn indicator **state** ∈ {off, left, right}: neither indicator lit, or the left or the right one **Not a stand-in for:** the turn or lane change itself — the indicator is the signal that precedes a manoeuvre, judged separately from it | general |
| `sig.brake_lamp` | brake lamps lit **Not a stand-in for:** a halt or a deceleration — a lamp is an actuation; the motion state is `kin.velocity` / `kin.accel_longitudinal` | general |
| `sig.hazard` | both indicators flashing together | general |
| `sig.headlamp` | headlamp **state** ∈ {off, low_beam, high_beam} | general |
| `sig.position_lamp` | position, parking, cowl or tail lamps lit (the lamps a vehicle shows without its headlamps) | general |
| `sig.compression_brake` | an engine compression brake sounding (audible) | general |
| `sig.reverse_lamp` | reversing lamps lit | general |
| `sig.warning_lamp` | a warning lamp lit; **colour** ∈ {red, blue, amber, white}, **mode** ∈ {flashing, rotating, steady}, **facing** ∈ {front, rear, side}; a formula names a colour, a colour and a mode, or a colour, a mode and a facing, and holds where one lit lamp shows every value named **Not a stand-in for:** an audible warning | general (steady blue rear lamps and amber-lamp roles: local) |
| `sig.siren` | a siren, whistle or bell sounding (audible; a warning lamp is not the sound — the two are separable and a road user may show one without the other) | general |
| `sig.horn` | an ordinary horn or a rail vehicle's horn or bell sounding (audible; no visible state stands in for it) **Not a stand-in for:** a siren | general |
| `sig.hand_signal` | a driver's or rider's arm signal; **meaning** ∈ {no_signal, left, right, stop_or_slow, re_enter}: no arm signal given, or the meaning of the one given | general |
| `sig.door_open` | a door open; **side** ∈ {traffic, curb} | general |

## 6. Environment (`env`)

| id | contract | scope |
|---|---|---|
| `env.darkness` | insufficient natural light; the boundary relative to sunset and sunrise is a reading parameter | general |
| `env.precipitation` | rain or snow falling | general |
| `env.wet_road` | road surface wet, standing water | general |
| `env.ice_or_snow` | road surface icy or snow-covered | general |
| `env.visibility` | visibility distance (fog, dust, smoke) | general |
| `env.civil_time` | the local calendar time of the observation: date, weekday, time of day (from the recording's metadata, not from the scene) **Not a stand-in for:** `kin.time`, which orders observations within a trace and carries no date | general |

Weather and surface conditions are what a speed or care standard is judged against; every one of
them is observable and is kept whether or not a single clause names it. Civil time is what a
posted hours-of-effect condition is judged against; where no calendar time is recorded, every
specification that reads it reports unknown.

## 7. Relations between road users (`rel`)

| id | contract | scope |
|---|---|---|
| `rel.centre_distance` | Euclidean ground-plane distance between reference points **Not a stand-in for:** a clearance between bodies or an order of arrival — centre-to-centre overstates a clearance by about the two half-extents, and proximity says nothing about who reached a boundary first | general |
| `rel.surface_gap` | distance between the nearest points of two bodies, each body's footprint read with its own heading and extent: zero when they touch or overlap, never negative; its longitudinal and lateral components are the lengths of the vector between those nearest points along and across the subject's heading, and a read without a component is the distance; a supplied gap with a negative component reads unknown, never as its magnitude, as zero or as contact | general |
| `rel.ahead_behind_in_lane` | a is ahead of / behind b in the same lane, along the lane direction | general |
| `rel.longitudinal_overlap` | the bodies overlap along the subject's heading (side by side): the length the two footprints' projections on that axis share, negative for the gap between the projections; a projection, so neither a contact nor a distance between the bodies | general |
| `rel.oncoming` | headings opposed and closing: the cosine of the angle between the headings is below the negative of its tolerance, which is the cosine of the largest angle off exactly opposed allowed, a ratio between -1 and 1 **Not a stand-in for:** the direction a road user approaches from — that is read through the carrier it approaches through, any carrier `st.lane_enters` admits (a lane or a kind refining it, or a roadway, one-way roadway, shoulder or bicycle lane or path recorded as a directed approach segment), whose entrance end is the intersection, and through that carrier's direction (`st.lane_direction`) at the same instant; where that evidence is unobserved, the direction is unknown, never a reason a duty does not arise. A turn can make the current headings cease to satisfy this relation while the vehicle's approach direction remains unchanged. | general |
| `rel.same_direction` | headings aligned: the cosine of the angle between the headings is above its tolerance, which is the cosine of the largest angle allowed, a ratio between -1 and 1 | general |
| `rel.bearing` | direction of b from a in a's frame (for "on the right of", "immediately to the rear") | general |
| `rel.contact` | the bodies of two road users, or a road user and a structure, touch or overlap (a collision); a formula reads two road users as `rel_contact`, and a road user and a structure whose outline is an object, an obstruction (`st.obstruction`) or a fire hydrant (`st.fire_hydrant`), as `rel_contact_structure`, which holds where the road user's body (its position, heading and extent) touches or overlaps the region's outline (`st.region_geometry`) and is unknown where either is not observed or the region is not decidedly of those kinds, never read from a reference point **Not a stand-in for:** a near miss; bodies that do not touch or overlap are not in contact; a footprint inside a region as the source records it is occupancy (`rel.occupies`). | general |
| `rel.visible` | b is visible from a: an unobstructed line of sight from a's reference point to b's body, as the source tests it (a ray cast, an occlusion test, an annotator's judgement) **Not a stand-in for:** a distance, the sight distance of a place (`st.sight_distance`) — what could be seen from or at a place, whether or not any road user is there, is that atom, the clarity of the air (`env.visibility`), or a lamp being lit — a visible vehicle may show no lamp and a lit lamp may be hidden | general |

Computed from kinematics; listed because traffic language names them directly and a source may
supply them measured rather than derived. `rel.visible` is the exception: it depends on what
stands between two bodies, which no kinematics carry, so only a source supplies it and it is
never computed.

## 8. Judgement standards — not atoms; how a rule gives them a concrete meaning

Traffic law states many duties as standards: a manoeuvre made "with safety", a speed that is
"reasonable", a distance that is "practicable", a vehicle "so close as to be a hazard", a stop
"when necessary". No scene contains a reasonableness. A specification that bottoms out in such a
word detects nothing, so a standard is never an atom and never a leaf of a rule.

**Operationalization.** The plan bounds every standard in a clause by concepts and primitives
with parameters the reading sets, and records an *operationalization claim*: the standard's
words, the concepts, the parameters, and the engineering convention their values come from (a
headway convention, a gap-acceptance convention, a stopping-distance model, a sight-distance
model). The
harness rejects a node that maps a standard to nothing. The claim bounds the standard; it never
replaces an observable the clause states outright. The claim records the specification's
operationalization; it does not determine a recording's label. Labels involving judgement calls are
confirmed independently under operator-reviewed, frozen parameters before they drive repair.

**Two kinds of rule follow.** Where the standard qualifies an otherwise concrete duty (a yield
that is owed when the other vehicle is "so close as to be a hazard"), the operationalization is a
bound on one element and the rule is the law's own rule. Where the standard *is* the duty ("due
care", "careless", "reasonable speed"), any operationalization is a policy choice, not a reading
of the text: such a rule is marked **surrogate**, its verdicts are evidence and not a legal
conclusion, and it is evaluated separately.

**One kind of standard has only a surrogate.** A standard about the driver's state of mind —
care, attention, intent, knowledge — is not observable (§9): any operationalization of it is a
surrogate, whatever concepts bound it. A declared intention (§9) is not of this kind: it is a fact
the trace supplies, not an operationalization of a standard.

## 9. Not atoms

**Legal region classes** — categories a jurisdiction defines administratively and that are not
visible on the road: a district defined by its buildings, an urban or rural area, a city or town
limit, a mountain or canyon highway, premises to which the public has access, the designation of a
highway as a priority road, whether school is in session and its hours, the hours a signed
restriction is in effect when the sign only refers to them. These enter a formalization only as
**reading assumptions** declared per map or per trace, never as atoms a rule reads from a scene.
Where the same category is *also* marked on the road by a sign (`dev.zone_sign`), the sign is the
atom and the category is not.

**Declared intentions** — where the words state that a road user intends, or is preparing, to
turn, the span is carried by a declared intention of that road user at the region the words name:
a fact the trace supplies, under an `int.*` id the plan declares with its meaning, never an act in
a window ahead nor a signal (a signal "of intention" is the signal, `sig.turn_indicator`). The act
the words also name ("is making …") is read by its manoeuvre concept, and the two are joined as the
words join them. What an id covers (an intention to turn, a preparation for a turn) is its
meaning; when it begins and ends is the source's declaration. A declared intention states, at each
scene, the source's declaration current at that scene for one road user at one target region:
- it is **true** where the source's current plan for that road user includes, at that target, what
  the id means;
- it is **false** where the source's current plan decides that what the id means does not hold at
  that target: another manoeuvre, passing through, a manoeuvre cancelled, or one the plan has
  completed;
- an **id is left out** of the record's values wherever the source's plan does not decide its
  meaning, even when other ids of the same pair are listed: what a plan does not mention is
  unknown, never false;
- the **pair is absent** where the source has no current plan for that road user at that target,
  or does not know it.

The value follows the source's plan, never the road user's motion: a manoeuvre that is blocked,
delayed or under way stays true while the plan still holds it. A source never writes false for a
road user whose plan it does not know. A change of declaration takes effect from the scene that
carries it, and a rule reads a declaration only at the observation it judges or before it, so a
later change never alters an earlier verdict or erases an obligation already triggered.

**Declared facts** — where the words make a trigger, subject, condition or exception turn on a
fact that no atom observes, no road-user class decides and a scene source can confirm, the span is
carried by a declared fact: a fact the trace supplies under a `fact.*` id the plan declares with its
meaning, its kind, its subjects, and the record on which a source declares it true and the one on
which it declares it false. One mechanism serves two families, kept apart by kind and subjects. A **temporary fact about
road users** is bound to one road user, an ordered pair of road users (in the order the meaning
names them) or a road user and a region, over the time the source declares it; its kind is a role
or a duty the road user is performing at the time (`duty`), a permit, licence or privilege it holds
(`permit`), an assignment the source holds for it (`assignment`), its membership of an organized
group of road users travelling together (`membership`), a consent one road user has given another
(`consent`), or an emergency its conduct answers to (`emergency`). A **map record's fact about a
region** (`map_record`) is bound to one region alone and is what the source's map records state of
it, such as the named segment of a way it lies on: the same at every scene that declares it,
declared false only for a region the records place outside, a region a boundary of the records
crosses split there or left undeclared, and never derived from a sign. A declared fact is never a
physical state of a road user or its equipment (an atom carries it), a road user's class or legal
identity (a class or an aggregate), a legal region class or a time (an assumption), an intention (a
declared intention) or conduct or a feature an atom observes. A declared fact states, at each scene, the source's declaration for those subjects:
it is **true** where the source holds what `true_when` states; it is **false** only where the source
holds a record that excludes the fact, as `false_when` states, never because no record states it; it
is **absent** everywhere else, and the rule is unknown wherever the fact can change its verdict and
decided wherever it cannot. A declared fact is carried only where the words name one, never added as
a condition they do not state. Where the words make a duty or a privilege turn on a road user's class
and what it displays (its warning lamps, its siren), the rule reads the class and the displayed
signal and declares no fact; where they make an exception or a condition turn on the road user's own
duty, task, permit or emergency, the declared fact carries those words and nothing the road user
displays stands for it: a lit lamp is never read as a duty performed or an emergency.

**Purpose, perception and imminent movement** — why a vehicle is stopped (loading, waiting for a
pedestrian, receiving passengers), what a driver perceived, knew or ascertained, a movement it is
about to make. These are not observable, and a rule is a check of conduct on a trace, so a span
that turns on one is read through the conduct or the outcome it governs: an imminent movement
("about to …") by the movement it leads to, a duty to perceive, ascertain or make sure by the outcome the check is there to secure
(the movement made with the clearances the reading sets), a purpose by the conduct it explains.
Who or what controls a vehicle — a person at the controls, an automated driving system, no one —
is not observable either: "drives", "operates" and "the driver" are read through the vehicle's
controlled motion, a vehicle moving on the road is taken to be driven, and the duty binds that
vehicle's conduct whoever or whatever controls it. Where the words offer observable evidence themselves, the rule reads that evidence (what was in an
actual road user's line of sight is `rel.visible`; what could be seen from or at a place is
`st.sight_distance`). Each such reading is disclosed on its span as a narrowing of kind
`observable_reading` with its category (`intention`, `perception`, `status`, `purpose`, `agency`): it is a
reading of the words, not an approximation by a neighbouring atom, and never an assumption or a
gap. A state of mind that shows in no conduct is outside what a trace can check, and a rule never
assumes one. The condition of a road user (disabled, unable to be moved), a role or duty a person
holds, an emergency, and what the law requires of a road user are none of these kinds: they are
never an `observable_reading`, as they are never an assumption; a role or duty and an emergency are
carried by a declared fact. A reading that would exempt the
subject from a duty is never carried by a signal the subject itself chooses to emit (its hazard or
warning lamps, a hand signal, a turn indicator, its horn): such a signal shows what the subject
displays, not the state or purpose the exemption turns on. A road user's class, as the source
declares it, may evidence the identity its contract names, with the fixed conditions of
qualification its contract carries and, of equipment, only what its contract explicitly includes. A
class never shows that a lamp is in use now, that the road user is responding to an emergency or
performing an official duty now, or that an equipment requirement listed apart and not carried by
its contract is met; operation and conduct (being operated in a manner the law provides) are dynamic
and are never presumed from a class. Whether a lamp is in use is observed in the trace; that the
road user is responding to an emergency or performing an official duty is carried by a declared fact
where the words make the rule turn on it; and an equipment requirement follows the paragraph on
equipment under the identity of a road user: where it also qualifies an observable act, the act is
checked under an approved abstraction and reported as partial coverage, or the qualification stays
unresolved. The control state of
a vehicle — engine running, parking brake set, gear, throttle, service brake — is not of this
kind: it is observed on an instrumented vehicle and carried by the control-state atoms of §2,
under the `subject` capability where only the subject's vehicle is instrumented.

**Legal status of a feature on the road** — that a sign, a signal, a marking, an opening or a
crossing is official, posted or designated by an authority. The feature's presence on the road is
the observable evidence of that status: a rule reads the feature and presumes the status (an
`observable_reading` of category `status`). A category that no feature on the road displays is a
legal region class (above).

**Identity of a road user and the legal kind it carries** — what kind of road user a vehicle is in
law, where a posted definition defines the kind by the vehicle's design or capacity, its service,
its designation, its use or its status. This is an approved reading with a trust boundary. The
road-user classes are the scene source's declaration: the source decides which classes a road user
carries, on evidence of its own (markings or livery it reads, the vehicle's configuration, an
identity the scenario's author assigns), lists every class it so decides, and marks unobserved a
class it cannot decide for a road user. The pipeline neither infers a class from appearance nor
verifies the source's evidence, and checks no owner, seat count, payment or trip fact. The reading:
- **Inclusion.** A class carries a legal kind only where its contract states a legal
  classification: that the source lists the class for a road user only where it confirms that the
  road user is of that kind under a definition the contract cites. Such a class carries each cited
  definition in full, as the source's declaration: every condition of that definition that makes a
  road user of the kind (its design and capacity, its use, its service, its status) holds of a
  member of the class. It carries automatically only the definitions its contract cites. A
  definition it does not cite is never carried over because its term is the same or alike: whether
  the class falls under it is decided from that definition's own words and the meaning of the
  class's contract, a judgment about the class and the definition, never a new check of a road
  user's appearance or of the source's evidence. A condition of equipment holds of a member only
  where the class's contract explicitly includes that equipment; an equipment requirement listed
  apart and not carried by the contract is never met by the class. A condition of what the road user
  is doing in the scene is not identity: operation and conduct (being operated in a manner the law
  provides, a lamp in use, an emergency answered or an official duty performed now) are dynamic, are
  never presumed from a class, and the rule carries them (context is not membership). The legal
  classification and its citation, quoted, are the proof; a class's name, or a resemblance of its
  name or of what its contract describes to the defined term, never is.
- **Coverage.** A legal classification proves membership in one direction only: a member of the
  class is of the kind. That a road user without the class is not of the kind follows only where the
  contract also states that the source lists the class for every road user it confirms is of that
  kind under the cited definition, and marks the class unobserved for a road user it cannot decide.
  Only then does that definition admit the members of other classes only as members of the classes
  that carry it (`covered`); without that statement the absence of the class proves nothing, and the
  other classes are decided by the words and their own contracts. Where the source does not observe
  a class of the aggregate (included or unresolved) for a road user, its membership stays unknown.
- A class whose legal classification is of a narrower kind (the kind qualified by a service, a use
  or a designation) carries the narrower kind only, never the broader one: it is of the broader kind
  only where the definition's words reach it on what its own contract carries, or where the source
  also lists, for the same road user, a class whose legal classification is of the broader kind. A
  contract may state that the source lists a second class only where it confirms that one as well;
  no class implies another.
- For every other class, and for every definition a legal classification does not cite, the reading
  supplies nothing: a physical property the words state (a capacity, a weight, a wheel count, a
  speed, a propulsion), a condition that the road user be equipped or operated in a certain manner,
  and a condition of conduct are decided by the words and what the class's contract describes (the
  meaning of the class, not a check of a road user), and a class whose contract does not explicitly
  carry them stays unresolved. The reading never separates the kinds one class's contract joins.
- The risk of a wrong class stays with the source: a road user it misclassifies (a vehicle used for
  hire that it lists only as an ordinary car, a vehicle it lists as of a kind that is not) can make
  a rule miss a violation or exempt a road user wrongly. Core does not prove a class from the
  definitions; it evaluates the classes the source declares.

The pipeline does not independently assess whether equipment meets statutory specifications. A
source-declared class carries identity-defining equipment conditions only where its contract says
so; an unobserved class remains unknown. An observable act, such as using a lamp, is evaluated from
the trace. Where an equipment specification also qualifies that act, omitting the specification
requires an approved scope abstraction and an explicit partial-coverage report. Without that
approval, the qualification remains unresolved; it is never silently treated as satisfied.

**A clearly marked marking** — the words "clearly marked" said of a stop line, of lanes, or of an
area of works on the road. The marking's presence as the scene records it is the evidence, and its
clarity or wear is not modelled (an `observable_reading` of category `status`): a stop line the
scene represents (`st.stop_line`); lanes whose dividing marking the scene records as a painted line
(`st.lane_marking` of type broken, solid, double_solid, solid_broken or dotted on the side the lanes
share) — a `curb` is no painted marking, `none` is no marking, and a marking the scene does not
observe is not shown to be marked (unknown); an area of works marked by a device or a sign placed
for it that the scene records as governing the travel region being judged
(`dev.temporary_traffic_control` or a sign, through `dev.governs`) — a device elsewhere in the
scene, or one whose governed regions are not observed, is no evidence that the region is marked
(unknown where the association is unobserved). The geometry of a lane or of a work area on the map,
with no such recorded marking or device, is not a marking and does not satisfy the words. This
reading never relaxes which stopping point governs, the action and its timing, or the road users to
yield to.

**A state of the road surface marked by a barrier or a warning** — where words condition a duty on a
state of the road surface (pavement newly laid or repaired) together with a barrier or a warning
placed for it, the state is read through that barrier or warning: a rule reads the barrier or the
warning the scene represents (`dev.temporary_traffic_control`, or a sign) and the region it closes or
marks, and presumes the state there (an `observable_reading` of category `status`). The state is
never assumed without it: not from the look of the surface, from works nearby or from a device placed
for something else. This reading never relaxes which place governs, the act, or the road users the
duty concerns.

**The posture of a hand signal** — which arm gives the signal, on which side of the vehicle, and in
which direction it is extended. A hand signal is read by its meaning (`sig.hand_signal`); the arm,
the side and the direction of the extension are not modelled. Words that prescribe or permit a
posture for a meaning are carried as that meaning: the signal given is read as the meaning the
words assign to its posture. This reading never relaxes whether a signal is given, which meaning it
has, or when it is given relative to the manoeuvre it announces.

**Lawfulness of another road user's conduct** ("pedestrians lawfully within the crosswalk", "a
person lawfully riding") — a reference to another rule's verdict, expressed by rule composition in
Core, not by an atom.

**The exceptions a defined act carries** — where a rule uses a word the corpus defines for coming
to rest or remaining at rest (to stop, to stand, to park, and the like), the exceptions that
definition states are carried with the word, whole. An exception for a halt made to avoid conflict
with other traffic is read through the conflict between the subject and the other road users: the
concepts that relate the subject's path at that halt to another road user's, whichever lane that
road user is in, never only a queue ahead in the subject's own lane and never the halt's duration
alone. Words that except a halt made in compliance with law, or with the directions of an officer
or a device, are carried by rule composition over the rule set; where that composition needs a
rule outside the corpus, the words stay a scope item for the operator, and the composition is never
reported complete. This reading relaxes no check of
the action, the place, its time or the road users it concerns.

**An act due at a place before an event: the approach** — where words require an act (a halt, a
yield) at a named place (a stop line, a crosswalk, the edge of an intersection) before an event the
words name (an entry into an intersection, the passing of a mark), and state no occurrence, timing
or exception of their own, the act is owed on the approach that leads to that event. The approach is
identified by the map and the event's target, never by the road user's motion: a road user's
approach to an intersection is a carrier it occupies whose entrance end is that intersection
(`st.lane_enters`), and a mark governs that approach where it is recorded as marking that carrier
(`st.entrance_of`); where the road user occupies several carriers entering that intersection, the
duty is owed through each of them, as `st.lane_enters` states. Below, the mark is the named place,
and where the place is the edge of the
intersection it is that carrier's entrance end. The approach starts at the last observation before
the event at which the road user, on a carrier the mark is recorded as marking, is outside the
mark's stopping zone upstream: off the mark, short of it, and farther from it than the stop-point
tolerance; where several marks of the place's kind mark that carrier, outside the zone of each and
short of each. The side of the mark is read along that carrier's designated
direction (`st.lane_direction`, by the sign of `prim.region_offset_along`), never along the road
user's heading; every distance to the mark, the tolerance and the zone's bound included, is the
distance between the road user's body and the mark (`st.region_geometry`). The stop-point tolerance is
one parameter the reading sets: the bound within which the act counts at the place is the bound
beyond which the road user is outside the zone, and a halt that lies within measurement noise of
that bound may be read on either side of it, the expected limit of this approximation. Where the
words place the act before the road user enters a region, a halt at which its footprint already
overlaps that region (`rel.occupies`) is not at the place, and the stop-point tolerance applies
outside that region only. A search for
the act runs back from the event and ends only at that approach start or at the previous occurrence
of the same event for the same road user and the same place; nothing else ends it: not another
intersection or mark, not the start of the recording, not a first observation, not a distance
travelled. Each occurrence of the event owes its own act: an act done before the previous
occurrence of the same event for the same road user and place discharged that occurrence, not the
new one; an entry and the passing of a mark are different events, each with its own occurrences. Only an observed exit from the stopping zone upstream begins a new approach, so a road
user that leaves the zone upstream and comes back owes the act again; crossing the mark, moving on
toward the event, a change of carrier or a lateral move within the same entry, a reverse that stays
within the zone, and speed noise begin no new approach, and none of them loses an act already done for the event still
to come.
Where the search finds the act, the duty is met; where it reaches either end without the act, the
duty is violated; only where it reaches neither end without finding the act is the duty unknown.
Whether the event occurred at an observation is read from that observation and the one before it: it
is unknown, never absent, where the one before does not show the road user's place relative to the
mark through its carrier, because there is no earlier observation of the road user (its recording
begins at that observation), it is on no mapped carrier, or it is on a carrier whose association
with the mark is not observed; where the one before shows it on a carrier the mark is observed not
to mark, or already within the region the event enters, it is not that mark's event. Which mark
governs is read through the same carrier: where a mark's association with that carrier is not
observed, whether the mark governs is unknown; where the mark's entrances are observed, so that its
list is complete, and exclude that carrier, the mark does not govern that approach, the duty's place
is read from the other places the words list, in their order, and the duty is not unknown on that
ground. Missing evidence makes the duty unknown only where the verdict depends on it: a recorded act at a place known
to govern, a duty that does not arise, and an association the source excludes are decided
whatever the missing fact would be; where the verdict does turn on a missing direction, association
or observation, the duty is unknown, never decided from a distance alone or from the absence of a
record. Words that state their own occurrence, timing or exception govern instead, written with
their own window. This reading fixes the time of a duty, a distinction of the driving task: it is a
modelling convention the operator adopts for the whole corpus, not an abstraction of an incidental
word, and it relaxes no check of which place governs, the act, or the road users it concerns.

**Concepts** (`drv`) — manoeuvres, states of motion, road configurations and relations between
road users over time (a stop, a turn, a pass, a following gap, a laned roadway) are not atoms.
They are concept nodes the pipeline defines over atoms, primitives and other concepts, each with a
contract of its own, accepted like a rule and called by id (`drv.<family>.<name>`); a rule never
rebuilds one inline.

**Dataset fields** — any edge label, trigger region, render distance, band label or node name of
a particular scene-graph format. These are how a source grounds an atom; they belong in the
adapter and its manifest, never in a rule.

**Approved abstractions with partial coverage** — the kinds of words the operator has approved a
rule to omit across the corpus and has designated as a limitation to be signalled downstream with
each verdict; each is under an id. A rule that omits words under one declares it on the span whose
words it omits, as a narrowing of kind `abstraction` naming the id, and names the id in its
`abstractions`. Such a rule is partial coverage: each verdict it gives, and each verdict of a rule
that reads it, is reported as a verdict on the conduct the rule checks under that abstraction, never
as full compliance with the law. A scope reading the operator has approved within the task scope
without that designation — the readings above of a clearly marked marking, of a state of the road
surface through its barrier or warning, and of the posture of a hand signal — is not an entry here:
it is written once in this section and disclosed as the rule's reading, and the rule's verdicts
under it are complete within the approved task scope, which is not a verification of every qualifier
the words state. No abstraction or scope reading relaxes a check of the act, the place, its time or
the road users the duty concerns; words of a kind neither listed here nor read in this section are
carried, or stay a gap or unresolved.

| id | scope |
|---|---|
| `equipment_specification_of_observed_use` | where a statutory equipment specification qualifies an observed act of using that equipment, the rule checks the act (e.g. that a lamp is in use) and omits whether the equipment meets the specification. It never omits the subject's identity, the timing, the place, or the driving conduct required; an unobserved class stays unknown. A rule that uses it is partial coverage. |

## 10. Primitives (`prim`) — computations the formula language cannot express

A primitive is a geometric computation over atoms with no legal word in it, defined once in Core
with its parameters exposed. A concept or a rule calls it by id; the set is closed, and a need
for another is a gap for the operator, never a definition written during a run.

`heading_since` (`Term.headingSince`) is a construct of the formula language, not an atom an
adapter supplies and not a primitive: the signed heading change of a road user since a formula
last became true, integrated from `kin.yaw_rate` with a step bound. It recognises no manoeuvre;
the formula that marks the onset does. `prim.heading_change`, over a fixed window behind each
observation, is not a stand-in for it.

| id | contract | parameters | result unit | parameter units |
|---|---|---|---|---|
| `prim.heading_change` | the signed heading change (degrees, left positive) of a road user over the window behind the observation, integrated from `kin.yaw_rate`; unknown where the window is truncated, sampled too sparsely, or a yaw rate is missing | the window length (time) | deg | s |
| `prim.closest_approach_within` | under constant velocities, the centres of two road users approach each other at some time between the observation and the horizon **Not a stand-in for:** contact between bodies, the clearance between bodies, or the danger of a crash — it is computed from the centres under constant velocities, and alone establishes none of them | the horizon (time) | boolean | s |
| `prim.closest_approach_time` | the time from the observation at which the two centres are closest, under constant velocities; undefined when they do not approach within the horizon **Not a stand-in for:** contact between bodies, the clearance between bodies, or the danger of a crash — it is computed from the centres under constant velocities, and alone establishes none of them | the horizon (time) | s | s |
| `prim.closest_approach_distance` | the centre distance at that closest approach; undefined when they do not approach within the horizon **Not a stand-in for:** contact between bodies, the clearance between bodies, or the danger of a crash — it is computed from the centres under constant velocities, and alone establishes none of them | the horizon (time) | m | s |
| `prim.conditions_hold` | the structured conditions of a device (`dev.zone_sign`, `dev.regulatory_sign`) hold at the observation for a road user: `env.civil_time` falls in one of its time windows on one of its days (a calendar class is an assumption), and any occupancy or class condition is met | — | boolean | — |
| `prim.region_lateral_offset` | the signed lateral offset (m, left positive) of a structure region from a road user: the component, perpendicular to the road user's heading, of the vector from its reference point to the point of the region's boundary nearest that reference point; zero where the reference point lies inside the region; where several boundary points are equally nearest, their common component, and undefined where their components differ; unknown where the position, the heading or the boundary is absent | — | m | — |
| `prim.region_offset_along` | the signed distance (m) from a road user's reference point (`kin.position`) to a structure region (`st.region_geometry`), measured along a carrier's designated direction (`st.lane_direction`) on the straight line through the reference point parallel to that direction. The region is a closed set: a vertex the line only touches and an edge it runs along are points of it the line meets. Zero where the reference point lies in the region or on its boundary; where every point of the region on that line lies ahead, the distance to the nearest of them (positive); where every one lies behind, minus the distance to the nearest (negative); where the line does not meet the region, the value comes from the region's projection on the direction, the interval [lo, hi] of the signed distances of its points along it: lo where lo > 0 (all of the region ahead), hi where hi < 0 (all behind) — a projection gap, not a distance along the line, so the value may jump where the line starts or stops meeting the region, while its sign gives the side in both cases; undefined where the line meets the region both ahead and behind (the reference point lies in an opening of the region), where it misses the region and [lo, hi] spans or touches zero, and where the boundary is not a simple polygon (empty, fewer than three vertices, zero area, or crossing or touching itself); unknown where the position, the direction (a zero vector included) or the boundary is absent; independent of the boundary's start vertex and orientation. The direction is read normalised as `st.lane_direction` is, with Core's micrometre-rounded square root, and the distance is counted in lengths of that normalised vector (between 1 and 1 + 2·10⁻⁶ m), so it carries that rounding. It is a geometric quantity only: it does not establish that the road user is on the carrier, that the region marks the carrier's entrance, that the whole body has crossed the region, or that a crossing happened between observations; a caller states those with its own relations, footprint occupancy and temporal formulas; a distance to the region is read from `st.region_geometry`, never from this value | — | m | — |

## 11. Units of the measured atoms

The unit of the value a formula reads from a measured atom, by the name a formula uses
(`Term.measure`); a vector atom's components share its unit. `1` marks a count, a ratio, a
direction or an ordinal, which carry no unit; `1/m` is a reciprocal length; `kg` is a mass. A primitive's units are
the last two columns of §10. These units type a comparison: two sides of a comparison, of a sum
or of the branches of a selection have the same unit.

| id | measure | unit |
|---|---|---|
| `kin.time` | `kin_time` | s |
| `kin.position` | `kin_position` | m |
| `kin.heading` | `kin_heading` | 1 |
| `kin.velocity` | `kin_velocity` | m/s |
| `kin.speed` | `kin_speed` | m/s |
| `kin.accel_longitudinal` | `kin_accel_longitudinal` | m/s² |
| `kin.yaw_rate` | `kin_yaw_rate` | deg/s |
| `kin.extent` | `kin_extent` | m |
| `kin.steer_angle` | `kin_steer_angle` | deg |
| `kin.path_length` | `kin_path_length` | m |
| `kin.gear` | `kin_gear` | 1 |
| `kin.throttle` | `kin_throttle` | 1 |
| `kin.service_brake` | `kin_service_brake` | 1 |
| `ru.occupant_count` | `ru_occupant_count` | 1 |
| `ru.unladen_mass` | `ru_unladen_mass` | kg |
| `ru.rider_posture` | `ru_rider_posture_hands_on_controls` | 1 |
| `ru.electric_bicycle` | `ru_electric_bicycle_class` | 1 |
| `st.lane_direction` | `st_lane_direction` | 1 |
| `st.lane_adjacency` | `st_lane_adjacency` | 1 |
| `st.lane_adjacency` | `st_lane_adjacency_ordinal` | 1 |
| `st.lane_adjacency` | `st_lane_adjacency_count` | 1 |
| `st.lane_width` | `st_lane_width` | m |
| `st.curvature` | `st_curvature` | 1/m |
| `st.grade` | `st_grade` | 1 |
| `st.sight_distance` | `st_sight_distance` | m |
| `st.sight_along_way` | `st_sight_along_way` | m |
| `st.parking_space` | `st_parking_space_angle` | deg |
| `st.parking_space` | `st_parking_space_axis` | 1 |
| `st.region_geometry` | `st_region_geometry` | m |
| `st.region_geometry` | `st_region_geometry_distance` | m |
| `dev.position` | `dev_position` | m |
| `dev.speed_limit_sign` | `dev_speed_limit_sign_value` | m/s |
| `dev.regulatory_sign` | `dev_regulatory_sign_legend_angle` | deg |
| `dev.zone_sign` | `dev_zone_sign_duration_limit` | s |
| `env.visibility` | `env_visibility` | m |
| `env.civil_time` | `env_civil_time` | 1 |
| `rel.centre_distance` | `rel_centre_distance` | m |
| `rel.surface_gap` | `rel_surface_gap` | m |
| `rel.longitudinal_overlap` | `rel_longitudinal_overlap` | m |
| `rel.bearing` | `rel_bearing` | m |
