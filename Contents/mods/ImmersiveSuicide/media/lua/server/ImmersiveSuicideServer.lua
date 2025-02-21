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
        local head = body:getBodyPart(BodyPartType.Head)

        head:setHaveBullet(true, 0)
        head:SetHealth(0)

        -- Force zombie if sandbox settings are enabled for it
        -- Otherwise, prevent zombie (even if bitten) because the head just got annihilated
        if SandboxVars.ImmersiveSuicide.ForceZombification == true then
            body:setInfected(true)
            body:setInfectionMortalityDuration(-1)
            body:setInfectionTime(-1)
            body:setInfectionLevel(100)
        else
            body:setInfected(false)
            body:setInfectionMortalityDuration(0)
            body:setInfectionTime(0)
            body:setInfectionLevel(0)
        end
        
        player:Kill(player)
        
        sendServerCommand(module, "recievePerformSuicide", {
            playerOnlineId = player:getOnlineID()
        })
    end
end

Events.OnClientCommand.Add(onKillPlayerCommand)
