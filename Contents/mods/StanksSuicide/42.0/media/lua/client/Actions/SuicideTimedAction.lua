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
end

-- Ripped from ISReloadWeaponAction.attackHook
local function playWeaponEffects(character, weapon)
    character:playSound(weapon:getSwingSound());

    local radius = weapon:getSoundRadius();
    if isClient() then -- limit sound radius in MP
        radius = radius / 1.8;
    end

    character:addWorldSoundUnlessInvisible(radius, weapon:getSoundVolume(), false);
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
    
    sendClientCommand("StanksSuicide", "requestPerformSuicide", {})
end

function SuicideTimedAction:shootWeapon()
    playWeaponEffects(self.character, self.weapon)
    processWeaponAmmo(self.character, self.weapon)
    sendClientCommand("StanksSuicide", "requestSynchronizedCharacterFX", {})
end

function SuicideTimedAction:animEvent(event, parameter)
    if event == "shootTime" then
        self:shootWeapon()
    end

    if event == "killTime" then
        killCharacter(self.character)
        self:forceComplete()
    end
end

function SuicideTimedAction:perform()
    ISBaseTimedAction.perform(self)
end

function SuicideTimedAction:new(character, weapon, anim, maxTime)
    local obj = ISBaseTimedAction:new(character)
    setmetatable(obj, self)
    self.__index = self

    obj.stopOnAim = true
    obj.stopOnWalk = true
    obj.stopOnRun = true
    
    if maxTime == nil then
        obj.maxTime = -1
    else
        obj.maxTime = maxTime
    end

    obj.anim = anim
    obj.weapon = weapon

    return obj
end

local function onSuicideServerCommand(module, command, args)
    if module ~= "StanksSuicide" then
        return
    end

    if command == "recieveSynchronizedCharacterFX" then
        local character = getPlayerByOnlineID(args.playerOnlineId)
        character:startMuzzleFlash()
        character:splatBloodFloorBig()
    end

    if command == "recievePerformSuicide" then
        local character = getPlayerByOnlineID(args.playerOnlineId)
        character:Kill(character)
    end
end
Events.OnServerCommand.Add(onSuicideServerCommand)
