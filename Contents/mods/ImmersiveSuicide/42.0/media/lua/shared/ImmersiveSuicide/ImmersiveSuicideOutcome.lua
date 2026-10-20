require "ImmersiveSuicide/ImmersiveSuicideDefinitions"

ImmersiveSuicideOutcome = {}

-- Single-player, the server and multiplayer clients all use this function.
-- Get the body part and bullet settings from ImmersiveSuicideDefinitions.lua using the animation ID.
function ImmersiveSuicideOutcome.perform(character, definitionId)
    local definition = ImmersiveSuicideDefinitions.get(definitionId)
    if not character or not definition then return false end

    local body = character:getBodyDamage()
    local stats = character:getStats()
    local target = body:getBodyPart(definition.targetBodyPart)
    if definition.causesBullet then
        target:setHaveBullet(true, 0)
    end
    target:SetHealth(0)

    -- Force zombification if the sandbox option is enabled. Otherwise, prevent it even if the player was bitten.
    if SandboxVars.ImmersiveSuicide.ForceZombification == true then
        body:setInfected(true)
        body:setInfectionMortalityDuration(-1)
        body:setInfectionTime(-1)
        stats:set(CharacterStat.ZOMBIE_INFECTION, 100)
        stats:set(CharacterStat.ZOMBIE_FEVER, 100)
    else
        body:setInfected(false)
        body:setInfectionMortalityDuration(0)
        body:setInfectionTime(0)
        stats:set(CharacterStat.ZOMBIE_INFECTION, 0)
        stats:set(CharacterStat.ZOMBIE_FEVER, 0)
    end
    character:Kill(character)
    return true
end
