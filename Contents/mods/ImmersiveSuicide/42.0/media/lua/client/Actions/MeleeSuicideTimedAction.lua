require "Actions/BaseSuicideTimedAction"

MeleeSuicideTimedAction = BaseSuicideTimedAction:derive("MeleeSuicideTimedAction")

function MeleeSuicideTimedAction:isValid()
    return self.definition ~= nil and self.definition.weaponKind == ImmersiveSuicideWeaponKind.SHORT_BLADE
        and BaseSuicideTimedAction.isValid(self)
end

function MeleeSuicideTimedAction:performImpact()
    if self.impactPerformed or not self:isValid() then return end

    self.impactPerformed = true

    self.character:playSound(self.weapon:getSwingSound())

    ImmersiveSuicideNetwork.impact(self.character)
end
