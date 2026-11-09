# NRS-484B-403(3) at C111662

Frozen intersection/u_turn/centerline cell and motor-vehicle actor. Exact law source hash is pinned in `native/build.py`; the source text is in `case-plan.json`. Business-district U-turn prohibition and its express intersection or divided-highway-opening exception require distinct proofs.

Two unselected controlled requests place the U-turn center at x=-45 m away from the authored intersection and x=0 m inside it. The same six-lane OpenDRIVE crossed street, vehicle blueprint, 20 Hz / 800-frame profile and candidate camera policy are held fixed within each pair. The semicircle uses a 6 m radius between outer lane centers y=-6 and y=+6 m, with a centerline crossing and heading reversal. Each case has primary, slower approach, elevated overview and two-second pre-turn dwell variants. Positive/negative exact request and synthetic raw-to-saved checks, independent geometry/pair audit, measured trigger checks and pinned offline constructions are under `native/`.

The district flag and type=town road are authored requests, not statutory business-district proof. The divided-highway opening alternative is not constructed. Original generated topology, physical turning, source-hashed pixels, territorial designation, legal exception review and accepted comparison remain worker-owned. No candidate is selected or ready; no accepted reuse is claimed.
