# PROB-21 — candidate shape contact sheet

Status: candidate renders and owner judgments pending. To generate the full sheet:

    python3 tools/research/shapes/hubbard.py --point 0 1 --catalog --out out/prob21 --sheet docs/research/shapes/contact-sheet.md
    bash out/prob21/render.sh

Each generated row has an exact decimal camera and width, a proposed yes/no
predicate, thumbnail placeholder and owner-vote column. Unavailable positive
or negative sets are reported as insufficient rather than padded.

These are NEW HYPOTHESES, not established Hubbard-tree identifications.
The calculated graph is only an Euclidean Steiner chord approximation, not
the correct regulated-arc Hubbard tree. No landing rays are traced, no
minibrot ladder is certified and Tan Lei similarity is asymptotic.

Predicates and thresholds:
- dendrite: >=3 forks, each with >=2 edges turning <0.35 rad
- spoke/backbone: weighted diameter >=65% of edge sum
- filament: fork-to-fork edge >=8% diameter
- tendril: edge twist >=pi/2, length >=8% diameter
- hook: leaf at fork with turn >=pi/2
- spindle: fork-to-fork edge >=16% diameter; minibrots unverified
- galaxy: >=3 p-step growing radii with turn >=0.25 rad
- whirlpool: >=4 spiral points within proposed view

Established basis: Douady-Hubbard (Orsay Notes), Bruin-Schleicher (2008),
Tan Lei (1990); visual names from Munafo Mu-Ency. None of these references
establishes the eight numeric thresholds.
