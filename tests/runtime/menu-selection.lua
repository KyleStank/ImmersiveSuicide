-- Check that each weapon gets the expected animation choices.
local defs = ImmersiveSuicideDefinitions
local knife = weapon(WeaponCategory.SMALL_BLADE)
local gun = weapon(nil, true)
local rifle = weapon(nil, true, true)
local hammer = weapon(WeaponCategory.SMALL_BLUNT)
check(#defs.getMatchingIds(gun) == 3, "handgun animation choices changed")
check(defs.getMatchingIds(rifle)[1] == "Suicide_Rifle", "rifle definition mismatch")
check(defs.getMatchingIds(knife)[1] == "IS_ShortBladeOneHand", "knife definition mismatch")
check(#defs.getMatchingIds(hammer) == 0, "unsupported weapon has definitions")

-- Try each handgun animation by controlling the random result.
local random = Math.random
local expected = { "Suicide_Handgun", "Suicide_Handgun_02", "Suicide_Handgun_03" }
for i, id in ipairs(expected) do
    Math.random = function()
        return (i - 1) / 3
    end
    ImmersiveSuicide.startSuicide(character(gun), gun)
    check(
        queued.definitionId == id and queued.Type == "FirearmSuicideTimedAction",
        "handgun choice/routing changed"
    )
end
Math.random = random
ImmersiveSuicide.startSuicide(character(rifle), rifle)
check(queued.definitionId == "Suicide_Rifle", "rifle selected wrong action")

-- Build an inventory menu and return its options for the checks below.
local function menuFor(c, items)
    onlinePlayer = c
    local context = { options = {} }
    function context:addOption(text, player, callback, item)
        local option = { callback = callback, item = item }
        self.options[#self.options + 1] = option
        return option
    end
    Events.OnFillInventoryObjectContextMenu.callbacks[1](0, context, items)
    return context.options
end
-- Duplicate items should add one option. Unequipped weapons should show a tooltip.
local c = character(knife)
local options = menuFor(c, {knife, knife, hammer})
check(#options == 1 and not options[1].notAvailable, "duplicate handling or knife availability changed")
check(
    options[1].callback == ImmersiveSuicide.startSuicide and options[1].item == knife,
    "inventory callback changed"
)
c.held = nil
options = menuFor(c, {knife})
check(
    options[1].notAvailable and options[1].toolTip.description == "UI_ImmersiveSuicide_EquipRequired_OneHand_Description",
    "knife equipment tooltip changed"
)
-- Equipment warnings should take priority over ammunition warnings.
c = character(gun)
gun.loaded = false
options = menuFor(c, {gun})
check(
    options[1].notAvailable and options[1].toolTip.description == "UI_ImmersiveSuicide_NoShoot_Tooltip_Description",
    "empty gun tooltip changed"
)
gun.loaded = true
gun.jammed = true
options = menuFor(c, {gun})
check(options[1].notAvailable, "jammed gun enabled")

c.held = nil
options = menuFor(c, {gun})
check(
    options[1].toolTip.description == "UI_ImmersiveSuicide_EquipRequired_OneHand_Description",
    "ammo tooltip took priority over equipment"
)
c = character(rifle)
c.isItemInBothHands = function()
    return false
end
options = menuFor(c, {rifle})
check(
    options[1].notAvailable and options[1].toolTip.description == "UI_ImmersiveSuicide_EquipRequired_TwoHands_Tooltip_Description",
    "rifle equipment tooltip changed"
)
