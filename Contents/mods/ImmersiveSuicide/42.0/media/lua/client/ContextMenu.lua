require "ImmersiveSuicide"
require "TimedActions/ISReloadWeaponAction"

local function createToolTip(title, description)
    local toolTip = ISToolTip:new()
    toolTip:initialise()
    toolTip:setName(title)
    toolTip.description = description
    return toolTip
end

local function createAndSetDisabledToolTipForOption(title, description, option)
    local tooltip = createToolTip(title, description)
    option.toolTip = tooltip
    option.notAvailable = true
end

local function addSuicideOptionInventory(player, context, items)
    local playerObj = getSpecificPlayer(player)
    local invItems = ISInventoryPane.getActualItems(items)
    local addedItems = {} -- Track item types that have had context menu added to them
    for _, item in ipairs(invItems) do
        local definitionIds = ImmersiveSuicideDefinitions.getMatchingIds(item)
        local definition = ImmersiveSuicideDefinitions.get(definitionIds[1])
        local itemType = item:getFullType() .. "_" .. item:getName()
        if definition and not addedItems[itemType] then
            addedItems[itemType] = true

            local option = context:addOption(getText("ContextMenu_ImmersiveSuicide_Suicide"), playerObj, ImmersiveSuicide.startSuicide, item)
            if not ImmersiveSuicideDefinitions.isEquipped(playerObj, item) then
                local descriptionKey = "UI_ImmersiveSuicide_EquipRequired_OneHand_Description"
                if item:isRequiresEquippedBothHands() then
                    descriptionKey = "UI_ImmersiveSuicide_EquipRequired_TwoHands_Tooltip_Description"
                end
                createAndSetDisabledToolTipForOption(
                    getText("UI_ImmersiveSuicide_EquipRequired_Tooltip"),
                    getText(descriptionKey),
                    option)
            elseif definition.weaponKind == ImmersiveSuicideWeaponKind.FIREARM
                and not ISReloadWeaponAction.canShoot(playerObj, item) then
                createAndSetDisabledToolTipForOption(
                    getText("UI_ImmersiveSuicide_NoShoot_Tooltip"),
                    getText("UI_ImmersiveSuicide_NoShoot_Tooltip_Description"),
                    option)
            end
        end
    end
end

Events.OnFillInventoryObjectContextMenu.Add(addSuicideOptionInventory)
