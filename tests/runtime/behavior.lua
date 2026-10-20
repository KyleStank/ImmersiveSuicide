-- Check weapon eligibility, animation events and the messages sent in multiplayer.
local defs = ImmersiveSuicideDefinitions
local knife = weapon(WeaponCategory.SMALL_BLADE)
local hammer = weapon("shortBlunt")
local twoHandBlade = weapon(WeaponCategory.SMALL_BLADE, false, true)
local gun = weapon(nil, true)
local rifle = weapon(nil, true, true)
check(defs.isOneHandedShortBlade(knife), "knife rejected")
check(not defs.isOneHandedShortBlade(hammer), "hammer accepted")
check(not defs.isOneHandedShortBlade(twoHandBlade), "two-handed blade accepted")
check(not defs.isOneHandedShortBlade(gun), "gun accepted as blade")
check(not defs.isOneHandedShortBlade(nil), "nil accepted")
check(not defs.isOneHandedShortBlade({class = "Food"}), "non-weapon accepted")

-- A melee impact should add blood without using ammunition.
local c = character(knife)
local melee = engineAction(MeleeSuicideTimedAction:new(c, knife, "IS_ShortBladeOneHand"))
check(melee:isValid(), "inherited constructor lost melee methods")
melee:start()
check(melee.playing == "IS_ShortBladeOneHand" and c.PerformSuicideSpeed == 1, "animation setup failed")
melee:animEvent("unrelatedEvent")
check(c.blood == 0, "melee handled unrelated event")
melee:animEvent("impactTime")
melee:animEvent("impactTime")
check(c.blood == 1 and knife.shots == nil, "melee impact duplicated or consumed ammo")
melee:animEvent("killTime")
melee:animEvent("killTime")
check(c.kills == 1 and melee.completed, "melee death duplicated or unfinished")
check(c.parts.head.health == 0 and c.parts.head.bullet == nil, "melee bullet or wrong damage")
melee:perform()
check(c.queueCompleted, "queue completion did not reach base class")
check(c.infected == false and c.infectionTime == 0 and c.stats.infection == 0, "default sandbox policy")

-- A firearm should use one round and add a bullet wound.
c = character(gun)
local firearm = engineAction(FirearmSuicideTimedAction:new(c, gun, "Suicide_Handgun"))
firearm:start()
firearm:animEvent("unrelatedEvent")
check(c.blood == 0, "firearm handled unrelated event")
firearm:animEvent("impactTime")
firearm:animEvent("impactTime")
check(gun.shots == 1 and c.blood == 1, "firearm impact duplicated")
check(firearm:isValid(), "empty gun invalidated action after shot")
firearm:animEvent("killTime")
check(c.kills == 1 and c.parts.head.bullet == true, "firearm outcome missing bullet")

local empty = engineAction(FirearmSuicideTimedAction:new(c, gun, "Suicide_Handgun"))
empty:start()
check(empty.stopped and not empty.playing, "empty/jammed firearm not stopped")

gun.loaded = true
gun.jammed = true
local jammed = engineAction(FirearmSuicideTimedAction:new(c, gun, "Suicide_Handgun"))
jammed:start()
check(jammed.stopped, "jammed firearm started")

gun.jammed = false
check(
    FirearmSuicideTimedAction:new(character(rifle), rifle, "Suicide_Rifle"):isValid(),
    "rifle rejected"
)
check(
    not FirearmSuicideTimedAction:new(character(gun), gun, "Suicide_Rifle"):isValid(),
    "wrong firearm handedness accepted"
)

-- Cancelled or invalid actions must not kill the character.
c = character(knife)
local cancelled = engineAction(MeleeSuicideTimedAction:new(c, knife, "IS_ShortBladeOneHand"))
cancelled:start()
cancelled:stop()
check(c.cancelled and c.kills == 0, "cancellation failed")

c.held = nil
check(not cancelled:isValid(), "unequipped action stayed valid")
cancelled:animEvent("killTime")
check(c.kills == 0, "invalid action killed character")

local unknown = engineAction(MeleeSuicideTimedAction:new(c, knife, "unknown"))
unknown:start()
check(unknown.stopped, "unknown definition started")

