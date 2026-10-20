-- Named weapon kind constants
ImmersiveSuicideWeaponKind = {
    FIREARM = "firearm",
    SHORT_BLADE = "shortBlade",
}

ImmersiveSuicideDefinitions = {}

-- Items that do not fit the animation for their weapon kind.
local excludedWeapons = {
    [ImmersiveSuicideWeaponKind.SHORT_BLADE] = {
        -- Butter knives
        ["Base.ButterKnife"] = true,
        ["Base.ButterKnife_Gold"] = true,
        ["Base.ButterKnife_Silver"] = true,

        -- Spoons
        ["Base.Spoon"] = true,
        ["Base.Spoon_Gold"] = true,
        ["Base.Spoon_Silver"] = true,
        ["Base.Spoon_Bone"] = true,
        ["Base.SpoonForged"] = true,

        -- Forks
        ["Base.Fork"] = true,
        ["Base.Fork_Gold"] = true,
        ["Base.Fork_Silver"] = true,
        ["Base.Fork_Bone"] = true,
        ["Base.ForkForged"] = true,
        ["Base.CarvingFork2"] = true,
        ["Base.HandFork"] = true,

        -- Screwdrivers
        ["Base.Screwdriver"] = true,
        ["Base.Screwdriver_Old"] = true,
        ["Base.Screwdriver_Improvised"] = true,

        -- Pointed items without a cutting edge
        ["Base.IcePick"] = true,
        ["Base.RailroadSpike"] = true,
        ["Base.Stake"] = true,
        ["Base.SharpBone_Long"] = true,

        -- Other tools and blunt blades
        ["Base.HandShovel"] = true,
        ["Base.MasonsTrowel"] = true,
        ["Base.DullBoneKnife"] = true,
    },
}

-- The client and server use each id to find the settings for an animation.
-- actionAnim must match the PerformingAction condition in that animation's XML file.
local definitions = {
    {
        id = "Suicide_Handgun",
        actionAnim = "Suicide_Handgun", weaponKind = ImmersiveSuicideWeaponKind.FIREARM, bothHands = false,
        targetBodyPart = BodyPartType.Head, causesBullet = true,
    },
    {
        id = "Suicide_Handgun_02",
        actionAnim = "Suicide_Handgun_02", weaponKind = ImmersiveSuicideWeaponKind.FIREARM, bothHands = false,
        targetBodyPart = BodyPartType.Head, causesBullet = true,
    },
    {
        id = "Suicide_Handgun_03",
        actionAnim = "Suicide_Handgun_03", weaponKind = ImmersiveSuicideWeaponKind.FIREARM, bothHands = false,
        targetBodyPart = BodyPartType.Head, causesBullet = true,
    },
    {
        id = "Suicide_Rifle",
        actionAnim = "Suicide_Rifle", weaponKind = ImmersiveSuicideWeaponKind.FIREARM, bothHands = true,
        targetBodyPart = BodyPartType.Head, causesBullet = true,
    },
    {
        id = "IS_ShortBladeOneHand",
        actionAnim = "IS_ShortBladeOneHand", weaponKind = ImmersiveSuicideWeaponKind.SHORT_BLADE, bothHands = false,
        targetBodyPart = BodyPartType.Head, causesBullet = false,
    },
    {
        id = "IS_ShortBladeOneHand2",
        actionAnim = "IS_ShortBladeOneHand2", weaponKind = ImmersiveSuicideWeaponKind.SHORT_BLADE, bothHands = false,
        targetBodyPart = BodyPartType.Head, causesBullet = false,
        impactCount = 3,
    }
}

local definitionsById = {}
for _, definition in ipairs(definitions) do
    definitionsById[definition.id] = definition
end

function ImmersiveSuicideDefinitions.get(id)
    return definitionsById[id]
end

function ImmersiveSuicideDefinitions.isFirearm(item)
    return instanceof(item, "HandWeapon") and item:isAimedFirearm()
end

function ImmersiveSuicideDefinitions.isOneHandedShortBlade(item)
    return instanceof(item, "HandWeapon")
        and not item:isRanged()
        and not item:isTwoHandWeapon()
        and not item:isRequiresEquippedBothHands()
        and item:getScriptItem():containsWeaponCategory(WeaponCategory.SMALL_BLADE)
end

function ImmersiveSuicideDefinitions.getWeaponKind(item)
    if ImmersiveSuicideDefinitions.isFirearm(item) then
        return ImmersiveSuicideWeaponKind.FIREARM
    elseif ImmersiveSuicideDefinitions.isOneHandedShortBlade(item) then
        return ImmersiveSuicideWeaponKind.SHORT_BLADE
    end
    return nil
end

function ImmersiveSuicideDefinitions.isExcluded(item, weaponKind)
    local exclusions = excludedWeapons[weaponKind]
    return item ~= nil and exclusions ~= nil and exclusions[item:getFullType()] == true
end

-- Match weapon type and handedness here. Exclusions are checked before queuing an action.
function ImmersiveSuicideDefinitions.matchesWeapon(definition, item)
    if not definition then return false end

    if definition.weaponKind == ImmersiveSuicideWeaponKind.FIREARM then
        return ImmersiveSuicideDefinitions.isFirearm(item)
            and item:isRequiresEquippedBothHands() == definition.bothHands
    elseif definition.weaponKind == ImmersiveSuicideWeaponKind.SHORT_BLADE then
        return ImmersiveSuicideDefinitions.isOneHandedShortBlade(item)
    end

    return false
end

function ImmersiveSuicideDefinitions.isEquipped(character, item)
    if not instanceof(item, "HandWeapon") then return false end

    if item:isRequiresEquippedBothHands() then
        return character:isItemInBothHands(item)
    end

    return character:isPrimaryHandItem(item)
end

-- Keep the animation choices here so menus and action selection use the same list.
function ImmersiveSuicideDefinitions.getMatchingIds(item)
    local ids = {}
    local weaponKind = ImmersiveSuicideDefinitions.getWeaponKind(item)
    if not weaponKind or ImmersiveSuicideDefinitions.isExcluded(item, weaponKind) then
        return ids
    end

    for _, definition in ipairs(definitions) do
        if ImmersiveSuicideDefinitions.matchesWeapon(definition, item) then
            ids[#ids + 1] = definition.id
        end
    end
    return ids
end
