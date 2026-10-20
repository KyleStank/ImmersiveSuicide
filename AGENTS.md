# Immersive Suicide: agent working agreement

## Purpose and orientation

This is an AI-assisted Project Zomboid mod maintained by a programmer, not an
animator. AI assists with implementation, investigation, animation authoring and
documentation; the maintainer supplies direction and in-game/visual review.

Read [ARCHITECTURE.md](ARCHITECTURE.md) for implementation boundaries and
[README.md](README.md) for development commands. Inspect the relevant code and
working tree before editing. Documentation describes intent and observed behavior;
it is not proof that a feature works. Resolve contradictions rather than guessing.

## Quality, scope and decisions

- Quality and accuracy are essential. Prefer correct, maintainable, verified work
  over a large or fast delivery. Keep changes focused; do not invent frameworks.
- Do not make unsupported assumptions. Inspect available evidence first. If
  requirements, game APIs, intended motion, naming, paths or compatibility remain
  unclear, ask the maintainer for direction before implementing uncertain behavior.
  Distinguish confirmed facts from hypotheses and untested behavior.
- New features and custom animations target **Build 42 only**. Build 41 is in
  pure maintenance mode; do not backport features or edit its tree unless requested.
  Build 42 work does not require B41 compatibility tracking.
- Preserve existing user changes and manually corrected animations. Do not clean
  unrelated files, overwrite approved work, or rename identifiers casually.
- An animation request does not authorize gameplay integration. A diagnostic
  request does not authorize a fix. Ask before materially expanding scope.
- Keep progress updates and final reports concise. Report what changed, what was
  actually verified, and what still needs human/game testing.
- Keep Lua, Java, PowerShell and Python scripts readable, including skill tools and
  tests. Use four-space indentation, blank lines between logical steps and one
  statement per line. Expand functions, conditionals and loops into clear blocks
  instead of dense one-liners; put larger parameter lists and tables on separate
  lines. Follow the existing cleaned-up scripts as examples.
- Write comments in plain language. Explain what the code does or why it is needed;
  use concrete names like client, server and animation XML instead of vague jargon.

## Repository and runtime rules

- Runtime files belong in `Contents/mods/ImmersiveSuicide/`. The unversioned
  `media/` is the legacy Build 41 tree; `42.0/media/` is the Build 42 tree.
  Do not mistake these similarly named files for interchangeable copies.
- Keep UI/client actions, server command handling, translations, sandbox options
  and animation definitions in their existing responsibilities. Preserve protocol
  strings and load order; check both ends of a multiplayer change.
- Check item exclusions when offering/selecting an action and accepting its server
  request. Keep exclusion lookups out of per-frame timed-action validation.
- Verify APIs against the targeted game build, not generic Lua or a Build 41
  example. Explain relevant Build 42 API limitations in plain comments when needed.
- Preserve translation keys and provide English text for new user-facing options;
  do not claim unreviewed translations are human-verified.
- Final editable Blender sources live in repository `animation/`. Final exported
  custom character GLBs live in `Contents/mods/ImmersiveSuicide/42.0/media/anims_X/Bob/`.
  Do not put source blends, tooling or drafts in the runtime media tree.
- Mod and project-configuration tests belong in root `tests/`. Animation-skill tests
  belong in `.agents/skills/pz-animation/tests/`.
- `dist/` is generated packaging output, not source. `_sandbox/` is local research,
  not authoritative implementation.

## Project initialization and configuration

Run root `initialize.ps1` to configure a new checkout and restore its developer
assets. Configuration is saved before the restore step; failed downloads leave it
available for a direct restore retry. `-SkipAssetRestore` performs configuration-only
setup. Default initialization, including reruns with `-Force`, restores and overwrites
listed assets; use the skip switch when only changing configuration.

All project skills share ignored root `.immersive-suicide.local.json`; no skill owns a separate machine
configuration or initializer. Shared PowerShell access lives in
`scripts/project-config.ps1`. Keep absolute machine paths out of shared scripts
and recipes. Extend the shared schema and its consumers/tests together when needed.
See README for setup and the current configuration fields. Keep `developer-assets.json`
paths and SHA-256 hashes current when approved, listed developer assets change.
Developer assets are files needed for development, regardless of file format;
do not limit the manifest or asset tools to `.blend` files.
The skill's regression-reference GLB is a developer asset; Build 42 runtime GLBs
under `Contents/` are game assets and must stay out of the developer manifest.

## Animation workflow

For authoring, revising or debugging Blender/exported motion, use
[pz-animation](.agents/skills/pz-animation/SKILL.md) and its routed references.

- Game preview inputs use `game:media/...`; Blender-only exports do not require a
  game installation. The skill consumes project configuration, not its own file.

- Never modify or directly open
  `.agents/skills/pz-animation/assets/rig/PZ_HumanRigV4.blend`. Always copy first.
- The skill owns reusable scripts, frozen examples, recipes and ignored working
  drafts. `animation/` owns final production sources, not the iteration archive.
- Use a new review name/output; never rebuild over a user's edited blend. Ask for
  visible feedback or an optional single-pose correction, not per-frame manual work.
- Keep authored motion sparse; export baking is separate. Preserve approved grip
  and motion unless the request calls for changing them.
- A filename, Blender action name, exported clip name and XML action identifier
  are distinct. Inspect their references before renaming or connecting them.
- Technical export checks do not establish visual quality or in-game approval.
  Promote only the exact reviewed source after explicit approval.

## Verification and external actions

Use the checks relevant to the change; see README and the skill workflow. Test
success and important failure paths without touching real saves or publishing.
Lua/XML checks cannot replace game testing. For runtime changes, identify required
single-player, cancellation, sandbox and multiplayer checks as applicable. Do not
report a check as passed unless it ran; disclose missing tools or game verification.

The maintainer normally installs local changes themselves. Workspace GLB staging,
installed-mod copying, packaging and Workshop publication are separate actions.
Do not install, publish, change Steam credentials, commit, tag or push without
explicit authorization. `scripts/pack.sh` deletes/recreates `dist/`; inspect its
scope before running and never treat packing as permission to publish.
Developer assets use `scripts/pack-developer-assets.ps1` and the manifest, separately
from `dist/`. Hash mismatches require reviewing the asset, not silently refreshing
hashes. `scripts/restore-developer-assets.ps1` intentionally overwrites listed
developer-asset destinations, including local edits, only after all downloaded files
pass the trusted local manifest hashes. Run it only when asset replacement is requested;
use a disposable `-DestinationRoot` for download verification. Developer-asset uploads
to Google Drive are a manual maintainer step; do not automate them.

## Living documentation: part of every change

Keep **AGENTS.md, ARCHITECTURE.md and README.md current as work proceeds**. Review
all three for impact and update affected sections in the same change, without
waiting for another request. Do not rewrite unaffected documents just for activity.

- `AGENTS.md`: durable working rules, maintainer expectations, boundaries and safety.
- `ARCHITECTURE.md`: implemented layout, runtime flows, extension points, evidence
  and known limitations. Do not describe planned features as completed.
- `README.md`: project overview, prerequisites, supported builds and usable commands.

Update skill documentation too when its interface or lessons change. Replace stale
guidance rather than appending contradictions. These documents are not chat logs,
session journals or exhaustive animation histories. Keep temporary experiments out;
record reusable lessons and confirmed decisions where future agents will find them.
