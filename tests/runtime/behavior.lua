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
melee:animEvent("impactTime", "")
melee:animEvent("impactTime", "1")
melee:animEvent("impactTime", "2")
check(c.blood == 1 and knife.shots == nil, "melee impact duplicated or consumed ammo")
melee:animEvent("killTime")
melee:animEvent("killTime")
check(c.kills == 1 and melee.completed, "melee death duplicated or unfinished")
check(c.parts.head.health == 0 and c.parts.head.bullet == nil, "melee bullet or wrong damage")
melee:perform()
check(c.queueCompleted, "queue completion did not reach base class")
check(c.infected == false and c.infectionTime == 0 and c.stats.infection == 0, "default sandbox policy")

-- Play the real three-stab XML events, including duplicate callbacks.
c = character(knife)
local repeated = engineAction(MeleeSuicideTimedAction:new(c, knife, "IS_ShortBladeOneHand2"))
repeated:start()
for _, parameter in ipairs({"invalid", "0", "-1", "1.5", "4"}) do
    repeated:animEvent("impactTime", parameter)
end
check(c.blood == 0 and #c.sounds == 0 and #c.voices == 0, "invalid impact played effects")

local previousTime = 0
for _, event in ipairs(headStabAnimationEvents) do
    check(event.time > previousTime and event.time <= 1, "animation events are not in playback order")
    previousTime = event.time
    repeated:animEvent(event.name, event.parameter)
    local blood = c.blood
    local sounds = #c.sounds
    local voices = #c.voices
    repeated:animEvent(event.name, event.parameter)
    check(c.blood == blood and #c.sounds == sounds and #c.voices == voices, "duplicate event repeated effects")
end
check(c.blood == 3 and #c.sounds == 6 and #c.voices == 3, "three-stab XML did not perform three impacts")
check(c.kills == 1 and repeated.completed, "repeated impacts changed death handling")

-- A failed eligibility check must not consume an impact number.
c = character(knife)
local invalidImpact = engineAction(MeleeSuicideTimedAction:new(c, knife, "IS_ShortBladeOneHand2"))
c.held = nil
invalidImpact:animEvent("impactTime", "2")
check(c.blood == 0, "unequipped action performed an impact")
c.held = knife
invalidImpact:animEvent("impactTime", "2")
check(c.blood == 1, "invalid callback consumed the impact number")
invalidImpact:animEvent("killTime")
invalidImpact:animEvent("impactTime", "3")
check(c.blood == 1, "impact performed after requesting death")

-- A firearm should use one round and add a bullet wound.
c = character(gun)
local firearm = engineAction(FirearmSuicideTimedAction:new(c, gun, "Suicide_Handgun"))
firearm:start()
firearm:animEvent("unrelatedEvent")
check(c.blood == 0, "firearm handled unrelated event")
firearm:animEvent("impactTime")
firearm:animEvent("impactTime")
firearm:animEvent("impactTime", "2")
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

-- Every distinct melee impact follows the existing server/client blood-FX path.
local repeatedCharacter = character(knife)
local observedCharacter = character(knife)
local networked = engineAction(MeleeSuicideTimedAction:new(repeatedCharacter, knife, "IS_ShortBladeOneHand2"))
for impactNumber = 1, 3 do
    clientMessage = nil
    networked:animEvent("impactTime", tostring(impactNumber))
    check(clientMessage ~= nil, "numbered impact did not send its FX request")
    local request = clientMessage
    clientMessage = nil
    networked:animEvent("impactTime", tostring(impactNumber))
    check(clientMessage == nil, "duplicate impact sent another FX request")
    serverMessage = nil
    onCommand(request[1], request[2], repeatedCharacter, request[3])
    check(serverMessage ~= nil, "server did not relay the impact FX")
    onlinePlayer = observedCharacter
    Events.OnServerCommand.callbacks[1](serverMessage[1], serverMessage[2], serverMessage[3])
end
check(observedCharacter.blood == 3 and observedCharacter.kills == 0, "observer did not receive three nonfatal impacts")

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
