# coding= utf-8
import datetime
import time

import Tkinter as tk
import ttk
import ttkHyperlinkLabel
import myNotebook as notebook
from config import config
import edrconfig

import lrucache
import edentities
import edrserver
import edrinara
import audiofeedback
import edrlog
import ingamemsg
import edrtogglingpanel
import edrsystems
import edrcmdrs
from edropponents import EDROpponents
import randomtips
import helpcontent
import edtime
import edrlegalrecords
from edri18n import _, _c, _edr, set_language

EDRLOG = edrlog.EDRLog()

class EDRClient(object):
    AUDIO_FEEDBACK = audiofeedback.AudioFeedback()

    def __init__(self):
        edr_config = edrconfig.EDRConfig()
        set_language(config.get("language"))

        self.edr_version = edr_config.edr_version()
        EDRLOG.log(u"Version {}".format(self.edr_version), "INFO")

        self.enemy_alerts_pledge_threshold = edr_config.enemy_alerts_pledge_threshold()
        self.system_novelty_threshold = edr_config.system_novelty_threshold()
        self.place_novelty_threshold = edr_config.place_novelty_threshold()
        self.ship_novelty_threshold = edr_config.ship_novelty_threshold()
        self.cognitive_novelty_threshold = edr_config.cognitive_novelty_threshold()
        self.intel_even_if_clean = edr_config.intel_even_if_clean()
        
        self.edr_needs_u_novelty_threshold = edr_config.edr_needs_u_novelty_threshold()
        self.previous_ad = None

        self.searching = False

        self.blips_cache = lrucache.LRUCache(edr_config.lru_max_size(), edr_config.blips_max_age())
        self.cognitive_blips_cache = lrucache.LRUCache(edr_config.lru_max_size(), edr_config.blips_max_age())
        self.traffic_cache = lrucache.LRUCache(edr_config.lru_max_size(), edr_config.traffic_max_age())
        self.scans_cache = lrucache.LRUCache(edr_config.lru_max_size(), edr_config.scans_max_age())
        self.cognitive_scans_cache = lrucache.LRUCache(edr_config.lru_max_size(), edr_config.blips_max_age())
        self.alerts_cache = lrucache.LRUCache(edr_config.lru_max_size(), edr_config.alerts_max_age())

        self._email = tk.StringVar(value=config.get("EDREmail"))
        self._password = tk.StringVar(value=config.get("EDRPassword"))
        # Translators: this is shown on the EDMC's status line
        self._status = tk.StringVar(value=_(u"not authenticated."))
        
        visual = 1 if config.get("EDRVisualFeedback") == "True" else 0
        self.IN_GAME_MSG = ingamemsg.InGameMsg() if visual else None
        self._visual_feedback = tk.IntVar(value=visual)

        visual_alt = 1 if config.get("EDRVisualAltFeedback") == "True" else 0
        self._visual_alt_feedback = tk.IntVar(value=visual_alt)
        
        self.ui = edrtogglingpanel.EDRTogglingPanel(self._status, self._visual_alt_feedback)

        audio = 1 if config.get("EDRAudioFeedback") == "True" else 0
        self._audio_feedback = tk.IntVar(value=audio)

        self.server = edrserver.EDRServer()
        self.inara = edrinara.EDRInara()
        
        self.realtime_params = {
            EDROpponents.OUTLAWS: { "min_bounty": None if config.get("EDROutlawsAlertsMinBounty") == "None" else config.getint("EDROutlawsAlertsMinBounty"),
                         "max_distance": None if config.get("EDROutlawsAlertsMaxDistance") == "None" else config.getint("EDROutlawsAlertsMaxDistance")},
            EDROpponents.ENEMIES: { "min_bounty": None if config.get("EDREnemiesAlertsMinBounty") == "None" else config.getint("EDREnemiesAlertsMinBounty"),
                         "max_distance": None if config.get("EDREnemiesAlertsMaxDistance") == "None" else config.getint("EDREnemiesAlertsMaxDistance")}
        }
        
        self.edrsystems = edrsystems.EDRSystems(self.server)
        self.edrcmdrs = edrcmdrs.EDRCmdrs(self.server, self.inara)
        self.player = self.edrcmdrs.player
        self.edropponents = {
            EDROpponents.OUTLAWS: EDROpponents(self.server, EDROpponents.OUTLAWS, self._realtime_callback),
            EDROpponents.ENEMIES: EDROpponents(self.server, EDROpponents.ENEMIES, self._realtime_callback),
        }
        self.edrlegal = edrlegalrecords.EDRLegalRecords(self.server)

        self.mandatory_update = False
        self.autoupdate_pending = False
        self.crimes_reporting = True
        self.motd = []
        self.tips = randomtips.RandomTips()
        self.help_content = helpcontent.HelpContent()

    def loud_audio_feedback(self):
        config.set("EDRAudioFeedbackVolume", "loud")
        self.AUDIO_FEEDBACK.loud()
        # Translators: this is shown on EDMC's status bar when a user enables loud audio cues
        self.status = _(u"loud audio cues.")

    def soft_audio_feedback(self):
        config.set("EDRAudioFeedbackVolume", "soft")
        self.AUDIO_FEEDBACK.soft()
        # Translators: this is shown on EDMC's status bar when a user enables soft audio cues
        self.status = _(u"soft audio cues.")

    def apply_config(self):
        c_email = config.get("EDREmail")
        c_password = config.get("EDRPassword")
        c_visual_feedback = config.get("EDRVisualFeedback")
        c_visual_alt_feedback = config.get("EDRVisualAltFeedback")
        c_audio_feedback = config.get("EDRAudioFeedback")
        c_audio_volume = config.get("EDRAudioFeedbackVolume")

        if c_email is None:
            self._email.set("")
        else:
            self._email.set(c_email)

        if c_password is None:
            self._password.set("")
        else:
            self._password.set(c_password)

        if c_visual_feedback is None or c_visual_feedback == "False":
            self._visual_feedback.set(0)
        else:
            self._visual_feedback.set(1)

        if c_visual_alt_feedback is None or c_visual_alt_feedback == "False":
            self._visual_alt_feedback.set(0)
        else:
            self._visual_alt_feedback.set(1)

        if c_audio_feedback is None or c_audio_feedback == "False":
            self._audio_feedback.set(0)
        else:
            self._audio_feedback.set(1)

        if c_audio_volume is None or c_audio_volume == "loud":
            self.loud_audio_feedback()
        else:
            self.soft_audio_feedback()


    def check_version(self):
        version_range = self.server.server_version()
        self.motd = _edr(version_range["l10n_motd"])

        if version_range is None:
            # Translators: this is shown on EDMC's status bar when the version check fails
            self.status = _(u"check for version update has failed.")
            return

        if self.is_obsolete(version_range["min"]):
            EDRLOG.log(u"Mandatory update! {version} vs. {min}"
                       .format(version=self.edr_version, min=version_range["min"]), "ERROR")
            self.mandatory_update = True
            self.autoupdate_pending = version_range.get("autoupdatable", False)
            self.__status_update_pending()
        elif self.is_obsolete(version_range["latest"]):
            EDRLOG.log(u"EDR update available! {version} vs. {latest}"
                       .format(version=self.edr_version, latest=version_range["latest"]), "INFO")
            self.mandatory_update = False
            self.autoupdate_pending = version_range.get("autoupdatable", False)
            self.__status_update_pending()

    def is_obsolete(self, advertised_version):
        client_parts = map(int, self.edr_version.split('.'))
        advertised_parts = map(int, advertised_version.split('.'))
        return client_parts < advertised_parts

    @property
    def email(self):
        return self._email.get()

    @email.setter
    def email(self, new_email):
        self._email.set(new_email)

    @property
    def password(self):
        return self._password.get()

    @password.setter
    def password(self, new_password):
        self._password.set(new_password)

    @property
    def status(self):
        return self._status.get()

    @status.setter
    def status(self, new_status):
        self._status.set(new_status)
        self.ui.nolink()

    @property
    def visual_feedback(self):
        if self._visual_feedback.get() == 0:
            return False
        
        if not self.IN_GAME_MSG:
             self.IN_GAME_MSG = ingamemsg.InGameMsg() 
        return True

    @visual_feedback.setter
    def visual_feedback(self, new_value):
        self._visual_feedback.set(new_value)

    @property
    def visual_alt_feedback(self):
        return self._visual_alt_feedback.get() == 1

    @visual_alt_feedback.setter
    def visual_alt_feedback(self, new_value):
        self._visual_alt_feedback.set(new_value)


    @property
    def audio_feedback(self):
        return self._audio_feedback.get() == 1

    @audio_feedback.setter
    def audio_feedback(self, new_value):
        self._audio_feedback.set(new_value)

    def player_name(self, name):
        self.edrcmdrs.set_player_name(name)
        self.server.set_player_name(name)

    def pledged_to(self, power, time_pledged=0):
        if self.server.is_anonymous():
            EDRLOG.log(u"Skipping pledged_to call since the user is anonymous.", "INFO")
            return
        nodotpower = power.replace(".", "")
        if self.edrcmdrs.player_pledged_to(nodotpower, time_pledged):
            for kind in self.edropponents:
                self.edropponents[kind].pledged_to(nodotpower, time_pledged)

    def login(self):
        self.server.logout()
        if self.server.login(self.email, self.password):
            # Translators: this is shown on EDMC's status bar when the authentication succeeds
            self.status = _(u"authenticated.")
            return True
        # Translators: this is shown on EDMC's status bar when the authentication fails
        self.status = _(u"not authenticated.")
        return False

    def is_logged_in(self):
        return self.server.is_authenticated()

    def is_anonymous(self):
        return (self.is_logged_in() and self.server.is_anonymous())

    def warmup(self):
        EDRLOG.log(u"Warming up client.", "INFO")
        # Translators: this is shown when EDR warms-up via the overlay
        details = [_(u"Check that Elite still has the focus!")]
        if self.mandatory_update:
            # Translators: this is shown when EDR warms-up via the overlay if there is a mandatory update pending
            details = [_(u"Mandatory update!")]
        details += self.motd
        # Translators: this is shown when EDR warms-up via the overlay, the -- are for presentation purpose
        details.append(_(u"-- Feeling lost? Send !help via the in-game chat --"))
        details.append(self.tips.tip())
        # Translators: this is shown when EDR warms-up via the overlay
        self.__notify(_(u"EDR v{} by LeKeno (Cobra Kai)").format(self.edr_version), details, clear_before=True)

    def shutdown(self, everything=False):
        self.edrcmdrs.persist()
        self.edrsystems.persist()
        for kind in self.edropponents:
            self.edropponents[kind].persist()
            self.edropponents[kind].shutdown_comms_link()
        self.edrlegal.persist()
        if self.IN_GAME_MSG:
            self.IN_GAME_MSG.shutdown()
        config.set("EDRVisualAltFeedback", "True" if self.visual_alt_feedback else "False")

        if not everything:
            return
        
        self.server.logout()

    def app_ui(self, parent):
        self.check_version()
        return self.ui

    def prefs_ui(self, parent):
        frame = notebook.Frame(parent)
        frame.columnconfigure(1, weight=1)

        # Translators: this is shown in the preferences panel
        ttkHyperlinkLabel.HyperlinkLabel(frame, text=_(u"EDR website"), background=notebook.Label().cget('background'), url="https://github.com/lekeno/edr/", underline=True).grid(padx=10, sticky=tk.W)       

        # Translators: this is shown in the preferences panel
        notebook.Label(frame, text=_(u'Credentials')).grid(padx=10, sticky=tk.W)
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(columnspan=2, padx=10, pady=2, sticky=tk.EW)
        # Translators: this is shown in the preferences panel
        cred_label = notebook.Label(frame, text=_(u'Log in with your EDR account for full access'))
        cred_label.grid(padx=10, columnspan=2, sticky=tk.W)

        notebook.Label(frame, text=_(u"Email")).grid(padx=10, row=11, sticky=tk.W)
        notebook.Entry(frame, textvariable=self._email).grid(padx=10, row=11,
                                                             column=1, sticky=tk.EW)

        notebook.Label(frame, text=_(u"Password")).grid(padx=10, row=12, sticky=tk.W)
        notebook.Entry(frame, textvariable=self._password,
                       show=u'*').grid(padx=10, row=12, column=1, sticky=tk.EW)

        # Translators: this is shown in the preferences panel as a heading for feedback options (e.g. overlay, audio cues)
        notebook.Label(frame, text=_(u"EDR Feedback:")).grid(padx=10, row=14, sticky=tk.W)
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(columnspan=2, padx=10, pady=2, sticky=tk.EW)
        
        notebook.Checkbutton(frame, text=_(u"Overlay"),
                             variable=self._visual_feedback).grid(padx=10, row=16,
                                                                  sticky=tk.W)
        notebook.Checkbutton(frame, text=_(u"Sound"),
                             variable=self._audio_feedback).grid(padx=10, row=17, sticky=tk.W)
        
        if self.server.is_authenticated():
            self.status = _(u"authenticated.")
        else:
            self.status = _(u"not authenticated.")

        return frame

    def __status_update_pending(self):
        # Translators: this is shown in EDMC's status
        if self.autoupdate_pending:
            self.status = _(u"mandatory update pending (relaunch EDMC)") if self.mandatory_update else _(u"update pending (relaunch EDMC to apply)")
        else:
            # Translators: this is shown in EDMC's status
            self.status = _(u"mandatory EDR update!") if self.mandatory_update else _(u"please update EDR!")
            self.ui.link("https://github.com/lekeno/edr/releases/latest")
            

    def prefs_changed(self):
        set_language(config.get("language"))
        if self.mandatory_update:
            EDRLOG.log(u"Out-of-date client, aborting.", "ERROR")
            self.__status_update_pending()
            return

        config.set("EDREmail", self.email)
        config.set("EDRPassword", self.password)
        config.set("EDRVisualFeedback", "True" if self.visual_feedback else "False")
        config.set("EDRAudioFeedback", "True" if self.audio_feedback else "False")
        EDRLOG.log(u"Audio cues: {}, {}".format(config.get("EDRAudioFeedback"),
                                                config.get("EDRAudioFeedbackVolume")), "DEBUG")
        self.login()

    def check_system(self, star_system, may_create=False):
        try:
            EDRLOG.log(u"Check system called: {}".format(star_system), "INFO")
            details = []
            notams = self.edrsystems.active_notams(star_system, may_create)
            if notams:
                EDRLOG.log(u"NOTAMs for {}: {}".format(star_system, notams), "DEBUG")
                details += notams
            
            if self.edrsystems.has_sitrep(star_system):
                if star_system == self.player.star_system and self.player.in_bad_neighborhood():
                    EDRLOG.log(u"Sitrep system is known to be an anarchy. Crimes aren't reported.", "INFO")
                    # Translators: this is shown via the overlay if the system of interest is an Anarchy (current system or !sitrep <system>)
                    details.append(_c(u"Sitrep|Anarchy: not all crimes are reported."))
                if self.edrsystems.has_recent_activity(star_system):
                    summary = self.edrsystems.summarize_recent_activity(star_system, self.player.power)
                    for section in summary:
                        details.append(u"{}: {}".format(section, "; ".join(summary[section])))
            if details:
                # Translators: this is the heading for the sitrep of a given system {}; shown via the overlay
                self.__sitrep(_(u"SITREP for {}").format(star_system), details)
        except edrserver.CommsJammedError:
            self.__commsjammed()
        

    def notams(self):
        summary = self.edrsystems.systems_with_active_notams()
        if summary:
            details = []
            # Translators: this shows a ist of systems {} with active NOtice To Air Men via the overlay
            details.append(_(u"Active NOTAMs for: {}").format("; ".join(summary)))
            # Translators: this is the heading for the active NOTAMs overlay
            self.__sitrep(_(u"NOTAMs"), details)
        else:
            self.__sitrep(_(u"NOTAMs"), [_(u"No active NOTAMs.")])

    def notam(self, star_system):
        summary = self.edrsystems.active_notams(star_system)
        if summary:
            EDRLOG.log(u"NOTAMs for {}: {}".format(star_system, summary), "DEBUG")
            # Translators: this is the heading to show any active NOTAM for a given system {} 
            self.__sitrep(_(u"NOTAM for {}").format(star_system), summary)
        else:
            self.__sitrep(_(u"NOTAM for {}").format(star_system), [_(u"No active NOTAMs.")])

    def sitreps(self):
        try:
            details = []
            summary = self.edrsystems.systems_with_recent_activity()
            for section in summary:
                details.append(u"{}: {}".format(section, "; ".join(summary[section])))
            if details:
                self.__sitrep(_(u"SITREPS"), details)
        except edrserver.CommsJammedError:
            self.__commsjammed()


    def cmdr_id(self, cmdr_name):
        try:
            profile = self.cmdr(cmdr_name, check_inara_server=False)
            if not (profile is None or profile.cid is None):
                EDRLOG.log(u"Cmdr {cmdr} known as id={cid}".format(cmdr=cmdr_name,
                                                                cid=profile.cid), "DEBUG")
                return profile.cid

            EDRLOG.log(u"Failed to retrieve/create cmdr {}".format(cmdr_name), "ERROR")
            return None
        except edrserver.CommsJammedError:
            self.__commsjammed()
            return None

    def cmdr(self, cmdr_name, autocreate=True, check_inara_server=False):
        try:
            return self.edrcmdrs.cmdr(cmdr_name, autocreate, check_inara_server)
        except edrserver.CommsJammedError:
            self.__commsjammed()
            return None

    def evict_system(self, star_system):
        self.edrsystems.evict(star_system)

    def evict_cmdr(self, cmdr):
        self.edrcmdrs.evict(cmdr)

    def __novel_enough_situation(self, new, old, cognitive = False):
        if old is None:
            return True

        delta = new["timestamp"] - old["timestamp"]
        
        if cognitive:
            return (new["starSystem"] != old["starSystem"] or new["place"] != old["place"]) or delta > self.cognitive_novelty_threshold

        if new["starSystem"] != old["starSystem"]:
            return delta > self.system_novelty_threshold

        if new["place"] != old["place"]:
            return (old["place"] == "" or
                    old["place"] == "Unknown" or
                    delta > self.place_novelty_threshold)

        if new["ship"] != old["ship"]:
            return (old["ship"] == "" or
                    old["ship"] == "Unknown" or
                    delta > self.ship_novelty_threshold)
        
        if "wanted" in new:
            return ("wanted" not in old or
                    new["wanted"] > old["wanted"])
        
        if "bounty" in new:
            return ("bounty" not in old or
                    new["bounty"] > old["bounty"])
        return False

    def novel_enough_alert(self, alert_for_cmdr, alert):
        last_alert = self.alerts_cache.get(alert_for_cmdr)
        return self.__novel_enough_situation(alert, last_alert)

    def novel_enough_blip(self, cmdr_id, blip, cognitive = False):
        last_blip = self.cognitive_blips_cache.get(cmdr_id) if cognitive else self.blips_cache.get(cmdr_id)
        return self.__novel_enough_situation(blip, last_blip, cognitive)

    def novel_enough_scan(self, cmdr_id, scan, cognitive = False):
        last_scan = self.cognitive_scans_cache.get(cmdr_id) if cognitive else self.scans_cache.get(cmdr_id)
        novel_situation = self.__novel_enough_situation(scan, last_scan, cognitive)
        return novel_situation or (scan["wanted"] != last_scan["wanted"]) or (scan["bounty"] != last_scan["bounty"])

    def novel_enough_traffic_report(self, sighted_cmdr, report):
        last_report = self.traffic_cache.get(sighted_cmdr)
        return self.__novel_enough_situation(report, last_report)

    def outlaws_alerts_enabled(self, silent=True):
        return self._alerts_enabled(EDROpponents.OUTLAWS, silent)
    
    def enemies_alerts_enabled(self, silent=True):
        return self._alerts_enabled(EDROpponents.ENEMIES, silent)

    def _alerts_enabled(self, kind, silent=True):
        enabled = self.edropponents[kind].is_comms_link_up()
        if not silent:
            details = [_(u"{} alerts enabled").format(_(kind)) if enabled else _(u"{} alerts disabled").format(_(kind))]
            if self.realtime_params[kind]["max_distance"]:
                details.append(_(u" <={max_distance}ly").format(max_distance=self.realtime_params[kind]["max_distance"]))
            if self.realtime_params[kind]["min_bounty"]:
                details.append(_(u" >={min_bounty}cr").format(min_bounty=self.realtime_params[kind]["min_bounty"]))
            self.notify_with_details(_(u"EDR Alerts"), details)
        return enabled
    
    def enable_outlaws_alerts(self, silent=False):
        self._enable_alerts(EDROpponents.OUTLAWS, silent)
    
    def enable_enemies_alerts(self, silent=False):
        self._enable_alerts(EDROpponents.ENEMIES, silent)

    def _enable_alerts(self, kind, silent=False):
        try:
            details = ""
            if self._alerts_enabled(kind, silent=True):
                details = _(u"{} alerts already enabled").format(_(kind))
            elif kind == EDROpponents.ENEMIES:
                if self.is_anonymous():
                    details = _(u"Request an EDR account to access enemy alerts (https://lekeno.github.io)")
                elif not self.player.power:
                    details = _(u"Pledge to a power to access enemy alerts")
                elif self.player.time_pledged < self.enemy_alerts_pledge_threshold:
                    details = _(u"Remain loyal for at least {} days to access enemy alerts").format(int(self.enemy_alerts_pledge_threshold / 24*60*60))
                else:
                    details = _(u"Enabling Enemy alerts") if self.edropponents[kind].establish_comms_link() else _(u"Couldn't enable Enemy alerts")
            else:            
                details = _(u"Enabling {kind} alerts").format(kind=_(kind)) if self.edropponents[kind].establish_comms_link() else _(u"Couldn't enable {kind} alerts").format(kind=_(kind))
            if not silent:
                if self.realtime_params[kind]["max_distance"]:
                    details += _(u" <={max_distance}ly").format(max_distance=self.realtime_params[kind]["max_distance"])
                if self.realtime_params[kind]["min_bounty"]:
                    details += _(u" >={min_bounty}cr").format(min_bounty=self.realtime_params[kind]["min_bounty"])
                self.notify_with_details(_(u"EDR Alerts"), [details])
        except edrserver.CommsJammedError:
            self.__commsjammed()
        
    def disable_outlaws_alerts(self, silent=False):
        self._disable_alerts(EDROpponents.OUTLAWS, silent)

    def disable_enemies_alerts(self, silent=False):
        self._disable_alerts(EDROpponents.ENEMIES, silent)

    def _disable_alerts(self, kind, silent=False):
        details = ""
        if self.edropponents[kind].is_comms_link_up():
            self.edropponents[kind].shutdown_comms_link()
            details = _(u"Disabling {} alerts").format(_(kind))
        else:
            details = _(u"{} alerts already disabled").format(_(kind))
        if not silent:
            self.notify_with_details(_(u"EDR Alerts"), [details])

    def min_bounty_outlaws_alerts(self, min_bounty):
        self._min_bounty_alerts(EDROpponents.OUTLAWS, min_bounty)

    def min_bounty_enemies_alerts(self, min_bounty):
        self._min_bounty_alerts(EDROpponents.ENEMIES, min_bounty)

    def _min_bounty_alerts(self, kind, min_bounty):
        new_value = self.realtime_params[kind]["min_bounty"]
        if min_bounty:
            try:
                new_value = int(min_bounty)
                self.notify_with_details(_(u"EDR Alerts"), [_(u"minimum bounty set to {min_bounty} cr for {kind}").format(min_bounty=edentities.EDBounty(new_value).pretty_print(), kind=_(kind))])
            except ValueError:
                self.notify_with_details(_(u"EDR Alerts"), [_(u"invalid value for minimum bounty")])
                new_value = None
        else:
            self.notify_with_details(_(u"EDR Alerts"), [_(u"no minimum bounty required")])
        self.realtime_params[kind]["min_bounty"] = new_value
        if new_value is None:
            config.set("EDR{}AlertsMinBounty".format(kind), "None")
        else:
            config.set("EDR{}AlertsMinBounty".format(kind), new_value)


    def max_distance_outlaws_alerts(self, max_distance):
        self._max_distance_alerts(EDROpponents.OUTLAWS, max_distance)

    def max_distance_enemies_alerts(self, max_distance):
        self._max_distance_alerts(EDROpponents.ENEMIES, max_distance)

    def _max_distance_alerts(self, kind, max_distance):
        new_value = self.realtime_params[kind]["max_distance"]
        if max_distance:
            try:
                new_value = int(max_distance)
                self.notify_with_details(_(u"EDR Alerts"), [_(u"maximum distance set to {max_distance} ly for {kind}").format(max_distance=new_value, kind=_(kind))])
            except ValueError:
                self.notify_with_details(_(u"EDR Alerts"), [_(u"invalid value, removing maximal distance")])
                new_value = None
        else:
            self.notify_with_details(_(u"Outlaws Alerts"), [_(u"no limits on distance")])

        self.realtime_params[kind]["max_distance"] = new_value
        if new_value is None:
            config.set("EDR{}AlertsMaxDistance".format(kind), "None")
        else:
            config.set("EDR{}AlertsMaxDistance".format(kind), new_value)

    def _realtime_callback(self, kind, events):
        summary = []
        if kind not in [EDROpponents.OUTLAWS, EDROpponents.ENEMIES]:
            return
        if events in ["cancel", "auth_revoked"]:
            summary = [_(u"Comms link interrupted. Send '?{} on' to re-establish.").format(kind.lower())]
        else:
            summary = self._summarize_realtime_alert(kind, events)
        if summary:
            self.notify_with_details(_(u"EDR Alerts"), summary)

    def _worthy_alert(self, kind, event):
        self_uid = self.server.uid()
        if event["uid"] == self_uid:
            return False
        if self.realtime_params[kind]["max_distance"]:
            try:
                origin = self.player.star_system
                distance = self.edrsystems.distance(origin, event["starSystem"])
                threshold = self.realtime_params[kind]["max_distance"]
                if distance > threshold:
                    EDRLOG.log(u"EDR alert not worthy. Distance {} between systems {} and {} exceeds threshold {}".format(distance, origin, event["starSystem"], threshold), "DEBUG")
                    return False
            except ValueError:
                EDRLOG.log(u"Can't compute distance between systems {} and {}: unknown system(s)".format(self.player.star_system, event["starSystem"]), "WARNING")
                pass
        if self.realtime_params[kind]["min_bounty"]:
            if "bounty" not in event:
                return False
            if event["bounty"] < self.realtime_params[kind]["min_bounty"]:
                EDRLOG.log(u"EDR alert not worthy. Bounty {} does not exceeds threshold {}".format(event["bounty"], self.realtime_params[kind]["min_bounty"]), "DEBUG")
                return False
        return self.novel_enough_alert(event["cmdr"].lower(), event)

    def _summarize_realtime_alert(self, kind, event):
        summary =  []
        EDRLOG.log(u"realtime {} alerts, handling {}".format(kind, event), "DEBUG")
        if not self._worthy_alert(kind, event):
            EDRLOG.log(u"Skipped realtime {} event because it wasn't worth alerting about: {}.".format(kind, event), "DEBUG")
        else:
            location = edentities.EDLocation(event["starSystem"], event["place"])
            distance = None
            try:
                distance = self.edrsystems.distance(self.player.star_system, location.star_system)
            except ValueError:
                pass
            
            oneliner = _(u"{cmdr} ({ship}) sighted in {location}")
            if kind is EDROpponents.ENEMIES and event.get("enemy", None):
                oneliner = _(u"Enemy {cmdr} ({ship}) sighted in {location}")
            elif kind is EDROpponents.OUTLAWS:
                oneliner = _(u"Outlaw {cmdr} ({ship}) sighted in {location}")
            oneliner = oneliner.format(cmdr=event["cmdr"], ship=event["ship"], location=location.pretty_print())
            
            if distance:
                oneliner += _(u" [{distance:.3g} ly]").format(distance=distance) if distance < 50.0 else _(u" [{distance} ly]").format(distance=int(distance))
            if event.get("wanted", None):
                if event["bounty"] > 0:
                    oneliner += _(u" wanted for {bounty} cr").format(bounty=edentities.EDBounty(event["bounty"]).pretty_print())
                else:
                    oneliner += _(u" wanted somewhere")
            
            if oneliner:
                summary.append(oneliner)
        return summary

    def who(self, cmdr_name, autocreate=False):
        try:
            profile = self.cmdr(cmdr_name, autocreate, check_inara_server=True)
            if profile:
                self.status = _(u"got info about {}").format(cmdr_name)
                EDRLOG.log(u"Who {} : {}".format(cmdr_name, profile.short_profile(self.player.powerplay)), "INFO")
                legal = self.edrlegal.summarize_recents(profile.cid)
                if legal:
                    self.__intel(cmdr_name, [profile.short_profile(self.player.powerplay), legal])
                else:
                    self.__intel(cmdr_name, [profile.short_profile(self.player.powerplay)])
            else:
                EDRLOG.log(u"Who {} : no info".format(cmdr_name), "INFO")
                self.__intel(cmdr_name, [_("No info about {cmdr}").format(cmdr=cmdr_name)])
        except edrserver.CommsJammedError:
            self.__commsjammed()    

    def distance(self, from_system, to_system):
        details = []
        distance = None
        try:
            distance = self.edrsystems.distance(from_system, to_system)
        except ValueError:
            pass
            
        if distance:
            pretty_dist = _(u"{distance:.3g}").format(distance=distance) if distance < 50.0 else _(u"{distance}").format(distance=int(distance))
            details.append(_(u"{dist}ly from {from_sys} to {to_sys}").format(dist=pretty_dist, from_sys=from_system, to_sys=to_system))
            taxi_jump_range = 50
            jumping_time = self.edrsystems.jumping_time(from_system, to_system, taxi_jump_range)
            transfer_time = self.edrsystems.transfer_time(from_system, to_system)
            details.append(_(u"Taxi time ({}LY): {}").format(taxi_jump_range, edtime.EDTime.pretty_print_timespan(jumping_time)))
            details.append(_(u"Transfer time: {}").format(edtime.EDTime.pretty_print_timespan(transfer_time)))
            self.status = _(u"distance: {dist}ly").format(dist=pretty_dist)
        else:
            self.status = _(u"distance failed")
            details.append(_(u"Couldn't calculate a distance. Invalid or unknown system names?"))
        self.__notify("Distance", details)


    def blip(self, cmdr_name, blip):
        cmdr_id = self.cmdr_id(cmdr_name)
        if cmdr_id is None:
            self.status = _(u"no cmdr id (contact).")
            EDRLOG.log(u"Can't submit blip (no cmdr id for {}).".format(cmdr_name), "ERROR")
            its_actually_fine = self.is_anonymous()
            return its_actually_fine

        profile = self.cmdr(cmdr_name, check_inara_server=True)
        if profile and (self.player.name != cmdr_name) and profile.is_dangerous(self.player.powerplay):
            self.status = _(u"{} is bad news.").format(cmdr_name)
            if self.novel_enough_blip(cmdr_id, blip, cognitive = True):
                self.__warning(_(u"Warning!"), [profile.short_profile(self.player.powerplay)])
                self.cognitive_blips_cache.set(cmdr_id, blip)
                if self.is_anonymous() and profile.is_dangerous(self.player.powerplay):
                    self.advertise_full_account(_("You could have helped other EDR users by reporting this outlaw."))
                elif self.is_anonymous():
                    self.advertise_full_account(_("You could have helped other EDR users by reporting this enemy."))
            else:
                EDRLOG.log(u"Skipping warning since a warning was recently shown.", "INFO")

        if not self.novel_enough_blip(cmdr_id, blip):
            self.status = u"skipping blip (not novel enough)."
            EDRLOG.log(u"Blip is not novel enough to warrant reporting", "INFO")
            return True

        if self.is_anonymous():
            EDRLOG.log("Skipping blip since the user is anonymous.", "INFO")
            self.blips_cache.set(cmdr_id, blip)
            return True

        success = self.server.blip(cmdr_id, blip)
        if success:
            self.status = u"blip reported for {}.".format(cmdr_name)
            self.blips_cache.set(cmdr_id, blip)

        return success

    def scanned(self, cmdr_name, scan):
        cmdr_id = self.cmdr_id(cmdr_name)
        if cmdr_id is None:
            self.status = _(u"cmdr unknown to EDR.")
            EDRLOG.log(u"Can't submit scan (no cmdr id for {}).".format(cmdr_name), "ERROR")
            its_actually_fine = self.is_anonymous()
            return its_actually_fine

        if self.novel_enough_scan(cmdr_id, scan, cognitive = True):
            profile = self.cmdr(cmdr_name, check_inara_server=True)
            legal = self.edrlegal.summarize_recents(profile.cid)
            bounty = edentities.EDBounty(scan["bounty"]) if scan["bounty"] else None
            if profile and (self.player.name != cmdr_name):
                if profile.is_dangerous(self.player.powerplay):
                    # Translators: this is shown via EDMC's EDR status line upon contact with a known outlaw
                    self.status = _(u"{} is bad news.").format(cmdr_name)
                    details = [profile.short_profile(self.player.powerplay)]
                    status = ""
                    if scan["enemy"]:
                        status += _(u"PP Enemy (weapons free). ")
                    if scan["bounty"]:
                        status += _(u"Wanted for {} cr").format(edentities.EDBounty(scan["bounty"]).pretty_print())
                    elif scan["wanted"]:
                        status += _(u"Wanted somewhere. A Kill-Warrant-Scan will reveal their highest bounty.")
                    if status:
                        details.append(status)
                    if legal:
                        details.append(legal)
                    self.__warning(_(u"Warning!"), details)
                elif self.intel_even_if_clean or (scan["wanted"] and bounty.is_significant()):
                    self.status = _(u"Intel for cmdr {}.").format(cmdr_name)
                    details = [profile.short_profile(self.player.powerplay)]
                    if bounty:
                        details.append(_(u"Wanted for {} cr").format(edentities.EDBounty(scan["bounty"]).pretty_print()))
                    elif scan["wanted"]:
                        details.append(_(u"Wanted somewhere but it could be minor offenses."))
                    if legal:
                        details.append(legal)
                    self.__intel(_(u"Intel"), details)
                if (self.is_anonymous() and (profile.is_dangerous(self.player.powerplay) or (scan["wanted"] and bounty.is_significant()))):
                    # Translators: this is shown to users who don't yet have an EDR account
                    self.advertise_full_account(_(u"You could have helped other EDR users by reporting this outlaw."))
                elif self.is_anonymous() and scan["enemy"] and self.player.power:
                    # Translators: this is shown to users who don't yet have an EDR account
                    self.advertise_full_account(_(u"You could have helped other {power} pledges by reporting this enemy.").format(self.player.power))
                self.cognitive_scans_cache.set(cmdr_id, scan)

        if not self.novel_enough_scan(cmdr_id, scan):
            self.status = _(u"not novel enough (scan).")
            EDRLOG.log(u"Scan is not novel enough to warrant reporting", "INFO")
            return True

        if self.is_anonymous():
            EDRLOG.log("Skipping reporting scan since the user is anonymous.", "INFO")
            self.scans_cache.set(cmdr_id, scan)
            return True

        success = self.server.scanned(cmdr_id, scan)
        if success:
            self.status = _(u"scan reported for {}.").format(cmdr_name)
            self.scans_cache.set(cmdr_id, scan)

        return success

    def traffic(self, star_system, traffic):
        try:
            if self.is_anonymous():
                EDRLOG.log(u"Skipping traffic report since the user is anonymous.", "INFO")
                return True

            sigthed_cmdr = traffic["cmdr"]
            if not self.novel_enough_traffic_report(sigthed_cmdr, traffic):
                self.status = _(u"not novel enough (traffic).")
                EDRLOG.log(u"Traffic report is not novel enough to warrant reporting", "INFO")
                return True

            sid = self.edrsystems.system_id(star_system, may_create=True)
            if sid is None:
                EDRLOG.log(u"Failed to report traffic for system {} : no id found.".format(star_system),
                        "DEBUG")
                return False

            success = self.server.traffic(sid, traffic)
            if success:
                self.status = _(u"traffic reported.")
                self.traffic_cache.set(sigthed_cmdr, traffic)

            return success
        except edrserver.CommsJammedError:
            self.__commsjammed()
            return False


    def crime(self, star_system, crime):
        if not self.crimes_reporting:
            EDRLOG.log(u"Crimes reporting is off (!crimes on to re-enable).", "INFO")
            self.status = _(u"Crimes reporting is off (!crimes on to re-enable)")
            return True
            
        if self.player.in_bad_neighborhood():
            EDRLOG.log(u"Crime not being reported because the player is in an anarchy.", "INFO")
            self.status = _(u"Anarchy system (crimes not reported).")
            return True

        if self.is_anonymous():
            EDRLOG.log(u"Skipping crime report since the user is anonymous.", "INFO")
            if crime["victim"] == self.player.name:
                self.advertise_full_account(_(u"You could have helped other EDR users or get help by reporting this crime!"))
            return True

        sid = self.edrsystems.system_id(star_system, may_create=True)
        if sid is None:
            EDRLOG.log(u"Failed to report crime in system {} : no id found.".format(star_system),
                       "DEBUG")
            return False

        if self.server.crime(sid, crime):
            self.status = _(u"crime reported!")
            return True
        return False

    def crew_report(self, report):
        if self.is_anonymous():
            EDRLOG.log(u"Skipping crew report since the user is anonymous.", "INFO")
            if report["captain"] == self.player.name and (report["crimes"] or report["kicked"]):
                self.advertise_full_account(_(u"You could have helped other EDR users by reporting this problematic crew member!"))
            return False

        crew_id = self.cmdr_id(report["crew"])
        if crew_id is None:
            self.status = _(u"{} is unknown to EDR.".format(report["crew"]))
            EDRLOG.log(u"Can't submit crew report (no cmdr id for {}).".format(report["crew"]), "ERROR")
            return False
        
        if self.server.crew_report(crew_id, report):
            self.status = _(u"multicrew session reported (cmdr {name}).").format(name=report["crew"])
            return True
        return False


    def tag_cmdr(self, cmdr_name, tag):
        if self.is_anonymous():
            EDRLOG.log(u"Skipping tag cmdr since the user is anonymous.", "INFO")
            self.advertise_full_account(_(u"Sorry, this feature only works with an EDR account."), passive=False)
            return False
        
        if  tag in ["enemy", "ally"]:
            if not self.player.squadron:
                EDRLOG.log(u"Skipping squadron tag since the user isn't a member of a squadron.", "INFO")
                self.notify_with_details(_(u"Squadron Dex"), [_(u"You need to join a squadron on https://inara.cz to use this feature."), _(u"Then, reboot EDR to reflect these changes.")])
                return False
            elif not self.player.is_empowered_by_squadron():
                EDRLOG.log(u"Skipping squadron tag since the user isn't trusted.", "INFO")
                self.notify_with_details(_(u"Squadron Dex"), [_(u"You need to reach {} to tag enemies or allies.").format(self.player.squadron_empowered_rank())])
                return False

        success = self.edrcmdrs.tag_cmdr(cmdr_name, tag)
        dex_name = _(u"Squadron Dex") if tag in ["enemy", "ally"] else _(u"Cmdr Dex") 
        if success:
            self.__notify(dex_name, [_(u"Successfully tagged cmdr {name} with {tag}").format(name=cmdr_name, tag=tag)])
        else:
            self.__notify(dex_name, [_(u"Could not tag cmdr {name} with {tag}").format(name=cmdr_name, tag=tag)])
        return success
    
    def memo_cmdr(self, cmdr_name, memo):
        if self.is_anonymous():
            EDRLOG.log(u"Skipping memo cmdr since the user is anonymous.", "INFO")
            self.advertise_full_account(_(u"Sorry, this feature only works with an EDR account."), passive=False)
            return False

        success = self.edrcmdrs.memo_cmdr(cmdr_name, memo)
        if success:
            self.__notify(_(u"Cmdr Dex"), [_(u"Successfully attached a memo to cmdr {}").format(cmdr_name)])
        else:
            self.__notify(_(u"Cmdr Dex"), [_(u"Failed to attach a memo to cmdr {}").format(cmdr_name)])       
        return success

    def clear_memo_cmdr(self, cmdr_name):
        if self.is_anonymous():
            EDRLOG.log(u"Skipping clear_memo_cmdr since the user is anonymous.", "INFO")
            self.advertise_full_account(_(u"Sorry, this feature only works with an EDR account."), passive=False)
            return False

        success = self.edrcmdrs.clear_memo_cmdr(cmdr_name)
        if success:
            self.__notify(_(u"Cmdr Dex"),[_(u"Successfully removed memo from cmdr {}").format(cmdr_name)])
        else:
            self.__notify(_(u"Cmdr Dex"), [_(u"Failed to remove memo from cmdr {}").format(cmdr_name)])        
        return success

    def untag_cmdr(self, cmdr_name, tag):
        if self.is_anonymous():
            EDRLOG.log(u"Skipping untag cmdr since the user is anonymous.", "INFO")
            self.advertise_full_account(_(u"Sorry, this feature only works with an EDR account."), passive=False)
            return False

        if  tag in ["enemy", "ally"]:
            if not self.player.squadron:
                EDRLOG.log(u"Skipping squadron untag since the user isn't a member of a squadron.", "INFO")
                self.notify_with_details(_(u"Squadron Dex"), [_(u"You need to join a squadron on https://inara.cz to use this feature."), _(u"Then, reboot EDR to reflect these changes.")])
                return False
            elif not self.player.is_empowered_by_squadron():
                EDRLOG.log(u"Skipping squadron untag since the user isn't trusted.", "INFO")
                self.notify_with_details(_(u"Squadron Dex"), [_(u"You need to reach {} to tag enemies or allies.").format(self.player.squadron_empowered_rank())])
                return False

        success = self.edrcmdrs.untag_cmdr(cmdr_name, tag)
        dex_name = _(u"Squadron Dex") if tag in ["enemy", "ally"] else _(u"Cmdr Dex")
        if success:
            if tag is None:
                self.__notify(dex_name, [_(u"Successfully removed all tags from cmdr {}").format(cmdr_name)])
            else:
                self.__notify(dex_name, [_(u"Successfully removed tag {} from cmdr {}").format(tag, cmdr_name)])
        else:
            self.__notify(dex_name, [_(u"Could not remove tag(s) from cmdr {}").format(cmdr_name)])
        return success

    def where(self, cmdr_name):
        report = {}
        try:
            for kind in self.edropponents:
                candidate_report = self.edropponents[kind].where(cmdr_name)
                if candidate_report and (not report or report["timestamp"] < candidate_report["timestamp"]):
                    report = candidate_report
            
            if report:
                self.status = _(u"got info about {}").format(cmdr_name)
                self.__intel(_(u"Intel for {}").format(cmdr_name), report["readable"])
            else:
                EDRLOG.log(u"Where {} : no info".format(cmdr_name), "INFO")
                self.status = _(u"no info about {}").format(cmdr_name)
                self.__intel(_(u"Intel for {}").format(cmdr_name), [_(u"Not recently sighted or not an outlaw.")])
        except edrserver.CommsJammedError:
            self.__commsjammed()

    def outlaws(self):
        try:
            return self._opponents(EDROpponents.OUTLAWS)
        except edrserver.CommsJammedError:
            self.__commsjammed()
            return False

    def enemies(self):
        try:
            return self._opponents(EDROpponents.ENEMIES)
        except edrserver.CommsJammedError:
            self.__commsjammed()
            return False

    def _opponents(self, kind):
        if kind is EDROpponents.ENEMIES and not self.player.power:
            EDRLOG.log(u"Not pledged to any power, can't have enemies.", "INFO")
            self.__notify(_(u"Recently Sighted {kind}").format(kind=_(kind)), [_(u"You need to be pledged to a power.")])
            return False
        opponents_report = self.edropponents[kind].recent_sightings()
        if not opponents_report:
            EDRLOG.log(u"No recently sighted {}".format(kind), "INFO")
            self.__sitrep(_(u"Recently Sighted {kind}").format(kind=_(kind)), [_(u"No {kind} sighted in the last {timespan}").format(kind=_(kind).lower(), timespan=edtime.EDTime.pretty_print_timespan(self.edropponents[kind].timespan))])
            return False
        
        self.status = _(u"recently sighted {kind}").format(kind=_(kind))
        EDRLOG.log(u"Got recently sighted {}".format(kind), "INFO")
        self.__sitrep(_(u"Recently Sighted {kind}").format(kind=_(kind)), opponents_report)

    def help(self, section):
        content = self.help_content.get(section)
        if not content:
            return False

        if self.visual_feedback:
            EDRLOG.log(u"Show help for {} with header: {} and details: {}".format(section, content["header"], content["details"][0]), "DEBUG")
            self.IN_GAME_MSG.help(content["header"], content["details"])
        EDRLOG.log(u"[Alt] Show help for {} with header: {} and details: {}".format(section, content["header"], content["details"][0]), "DEBUG")
        self.ui.help(content["header"], content["details"])
        return True

    def clear(self):
        if self.visual_feedback:
            self.IN_GAME_MSG.clear()
        self.ui.clear()
           

    def __sitrep(self, header, details):
        if self.audio_feedback:
            self.AUDIO_FEEDBACK.notify()
        if self.visual_feedback:
            EDRLOG.log(u"sitrep with header: {}; details: {}".format(header, details[0]), "DEBUG")
            self.IN_GAME_MSG.clear_sitrep()
            self.IN_GAME_MSG.sitrep(header, details)
        EDRLOG.log(u"[Alt] sitrep with header: {}; details: {}".format(header, details[0]), "DEBUG")
        self.ui.sitrep(header, details)

    def __intel(self, who, details, clear_before=False):
        if self.audio_feedback:
            self.AUDIO_FEEDBACK.notify()
        if self.visual_feedback:
            EDRLOG.log(u"Intel for {}; details: {}".format(who, details[0]), "DEBUG")
            if clear_before:
                self.IN_GAME_MSG.clear_intel()
            self.IN_GAME_MSG.intel(_(u"Intel"), details)
        EDRLOG.log(u"[Alt] Intel for {}; details: {}".format(who, details[0]), "DEBUG")
        self.ui.intel(_(u"Intel"), details)

    def __warning(self, header, details, clear_before=False):
        if self.audio_feedback:
            self.AUDIO_FEEDBACK.warn()
        if self.visual_feedback:
            EDRLOG.log(u"Warning; details: {}".format(details[0]), "DEBUG")
            if clear_before:
                self.IN_GAME_MSG.clear_warning()
            self.IN_GAME_MSG.warning(header, details)
        EDRLOG.log(u"[Alt] Warning; details: {}".format(details[0]), "DEBUG")
        self.ui.warning(header, details)
    
    def __notify(self, header, details, clear_before=False):
        if self.audio_feedback:
            self.AUDIO_FEEDBACK.notify()
        if self.visual_feedback:
            EDRLOG.log(u"Notify about {}; details: {}".format(header, details[0]), "DEBUG")
            if clear_before:
                self.IN_GAME_MSG.clear_notice()
            self.IN_GAME_MSG.notify(header, details)
        EDRLOG.log(u"[Alt] Notify about {}; details: {}".format(header, details[0]), "DEBUG")
        self.ui.notify(header, details)        

    def __commsjammed(self):
        self.__notify(_(u"Comms Link Error"), [_(u"EDR Central can't be reached at the moment"), _(u"Try again later or contact Cmdr LeKeno if it keeps failing")])

    def notify_with_details(self, notice, details):
        self.__notify(notice, details)

    def warn_with_details(self, warning, details):
        self.__warning(warning, details)
    
    def advertise_full_account(self, context, passive=True):
        now = datetime.datetime.now()
        now_epoch = time.mktime(now.timetuple())            
        if passive and self.previous_ad:
            if (now_epoch - self.previous_ad) <= self.edr_needs_u_novelty_threshold:
                return False

        self.__notify(_(u"EDR needs you!"), [context, u"--", _(u"Apply for an account at https://lekeno.github.io/"), _(u"It's free, no strings attached.")], clear_before=True)
        self.previous_ad = now_epoch
        return True

    def interstellar_factors_near(self, star_system, override_sc_distance = None):
        if not star_system:
            return
        
        if self.searching:
            self.__notify(_(u"EDR Search"), [_(u"Already searching for something, please wait...")])
            return

        if not (self.edrsystems.in_bubble(star_system) or self.edrsystems.in_colonia(star_system)):
            self.__notify(_(u"EDR Search"), [_(u"Search features only work in the bubble or Colonia.")])
            return

        # TODO adjust needs large pad depending on the player's current ship.
        try:
            self.edrsystems.search_interstellar_factors(star_system, self.__soi_found, override_sc_distance = override_sc_distance)
            self.searching = True
            self.status = _(u"I.Factors: searching...")
            self.__notify(_(u"EDR Search"), [_(u"Interstellar Factors: searching...")])
        except ValueError:
            self.status = _(u"I.Factors: failed")
            self.notify_with_details(_(u"EDR Search"), [_(u"Unknown system")])

    def raw_material_trader_near(self, star_system, override_sc_distance = None):
        if not star_system:
            return
        
        if self.searching:
            self.__notify(_(u"EDR Search"), [_(u"Already searching for something, please wait...")])
            return

        if not (self.edrsystems.in_bubble(star_system) or self.edrsystems.in_colonia(star_system)):
            self.__notify(_(u"EDR Search"), [_(u"Search features only work in the bubble or Colonia.")])
            return

        # TODO adjust needs large pad depending on the player's current ship.
        try:
            self.edrsystems.search_raw_trader(star_system, self.__soi_found, override_sc_distance = override_sc_distance)
            self.searching = True
            self.status = _(u"Raw mat. trader: searching...")
            self.__notify(_(u"EDR Search"), [_(u"Raw material trader: searching...")])
        except ValueError:
            self.status = _(u"Raw mat. trader: failed")
            self.notify_with_details(_(u"EDR Search"), [_(u"Unknown system")])
        
    def encoded_material_trader_near(self, star_system, override_sc_distance = None):
        if not star_system:
            return
        
        if self.searching:
            self.__notify(_(u"EDR Search"), [_(u"Already searching for something, please wait...")])
            return

        if not (self.edrsystems.in_bubble(star_system) or self.edrsystems.in_colonia(star_system)):
            self.__notify(_(u"EDR Search"), [_(u"Search features only work in the bubble or Colonia.")])
            return

        # TODO adjust needs large pad depending on the player's current ship.
        try:
            self.edrsystems.search_encoded_trader(star_system, self.__soi_found, override_sc_distance = override_sc_distance)
            self.searching = True
            self.status = _(u"Encoded data trader: searching...")
            self.__notify(_(u"EDR Search"), [_(u"Encoded data trader: searching...")])
        except ValueError:
            self.status = _(u"Encoded data trader: failed")
            self.notify_with_details(_(u"EDR Search"), [_(u"Unknown system")])


    def manufactured_material_trader_near(self, star_system, override_sc_distance = None):
        if not star_system:
            return
        
        if self.searching:
            self.__notify(_(u"EDR Search"), [_(u"Already searching for something, please wait...")])
            return

        if not (self.edrsystems.in_bubble(star_system) or self.edrsystems.in_colonia(star_system)):
            self.__notify(_(u"EDR Search"), [_(u"Search features only work in the bubble or Colonia.")])
            return
        
        # TODO adjust needs large pad depending on the player's current ship.
        try:
            self.edrsystems.search_manufactured_trader(star_system, self.__soi_found, override_sc_distance = override_sc_distance)
            self.searching = True
            self.status = _(u"Manufactured mat. trader: searching...")
            self.__notify(_(u"EDR Search"), [_(u"Manufactured material trader: searching...")])
        except ValueError:
            self.status = _(u"Manufactured mat. trader: failed")
            self.__notify(_(u"EDR Search"), [_(u"Unknown system")])


    def staging_station_near(self, star_system, override_sc_distance = None):
        if not star_system:
            return

        if self.searching:
            self.__notify(_(u"EDR Search"), [_(u"Already searching for something, please wait...")])
            return
        
        if not (self.edrsystems.in_bubble(star_system) or self.edrsystems.in_colonia(star_system)):
            self.__notify(_(u"EDR Search"), [_(u"Search features only work in the bubble or Colonia.")])
            return

        # TODO adjust needs large pad depending on the player's current ship.
        try:
            self.edrsystems.search_staging_station(star_system, self.__soi_found)
            self.searching = True
            self.status = _(u"Staging station: searching...")
            self.__notify(_(u"EDR Search"), [_(u"Staging station: searching...")])
        except ValueError:
            self.status = _(u"Staging station: failed")
            self.notify_with_details(_(u"EDR Search"), [_(u"Unknown system")])

    def human_tech_broker_near(self, star_system, override_sc_distance = None):
        if not star_system:
            return
        
        if self.searching:
            self.__notify(_(u"EDR Search"), [_(u"Already searching for something, please wait...")])
            return

        if not (self.edrsystems.in_bubble(star_system) or self.edrsystems.in_colonia(star_system)):
            self.__notify(_(u"EDR Search"), [_(u"Search features only work in the bubble or Colonia.")])
            return

        # TODO adjust needs large pad depending on the player's current ship.
        try:
            self.edrsystems.search_human_tech_broker(star_system, self.__soi_found, override_sc_distance = override_sc_distance)
            self.searching = True
            self.status = _(u"Human tech broker: searching...")
            self.__notify(_(u"EDR Search"), [_(u"Human tech broker: searching...")])
        except ValueError:
            self.status = _(u"Human tech broker: failed")
            self.__notify(_(u"EDR Search"), [_(u"Unknown system")])
    
    def guardian_tech_broker_near(self, star_system, override_sc_distance = None):
        if not star_system:
            return
        
        if self.searching:
            self.__notify(_(u"EDR Search"), [_(u"Already searching for something, please wait...")])
            return

        if not (self.edrsystems.in_bubble(star_system) or self.edrsystems.in_colonia(star_system)):
            self.__notify(_(u"EDR Search"), [_(u"Search features only work in the bubble or Colonia.")])
            return

        # TODO adjust needs large pad depending on the player's current ship.
        try:
            self.edrsystems.search_guardian_tech_broker(star_system, self.__soi_found, override_sc_distance = override_sc_distance)
            self.searching = True
            self.status = _(u"Guardian tech broker: searching...")
            self.__notify(_(u"EDR Search"), [_(u"Guardian tech broker: searching...")])
        except ValueError:
            self.status = _(u"Guardian tech broker: failed")
            self.__notify(_(u"EDR Search"), [_(u"Unknown system")])


    def __soi_found(self, reference, radius, sc, soi_checker, result):
        self.searching = False
        details = []
        if result:
            sc_distance = result['station']['distanceToArrival']
            distance = result['distance']
            pretty_dist = _(u"{dist:.3g}LY").format(dist=distance) if distance < 50.0 else _(u"{dist}LY").format(dist=int(distance))
            pretty_sc_dist = _(u"{dist}LS").format(dist=int(sc_distance))
            details.append(_(u"{}, {}").format(result['name'], pretty_dist))
            details.append(_(u"{} ({}), {}").format(result['station']['name'], result['station']['type'], pretty_sc_dist))
            details.append(_(u"as of {}").format(result['station']['updateTime']['information']))
            self.status = u"{}: {}, {} - {} ({}), {}".format(soi_checker.name, result['name'], pretty_dist, result['station']['name'], result['station']['type'], pretty_sc_dist)
        else:
            self.status = _(u"{}: nothing within [{}LY, {}LS] of {}".format(soi_checker.name, int(radius), int(sc), reference))
            checked = _("checked {} systems").format(soi_checker.systems_counter) 
            if soi_checker.stations_counter: 
                checked = _("checked {} systems and {} stations").format(soi_checker.systems_counter, soi_checker.stations_counter) 
            details.append(_(u"nothing found within [{}LY, {}LS], {}.").format(int(radius), int(sc), checked))
            if soi_checker.hint:
                details.append(soi_checker.hint)
        self.__notify(_(u"{} near {}").format(soi_checker.name, reference), details, clear_before = True)