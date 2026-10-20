require "Actions/BaseSuicideTimedAction"

MeleeSuicideTimedAction = BaseSuicideTimedAction:derive("MeleeSuicideTimedAction")

function MeleeSuicideTimedAction:isValid()
    return self.definition ~= nil and self.definition.weaponKind == ImmersiveSuicideWeaponKind.SHORT_BLADE
        and BaseSuicideTimedAction.isValid(self)
end

function MeleeSuicideTimedAction:performImpact(parameter)
    if self.outcomeRequested or not self:isValid() then
        return
    end

    local impactNumber = 1
    if parameter ~= nil and parameter ~= "" then
        impactNumber = tonumber(parameter)
    end

    local impactCount = self.definition.impactCount or 1
    if impactNumber == nil or impactNumber < 1 or impactNumber > impactCount
        or impactNumber ~= math.floor(impactNumber) then
        return
    end

    self.processedImpacts = self.processedImpacts or {}
    if self.processedImpacts[impactNumber] then
        return
    end
    self.processedImpacts[impactNumber] = true

    self.character:playSound(self.weapon:getSwingSound())
    self.character:playSound("HeadStab")
    self.character:transmitPlayerVoiceSound("PainFromLacerate")

    ImmersiveSuicideNetwork.impact(self.character)
end
