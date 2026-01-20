

# ----------------------------
# Guild, channel and roles
# ----------------------------

TICKET_CATEGORY_ID = 1461438586066043083  # Obvious enough retard !
STAFF_ROLE_ID = 1435954554180206655       # All Mods !


GUILD_ID = 1362770221034897639 # !
MOD_LOG_CHANNEL_ID = 1438981968380301403 # !
VOUCH_CHANNEL_ID = 1442867774337843381 #

PERMISSION_TIERS = {
    1362889706563440900: ["kick", "ban", "timeout", "log", "warn", "warnlog", "warndelete",
                          "panel"],  # owner
    1362896066504036402: ["kick", "ban", "timeout", "log", "warn", "warnlog", "warndelete"],  # co owner
    1399809075252039824: ["kick", "ban", "timeout", "log", "warn", "warnlog", "warndelete"],  # senior
    1391861560967954483: ["kick", "ban", "timeout", "log", "warn", "warnlog", "warndelete"],  # mod
    1399808293999738961: ["kick", "timeout", "log", "warn", "warnlog", "warndelete"],  # junior
    1440250118946164816: ["timeout", "warn", "warnlog", "warndelete", "log"],  # trial
}



# Role ladders: Class role + ranks [Base, Apprentice, Master]
ROLE_LADDERS = {
    "Enmity Hoster": {
        "class": 1438977760872628327,
        "ranks": [
            1362807172161077510,  # Base hoster !
            1389656345342513244,  # Expert !
            1383504317360902236,   # sov !
            1400181553493184613, # Divine !
            1411038382510969003, # Supreme !
            1429037904151449610, # Stormal !
            1429142963019317438, # Otherwordly
            1449405540902899875, # Void !
        ]
    },
    "Titus Hoster": {
        "class": 1438977624461410486,
        "ranks": [
            1362807172161077510,  # Base hoster !
            1389656345342513244,  # expert !
            1383504317360902236,   # sov !
            1400181553493184613, # Divine !
            1411038382510969003, # Supreme !
            1429037904151449610, # Stormal !
            1429142963019317438, # Otherwordly !
            1449405540902899875 # Void !
        ]
    },
    "Support": {
        "class": 1438977558266777761,
        "ranks": [
            1366106891461329076,  # Base support !
            1448712662274801776,  # expert
            1448712939099127974,   # sov
            1414527779164127372, #divine !
            1425907600951611543, # supreme !
            1429039065105436712, # Stormal !
            1429143179151802378, # Otherwordly !
            1449405678773866557 # Void !
        ]
    },
    "Depths Force": {
        "class": 1438977842049450014,
        "ranks": [
            1381152811978592307,  # Base depths force !
            1405888413789454446,  # Apprentice !
            1405888372559446027,   # Diver !
            1405888300408897566, # Black Diver !
            1429162252228886569, # Depths knight!
            1429390107537834035 # Sentinel!
        ]
    }
}

# Vouch requirements (TOTAL vouches required to reach each rank index)
# The list length matches the ranks list; index 0 (Base) -> 0 vouches required.
VOUCH_REQUIREMENTS = {
    "Enmity Hoster":       [0, 100, 200, 400, 800, 1600, 2500, 4000],
    "Titus Hoster":        [0, 100, 200, 400, 800, 1600, 2500, 4000],
    "Support":      [0, 75, 150, 250, 500, 875, 1250, 2000],
    "Depths Force": [0, 25, 50, 100, 250, 500]
} # !

VOUCH_CHECK_CHANNEL_ID = 1438981968380301403 # !

STAFF_ROLE_BY_TICKET = {
    "👑 Enmity Hoster": 1461754415839969300, #!
    "🔱 Titus Hoster": 1461754415839969300, #!
    "⚔️ Depths Force": 1381154181892673636, #!
    "❤️ Support | 🛡️ Parry": 1461754280485716110, #!
    "Complaints | Roles": 1461754577132195850 #!
}

WELCOME_CHANNEL_ID = 1461801245877600500   # change to your welcome channel NOT DONE YET !
BOOSTER_CHANNEL_ID = 1461801490099470519   # change if you want a different channel NOT DONE YET !
BOOSTER_ROLE_ID = 123456789012345678       # Nitro Booster role ID PRACTICALLY WORTHLESS
