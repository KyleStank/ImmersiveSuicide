require "ImmersiveSuicide/ImmersiveSuicideOutcome"

local function onKillPlayerCommand(module, command, player, args)
    if module ~= "ImmersiveSuicide" then return end

    if command == "requestSynchronizedCharacterFX" then
        sendServerCommand(module, "recieveSynchronizedCharacterFX", {
            playerOnlineId = player:getOnlineID()
        })
    elseif command == "requestPerformSuicide" then
        local definitionId = args and args.definitionId
        local definition = ImmersiveSuicideDefinitions.get(definitionId)
        local weapon = player:getPrimaryHandItem()
        
        if not ImmersiveSuicideDefinitions.matchesWeapon(definition, weapon)
            or not ImmersiveSuicideDefinitions.isEquipped(player, weapon)
            or ImmersiveSuicideDefinitions.isExcluded(weapon, definition.weaponKind) then
            return
        end

        if ImmersiveSuicideOutcome.perform(player, definitionId) then
            sendServerCommand(module, "recievePerformSuicide", {
                playerOnlineId = player:getOnlineID(),
                definitionId = definitionId
            })
        end
    end
end

Events.OnClientCommand.Add(onKillPlayerCommand)
