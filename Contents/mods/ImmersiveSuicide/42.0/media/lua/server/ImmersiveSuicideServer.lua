local function onKillPlayerCommand(module, command, player, args)
    if module ~= "ImmersiveSuicide" then
        return
    end
    
    if command == "requestSynchronizedCharacterFX" then
        sendServerCommand(module, "recieveSynchronizedCharacterFX", {
            playerOnlineId = player:getOnlineID()
        })
    end

    if command == "requestPerformSuicide" then
        local body = player:getBodyDamage()
        local stats = player:getStats() -- BUILD_NOTE: Build 41/42 Difference: "stats" is a B42 concept only
        local head = body:getBodyPart(BodyPartType.Head)

        head:setHaveBullet(true, 0)
        head:SetHealth(0)

        -- Force zombie if sandbox settings are enabled for it
        -- Otherwise, prevent zombie (even if bitten) because the head just got annihilated
        if SandboxVars.ImmersiveSuicide.ForceZombification == true then
            body:setInfected(true)
            body:setInfectionMortalityDuration(-1)
            -- BUILD_NOTE: Build 41/42 Difference: "stats" is a B42 concept only. B41 uses "body:setInfectionLevel" instead
            stats:set(CharacterStat.ZOMBIE_INFECTION, 100)
            stats:set(CharacterStat.ZOMBIE_FEVER, 100)
        else
            body:setInfected(false)
            body:setInfectionMortalityDuration(0)
            -- BUILD_NOTE: Build 41/42 Difference: "stats" is a B42 concept only. B41 uses "body:setInfectionLevel" instead
            stats:set(CharacterStat.ZOMBIE_INFECTION, 0)
            stats:set(CharacterStat.ZOMBIE_FEVER, 0)
        end
        
        player:Kill(player)
        
        sendServerCommand(module, "recievePerformSuicide", {
            playerOnlineId = player:getOnlineID()
        })
    end
end

Events.OnClientCommand.Add(onKillPlayerCommand)
