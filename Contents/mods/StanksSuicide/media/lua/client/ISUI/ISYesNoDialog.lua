require "ISUI/ISModalDialog"

ISYesNoDialog = ISModalDialog:derive("ISYesNoDialog")

function ISYesNoDialog:onClickCallback(button)
    if self.onYesCallback and button.internal == "YES" then
        self.onYesCallback()
    elseif self.onNoCallback and button.internal == "NO" then
        self.onNoCallback()
    end
end

function ISYesNoDialog:new(x, y, width, height, player, onYesCallback, onNoCallback)
    local obj = ISModalDialog:new(
        x, y, width, height, getText("UI_StanksSuicide_ConfirmSuicide"), true, nil, ISYesNoDialog.onClickCallback, player, nil, nil)
    setmetatable(obj, self)
    self.__index = self;

    obj.onYesCallback = onYesCallback
    obj.onNoCallback = onNoCallback
    obj.target = obj

    return obj
end
