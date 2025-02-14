local function addSuicideOption(player, context, worldObjects)
    context:addOption(getText("ContextMenu_StanksSuicide_Suicide"), worldObjects, function()
        local width, height = 350, 140
        local dialog = ISYesNoDialog:new(
            (getCore():getScreenWidth() / 2) - width / 2,
            (getCore():getScreenHeight() / 2) - height / 2,
            width, height, player,
            function ()
                print("[Stank's Suicide] You have killed yourself")
                sendClientCommand("StanksSuicide", "killPlayer", { playerIndex = player })
            end)

        dialog:initialise()
        dialog:addToUIManager()
    end)
end

Events.OnFillWorldObjectContextMenu.Add(addSuicideOption)
