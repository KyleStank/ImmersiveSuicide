-- Applying the patch twice should still wrap the original menu only once.
local patch = Events.OnGameStart.callbacks[1]
patch()
local wrapped = ISFirearmRadialMenu.fillMenu
patch()
check(ISFirearmRadialMenu.fillMenu == wrapped, "radial patch installed twice")

-- A loaded firearm should add an option that queues the firearm action.
local gun = weapon(nil, true)
local c = character(gun)
local menu = { character = c, playerNum = 0, getWeapon = ISFirearmRadialMenu.getWeapon }
wrapped(menu)
check(menu.originalCalls == 1 and #radialMenu.slices == 1, "original menu or firearm option missing")

queued = nil
radialMenu.slices[1].callback()
check(
    queued.Type == "FirearmSuicideTimedAction" and queued.weapon == gun,
    "radial option queued wrong action"
)

-- Empty or jammed firearms should not add the option.
gun.loaded = false
wrapped(menu)
check(#radialMenu.slices == 0, "empty gun added radial option")

gun.loaded = true
gun.jammed = true
wrapped(menu)
check(#radialMenu.slices == 0, "jammed gun added radial option")
-- Melee weapons and empty hands should not add the option.
gun.jammed = false
c.held = weapon(WeaponCategory.SMALL_BLADE)
wrapped(menu)
check(#radialMenu.slices == 0, "melee added radial option")

c.held = nil
wrapped(menu)
check(#radialMenu.slices == 0, "missing weapon added radial option")

-- A rifle must be held in both hands.
local rifle = weapon(nil, true, true)
c.held = rifle
wrapped(menu)
check(#radialMenu.slices == 1, "equipped rifle missing radial option")

c.isItemInBothHands = function()
    return false
end
wrapped(menu)
check(#radialMenu.slices == 0, "rifle held in one hand added radial option")
check(menu.originalCalls == 7, "patch skipped or duplicated original menu calls")
