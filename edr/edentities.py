import os
import json

import edtime
import edrlog
import edrconfig
from edri18n import _, _c
EDRLOG = edrlog.EDRLog()

class EDRCrew(object):
    def __init__(self, captain):
        self.captain = captain
        self.creation = edtime.EDTime.py_epoch_now()
        self.members = {captain: self.creation}

    def add(self, crew_member):
        if crew_member in self.members:
            return False
        self.members[crew_member] = edtime.EDTime.py_epoch_now()
        return True

    def remove(self, crew_member):
        try:
            del self.members[crew_member]
            return True
        except:
            return False
    
    def disband(self):
        self.members = {}
        self.captain = None
        self.creation = None

    def is_captain(self, member):
        return member == self.captain

    def duration(self, member):
        if member not in self.members:
            return 0
        now = edtime.EDTime.py_epoch_now()
        then = self.members[member]
        return now - then
   

class EDRSquadronMember(object):
    SOMEWHAT_TRUSTED_LEVEL = {"rank": "wingman", "level": 100}
    FULLY_TRUSTED_LEVEL = {"rank": "co-pilot", "level": 300}

    def __init__(self, squadron_dict):
        self.name = squadron_dict.get("squadronName", None)
        self.inara_id = squadron_dict.get("squadronId", None)
        self.rank = squadron_dict.get("squadronRank", None)
        self.heartbeat = squadron_dict.get("heartbeat", None)
        self.level = squadron_dict.get("squadronLevel", None)
    
    def is_somewhat_trusted(self):
        return self.level >= EDRSquadronMember.SOMEWHAT_TRUSTED_LEVEL["level"]

    def is_fully_trusted(self):
        return self.level >= EDRSquadronMember.FULLY_TRUSTED_LEVEL["level"]

    def info(self):
        return {"squadronName": self.name, "squadronId": self.inara_id, "squadronRank": self.rank, "squadronLevel": self.level }

class EDRPowerplay(object):
    def __init__(self, pledged_to, time_pledged):
        self.pledged_to = pledged_to
        self.since = edtime.EDTime.py_epoch_now() - time_pledged

    def is_enemy(self, power): 
        POWERS_AFFILIATION = {
            "a_lavigny-duval": "Empire",
            "arissa lavigny duval": "Empire",
            "aisling_duval": "Empire",
            "aisling duval": "Empire",
            "archon_delaine": None,
            "archon delaine": None,
            "denton_patreus": "Empire",
            "denton patreus": "Empire",
            "edmund_mahon": "Alliance",
            "edmund mahon": "Alliance",
            "felicia_winters": "Federation",
            "felicia winters": "Federation",
            "li_yong-rui": None,
            "li yong-rui": None,
            "pranav_antal": None,
            "pranav antal": None,
            "yuri_grom": None,
            "yuri grom": None,
            "zachary_hudson": "Federation",
            "zachary hudson": "Federation",
            "zemina_torval": "Empire",
            "zemina torval": "Empire",   
        }

        power = power.lower()
        if not (self.pledged_to in POWERS_AFFILIATION and power in POWERS_AFFILIATION):
            return False
        my_affiliation = POWERS_AFFILIATION[self.pledged_to]
        their_affiliation = POWERS_AFFILIATION[power]
        return my_affiliation != their_affiliation if my_affiliation else True

    def pretty_print(self):
        POWERS_AFFILIATION = {
            "a_lavigny-duval": "Lavigny",
            "aisling_duval": "Aisling",
            "archon_delaine": "Archon",
            "denton_patreus": "Patreus",
            "edmund_mahon": "Mahon",
            "felicia_winters": "Winters",
            "li_yong-rui": "Li Yong-rui",
            "pranav_antal": "Antal",
            "yuri_grom": "Yuri",
            "zachary_hudson": "Zachary",
            "zemina_torval": "Zemina",   
        }

        if self.pledged_to in POWERS_AFFILIATION:
            return POWERS_AFFILIATION[self.pledged_to]
        return self.pledged_to

    def canonicalize(self):
        return self.pledged_to.lower().replace(" ", "_")

    def time_pledged(self):
        return edtime.EDTime.py_epoch_now() - self.since

    def is_somewhat_trusted(self):
        return False
        #TODO return true if enough time has passed (parameterize)

    def is_fully_trusted(self):
        return False
        #TODO return true if enough time has passed (parameterize)


