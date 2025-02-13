local function onKillPlayerCommand(module, command, player, args)
    if module == "StanksSuicide" and command == "killPlayer" then
        local playerObj = getSpecificPlayer(args.playerIndex)
        local body = playerObj:getBodyDamage()
        local bodyParts = body:getBodyParts()

        -- Mark all body parts as bitten and infected
        for i = 0, BodyPartType.ToIndex(BodyPartType.MAX) - 1 do
            local bodyPart = bodyParts:get(i)
            bodyPart:SetBitten(true)
            bodyPart:SetInfected(true)
        end

        body:ReduceGeneralHealth(body:getOverallBodyHealth() + 10) -- Add small buffer to ensure all health is *always* removed
    end
end

Events.OnClientCommand.Add(onKillPlayerCommand)
