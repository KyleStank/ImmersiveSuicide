local function addSuicideOption(player, context, worldObjects)
    context:addOption('Suicide', worldObjects, function()
        print("You have killed yourself")

        sendClientCommand("StanksSuicide", "killPlayer", { playerIndex = player })
    end)
end

Events.OnFillWorldObjectContextMenu.Add(addSuicideOption)
