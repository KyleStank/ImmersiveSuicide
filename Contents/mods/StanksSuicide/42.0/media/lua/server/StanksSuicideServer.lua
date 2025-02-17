local function onKillPlayerCommand(module, command, player, args)
    if module ~= "StanksSuicide" then
        return
    end
    
    if command == "requestSynchronizedCharacterFX" then
        sendServerCommand(module, "recieveSynchronizedCharacterFX", {
            playerOnlineId = player:getOnlineID()
        })
    end

    if command == "requestPerformSuicide" then
        player:Kill(player)
        sendServerCommand(module, "recievePerformSuicide", {
            playerOnlineId = player:getOnlineID()
        })
    end
end

Events.OnClientCommand.Add(onKillPlayerCommand)
