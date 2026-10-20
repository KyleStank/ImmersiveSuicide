-- Build 42 debug-only prop test. Extends the stock viewer without editing it.
if not getDebug or not getDebug() then return end

require "DebugUIs/AnimationClipViewer"
require "ISUI/ISButton"

if AnimationClipViewer.ISKnifePreviewInstalled then return end
AnimationClipViewer.ISKnifePreviewInstalled = true

local MODEL_ID = "ImmersiveSuicide_KnifePreview"
local MODEL_SCRIPT = "Base.Knife"
local PREFIX = "[ImmersiveSuicide AnimationViewer] "

local function updateVisibility(viewer)
    if not viewer.ISKnifeModelCreated then return end
    local visible = viewer.ISKnifeEnabled and viewer.currentObjectName == "character1"
    if visible == viewer.ISKnifeVisible then return end
    viewer:java2("setObjectVisible", MODEL_ID, visible)
    viewer.ISKnifeVisible = visible
end

local function onKnifeToggle(viewer)
    local enabled = not viewer.ISKnifeEnabled
    local ok, err = pcall(function()
        if enabled and not viewer.ISKnifeModelCreated then
            if not getScriptManager():getModelScript(MODEL_SCRIPT) then
                error("Model script " .. MODEL_SCRIPT .. " was not found")
            end
            -- Same scene calls used by vanilla AttachmentEditorUI.lua.
            viewer:java2("createModel", MODEL_ID, MODEL_SCRIPT)
            viewer.ISKnifeModelCreated = true
            viewer:java2("setModelUseWorldAttachment", MODEL_ID, false)
            viewer:java2("setModelWeaponRotationHack", MODEL_ID, false)
            -- Knife has no right-hand child attachment. Use its model origin;
            -- the parent's attachment maps directly to the animated prop bone.
            viewer:java4("setObjectParent", MODEL_ID, nil, "character1", "Bip01_Prop1")
            print(PREFIX .. "Attached " .. MODEL_SCRIPT .. " to character1/Bip01_Prop1")
        end
        viewer.ISKnifeEnabled = enabled
        updateVisibility(viewer)
    end)
    if not ok then
        if viewer.ISKnifeModelCreated then
            pcall(function() viewer:java1("removeModel", MODEL_ID) end)
        end
        viewer.ISKnifeModelCreated = false
        viewer.ISKnifeEnabled = false
        viewer.ISKnifeVisible = nil
        viewer.ISKnifeButton:setTitle("Knife: ERROR (console)")
        print(PREFIX .. tostring(err))
        return
    end
    viewer.ISKnifeButton:setTitle(enabled and "Kitchen knife: ON" or "Kitchen knife: OFF")
end

local originalCreateToolbar = AnimationClipViewer.createToolbar
function AnimationClipViewer:createToolbar(...)
    originalCreateToolbar(self, ...)
    local button = ISButton:new(
        self.buttonOptions:getRight() + 8, 0, 180, self.buttonOptions:getHeight(),
        "Kitchen knife: OFF", self, onKnifeToggle
    )
    button:initialise()
    button:instantiate()
    button.tooltip = "Preview the vanilla Knife model on the right-hand prop bone."
    self.toolBar:addChild(button)
    self.ISKnifeButton = button
    self.ISKnifeEnabled = false
    self.ISKnifeModelCreated = false
    self.toolBar:setWidth(button:getRight())
    self.toolBar:setX(self.width / 2 - self.toolBar.width / 2)
end

local originalAnimalCombo = AnimationClipViewer.onComboAnimalModel
function AnimationClipViewer:onComboAnimalModel(...)
    originalAnimalCombo(self, ...)
    updateVisibility(self)
end

print(PREFIX .. "Kitchen knife preview toggle installed")
