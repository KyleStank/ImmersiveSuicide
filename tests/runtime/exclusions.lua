-- Give test weapons real item IDs so exclusions can be checked separately from category.
local defs = ImmersiveSuicideDefinitions
local kinds = ImmersiveSuicideWeaponKind

local function shortBlade(fullType)
    local item = weapon(WeaponCategory.SMALL_BLADE)

    function item:getFullType()
        return fullType
    end

    return item
end

-- Check examples from each exclusion group and an ordinary supported knife.
local excludedTypes = {
    "Base.ButterKnife_Silver",
    "Base.SpoonForged",
    "Base.CarvingFork2",
    "Base.Screwdriver_Improvised",
    "Base.SharpBone_Long",
    "Base.MasonsTrowel",
    "Base.DullBoneKnife",
}

for _, fullType in ipairs(excludedTypes) do
    local item = shortBlade(fullType)
    check(defs.isExcluded(item, kinds.SHORT_BLADE), "excluded short blade accepted: " .. fullType)
    check(#defs.getMatchingIds(item) == 0, "excluded item has animation choices: " .. fullType)
end

local knife = shortBlade("Base.KitchenKnife")
local butterKnife = shortBlade("Base.ButterKnife")
check(not defs.isExcluded(knife, kinds.SHORT_BLADE), "kitchen knife excluded")
check(not defs.isExcluded(nil, kinds.SHORT_BLADE), "missing item excluded")
check(not defs.isExcluded(knife, nil), "missing kind excluded")
check(not defs.isExcluded(knife, "unknown"), "missing exclusion group did not return false")
check(not defs.isExcluded(weapon(nil, true), kinds.FIREARM), "firearm with no exclusion group excluded")

-- Classification still recognizes excluded items. Only action entry points reject them.
local definition = defs.get("IS_ShortBladeOneHand")
check(defs.matchesWeapon(definition, butterKnife), "exclusion changed weapon classification")

local originalIsExcluded = defs.isExcluded
local exclusionChecks = 0

defs.isExcluded = function(item, weaponKind)
    exclusionChecks = exclusionChecks + 1
    return originalIsExcluded(item, weaponKind)
end

local gun = weapon(nil, true)
check(#defs.getMatchingIds(gun) == 3 and exclusionChecks == 1, "checked exclusions once per animation instead of once per weapon")

local action = MeleeSuicideTimedAction:new(character(knife), knife, "IS_ShortBladeOneHand")
local before = exclusionChecks
for i = 1, 5 do
    check(action:isValid(), "valid knife action rejected")
end
check(exclusionChecks == before, "action validity repeatedly checked exclusions")
defs.isExcluded = originalIsExcluded

-- An excluded item must not appear in the inventory menu or queue an action directly.
onlinePlayer = character(butterKnife)
local context = {
    options = 0,
    addOption = function(self)
        self.options = self.options + 1
        return {}
    end
}

Events.OnFillInventoryObjectContextMenu.callbacks[1](0, context, { butterKnife, knife })
check(context.options == 1, "excluded item appeared in inventory menu")

queued = nil
ImmersiveSuicide.startSuicide(onlinePlayer, butterKnife)
check(queued == nil, "excluded item queued an action")
ImmersiveSuicide.startSuicide(character(knife), knife)
check(queued ~= nil and queued.weapon == knife, "supported knife did not queue")

-- Recheck support after confirmation, before creating the action.
local pending = shortBlade("Base.KitchenKnife")
SandboxVars.ImmersiveSuicide.ShowConfirmationModal = true
queued = nil
ImmersiveSuicide.startSuicide(character(pending), pending)

function pending:getFullType()
    return "Base.ButterKnife"
end

confirmation()
check(queued == nil, "confirmation callback bypassed exclusions")
SandboxVars.ImmersiveSuicide.ShowConfirmationModal = false

-- The server must reject a request even if the client skipped the menu checks.
local onCommand = Events.OnClientCommand.callbacks[1]
local c = character(butterKnife)
serverMessage = nil
onCommand("ImmersiveSuicide", "requestPerformSuicide", c, { definitionId = "IS_ShortBladeOneHand" })
check(c.kills == 0 and serverMessage == nil, "server accepted excluded weapon")

c = character(knife)
onCommand("ImmersiveSuicide", "requestPerformSuicide", c, { definitionId = "IS_ShortBladeOneHand" })
check(c.kills == 1 and serverMessage[3].definitionId == "IS_ShortBladeOneHand", "server rejected supported knife")
