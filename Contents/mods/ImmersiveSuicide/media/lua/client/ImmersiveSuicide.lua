require "Actions/SuicideTimedAction"

if not ImmersiveSuicide then
    ImmersiveSuicide = {}
end

-- Patches
ImmersiveSuicide.RuntimePatchStatus = {
    FirearmRadialMenu = false
}

local function performOneHandedSuicide(playerObj, item)
    local animations = {"Suicide_Handgun", "Suicide_Handgun_02", "Suicide_Handgun_03"}
    local randomIndex = Math.floor(Math.random() * 3) + 1
    local selectedAnimation = animations[randomIndex]

    ISTimedActionQueue.add(SuicideTimedAction:new(playerObj, item, selectedAnimation))
end

local function performTwoHandedSuicide(playerObj, item)
    ISTimedActionQueue.add(SuicideTimedAction:new(playerObj, item, "Suicide_Rifle"))
end

local function performSuicide(playerObj, item)
    if not item:isRequiresEquippedBothHands() then
        performOneHandedSuicide(playerObj, item)
    else
        performTwoHandedSuicide(playerObj, item)
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
end

function ImmersiveSuicide.startSuicide(playerObj, item)
    if SandboxVars.ImmersiveSuicide.ShowConfirmationModal then
        promptSuicideConfirmation(playerObj, item)
    else
        performSuicide(playerObj, item)
    end
end