-- Changing the definition should change the injured body part.
-- A melee action should leave an existing bullet wound alone.
local bladeDef = defs.get("IS_ShortBladeOneHand")
bladeDef.targetBodyPart = BodyPartType.Torso_Upper
SandboxVars.ImmersiveSuicide.ForceZombification = true
c = character(knife)
c.parts.torso = {
    bullet = true,
    SetHealth = function(part, value)
        part.health = value
    end
}
ImmersiveSuicideOutcome.perform(c, "IS_ShortBladeOneHand")
check(c.lastTarget == "torso" and c.parts.torso.bullet == true, "torso data ignored or bullet removed")
check(c.infected and c.infectionTime == -1 and c.stats.fever == 100, "forced zombification policy")
bladeDef.targetBodyPart = BodyPartType.Head
SandboxVars.ImmersiveSuicide.ForceZombification = false
check(not ImmersiveSuicideOutcome.perform(c, "unknown"), "unknown outcome accepted")
check(not ImmersiveSuicideOutcome.perform(nil, "Suicide_Rifle"), "missing player accepted")

-- Check that the inventory menu and queued actions accept the same weapons.
onlinePlayer = character(knife)
local context = {
    options = 0,
    addOption = function(self)
        self.options = self.options + 1
        return {}
    end
}
Events.OnFillInventoryObjectContextMenu.callbacks[1](0, context, {knife, hammer, twoHandBlade, gun})
check(context.options == 2, "inventory eligibility mismatch")

ImmersiveSuicide.startSuicide(onlinePlayer, knife)
check(queued.Type == "MeleeSuicideTimedAction", "knife queued wrong class")

queued = nil
ImmersiveSuicide.startSuicide(onlinePlayer, hammer)
check(queued == nil, "hammer queued")

ImmersiveSuicide.startSuicide(onlinePlayer, gun)
check(queued.Type == "FirearmSuicideTimedAction", "gun queued wrong class")

-- Confirmation should delay queuing the action until the player accepts.
SandboxVars.ImmersiveSuicide.ShowConfirmationModal = true
queued = nil
ImmersiveSuicide.startSuicide(onlinePlayer, knife)
check(queued == nil and confirmation ~= nil, "confirmation did not defer action")
confirmation()
check(queued.Type == "MeleeSuicideTimedAction", "confirmation queued wrong action")

SandboxVars.ImmersiveSuicide.ShowConfirmationModal = false

-- Send a death request to the server, then pass its response to the observing client.
clientMode = true
c = character(knife)
ImmersiveSuicideNetwork.kill(c, "IS_ShortBladeOneHand")
check(c.kills == 0 and clientMessage[3].definitionId == "IS_ShortBladeOneHand", "client request payload")

local onCommand = Events.OnClientCommand.callbacks[1]
serverMessage = nil
onCommand(clientMessage[1], clientMessage[2], c, clientMessage[3])
check(
    c.kills == 1 and serverMessage[3].definitionId == "IS_ShortBladeOneHand",
    "server outcome/broadcast"
)
onlinePlayer = character(knife)
Events.OnServerCommand.callbacks[1](serverMessage[1], serverMessage[2], serverMessage[3])
check(onlinePlayer.kills == 1 and onlinePlayer.parts.head.bullet == nil, "client received wrong outcome")

local before = c.kills
serverMessage = nil
onCommand("ImmersiveSuicide", "requestPerformSuicide", c, { definitionId = "unknown" })
onCommand("ImmersiveSuicide", "requestPerformSuicide", c, { definitionId = "Suicide_Rifle" })
onCommand("ImmersiveSuicide", "requestPerformSuicide", c, {})
c.held = hammer
onCommand("ImmersiveSuicide", "requestPerformSuicide", c, { definitionId = "IS_ShortBladeOneHand" })
check(c.kills == before and serverMessage == nil, "invalid MP requests accepted")
-- The server and observing client should both apply the firearm bullet wound.
c = character(gun)
onCommand("ImmersiveSuicide", "requestPerformSuicide", c, { definitionId = "Suicide_Handgun" })
onlinePlayer = character(gun)
Events.OnServerCommand.callbacks[1](serverMessage[1], serverMessage[2], serverMessage[3])
check(c.parts.head.bullet and onlinePlayer.parts.head.bullet, "MP firearm bullet flag lost")
onlinePlayer = nil
Events.OnServerCommand.callbacks[1](serverMessage[1], serverMessage[2], serverMessage[3])
Events.OnServerCommand.callbacks[1]("ImmersiveSuicide", "recieveSynchronizedCharacterFX", { playerOnlineId = 999 })
check(#Events.OnServerCommand.callbacks == 1, "network handler registered per action")
