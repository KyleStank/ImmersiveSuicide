require "Actions/FirearmSuicideTimedAction"
require "Actions/MeleeSuicideTimedAction"

if not ImmersiveSuicide then
    ImmersiveSuicide = {}
end

-- Patches
ImmersiveSuicide.RuntimePatchStatus = ImmersiveSuicide.RuntimePatchStatus or {
    FirearmRadialMenu = false
}

local actionClasses = {
    [ImmersiveSuicideWeaponKind.FIREARM] = FirearmSuicideTimedAction,
    [ImmersiveSuicideWeaponKind.SHORT_BLADE] = MeleeSuicideTimedAction,
}

local function performSuicide(playerObj, item)
    local definitionIds = ImmersiveSuicideDefinitions.getMatchingIds(item)
    if #definitionIds == 0 then return end

    local definitionId = definitionIds[1]
    if #definitionIds > 1 then
        local randomIndex = Math.floor(Math.random() * #definitionIds) + 1
        definitionId = definitionIds[randomIndex]
    end

    local definition = ImmersiveSuicideDefinitions.get(definitionId)
    local actionClass = actionClasses[definition.weaponKind]
    if actionClass then
        ISTimedActionQueue.add(actionClass:new(playerObj, item, definitionId))
    end
end

local function promptSuicideConfirmation(playerObj, item)
    local playerNum = playerObj:getPlayerNum()
    local width, height = 350, 140
    local dialog = ISYesNoDialog:new(
        (getCore():getScreenWidth() / 2) - width / 2,
        (getCore():getScreenHeight() / 2) - height / 2,
        width, height, playerNum,
        function ()
            performSuicide(playerObj, item)
        end)

    dialog:initialise()
    dialog.moveWithMouse = true
    dialog:addToUIManager()

    if JoypadState.players[playerNum + 1] then
        local inventory = getPlayerInventory(playerNum)
        local loot = getPlayerLoot(playerNum)

        inventory:setVisible(false)
        loot:setVisible(false)

        setJoypadFocus(playerNum, dialog)
    end
end

function ImmersiveSuicide.startSuicide(playerObj, item)
    if SandboxVars.ImmersiveSuicide.ShowConfirmationModal then
        promptSuicideConfirmation(playerObj, item)
    else
        performSuicide(playerObj, item)
    end
end