class EDBounty(object):
    def __init__(self, value):
        self.value = value
        config = edrconfig.EDRConfig()
        self.threshold = config.intel_bounty_threshold()
    
    def is_significant(self):
        return self.value >= self.threshold

    def pretty_print(self):
        readable = ""
        if self.value >= 10000000000:
            # Translators: this is a short representation for a bounty >= 10 000 000 000 credits (b stands for billion)  
            readable = _(u"{} b").format(self.value / 1000000000)
        elif self.value >= 1000000000:
            # Translators: this is a short representation for a bounty >= 1 000 000 000 credits (b stands for billion)
            readable = _(u"{:.1f} b").format(self.value / 1000000000.0)
        elif self.value >= 10000000:
            # Translators: this is a short representation for a bounty >= 10 000 000 credits (m stands for million)
            readable = _(u"{} m").format(self.value / 1000000)
        elif self.value > 1000000:
            # Translators: this is a short representation for a bounty >= 1 000 000 credits (m stands for million)
            readable = _(u"{:.1f} m").format(self.value / 1000000.0)
        elif self.value >= 10000:
            # Translators: this is a short representation for a bounty >= 10 000 credits (k stands for kilo, i.e. thousand)
            readable = _(u"{} k").format(self.value / 1000)
        elif self.value >= 1000:
            # Translators: this is a short representation for a bounty >= 1000 credits (k stands for kilo, i.e. thousand)
            readable = _(u"{:.1f} k").format(self.value / 1000.0)
        else:
            # Translators: this is a short representation for a bounty < 1000 credits (i.e. shows the whole bounty, unabbreviated)
            readable = _(u"{}").format(self.value)
        return readable

class EDVehicles(object):
    CANONICAL_SHIP_NAMES = json.loads(open(os.path.join(
        os.path.abspath(os.path.dirname(__file__)), 'data/shipnames.json')).read())

    @staticmethod
    def canonicalize(name):
        if name is None:
            return u"Unknown" # Note: this shouldn't be translated

        if name.lower() in EDVehicles.CANONICAL_SHIP_NAMES:
            return EDVehicles.CANONICAL_SHIP_NAMES[name.lower()]

        return name.lower()

class EDLocation(object):
    def __init__(self, star_system=None, place=None, security=None):
        self.star_system = star_system
        self.place = place
        self.security = security
    
    def is_anarchy_or_lawless(self):
        return self.security in ["$GAlAXY_MAP_INFO_state_anarchy;", "$GALAXY_MAP_INFO_state_lawless;"]

    def pretty_print(self):
        location = u"{system}".format(system=self.star_system)
        if self.place and self.place != self.star_system:
            if self.place.startswith(self.star_system + " "):
                # Translators: this is a continuation of the previous item (location of recently sighted outlaw) and shows a place in the system (e.g. supercruise, Cleve Hub) 
                location += u", {place}".format(place=self.place.partition(self.star_system + " ")[2])
            else:
                location += u", {place}".format(place=self.place)
        return location

