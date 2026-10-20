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

For the numbered, selected milestones from our first animation, read
[the example progression](references/motion-and-validation.md#example-progression).
These are reusable worked examples, not automatic model training or a complete
draft history; inspect the relevant milestone and its documented limitations.

For timing, body transitions and preserving edits, read
[motion-and-validation.md](references/motion-and-validation.md). Four knife-specific
construction examples are retained for their techniques, NOT as general-purpose
commands. Read one only when its technique is relevant; adapt its frame assumptions.
Do not send a non-animator to pick or run these examples.

For Lua syntax or native X-mesh problems, read
[diagnostics.md](references/diagnostics.md); those Java helpers are optional.

This is a tested AI-assisted authoring workflow, not a trained motion model,
one-shot full-body generator, physics solver, or guarantee of a natural result.
