# Optional game-format diagnostics

These are troubleshooting helpers, NOT dependencies of the normal animation
build. Both require a JDK and the local Build42 game installation. They read
inputs only; they do not install mods or change animations.

- `tests/CheckLua.java`: compile Lua with PZ's Kahlua parser to catch
  syntax errors in the animation-viewer debug extension. This does not validate
  runtime behavior and is not an animation authoring step.
- `scripts/diagnostics/InspectXMesh.java`: inspect a native `.X` mesh through the
  game's Jassimp importer; print first-mesh bounds, raw text-mesh bounds, and the
  right-thumb/finger animation rotations when present. Useful for item axes/grips.
  This is a narrow text-X diagnostic, not a general mesh validator.

Commands below run from repository root. Initialize with `-ProjectZomboidPath`
first. These native commands describe the verified Windows game layout; use the
matching native library/classpath conventions on other systems, not a renamed DLL.

```powershell
$pzSkill = '.agents/skills/pz-animation'
. ./scripts/project-config.ps1
$pzGame = (Get-ProjectLocalConfig).project_zomboid_path
if (-not $pzGame) { throw 'Initialize with -ProjectZomboidPath first.' }
# Syntax-check one or more Lua files without launching the game:
java -cp "$pzGame/projectzomboid.jar" "$pzSkill/tests/CheckLua.java" <file.lua>

# Native mesh inspection needs compiled classes, not Java source-launch mode
# (the native JNI symbols could not resolve in the source-launch classloader).
New-Item -ItemType Directory -Force "$pzSkill/work/diagnostics" | Out-Null
javac -cp "$pzGame/projectzomboid.jar" -d "$pzSkill/work/diagnostics" "$pzSkill/scripts/diagnostics/InspectXMesh.java"
java -cp "$pzGame/projectzomboid.jar;$pzSkill/work/diagnostics" InspectXMesh "$pzGame/jassimp64.dll" "$pzGame/media/models_X/weapons/1handed/Knife.X"
```

Keep compiled `.class` files in ignored `work/`, not beside the source. The normal
toolkit requires Blender/PowerShell, not these Java diagnostics or a JDK.
