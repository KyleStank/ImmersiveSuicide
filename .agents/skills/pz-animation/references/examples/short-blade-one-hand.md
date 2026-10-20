# Short-blade one-hand example

Frozen assets: `assets/examples/short-blade-one-hand/`. Numbering belongs to
this animation; the original filenames and binary contents are unchanged.


The numbered files in `assets/examples/short-blade-one-hand/` are selected milestones, in development
order, from building our first animation incrementally with AI drafts and human
feedback. They are not every revision, a directly replayable build chain, or a
collection where each file is wholly good or bad. Earlier examples isolate useful
parts; later examples add motion and expose different problems. File numbering
does not change action names inside Blender or clip names in the game.

| File stem | What to reuse or learn |
| --- | --- |
| `01-natural-reach-wrist` | Approved natural arm reach and wrist alignment; no complete knife action yet. |
| `02-manual-knife-placement` | Human-corrected attachment placement; intentional thumb clipping, not a finished finger grip. |
| `03-approved-finger-grip` | Approved prop/thumb/finger pose saved at frame 20; reusable local grip transforms. |
| `04-manual-early-motion` | Human corrections to the early motion through frame 38; the later original continuation was reported broken and is NOT an approved target. |
| `05-manual-wrist-blade-orientation` | Human correction to wrist/blade direction; learn orientation intent, not a universal anatomical wrist pose. |
| `06-manual-timing-before-handle-repair` | Human timing decisions before handle repair; moved keys alone do not guarantee valid Bezier timing. |
| `07-approved-overlapping-collapse` | Complete in-game-approved motion: arm recovery overlaps body collapse. Matching GLB is the golden export for regression checks. |

The AI must read the relevant lesson, inspect the needed curves/poses in a working
copy, and adapt them to the new motion. Merely storing these files does not train
the model or teach it which poses are wrong. Failure lessons are documented here
and in [rig-and-authoring.md](../rig-and-authoring.md); do not infer failure labels for whole files.
For a new animation, repeat the small-draft/review/correction loop in [SKILL.md](../../SKILL.md),
not this specific sequence of knife milestones. Exact paths, roles and unchanged
content hashes are recorded in `assets/references.json`.

## Construction techniques


These four files under `assets/examples/short-blade-one-hand/construction/` preserve techniques from
the successful knife animation. Their direct-launch guards deliberately reject
historical recipe replay. They are learning material to adapt, not toolkit commands.

- `append_recovery.py`: knife clearance before wrist unwinding, preserving the
  approved prefix and the hand-relative grip.
- `append_kneel.py`: root-parented limb targets, pelvis descent, evaluated toe
  pivots and mild torso motion. The IK foot-control origin is not the ankle.
- `append_fall.py`: isolated DeadDown reference sampling, FK-to-IK matching,
  heading/ground alignment and a truly still ending.
- `overlap_recovery_collapse.py`: separate arm/body clocks and compensate targets
  with `pelvis(body_time) @ inverse(pelvis(arm_time))`. This avoids lowering the
  hand completely before the body starts collapsing.

Do not carry their old pose times or distances into a different animation.
The accepted example finishes the pass near31, yields from36, kneels56, contacts
ground72 and ends84 at30fps. Those are reference-specific, not universal timing.

Do not independently interpolate world matrices for anatomically parented chest,
head or FK arm attachments: that stretched the neck. Preserve anatomical LOCAL
positions/scales while changing rotation. Snapshot world targets before moving a
parent so a common lift isn't applied twice. DeadDown is a bundled pose reference,
not proof of an exact runtime corpse pose. Ground contact remains approximate.

