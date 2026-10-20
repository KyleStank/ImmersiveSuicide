-- These replacements let us test the mod without starting the game.
-- The Java runner loads the real base classes separately.
function require(name)
end

function ipairs(t)
    return function(t, i)
        i = i + 1

        if t[i] ~= nil then
            return i, t[i]
        end
    end, t, 0
end

function check(value, message)
    if not value then
        error(message)
    end
end

-- Only include the game constants needed by these tests.
BodyPartType = {
    Head = "head",
    Torso_Upper = "torso"
}

WeaponCategory = {
    SMALL_BLADE = "base:smallblade",
    SMALL_BLUNT = "shortBlunt"
}

CharacterStat = {
    ZOMBIE_INFECTION = "infection",
    ZOMBIE_FEVER = "fever"
}

Perks = {}

Math = {
    floor = math.floor,
    random = function()
        return 0
    end
}

SandboxVars = {
    ImmersiveSuicide = {
        ForceZombification = false,
        ShowConfirmationModal = false
    }
}

-- Save event handlers so the tests can call them directly.
local function event()
    local callbacks = {}

    return {
        callbacks = callbacks,
        Add = function(fn)
            callbacks[#callbacks + 1] = fn
        end
    }
end

Events = {
    OnGameStart = event(),
    OnClientCommand = event(),
    OnServerCommand = event(),
    OnFillInventoryObjectContextMenu = event()
}

function instanceof(item, class)
    return item ~= nil and item.class == class
end

-- Tests switch between single-player and multiplayer and inspect the messages sent.
clientMode = false

function isClient()
    return clientMode
end

function sendClientCommand(module, command, args)
    clientMessage = { module, command, args }
end

function sendServerCommand(module, command, args)
    serverMessage = { module, command, args }
end

function getPlayerByOnlineID(id)
    return onlinePlayer
end

function getSpecificPlayer(id)
    return onlinePlayer
end

function getText(key)
    return key
end

-- Record menu options, queued actions and confirmation callbacks for later checks.
ISInventoryPane = {
    getActualItems = function(items)
        return items
    end
}

ISToolTip = {
    new = function()
        return {
            initialise = function()
            end,
            setName = function()
            end
        }
    end
}

ISTimedActionQueue = {
    add = function(action)
        queued = action
    end,
    getTimedActionQueue = function(character)
        return {
            resetQueue = function()
                character.cancelled = true
            end,
            onCompleted = function(queue, action)
                character.queueCompleted = true
            end,
        }
    end,
}

ISLogSystem = {
    logAction = function()
    end
}

ISYesNoDialog = {
    new = function(self, x, y, w, h, num, callback)
        confirmation = callback

        return {
            initialise = function()
            end,
            addToUIManager = function()
            end
        }
    end
}

JoypadState = { players = {} }

function getCore()
    return {
        getScreenWidth = function()
            return 100
        end,
        getScreenHeight = function()
            return 100
        end
    }
end

-- Track ammunition use and fail if a melee weapon reaches the firearm checks.
ISReloadWeaponAction = {
    canShoot = function(character, weapon)
        check(weapon.firearm, "melee called firearm validation")
        return weapon.loaded and not weapon.jammed
    end,
    onShoot = function(character, weapon)
        weapon.loaded = false
        weapon.shots = (weapon.shots or 0) + 1
    end,
}

function getSandboxOptions()
    return {
        getOptionByName = function()
            return {
                getValue = function()
                    return 1
                end
            }
        end
    }
end

-- Create a test weapon with the methods our mod calls.
function weapon(category, firearm, twoHands)
    local item = {
        class = "HandWeapon",
        category = category,
        firearm = firearm == true,
        twoHands = twoHands == true,
        loaded = true
    }

    function item:isAimedFirearm()
        return self.firearm
    end

    function item:isRanged()
        return self.firearm
    end

    function item:isTwoHandWeapon()
        return self.twoHands
    end

    function item:isRequiresEquippedBothHands()
        return self.twoHands
    end

    function item:getScriptItem()
        return self
    end

    function item:containsWeaponCategory(category)
        return self.category == category
    end

    function item:getSwingSound()
        return "sound"
    end

    function item:getSoundRadius()
        return 5
    end

    function item:getSoundVolume()
        return 5
    end

    function item:getFullType()
        return self.category or "gun"
    end

    function item:getName()
        return self:getFullType()
    end

    return item
end

-- Record injuries, blood, equipment and death on a test character.
function character(item)
    local c = {
        held = item,
        kills = 0,
        blood = 0,
        parts = {},
        stats = {}
    }

    c.body = {
        getBodyPart = function(body, part)
            c.lastTarget = part

            if not c.parts[part] then
                c.parts[part] = {
                    setHaveBullet = function(target, value)
                        target.bullet = value
                    end,
                    SetHealth = function(target, value)
                        target.health = value
                    end,
                }
            end

            return c.parts[part]
        end,
        setInfected = function(body, value)
            c.infected = value
        end,
        setInfectionMortalityDuration = function(body, value)
            c.mortality = value
        end,
        setInfectionTime = function(body, value)
            c.infectionTime = value
        end,
    }

    function c:setIsFarming(value)
    end

    function c:getPlayerNum()
        return 0
    end

    function c:getBodyDamage()
        return self.body
    end

    function c:getStats()
        return {
            set = function(stats, key, value)
                self.stats[key] = value
            end
        }
    end

    function c:Kill()
        self.kills = self.kills + 1
    end

    function c:splatBloodFloorBig()
        self.blood = self.blood + 1
    end

    function c:isPrimaryHandItem(item)
        return self.held == item
    end

    function c:isItemInBothHands(item)
        return self.held == item and item.twoHands
    end

    function c:getPrimaryHandItem()
        return self.held
    end

    function c:getOnlineID()
        return 1
    end

    function c:setVariable(key, value)
        self[key] = value
    end

    function c:playSound()
    end

    function c:isOutside()
        return true
    end

    function c:addWorldSoundUnlessInvisible()
    end

    return c
end

-- Record what the timed action asks the game to do.
function engineAction(action)
    action.action = {
        setActionAnim = function(engine, anim)
            action.playing = anim
        end,
        forceStop = function()
            action.stopped = true
        end,
        forceComplete = function()
            action.completed = true
        end,
    }

    return action
end

-- Keep the menu simple so the tests focus on what our patch adds.
radialMenu = { slices = {} }

function radialMenu:addSlice(text, texture, callback)
    self.slices[#self.slices + 1] = { callback = callback }
end

function getPlayerRadialMenu(playerNum)
    return radialMenu
end

function getTexture(path)
    return path
end

ISFirearmRadialMenu = {
    fillMenu = function(self)
        self.originalCalls = (self.originalCalls or 0) + 1
        radialMenu.slices = {}
    end,
    getWeapon = function(self)
        return self.character:getPrimaryHandItem()
    end,
}
