require "ImmersiveSuicide"
require "ISUI/ISFirearmRadialMenu"
require "TimedActions/ISReloadWeaponAction"

local function applyPatch()
    if ImmersiveSuicide.RuntimePatchStatus.FirearmRadialMenu then
        return
    end
    ImmersiveSuicide.RuntimePatchStatus.FirearmRadialMenu = true

    local _origFillMenu = ISFirearmRadialMenu.fillMenu

    function ISFirearmRadialMenu:fillMenu(...)
        _origFillMenu(self, ...)

        local menu = getPlayerRadialMenu(self.playerNum)
        local weapon = self:getWeapon()
        if not ImmersiveSuicideDefinitions.isFirearm(weapon)
            or not ImmersiveSuicideDefinitions.isEquipped(self.character, weapon)
            or ImmersiveSuicideDefinitions.isExcluded(weapon, ImmersiveSuicideWeaponKind.FIREARM) then
            return
        end

        if not ISReloadWeaponAction.canShoot(self.character, weapon) then
            return
        end

        menu:addSlice(
            getText("ContextMenu_ImmersiveSuicide_Suicide"),
            getTexture("media/ui/FirearmRadial_Suicide.png"),
            function()
                ImmersiveSuicide.startSuicide(self.character, weapon)
            end,
            self.character,
            weapon
        )
    end
end

Events.OnGameStart.Add(applyPatch)