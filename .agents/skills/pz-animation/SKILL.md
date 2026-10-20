---
name: pz-animation
description: Create, revise, export and validate Build 42 Project Zomboid animations using Paddlefruit V4. Use for animation authoring and Blender/game motion mismatches, not unrelated Lua gameplay changes.
---

# PZ animation authoring

Use [workflow.md](references/workflow.md) for commands and supported operations.
On a new checkout, run repository-root `initialize.ps1` before authoring/exporting;
all skills share ignored root `.immersive-suicide.local.json` for machine paths.
Initialization also restores developer assets; use `-SkipAssetRestore` for
configuration-only setup. Follow the repository's [script formatting rules](../../../AGENTS.md)
when editing this skill's tools and tests.
The AI does the authoring and validation. The maintainer is not an animator:
ask for visible feedback or an optional correction to one pose, not curve editing.

## Non-negotiable boundaries

- Build42 only. Never modify or directly open `assets/rig/PZ_HumanRigV4.blend`;
  always copy it before working. Preserve approved sources and manual references.
- Tools, example assets and drafts belong in this skill. Repository `animation/`
  contains approved final editable blends only; never put test output there.
- Skill tests live in `tests/` inside this skill. Mod and project-configuration tests
  live in the repository-root `tests/` folder.
- Use a new `Bob_...` name per review. Do not bypass overwrite guards.
- Stage only when requested; the maintainer installs the mod themselves.
- Technical checks are not visual or in-game approval. Do not claim natural
  motion or collision-free contact based only on numeric scores.

## Authoring loop

1. Read [rig-and-authoring.md](references/rig-and-authoring.md) for new poses,
   grip or item work. Reuse an appropriate approved reference from
   `assets/references.json`; the file records purpose, approval and source hashes.
2. Make a small coherent draft with sparse moving keys and full-body previews.
   For coordinated motion, overlap actions rather than staging every phase serially.
3. Run the supported command, export checks and any relevant grip comparison.
   Give the exact clip name, editable blend path and a concrete visual question.
4. If the maintainer fixes one pose, inspect their saved frame without overwriting
   it. Extract reusable LOCAL controller transforms; apply them consistently.
   Never ask them to correct every frame or rebuild over their edited file.
5. After explicit in-game approval, promote the exact reviewed blend to repository
   `animation/<clip>.blend` and verify hashes. Do not tie the skill registry to
   mutable production filenames; register only frozen reusable skill assets.
   Keep useful learning references inside the skill, with an explicit purpose.

For motion editing and checks, read
[motion-and-validation.md](references/motion-and-validation.md). Frozen examples
are grouped by animation, each with its own `01`, `02`, ... sequence:

- [Short-blade one-hand](references/examples/short-blade-one-hand.md): grip,
  wrist, timing and overlapping forward collapse.
- [Head stab](references/examples/head-stab.md): preserving a corrected lift,
  repeating the corrected hand/elbow stroke and a full-body backward fall.

Read the relevant guide and milestone rather than every draft. Construction code
inside each example is reference-only; adapt it rather than replaying old timing.
Keep approval status explicit: visual approval does not establish game approval.

For Lua syntax or native X-mesh problems, read
[diagnostics.md](references/diagnostics.md); those Java helpers are optional.

This is a tested AI-assisted authoring workflow, not a trained motion model,
one-shot full-body generator, physics solver, or guarantee of a natural result.
