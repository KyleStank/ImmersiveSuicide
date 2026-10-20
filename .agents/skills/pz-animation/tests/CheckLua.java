// Check Lua syntax with the game's compiler without starting the game.
// See ../references/diagnostics.md for the command to run from the repository root.
import java.nio.file.Files;
import java.nio.file.Path;
import se.krka.kahlua.luaj.compiler.LuaCompiler;

class CheckLua {
    public static void main(String[] args) throws Exception {
        if (args.length == 0) {
            throw new IllegalArgumentException("Supply Lua source files");
        }

        for (String file : args) {
            LuaCompiler.loadstring(Files.readString(Path.of(file)), file, null);
            System.out.println("LUA_SYNTAX_OK " + file);
        }
    }
}
