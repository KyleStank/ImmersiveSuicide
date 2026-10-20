require "Actions/BaseSuicideTimedAction"
require "TimedActions/ISReloadWeaponAction"

FirearmSuicideTimedAction = BaseSuicideTimedAction:derive("FirearmSuicideTimedAction")

function FirearmSuicideTimedAction:isValid()
    return self.definition ~= nil and self.definition.weaponKind == ImmersiveSuicideWeaponKind.FIREARM
        and BaseSuicideTimedAction.isValid(self)
end

function FirearmSuicideTimedAction:start()
    if not self:isValid() or not ISReloadWeaponAction.canShoot(self.character, self.weapon) then
        self:forceStop()
        return
    end
    BaseSuicideTimedAction.start(self)
end

function FirearmSuicideTimedAction:performImpact()
    if self.impactPerformed or not self:isValid() then return end

    if not ISReloadWeaponAction.canShoot(self.character, self.weapon) then
        self:forceStop()
        return
    end

    self.impactPerformed = true
    
    self.character:playSound(self.weapon:getSwingSound())
    local radius = self.weapon:getSoundRadius()
        * getSandboxOptions():getOptionByName("FirearmNoiseMultiplier"):getValue()
    if not self.character:isOutside() then radius = radius * 0.5 end
    self.character:addWorldSoundUnlessInvisible(radius, self.weapon:getSoundVolume(), true)
    
    ISReloadWeaponAction.onShoot(self.character, self.weapon)
    ImmersiveSuicideNetwork.impact(self.character)
end
