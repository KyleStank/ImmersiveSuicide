require "Actions/SuicideTimedAction"

local function performOneHandedSuicide(playerObj, item)
    local animations = {"Suicide_Handgun", "Suicide_Handgun_02", "Suicide_Handgun_03"}
    local randomIndex = Math.floor(Math.random() * 3) + 1
    local selectedAnimation = animations[randomIndex]

    ISTimedActionQueue.add(SuicideTimedAction:new(playerObj, item, selectedAnimation))
end

local function performTwoHandedSuicide(playerObj, item)
    ISTimedActionQueue.add(SuicideTimedAction:new(playerObj, item, "Suicide_Rifle"))
end

local function promptSuicideConfirmation(playerObj, item, type)
    local playerNum = playerObj:getPlayerNum()
    local width, height = 350, 140
    local dialog = ISYesNoDialog:new(
        (getCore():getScreenWidth() / 2) - width / 2,
        (getCore():getScreenHeight() / 2) - height / 2,
        width, height, playerNum,
        function ()
            if type == "ONE_HANDED" then
                performOneHandedSuicide(playerObj, item)
            elseif type == "TWO_HANDED" then
                performTwoHandedSuicide(playerObj, item)
            end
        end)

    dialog:initialise()
    dialog.moveWithMouse = true
    dialog:addToUIManager()
end

local function onSuicideInventoryOptionSelected(playerObj, item)
    if not item:isRequiresEquippedBothHands() then
        promptSuicideConfirmation(playerObj, item, "ONE_HANDED")
    else
        promptSuicideConfirmation(playerObj, item, "TWO_HANDED")
    end
end

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

                local option = context:addOption(getText("ContextMenu_ImmersiveSuicide_Suicide"), playerObj, onSuicideInventoryOptionSelected, item)
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
                elseif not ISReloadWeaponAction.canShoot(item) then
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
