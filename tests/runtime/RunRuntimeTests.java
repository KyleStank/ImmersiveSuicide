// Run the mod tests using the game's Lua compiler without starting the game.
import java.nio.file.*;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Element;
import se.krka.kahlua.j2se.J2SEPlatform;
import se.krka.kahlua.luaj.compiler.LuaCompiler;
import se.krka.kahlua.stdlib.*;
import se.krka.kahlua.vm.*;

class RunRuntimeTests {
    public static void main(String[] args) throws Exception {
        Path game = Path.of(args[0]);
        Path root = Path.of(args[1]);

        // Set up Lua and the standard functions used by the tests.
        var platform = J2SEPlatform.getInstance();
        var env = platform.newTable();
        env.rawset("_G", env);
        BaseLib.register(env);
        TableLib.register(platform, env);
        se.krka.kahlua.j2se.MathLib.register(platform, env);

        var thread = new KahluaThread(platform, env);
        thread.debugOwnerThread = Thread.currentThread();

        // Exercise the actual animation event names, parameters and timing order.
        Path headStabXml = root.resolve(
            "Contents/mods/ImmersiveSuicide/42.0/media/AnimSets/player/actions/IS_ShortBladeOneHand2.xml"
        );
        var document = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(headStabXml.toFile());
        var eventNodes = document.getElementsByTagName("m_Events");
        var animationEvents = platform.newTable();

        for (int index = 0; index < eventNodes.getLength(); index++) {
            var node = (Element) eventNodes.item(index);
            var event = platform.newTable();
            event.rawset("name", childText(node, "m_EventName"));
            event.rawset("parameter", childText(node, "m_ParameterValue"));
            event.rawset("time", Double.parseDouble(childText(node, "m_TimePc")));
            animationEvents.rawset(index + 1, event);
        }

        env.rawset("headStabAnimationEvents", animationEvents);

        // Load the test replacements first, then the game classes and mod files.
        String[] files = {
            root.resolve("tests/runtime/bootstrap.lua").toString(),

            game.resolve("media/lua/shared/ISBaseObject.lua").toString(),
            game.resolve("media/lua/shared/TimedActions/ISBaseTimedAction.lua").toString(),

            root.resolve("Contents/mods/ImmersiveSuicide/42.0/media/lua/shared/ImmersiveSuicide/ImmersiveSuicideDefinitions.lua").toString(),
            root.resolve("Contents/mods/ImmersiveSuicide/42.0/media/lua/shared/ImmersiveSuicide/ImmersiveSuicideOutcome.lua").toString(),
            root.resolve("Contents/mods/ImmersiveSuicide/42.0/media/lua/client/ImmersiveSuicideNetwork.lua").toString(),
            root.resolve("Contents/mods/ImmersiveSuicide/42.0/media/lua/client/Actions/BaseSuicideTimedAction.lua").toString(),
            root.resolve("Contents/mods/ImmersiveSuicide/42.0/media/lua/client/Actions/FirearmSuicideTimedAction.lua").toString(),
            root.resolve("Contents/mods/ImmersiveSuicide/42.0/media/lua/client/Actions/MeleeSuicideTimedAction.lua").toString(),
            root.resolve("Contents/mods/ImmersiveSuicide/42.0/media/lua/client/ImmersiveSuicide.lua").toString(),
            root.resolve("Contents/mods/ImmersiveSuicide/42.0/media/lua/client/ContextMenu.lua").toString(),
            root.resolve("Contents/mods/ImmersiveSuicide/42.0/media/lua/server/ImmersiveSuicideServer.lua").toString(),
            root.resolve("Contents/mods/ImmersiveSuicide/42.0/media/lua/client/FirearmRadialMenuPatch.lua").toString(),

            // Run the checks after all the code they need has loaded.
            root.resolve("tests/runtime/behavior.lua").toString(),
            root.resolve("tests/runtime/radial.lua").toString(),
            root.resolve("tests/runtime/menu-selection.lua").toString(),
            root.resolve("tests/runtime/exclusions.lua").toString(),
        };

        for (String file : files) {
            var result = thread.pcall(
                LuaCompiler.loadstring(Files.readString(Path.of(file)), file, env),
                new Object[0]
            );

            // Stop at the first failed check and include the file and Lua error.
            if (!Boolean.TRUE.equals(result[0])) {
                throw new AssertionError(file + ": " + java.util.Arrays.toString(result));
            }
        }

        System.out.println("RUNTIME_BEHAVIOR_OK (mocked game services, actual Kahlua and base classes)");
    }

    private static String childText(Element node, String name) {
        var matches = node.getElementsByTagName(name);
        if (matches.getLength() == 0) {
            return "";
        }
        return matches.item(0).getTextContent().trim();
    }
}