class EDCmdr(object):
    def __init__(self):
        self.name = None
        self._ship = None
        self.location = EDLocation()
        self.game_mode = None
        self.previous_mode = None
        self.previous_wing = set()
        self.from_birth = False
        self._timestamp = edtime.EDTime()
        self.wing = set()
        self.friends = set()
        self.crew = None
        self.powerplay = None
        self.squadron = None
        self.destroyed = False
        self.target = None

    def in_solo_or_private(self):
        return self.game_mode in ["Solo", "Group"]

    def in_open(self):
        return self.game_mode == "Open"

    def inception(self):
        self.from_birth = True
        self.previous_mode = None
        self.previous_wing = set()
        self.wing = set()
        self.crew = None
        self.destroyed = False
        self.target = None

    def killed(self):
        self.previous_mode = self.game_mode 
        self.previous_wing = self.wing.copy()
        self.game_mode = None
        self.wing = set()
        self.crew = None
        self.destroyed = True
        self.target = None

    def resurrect(self):
        self.game_mode = self.previous_mode 
        self.wing = self.previous_wing.copy()
        self.previous_mode = None
        self.previous_wing = set()
        self.destroyed = False
        self.target = None

    def leave_wing(self):
        self.wing = set()

    def join_wing(self, others):
        self.wing = set(others)
        self.crew = None

    def add_to_wing(self, other):
        self.wing.add(other)

    def is_crew_member(self):
        if not self.crew:
            return False
        return self.crew.captain != self.name

    def in_a_crew(self):
        return self.crew is not None

    def in_a_wing(self):
        return len(self.wing) > 0
        
    def leave_crew(self):
        if not self.crew:
            return
        self.crew = None

    def disband_crew(self):
        if not self.crew:
            return
        self.crew.disband()

    def join_crew(self, captain):
        self.crew = EDRCrew(captain)
        self.crew.add(self.name)
        self.wing = set()
        self.ship = u"Unknown"
    
    def add_to_crew(self, member):
        if not self.crew:
            self.crew = EDRCrew(self.name)
            self.wing = set()
        return self.crew.add(member)
    
    def remove_from_crew(self, member):
        if not self.crew:
            self.crew = EDRCrew(self.name)
            self.wing = set()
        return self.crew.remove(member)

    def crew_time_elapsed(self, member):
        if not self.crew:
            return 0
        return self.crew.duration(member)
    
    def is_captain(self, member=None):
        if not self.crew:
            return False
        if not member:
            member = self.name 
        return self.crew.is_captain(member)

    def is_friend_or_in_wing(self, interlocutor):
        return interlocutor in self.friends or interlocutor in self.wing

    def is_enemy_with(self, power):
        if self.is_independent() or not power:
            return False
        return self.powerplay.is_enemy(power)

    @property
    def ship(self):
        return self._ship

    @ship.setter
    def ship(self, new_ship):
        self._ship = EDVehicles.canonicalize(new_ship)

    @property
    def timestamp(self):
        return self._timestamp.as_journal_timestamp()

    @timestamp.setter
    def timestamp(self, ed_timestamp):
        self._timestamp.from_journal_timestamp(ed_timestamp)

    def timestamp_js_epoch(self):
        return self._timestamp.as_js_epoch()

    @property
    def star_system(self):
        return self.location.star_system

    @star_system.setter
    def star_system(self, star_system):
        self.location.star_system = star_system

    @property
    def place(self):
        if self.location.place is None:
            # Translators: this is used when a location, comprised of a system and a place (e.g. Alpha Centauri & Hutton Orbital), has no place specified
            return _c(u"For an unknown or missing place|Unknown")
        return self.location.place

    @place.setter

    def place(self, place):
        self.location.place = place
    def location_security(self, ed_security_state):
        self.location.security = ed_security_state

    def in_bad_neighborhood(self):
        return self.location.is_anarchy_or_lawless()

    @property
    def power(self):
        if self.is_independent():
            return None
        return self.powerplay.pledged_to
    
    @property
    def time_pledged(self):
        if self.is_independent():
            return None
        return self.powerplay.time_pledged()

    def pledged_to(self, power, time_pledged):
        self.powerplay = EDRPowerplay(power, time_pledged)
    
    def pledged_since(self):
        if self.is_independent():
            return None
        return self.powerplay.since

    def squadron_member(self, squadron_dict):
        self.squadron = EDRSquadronMember(squadron_dict)

    def lone_wolf(self):
        self.squadron = None

    def squadron_info(self):
        if self.is_lone_wolf():
            return None
        return self.squadron.info()
    
    def is_independent(self):
        return self.powerplay is None

    def is_lone_wolf(self):
        return self.squadron is None

    def is_trusted_by_squadron(self):
        if self.is_lone_wolf():
            return False
        return self.squadron.is_somewhat_trusted()

    def squadron_trusted_rank(self):
        return EDRSquadronMember.SOMEWHAT_TRUSTED_LEVEL["rank"]

    def squadron_empowered_rank(self):
        return EDRSquadronMember.FULLY_TRUSTED_LEVEL["rank"]

    def is_empowered_by_squadron(self):
        if self.is_lone_wolf():
            return False
        return self.squadron.is_fully_trusted()
    
    def is_trusted_by_power(self):
        if self.is_independent():
            return False
        return self.powerplay.is_somewhat_trusted()

    def is_empowered_by_power(self):
        if self.is_independent():
            return True
        return self.powerplay.is_fully_trusted()

    def has_partial_status(self):
        return self._ship is None or self.location.star_system is None or self.location.place is None

    def update_ship_if_obsolete(self, ship, ed_timestamp):
        if self._ship is None or self._ship != EDVehicles.canonicalize(ship):
            EDRLOG.log(u"Updating ship info (was missing or obsolete). {old} vs. {ship}".format(old=self._ship, ship=ship), "DEBUG")
            self._ship = EDVehicles.canonicalize(ship)
            self._timestamp.from_journal_timestamp(ed_timestamp)
            return True

        return False


    def update_star_system_if_obsolete(self, star_system, ed_timestamp):
        if self.location.star_system is None or self.location.star_system != star_system:
            EDRLOG.log(u"Updating system info (was missing or obsolete). {old} vs. {system}".format(old=self.location.star_system, system=star_system), "INFO")
            self.location.star_system = star_system
            self._timestamp.from_journal_timestamp(ed_timestamp)
            return True

        return False


    def update_place_if_obsolete(self, place, ed_timestamp):
        if self.location.place is None or self.location.place != place:
            EDRLOG.log(u"Updating place info (was missing or obsolete). {old} vs. {place}".format(old=self.location.place, place=place), "INFO")
            self.location.place = place
            self._timestamp.from_journal_timestamp(ed_timestamp)
            return True

        return False
