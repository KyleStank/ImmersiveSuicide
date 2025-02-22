if [ -d ./dist ]; then
    rm -r ./dist
fi
mkdir -p ./dist/mods/ImmersiveSuicide
cp -r Contents/mods/ImmersiveSuicide dist/mods
