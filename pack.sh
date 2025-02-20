rm -r ./dist
mkdir -p ./dist

cp preview.gif preview.png workshop.txt dist

mkdir -p dist/Contents/mods/ImmersiveSuicide
cp -r Contents/mods/ImmersiveSuicide dist/Contents/mods
