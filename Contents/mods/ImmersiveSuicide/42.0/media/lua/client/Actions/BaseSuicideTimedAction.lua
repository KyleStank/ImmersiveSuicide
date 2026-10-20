require "TimedActions/ISBaseTimedAction"
require "ImmersiveSuicideNetwork"

-- Common code for both actions. Queue FirearmSuicideTimedAction or MeleeSuicideTimedAction instead of this one.
BaseSuicideTimedAction = ISBaseTimedAction:derive("BaseSuicideTimedAction")

function BaseSuicideTimedAction:isValid()
    return ImmersiveSuicideDefinitions.matchesWeapon(self.definition, self.weapon)
        and ImmersiveSuicideDefinitions.isEquipped(self.character, self.weapon)
end

function BaseSuicideTimedAction:start()
    if not self:isValid() then
        self:forceStop()
        return
    end
    self.character:setVariable("PerformSuicideSpeed", self.animSpeed)
    self:setActionAnim(self.anim)
end

function BaseSuicideTimedAction:update()
    local gameSpeed = UIManager:getSpeedControls():getCurrentGameSpeed()
    if gameSpeed ~= 1 then
        UIManager:getSpeedControls():SetCurrentGameSpeed(1)
    end
end

function BaseSuicideTimedAction:animEvent(event, parameter)
    if event == "impactTime" then
        self:performImpact(parameter)
    elseif event == "killTime" and not self.outcomeRequested and self:isValid() then
        self.outcomeRequested = true
        ImmersiveSuicideNetwork.kill(self.character, self.definitionId)
        self:forceComplete()
    end
end

function BaseSuicideTimedAction:perform()
    ISBaseTimedAction.perform(self)
end

function BaseSuicideTimedAction:new(character, weapon, definitionId, maxTime)
    local obj = ISBaseTimedAction:new(character)
    setmetatable(obj, self)
    self.__index = self

    obj.stopOnAim = true
    obj.stopOnWalk = true
    obj.stopOnRun = true

    if maxTime == nil then
        obj.maxTime = -1
        obj.useProgressBar = false
        obj.animSpeed = 1
    else
        obj.maxTime = maxTime
        obj.animSpeed = 1

        -- If Efficiency Skill mod is enabled, update animation speed to a ratio relative of efficiency skill
        if Perks.Efficiency ~= nil then
            local efficiency = obj.character:getPerkLevel(Perks.Efficiency)
            local efficiencyMultipliers = {
                SandboxVars.Efficiency.Level0,
                SandboxVars.Efficiency.Level1,
                SandboxVars.Efficiency.Level2,
                SandboxVars.Efficiency.Level3,
                SandboxVars.Efficiency.Level4,
                SandboxVars.Efficiency.Level5,
                SandboxVars.Efficiency.Level6,
                SandboxVars.Efficiency.Level7,
                SandboxVars.Efficiency.Level8,
                SandboxVars.Efficiency.Level9,
                SandboxVars.Efficiency.Level10,
            }

            local efficientTime = maxTime * efficiencyMultipliers[efficiency + 1]
            obj.animSpeed = 1 + (maxTime / efficientTime) -- Apply percentage increase
        end
    end

    obj.definitionId = definitionId
    obj.definition = ImmersiveSuicideDefinitions.get(definitionId)
    obj.anim = obj.definition and obj.definition.actionAnim
    obj.weapon = weapon

    return obj
end

