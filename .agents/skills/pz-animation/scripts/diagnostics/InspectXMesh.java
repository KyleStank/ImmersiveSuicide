// Read mesh coordinates using the game's .X importer. No source files are changed.
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.EnumSet;
import java.util.regex.Pattern;
import jassimp.*;

class InspectXMesh {
    public static void main(String[] args) throws Exception {
        // Use the native importer supplied with the game.
        Jassimp.setLibraryLoader(new JassimpLibraryLoader() {
            public void loadLibrary() {
                System.load(Path.of(args[0]).toAbsolutePath().toString());
            }
        });

        var steps = EnumSet.of(
            AiPostProcessSteps.FIND_INSTANCES,
            AiPostProcessSteps.MAKE_LEFT_HANDED,
            AiPostProcessSteps.LIMIT_BONE_WEIGHTS,
            AiPostProcessSteps.TRIANGULATE,
            AiPostProcessSteps.OPTIMIZE_MESHES,
            AiPostProcessSteps.REMOVE_REDUNDANT_MATERIALS,
            AiPostProcessSteps.JOIN_IDENTICAL_VERTICES
        );

        var scene = Jassimp.importFile(args[1], steps);

        // Print the right thumb and finger rotations near the middle of each animation.
        for (var animation : scene.getAnimations()) {
            System.out.println("ANIMATION " + animation.getName() + " duration=" + animation.getDuration());

            for (var channel : animation.getChannels()) {
                if (!channel.getNodeName().equals("Bip01_R_Finger0")
                        && !channel.getNodeName().equals("Bip01_R_Finger1")) {
                    continue;
                }

                int key = 0;

                for (int i = 0; i < channel.getNumRotKeys(); ++i) {
                    if (channel.getRotKeyTime(i) <= animation.getDuration() * 0.5) {
                        key = i;
                    }
                }

                System.out.println("GRIP_ROTATION " + channel.getNodeName() + " tick="
                    + channel.getRotKeyTime(key) + " [" + channel.getRotKeyW(key) + ","
                    + channel.getRotKeyX(key) + "," + channel.getRotKeyY(key) + ","
                    + channel.getRotKeyZ(key) + "]");
            }
        }

        // Find the imported mesh's smallest and largest coordinates on each axis.
        var mesh = scene.getMeshes().get(0);
        var bounds = new double[][] {{1e9, 1e9, 1e9}, {-1e9, -1e9, -1e9}};

        for (int i = 0; i < mesh.getNumVertices(); ++i) {
            double[] p = {mesh.getPositionX(i), mesh.getPositionY(i), mesh.getPositionZ(i)};

            for (int j = 0; j < 3; ++j) {
                bounds[0][j] = Math.min(bounds[0][j], p[j]);
                bounds[1][j] = Math.max(bounds[1][j], p[j]);
            }
        }

        System.out.println("GAME_X_BOUNDS " + java.util.Arrays.deepToString(bounds));

        // Read the coordinates directly from the text file for comparison.
        var match = Pattern.compile("(?m)^\\s*Mesh\\s+\\w+\\s*\\{").matcher(Files.readString(Path.of(args[1])));

        if (!match.find()) {
            throw new IllegalArgumentException("No static mesh");
        }

        String raw = Files.readString(Path.of(args[1])).substring(match.end());
        var numbers = Pattern.compile("[-+]?\\d+(?:\\.\\d+)?").matcher(raw);
        numbers.find();

        int count = Integer.parseInt(numbers.group());
        double[][] rawBounds = {{1e9, 1e9, 1e9}, {-1e9, -1e9, -1e9}};

        for (int i = 0; i < count; ++i) {
            for (int j = 0; j < 3; ++j) {
                numbers.find();
                double value = Double.parseDouble(numbers.group());
                rawBounds[0][j] = Math.min(rawBounds[0][j], value);
                rawBounds[1][j] = Math.max(rawBounds[1][j], value);
            }
        }

        System.out.println("RAW_X_BOUNDS " + java.util.Arrays.deepToString(rawBounds));
    }
}
