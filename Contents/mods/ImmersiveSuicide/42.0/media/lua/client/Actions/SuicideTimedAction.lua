require "TimedActions/ISBaseTimedAction"

SuicideTimedAction = ISBaseTimedAction:derive("SuicideTimedAction")

function SuicideTimedAction:isValid()
    return true
end

function SuicideTimedAction:start()
    if not self.anim then
        print("[Immersive Suicide] No animation for suicide set, forcing complete")
        self:forceComplete()
        return
    end

    if not self.weapon then
        print("[Immersive Suicide] No weapon for suicide set, forcing complete")
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

local function syncCharacterFX(character)
    -- character:startMuzzleFlash() -- BUILD_NOTE: Build 41/42 Difference: This line is enabled and worked for Build 41. It is disabled and DOES NOT work for Build 42 (throws error when enabled).
    character:splatBloodFloorBig()
end

local function performSuicide(character)
    local body = character:getBodyDamage()
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
    
    character:Kill(character)
end

local function killCharacter(character)
    if isClient() then
        sendClientCommand("ImmersiveSuicide", "requestPerformSuicide", {})
    else
        performSuicide(character)
    end
end

function SuicideTimedAction:shootWeapon()
    playWeaponEffects(self.character, self.weapon)
    processWeaponAmmo(self.character, self.weapon)
    if isClient() then
        sendClientCommand("ImmersiveSuicide", "requestSynchronizedCharacterFX", {})
    else
        syncCharacterFX(self.character)
    end
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
    obj.character:setVariable("PerformSuicideSpeed", obj.animSpeed)

    obj.anim = anim
    obj.weapon = weapon

    return obj
end

local function onSuicideServerCommand(module, command, args)
    if module ~= "ImmersiveSuicide" then
        return
    end

    if command == "recieveSynchronizedCharacterFX" then
        local character = getPlayerByOnlineID(args.playerOnlineId)
        syncCharacterFX(character)
    end

    if command == "recievePerformSuicide" then
        local character = getPlayerByOnlineID(args.playerOnlineId)
        performSuicide(character)
    end
end
Events.OnServerCommand.Add(onSuicideServerCommand)
