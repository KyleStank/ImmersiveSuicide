require "TimedActions/ISBaseTimedAction"

SuicideTimedAction = ISBaseTimedAction:derive("SuicideTimedAction")

function SuicideTimedAction:isValid()
    return true
end

function SuicideTimedAction:start()
    if not self.anim then
        print("[Stank's Suicide] No animation for suicide set, forcing complete")
        self:forceComplete()
        return
    end

    if not self.weapon then
        print("[Stank's Suicide] No weapon for suicide set, forcing complete")
        self:forceComplete()
        return
    end

    self:setActionAnim(self.anim)
end

function SuicideTimedAction:update()
    -- Ensure game speed is always running at 1 during action
    local gameSpeed = UIManager:getSpeedControls():getCurrentGameSpeed()
    if gameSpeed ~= 1 then
        UIManager:getSpeedControls():SetCurrentGameSpeed(1)
    end

    if self.isComplete then
        self:forceComplete()
    end
end

-- Ripped from ISReloadWeaponAction.attackHook
local function playWeaponEffects(character, weapon)
    character:playSound(weapon:getSwingSound());

    local radius = weapon:getSoundRadius();
    if isClient() then -- limit sound radius in MP
        radius = radius / 1.8;
    end

    character:addWorldSoundUnlessInvisible(radius, weapon:getSoundVolume(), false);
    character:startMuzzleFlash()

    character:splatBloodFloorBig()
end

-- Ripped from ISReloadWeaponAction.onShoot
local function processWeaponAmmo(character, weapon)
    if weapon:haveChamber() then
		weapon:setRoundChambered(false);
	end

	if weapon:isRackAfterShoot() then
		-- shotgun need to be rack after each shot to rechamber round
		-- See ISReloadWeaponAction.OnPlayerAttackFinished()
		if weapon:haveChamber() then
			weapon:setSpentRoundChambered(true);
		end
	else
		-- automatic weapons eject the bullet cartridge
		if not weapon:isManuallyRemoveSpentRounds() then
			if weapon:getShellFallSound() then
                character:playSound(weapon:getShellFallSound())
			end
		end

		if weapon:getCurrentAmmoCount() >= weapon:getAmmoPerShoot() then
			-- remove ammo, add one to chamber if we still have some
			if weapon:haveChamber() then
				weapon:setRoundChambered(true);
			end
			weapon:setCurrentAmmoCount(weapon:getCurrentAmmoCount() - weapon:getAmmoPerShoot())
		end
	end

	if weapon:isManuallyRemoveSpentRounds() then
		weapon:setSpentRoundCount(weapon:getSpentRoundCount() + weapon:getAmmoPerShoot())
	end
end

local function killCharacter(character)
    local body = character:getBodyDamage()
    local head = body:getBodyPart(BodyPartType.Head)

    head:setHaveBullet(true, 0)
    head:SetHealth(0)

    -- Force zombie if sandbox settings are enabled for it
    -- Otherwise, prevent zombie (even if bitten) because the head just got annihilated
    if SandboxVars.StanksSuicide.ForceZombification == true then
        body:setInfected(true)
        body:setInfectionMortalityDuration(0)
        body:setInfectionLevel(100)
    else
        body:setInfected(false)
        body:setInfectionMortalityDuration(-1)
        body:setInfectionLevel(0)
    end
    
    character:Kill(character)
end

function SuicideTimedAction:shootWeapon()
    playWeaponEffects(self.character, self.weapon)
    processWeaponAmmo(self.character, self.weapon)
    killCharacter(self.character)
end

function SuicideTimedAction:animEvent(event, parameter)
    if event == "shootTime" then
        self:shootWeapon()
    end

    if event == "completeTime" then
        self.isComplete = true
    end
end

function SuicideTimedAction:perform()
    ISBaseTimedAction.perform(self)
end

function SuicideTimedAction:new(character, weapon, anim)
    local obj = ISBaseTimedAction:new(character)
    setmetatable(obj, self)
    self.__index = self

    obj.stopOnAim = true
    obj.stopOnWalk = true
    obj.stopOnRun = true
    obj.maxTime = 48 -- No real purpose for maxTime as real functionality uses animation events. This is only here to keep the progress bar there.

    obj.anim = anim
    obj.weapon = weapon
    obj.isComplete = false

    return obj
end
