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
        if instanceof(item, "HandWeapon") and item:isAimedFirearm() then
            local itemType = item:getFullType() .. "_" .. item:getName()
            if not addedItems[itemType] then
                addedItems[itemType] = true

                local option = context:addOption(getText("ContextMenu_ImmersiveSuicide_Suicide"), playerObj, ImmersiveSuicide.startSuicide, item)
                if item:isRequiresEquippedBothHands() and not playerObj:isItemInBothHands(item) then
                    createAndSetDisabledToolTipForOption(
                        getText("UI_ImmersiveSuicide_EquipRequired_Tooltip"),
                        getText("UI_ImmersiveSuicide_EquipRequired_TwoHands_Tooltip_Description"),
                        option)
                elseif not item:isRequiresEquippedBothHands() and not playerObj:isPrimaryHandItem(item) then
                    createAndSetDisabledToolTipForOption(
                        getText("UI_ImmersiveSuicide_EquipRequired_Tooltip"),
                        getText("UI_ImmersiveSuicide_EquipRequired_OneHand_Description"),
                        option)
                elseif not ISReloadWeaponAction.canShoot(item) then -- BUILD_NOTE: Build 41/42 Difference: "playerObj" does NOT get passed into this function for Build 41
                    createAndSetDisabledToolTipForOption(
                        getText("UI_ImmersiveSuicide_NoShoot_Tooltip"),
                        getText("UI_ImmersiveSuicide_NoShoot_Tooltip_Description"),
                        option)
                end
            end
        end
    end
end

Events.OnFillInventoryObjectContextMenu.Add(addSuicideOptionInventory)
