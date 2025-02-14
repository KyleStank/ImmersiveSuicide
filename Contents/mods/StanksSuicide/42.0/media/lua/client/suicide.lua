local function addSuicideOption(player, context, worldObjects)
    context:addOption(getText("ContextMenu_StanksSuicide_Suicide"), worldObjects, function()
        print("[Stank's Suicide] You have killed yourself")
        sendClientCommand("StanksSuicide", "killPlayer", { playerIndex = player })
    end)
end

Events.OnFillWorldObjectContextMenu.Add(addSuicideOption)
