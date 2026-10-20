require "ImmersiveSuicide/ImmersiveSuicideOutcome"

ImmersiveSuicideNetwork = {}

local function syncCharacterFX(character)
    if character then
        character:splatBloodFloorBig()
    end
end

function ImmersiveSuicideNetwork.impact(character)
    if isClient() then
        sendClientCommand("ImmersiveSuicide", "requestSynchronizedCharacterFX", {})
    else
        syncCharacterFX(character)
    end
end

function ImmersiveSuicideNetwork.kill(character, definitionId)
    if not ImmersiveSuicideDefinitions.get(definitionId) then return end
    
    if isClient() then
        sendClientCommand("ImmersiveSuicide", "requestPerformSuicide", {
            definitionId = definitionId
        })
    else
        ImmersiveSuicideOutcome.perform(character, definitionId)
    end
end

local function onSuicideServerCommand(module, command, args)
    if module ~= "ImmersiveSuicide" or not args then return end

    if command == "recieveSynchronizedCharacterFX" then
        syncCharacterFX(getPlayerByOnlineID(args.playerOnlineId))
    elseif command == "recievePerformSuicide" then
        ImmersiveSuicideOutcome.perform(
            getPlayerByOnlineID(args.playerOnlineId), args.definitionId)
    end
end

-- Handle server messages here so the firearm and melee actions do not each handle the same message.
Events.OnServerCommand.Add(onSuicideServerCommand)
