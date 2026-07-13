import reflex as rx
import requests
import datetime
import asyncio
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from .translations import translations

from .api_config import API_BASE_URL
BACKEND_URL = API_BASE_URL

class AlertItem(BaseModel):
    id: int
    trip_id: int
    phone_number: str
    type: str
    lat: float
    lng: float
    timestamp: str
    status: str
    dispatch_notes: Optional[str] = ""

class BriefingZoneItem(BaseModel):
    name: str
    risk_score: float
    risk_level: str
    photo_url: Optional[str] = None
    hazard_type: Optional[str] = None
    avoid_caption: Optional[str] = None

class State(rx.State):
    # --- TOURIST STATE ---
    tourist_phone: str = ""
    tourist_otp: str = ""
    otp_sent: bool = False
    tourist_token: str = ""
    tourist_user_id: int = 0
    tourist_name: str = ""
    
    # Destination Search State
    search_query: str = ""
    search_suggestions: List[Dict[str, Any]] = []
    selected_lat: float = 0.0
    selected_lng: float = 0.0
    
    # Multilingual language support state
    language: str = "en"

    @rx.var
    def translation(self) -> Dict[str, str]:
        return translations.get(self.language, translations["en"])

    @rx.var
    def briefing_title(self) -> str:
        if len(self.briefing_zones) == 1 and self.briefing_zones[0].name == "General Trip Area":
            return "Area Risk Rating:"
        return "Danger Zones in Region:"

    @rx.event
    def load_language_preference(self):
        js_code = """
        (async () => {
            let lang = 'en';
            try {
                const cap = window.parent.Capacitor || window.Capacitor;
                if (cap && cap.Plugins && cap.Plugins.Preferences) {
                    const res = await cap.Plugins.Preferences.get({ key: 'preferred_language' });
                    if (res.value) lang = res.value;
                } else {
                    const saved = localStorage.getItem('preferred_language');
                    if (saved) lang = saved;
                }
            } catch (e) {
                console.warn(e);
            }
            if (!lang) {
                const navLang = navigator.language || navigator.userLanguage || '';
                if (navLang.startsWith('hi')) lang = 'hi';
                else if (navLang.startsWith('mr')) lang = 'mr';
                else lang = 'en';
            }
            return lang;
        })()
        """
        return rx.call_script(js_code, callback=State.set_language_from_client)

    @rx.event
    def set_language_from_client(self, lang: str):
        self.language = lang
        if self.tourist_token:
            self.sync_language_to_backend(lang)

    @rx.event
    def change_language(self, lang: str):
        self.language = lang
        js_code = f"""
        (async () => {{
            try {{
                const cap = window.parent.Capacitor || window.Capacitor;
                if (cap && cap.Plugins && cap.Plugins.Preferences) {{
                    await cap.Plugins.Preferences.set({{ key: 'preferred_language', value: '{lang}' }});
                }} else {{
                    localStorage.setItem('preferred_language', '{lang}');
                }}
            }} catch (e) {{
                console.warn(e);
            }}
        }})()
        """
        if self.tourist_token:
            self.sync_language_to_backend(lang)
            
        js_post = f"""
        try {{
            const iframe = document.querySelector('iframe');
            if (iframe && iframe.contentWindow) {{
                iframe.contentWindow.postMessage({{ type: 'set_language', language: '{lang}' }}, '*');
            }}
        }} catch(e) {{}}
        """
        return [rx.call_script(js_code), rx.call_script(js_post)]

    def sync_language_to_backend(self, lang: str):
        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        try:
            requests.put(
                f"{BACKEND_URL}/api/auth/tourist/language",
                json={"preferred_language": lang},
                headers=headers
            )
        except Exception as e:
            print("Failed to sync language to backend:", e)
    
    # Active Trip Info
    active_trip_id: int = 0
    active_trip_region: str = ""
    active_trip_status: str = ""
    active_trip_end: str = ""
    
    # Trip Start Form
    form_region: str = "Yosemite National Park"
    form_start_date: str = ""
    form_end_date: str = ""
    form_checkin_interval: str = "None"

    # Alert resolution modal
    show_resolve_modal: bool = False
    resolve_alert_id: int = 0
    resolve_alert_type: str = ""
    resolve_alert_lat: float = 0.0
    resolve_alert_lng: float = 0.0
    resolve_alert_phone: str = ""
    resolve_alert_time: str = ""
    dispatch_notes_input: str = ""

    # Reports Date Filter
    report_from_date: str = ""
    report_to_date: str = ""
    active_checkin_interval: float = 0.0
    active_last_checkin: str = ""

    # Feedback form variables
    show_feedback_modal: bool = False
    feedback_rating: int = 5
    feedback_felt_unsafe: bool = False
    feedback_unsafe_location: str = ""
    feedback_suggestions: str = ""

    # Feedback summary data
    feedback_regions: List[Dict[str, Any]] = []
    feedback_zones: List[Dict[str, Any]] = []
    feedback_suggestions_list: List[Dict[str, Any]] = []
    
    # SOS Overlay state
    sos_active: bool = False
    sos_alert_id: int = 0
    
    # Map URLs
    tourist_map_url: str = ""
    
    # Errors/Messages
    tourist_error: str = ""
    tourist_success: str = ""
    tourist_warning: str = ""

    # Trip Buddy Group State
    group_join_code: str = ""
    group_members: List[Dict[str, Any]] = []
    group_alerts: List[Dict[str, Any]] = []
    group_code_input: str = ""
    has_group: bool = False
    group_error: str = ""
    group_success: str = ""

    @rx.var
    def active_group_alert(self) -> Dict[str, Any]:
        if self.group_alerts and len(self.group_alerts) > 0:
            return self.group_alerts[0]
        return {}

    @rx.var
    def active_group_alert_phone(self) -> str:
        alert_obj = self.active_group_alert
        if alert_obj and "alert" in alert_obj:
            return alert_obj["alert"].get("phone_number", "Unknown")
        return "Unknown"

    @rx.var
    def active_group_alert_type(self) -> str:
        alert_obj = self.active_group_alert
        if alert_obj and "alert" in alert_obj:
            return alert_obj["alert"].get("type", "distress")
        return "distress"

    @rx.var
    def active_group_alert_coords(self) -> str:
        alert_obj = self.active_group_alert
        if alert_obj and "alert" in alert_obj:
            lat = alert_obj["alert"].get("lat", 0.0)
            lng = alert_obj["alert"].get("lng", 0.0)
            return f"{lat}, {lng}"
        return "0.0, 0.0"

    @rx.var
    def active_group_alert_id(self) -> int:
        alert_obj = self.active_group_alert
        if alert_obj:
            return alert_obj.get("id", 0)
        return 0

    @rx.var
    def checkin_countdown_msg(self) -> str:
        if self.active_checkin_interval <= 0 or not self.active_last_checkin:
            return ""
        try:
            import datetime
            clean_str = self.active_last_checkin.replace("Z", "")
            if "." in clean_str:
                clean_str = clean_str.split(".")[0]
            last_dt = datetime.datetime.fromisoformat(clean_str)
            now_dt = datetime.datetime.utcnow()
            
            due_dt = last_dt + datetime.timedelta(hours=self.active_checkin_interval)
            delta = due_dt - now_dt
            minutes_left = int(delta.total_seconds() / 60)
            
            if minutes_left > 0:
                return f"Next check-in due in {minutes_left} minutes"
            else:
                return f"Check-in was due {-minutes_left} minutes ago!"
        except Exception as e:
            print("Failed calculating checkin countdown:", e)
            return ""

    @rx.var
    def is_checkin_overdue(self) -> bool:
        if self.active_checkin_interval <= 0 or not self.active_last_checkin:
            return False
        try:
            import datetime
            clean_str = self.active_last_checkin.replace("Z", "")
            if "." in clean_str:
                clean_str = clean_str.split(".")[0]
            last_dt = datetime.datetime.fromisoformat(clean_str)
            now_dt = datetime.datetime.utcnow()
            
            due_dt = last_dt + datetime.timedelta(hours=self.active_checkin_interval)
            return now_dt > due_dt
        except Exception as e:
            print("Failed checkin overdue calculation:", e)
            return False


    # Pre-Trip Briefing State
    show_briefing_card: bool = False
    briefing_zones: List[BriefingZoneItem] = []
    briefing_destination_photo: str = ""
    briefing_temp: float = 0.0
    briefing_cond: str = ""
    briefing_rain_status: str = ""
    briefing_weather_warning: bool = False
    briefing_safety_tips: List[str] = []
    briefing_safe_hours: str = ""
    briefing_warnings: List[str] = []

    # --- AUTHORITY STATE ---
    auth_email: str = ""
    auth_password: str = ""
    authority_token: str = ""
    authority_name: str = ""
    
    authority_map_url: str = ""
    alerts: List[AlertItem] = []
    active_trips_count: int = 1
    sos_queued: bool = False
    
    # UI Control
    auth_error: str = ""
    operator_success: str = ""
    dashboard_tab: str = "map"  # 'map' or 'alerts'

    # --- TOURIST EVENT HANDLERS ---
    def set_tourist_phone(self, val: str):
        self.tourist_phone = val
        self.tourist_error = ""

    def set_tourist_otp(self, val: str):
        self.tourist_otp = val
        self.tourist_error = ""

    def set_group_code_input(self, val: str):
        self.group_code_input = val
        self.group_error = ""

    def set_form_region(self, val: str):
        self.form_region = val

    def set_form_start_date(self, val: str):
        self.form_start_date = val

    def set_form_end_date(self, val: str):
        self.form_end_date = val

    def set_form_checkin_interval(self, val: str):
        self.form_checkin_interval = val

    def confirm_safe(self):
        if not self.active_trip_id or not self.tourist_token:
            return
        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        try:
            res = requests.post(f"{BACKEND_URL}/api/trips/{self.active_trip_id}/checkin", headers=headers)
            if res.status_code == 200:
                self.tourist_success = "Checked in successfully! You are safe."
                self.tourist_error = ""
                self.check_active_trip()
            else:
                self.tourist_error = res.json().get("detail", "Failed to check in")
        except Exception as e:
            self.tourist_error = f"Backend Connection Error: {str(e)}"

    def request_otp(self):
        if not self.tourist_phone.strip():
            self.tourist_error = "Phone number is required"
            return
        
        try:
            res = requests.post(
                f"{BACKEND_URL}/api/auth/tourist/otp",
                json={"phone_number": self.tourist_phone.strip()}
            )
            if res.status_code == 200:
                self.otp_sent = True
                self.tourist_success = "Verification code sent! (Check backend console logs or use '123456')"
                self.tourist_error = ""
            else:
                self.tourist_error = res.json().get("detail", "Failed to send OTP")
        except Exception as e:
            self.tourist_error = f"Backend Connection Error: {str(e)}"

    def verify_otp(self):
        if not self.tourist_otp.strip():
            self.tourist_error = "OTP Code is required"
            return
            
        try:
            res = requests.post(
                f"{BACKEND_URL}/api/auth/tourist/verify",
                json={
                    "phone_number": self.tourist_phone.strip(),
                    "code": self.tourist_otp.strip()
                }
            )
            if res.status_code == 200:
                data = res.json()
                self.tourist_token = data["access_token"]
                self.tourist_user_id = data["user_id"]
                self.tourist_name = data["name"]
                self.tourist_error = ""
                self.tourist_success = "Logged in successfully!"
                
                # Fetch user details to get preferred language
                headers = {"Authorization": f"Bearer {self.tourist_token}"}
                try:
                    me_res = requests.get(f"{BACKEND_URL}/api/auth/me/tourist", headers=headers)
                    if me_res.status_code == 200:
                        me_data = me_res.json()
                        self.language = me_data.get("preferred_language", "en")
                except Exception as me_err:
                    print("Failed to fetch user info on login:", me_err)
                
                # Set default form dates to now and +4 hours
                now = datetime.datetime.now()
                self.form_start_date = now.strftime("%Y-%m-%dT%H:%M")
                self.form_end_date = (now + datetime.timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M")
                
                # Check for active trip
                self.check_active_trip()
            else:
                self.tourist_error = res.json().get("detail", "Invalid OTP Code")
        except Exception as e:
            self.tourist_error = f"Backend Connection Error: {str(e)}"

    def check_active_trip(self):
        if not self.tourist_token:
            return
            
        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        try:
            try:
                me_res = requests.get(f"{BACKEND_URL}/api/auth/me/tourist", headers=headers)
                if me_res.status_code == 200:
                    me_data = me_res.json()
                    self.language = me_data.get("preferred_language", "en")
            except Exception as me_err:
                print("Failed to fetch user info on check_active_trip:", me_err)

            res = requests.get(f"{BACKEND_URL}/api/trips/active", headers=headers)
            if res.status_code == 200:
                data = res.json()
                self.active_trip_id = data["id"]
                self.active_trip_region = data["region"]
                self.active_trip_status = data["status"]
                self.active_trip_end = data["end_date"]
                self.active_checkin_interval = data.get("checkin_interval_hours") or 0.0
                self.active_last_checkin = data.get("last_checkin_at") or ""
                
                # Update tourist map url dynamically with destination coordinates
                d_lat = data.get("region_lat") or 0.0
                d_lng = data.get("region_lng") or 0.0
                self.tourist_map_url = f"/tourist_map.html?token={self.tourist_token}&trip_id={self.active_trip_id}&backend={BACKEND_URL}&dest_lat={d_lat}&dest_lng={d_lng}"
                
                # Check if SOS is active (check if this trip has open SOS alerts)
                self.check_sos_status()
                
                return rx.redirect("/tourist/active")
            else:
                self.active_trip_id = 0
                self.active_trip_region = ""
                self.active_trip_status = ""
        except Exception as e:
            print("Check active trip failed:", e)

    def check_sos_status(self):
        if not self.active_trip_id or not self.tourist_token:
            return
        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        try:
            res = requests.get(f"{BACKEND_URL}/api/trips/authority/alerts", headers=headers)
            if res.status_code == 200:
                alerts = res.json()
                # Check if there is an open SOS alert for this trip
                open_sos = [a for a in alerts if a["trip_id"] == self.active_trip_id and a["type"] == "sos" and a["status"] == "open"]
                if open_sos:
                    self.sos_active = True
                    self.sos_alert_id = open_sos[0]["id"]
                else:
                    self.sos_active = False
        except Exception as e:
            print("Check SOS status failed:", e)

    @rx.event(background=True)
    async def handle_search_change(self, val: str):
        async with self:
            self.search_query = val
            if not val.strip():
                self.search_suggestions = []
                return
        
        # Debounce sleep for 400ms
        await asyncio.sleep(0.4)
        
        async with self:
            if self.search_query != val:
                return
        
        try:
            import urllib.parse
            encoded_query = urllib.parse.quote(val)
            url = f"https://nominatim.openstreetmap.org/search?q={encoded_query}&format=json&limit=5"
            headers = {"User-Agent": "SafeTrip-Web-App-Agent/1.0"}
            res = requests.get(url, headers=headers, timeout=3)
            if res.status_code == 200:
                data = res.json()
                suggestions = []
                for item in data:
                    suggestions.append({
                        "display_name": item.get("display_name", ""),
                        "lat": float(item.get("lat", 0.0)),
                        "lng": float(item.get("lon", 0.0))
                    })
                async with self:
                    self.search_suggestions = suggestions
        except Exception as e:
            print("Nominatim search failed:", e)

    def select_suggestion(self, sugg: Dict[str, Any]):
        self.form_region = sugg["display_name"]
        self.search_query = sugg["display_name"]
        self.selected_lat = float(sugg["lat"])
        self.selected_lng = float(sugg["lng"])
        self.search_suggestions = []

    def request_briefing(self):
        if not self.tourist_token:
            self.tourist_error = "You must be logged in"
            return
        if not self.form_region.strip():
            self.tourist_error = "Region is required"
            return
        if not self.form_start_date or not self.form_end_date:
            self.tourist_error = "Start and estimated end dates are required"
            return

        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        payload = {
            "region": self.form_region.strip(),
            "lat": self.selected_lat if self.selected_lat != 0.0 else None,
            "lng": self.selected_lng if self.selected_lng != 0.0 else None
        }
        try:
            res = requests.post(f"{BACKEND_URL}/api/trips/briefing", json=payload, headers=headers)
            if res.status_code == 200:
                data = res.json()
                self.briefing_zones = [BriefingZoneItem(**z) for z in data["danger_zones"]]
                self.briefing_destination_photo = data.get("destination_photo_url") or ""
                self.briefing_temp = data["weather"]["temp"]
                self.briefing_cond = data["weather"]["condition"]
                self.briefing_rain_status = data["weather"]["rainfall_status"]
                self.briefing_weather_warning = data["weather"]["is_warning"]
                self.briefing_safety_tips = data["safety_tips"]
                self.briefing_safe_hours = data["safe_hours"]
                self.briefing_warnings = data["warnings"]
                self.show_briefing_card = True
                self.tourist_error = ""
            else:
                self.tourist_error = res.json().get("detail", "Failed to retrieve pre-trip risk briefing.")
        except Exception as e:
            self.tourist_error = f"Backend Connection Error: {str(e)}"

    def cancel_briefing(self):
        self.show_briefing_card = False

    def confirm_start_trip(self):
        self.show_briefing_card = False
        return self.start_trip()

    def start_trip(self):
        if not self.tourist_token:
            self.tourist_error = "You must be logged in"
            return
        if not self.form_region.strip():
            self.tourist_error = "Region is required"
            return
        if not self.form_start_date or not self.form_end_date:
            self.tourist_error = "Start and estimated end dates are required"
            return

        # Convert local html datetime-local string to ISO format with timezone (UTC)
        try:
            start_dt = datetime.datetime.fromisoformat(self.form_start_date).isoformat() + "Z"
            end_dt = datetime.datetime.fromisoformat(self.form_end_date).isoformat() + "Z"
        except Exception:
            self.tourist_error = "Invalid date formatting"
            return

        interval_hours = None
        if self.form_checkin_interval == "1 Hour":
            interval_hours = 1.0
        elif self.form_checkin_interval == "2 Hours":
            interval_hours = 2.0
        elif self.form_checkin_interval == "4 Hours":
            interval_hours = 4.0

        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        payload = {
            "start_date": start_dt,
            "end_date": end_dt,
            "region": self.form_region.strip(),
            "checkin_interval_hours": interval_hours,
            "region_lat": self.selected_lat if self.selected_lat != 0.0 else None,
            "region_lng": self.selected_lng if self.selected_lng != 0.0 else None
        }

        try:
            res = requests.post(f"{BACKEND_URL}/api/trips/start", json=payload, headers=headers)
            if res.status_code == 201:
                data = res.json()
                self.active_trip_id = data["id"]
                self.active_trip_region = data["region"]
                self.active_trip_status = data["status"]
                self.active_trip_end = data["end_date"]
                self.active_checkin_interval = data.get("checkin_interval_hours") or 0.0
                self.active_last_checkin = data.get("last_checkin_at") or ""
                self.tourist_error = ""
                
                # Set map URL with coordinates
                d_lat = data.get("region_lat") or 0.0
                d_lng = data.get("region_lng") or 0.0
                self.tourist_map_url = f"/tourist_map.html?token={self.tourist_token}&trip_id={self.active_trip_id}&backend={BACKEND_URL}&dest_lat={d_lat}&dest_lng={d_lng}"
                
                return rx.redirect("/tourist/active")
            else:
                self.tourist_error = res.json().get("detail", "Failed to start trip")
        except Exception as e:
            self.tourist_error = f"Backend Connection Error: {str(e)}"

    def trigger_sos(self, is_online: bool = True, last_lat: float = 37.7456, last_lng: float = -119.5332):
        if not self.active_trip_id or not self.tourist_token:
            return
        
        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        payload = {
            "lat": last_lat,
            "lng": last_lng,
            "is_offline": not is_online
        }

        try:
            res = requests.post(f"{BACKEND_URL}/api/trips/{self.active_trip_id}/sos", json=payload, headers=headers, timeout=5)
            if res.status_code == 200:
                self.sos_active = True
                if not is_online:
                    self.sos_queued = False
                    self.tourist_success = "Offline SOS fallback SMS triggered successfully!"
                    self.tourist_error = ""
                else:
                    self.sos_queued = False
                    self.tourist_success = "SOS Emergency Transmitting!"
                    self.tourist_error = ""
                # Trigger native notification via LocalNotifications plugin
                return rx.call_script(
                    "const cap = window.Capacitor || (window.parent && window.parent.Capacitor);"
                    "if (cap && cap.Plugins && cap.Plugins.LocalNotifications) {"
                    "  const LocalNotifications = cap.Plugins.LocalNotifications;"
                    "  LocalNotifications.requestPermissions().then((status) => {"
                    "    if (status.display === 'granted') {"
                    "      LocalNotifications.schedule({"
                    "        notifications: [{"
                    "          title: '🚨 SOS Alert Active',"
                    "          body: 'Search and rescue dispatchers notified. Real-time location sharing active.',"
                    "          id: 2000,"
                    "          schedule: { at: new Date(Date.now() + 100) }"
                    "        }]"
                    "      });"
                    "    }"
                    "  });"
                    "}"
                )
            else:
                self.tourist_error = res.json().get("detail", "Failed to trigger SOS")
        except Exception as e:
            self.sos_active = True
            if not is_online:
                self.sos_queued = False
                self.tourist_error = "Server connection lost. Please call emergency services directly."
            else:
                self.sos_queued = True
                self.tourist_error = "Network disconnected. SOS queued locally. Sending when connection restores..."
            print("SOS request failed due to network error:", e)

    def handle_client_sos(self, is_online: bool, last_lat: float, last_lng: float):
        return self.trigger_sos(is_online=is_online, last_lat=last_lat, last_lng=last_lng)

    def retry_queued_sos(self):
        if not self.active_trip_id or not self.tourist_token:
            return
        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        payload = {
            "lat": 37.7456,
            "lng": -119.5332
        }
        try:
            res = requests.post(f"{BACKEND_URL}/api/trips/{self.active_trip_id}/sos", json=payload, headers=headers, timeout=3)
            if res.status_code == 200:
                self.sos_queued = False
                self.tourist_success = "SOS Emergency Transmitting!"
                self.tourist_error = ""
        except Exception as e:
            print("Retry SOS failed, still queued:", e)

    def cancel_sos(self):
        if not self.active_trip_id or not self.tourist_token:
            return

        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        try:
            res = requests.post(f"{BACKEND_URL}/api/trips/{self.active_trip_id}/sos/cancel", headers=headers)
            if res.status_code == 200:
                self.sos_active = False
                self.sos_queued = False
                self.tourist_success = "SOS cancelled."
                self.tourist_error = ""
            else:
                self.tourist_error = res.json().get("detail", "Failed to cancel SOS")
        except Exception as e:
            self.tourist_error = f"Backend Connection Error: {str(e)}"

    def end_trip(self):
        if not self.active_trip_id or not self.tourist_token:
            return

        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        try:
            res = requests.post(f"{BACKEND_URL}/api/trips/{self.active_trip_id}/end", headers=headers)
            if res.status_code == 200:
                self.active_trip_id = 0
                self.active_trip_region = ""
                self.active_trip_status = ""
                self.tourist_map_url = ""
                self.sos_active = False
                self.tourist_success = "Trip ended successfully. Return home safely!"
                return rx.redirect("/")
            else:
                self.tourist_error = res.json().get("detail", "Failed to end trip")
        except Exception as e:
            self.tourist_error = f"Backend Connection Error: {str(e)}"

    def tourist_logout(self):
        self.tourist_token = ""
        self.tourist_phone = ""
        self.tourist_otp = ""
        self.otp_sent = False
        self.active_trip_id = 0
        self.sos_active = False
        self.tourist_map_url = ""
        return rx.redirect("/")

    # --- AUTHORITY EVENT HANDLERS ---
    def set_auth_email(self, val: str):
        self.auth_email = val
        self.auth_error = ""

    def set_auth_password(self, val: str):
        self.auth_password = val
        self.auth_error = ""

    def set_dashboard_tab(self, tab: str):
        self.dashboard_tab = tab
        if tab == "alerts":
            self.load_alerts()

    def login_operator(self):
        if not self.auth_email.strip() or not self.auth_password.strip():
            self.auth_error = "Email and password are required"
            return

        try:
            res = requests.post(
                f"{BACKEND_URL}/api/auth/authority/login",
                json={
                    "email": self.auth_email.strip(),
                    "password": self.auth_password.strip()
                }
            )
            if res.status_code == 200:
                data = res.json()
                self.authority_token = data["access_token"]
                self.authority_name = data["name"]
                self.auth_error = ""
                self.operator_success = "Access granted"
                
                # Build map URL
                self.authority_map_url = f"/authority_map.html?token={self.authority_token}&backend={BACKEND_URL}"
                
                # Preload alerts
                self.load_alerts()
                
                return rx.redirect("/authority/dashboard")
            else:
                self.auth_error = res.json().get("detail", "Incorrect email or password")
        except Exception as e:
            self.auth_error = f"Backend Connection Error: {str(e)}"

    def load_alerts(self):
        if not self.authority_token:
            return
            
        headers = {"Authorization": f"Bearer {self.authority_token}"}
        try:
            res = requests.get(f"{BACKEND_URL}/api/trips/authority/alerts", headers=headers)
            if res.status_code == 200:
                self.alerts = []
                for item in res.json():
                    # Format timestamp cleanly
                    ts = item.get("timestamp")
                    if ts and isinstance(ts, str):
                        try:
                            dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            ts = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            pass
                    self.alerts.append(AlertItem(
                        id=item["id"],
                        trip_id=item["trip_id"],
                        phone_number=item["phone_number"],
                        type=item["type"],
                        lat=item["lat"],
                        lng=item["lng"],
                        timestamp=str(ts),
                        status=item["status"],
                        dispatch_notes=item.get("dispatch_notes") or ""
                    ))
            else:
                print("Failed to load alerts:", res.text)
        except Exception as e:
            print("Connection error loading alerts:", e)

        try:
            res_trips = requests.get(f"{BACKEND_URL}/api/trips/authority/active-trips", headers=headers, timeout=5)
            if res_trips.status_code == 200:
                self.active_trips_count = len(res_trips.json())
            else:
                print("Failed to load active trips count:", res_trips.text)
        except Exception as e:
            print("Connection error loading active trips count:", e)

    def set_tourist_warning(self, val: str):
        self.tourist_warning = val

    def check_tourist_alerts(self):
        if not self.tourist_token or not self.active_trip_id:
            return
        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        try:
            res = requests.get(f"{BACKEND_URL}/api/trips/authority/alerts", headers=headers)
            if res.status_code == 200:
                alerts = res.json()
                active_alerts = [a for a in alerts if a["trip_id"] == self.active_trip_id and a["status"] == "open" and a["type"] != "sos"]
                if active_alerts:
                    reasons = []
                    for a in active_alerts:
                        if a["type"] == "geofence":
                            reasons.append("Entering High-Risk Geofence Zone")
                        elif "distress" in a["type"]:
                            reasons.append(f"Distress Flagged ({a['type'].replace('distress_', '')})")
                    self.tourist_warning = "⚠️ " + " | ".join(reasons)
                else:
                    self.tourist_warning = ""
            else:
                print("Failed checking tourist warnings:", res.text)
        except Exception as e:
            print("Failed checking tourist warnings:", e)

    @rx.event(background=True)
    async def poll_tourist_alerts(self):
        while True:
            await asyncio.sleep(5)
            async with self:
                if not self.tourist_token or not self.active_trip_id:
                    break
                if self.sos_queued:
                    self.retry_queued_sos()
                self.check_tourist_alerts()
                self.load_group_info()

    def load_group_info(self):
        if not self.tourist_token:
            self.has_group = False
            self.group_join_code = ""
            return

        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        try:
            res = requests.get(f"{BACKEND_URL}/api/trips/group/my-group", headers=headers)
            if res.status_code == 200:
                data = res.json()
                self.has_group = True
                self.group_join_code = data["join_code"]

                # Load group members
                members_res = requests.get(f"{BACKEND_URL}/api/trips/group/members", headers=headers)
                if members_res.status_code == 200:
                    self.group_members = members_res.json()
                else:
                    self.group_members = []

                # Load group alerts
                alerts_res = requests.get(f"{BACKEND_URL}/api/trips/group/alerts", headers=headers)
                if alerts_res.status_code == 200:
                    self.group_alerts = alerts_res.json()
                else:
                    self.group_alerts = []
            else:
                self.has_group = False
                self.group_join_code = ""
                self.group_members = []
                self.group_alerts = []
        except Exception as e:
            print("Error loading group info:", e)

    def create_group_trip(self):
        if not self.tourist_token or not self.active_trip_id:
            self.group_error = "You must have an active trip first."
            return

        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        try:
            res = requests.post(f"{BACKEND_URL}/api/trips/group/create", headers=headers)
            if res.status_code == 201:
                self.group_success = "Group trip created successfully!"
                self.group_error = ""
                self.load_group_info()
            else:
                self.group_error = res.json().get("detail", "Failed to create group trip.")
                self.group_success = ""
        except Exception as e:
            self.group_error = f"Connection error: {str(e)}"
            self.group_success = ""

    def join_group_trip(self):
        if not self.tourist_token or not self.active_trip_id:
            self.group_error = "You must have an active trip first."
            return
        if not self.group_code_input.strip():
            self.group_error = "Join code is required."
            return

        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        payload = {"join_code": self.group_code_input.strip()}
        try:
            res = requests.post(f"{BACKEND_URL}/api/trips/group/join", json=payload, headers=headers)
            if res.status_code == 200:
                self.group_success = "Successfully joined group trip!"
                self.group_error = ""
                self.group_code_input = ""
                self.load_group_info()
            else:
                self.group_error = res.json().get("detail", "Failed to join group trip.")
                self.group_success = ""
        except Exception as e:
            self.group_error = f"Connection error: {str(e)}"
            self.group_success = ""

    def leave_group_trip(self):
        if not self.tourist_token:
            return
        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        try:
            res = requests.post(f"{BACKEND_URL}/api/trips/group/leave", headers=headers)
            if res.status_code == 200:
                self.group_success = "Left group trip."
                self.group_error = ""
                self.has_group = False
                self.group_join_code = ""
                self.group_members = []
                self.group_alerts = []
            else:
                self.group_error = res.json().get("detail", "Failed to leave group.")
        except Exception as e:
            self.group_error = f"Connection error: {str(e)}"

    def respond_to_group_alert(self, group_alert_id: int, action: str):
        if not self.tourist_token:
            return
        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        payload = {"action": action}
        try:
            res = requests.post(f"{BACKEND_URL}/api/trips/group/alerts/{group_alert_id}/respond", json=payload, headers=headers)
            if res.status_code == 200:
                self.load_group_info()
            else:
                print("Failed responding to group alert:", res.text)
        except Exception as e:
            print("Error responding to group alert:", e)

    @rx.event(background=True)
    async def poll_operator_alerts(self):
        while True:
            await asyncio.sleep(5)
            async with self:
                if not self.authority_token:
                    break
                self.load_alerts()

    def resolve_alert(self, alert_id: int):
        if not self.authority_token:
            return
            
        headers = {"Authorization": f"Bearer {self.authority_token}"}
        try:
            res = requests.post(
                f"{BACKEND_URL}/api/trips/authority/alerts/{alert_id}/resolve",
                headers=headers
            )
            if res.status_code == 200:
                self.load_alerts()
                self.operator_success = f"Alert #{alert_id} marked as resolved."
            else:
                self.auth_error = res.json().get("detail", "Failed to resolve alert")
        except Exception as e:
            self.auth_error = f"Backend Connection Error: {str(e)}"

    def operator_logout(self):
        self.authority_token = ""
        self.auth_email = ""
        self.auth_password = ""
        self.authority_map_url = ""
        self.alerts = []
        return rx.redirect("/authority")

    def set_dispatch_notes_input(self, val: str):
        self.dispatch_notes_input = val

    def set_report_from_date(self, val: str):
        self.report_from_date = val

    def set_report_to_date(self, val: str):
        self.report_to_date = val

    def open_resolve_modal(self, alert_id: int, alert_type: str, lat: float, lng: float, phone: str, timestamp: str):
        self.resolve_alert_id = alert_id
        self.resolve_alert_type = alert_type
        self.resolve_alert_lat = lat
        self.resolve_alert_lng = lng
        self.resolve_alert_phone = phone
        self.resolve_alert_time = timestamp
        self.dispatch_notes_input = ""
        self.show_resolve_modal = True

    def close_resolve_modal(self):
        self.show_resolve_modal = False
        self.dispatch_notes_input = ""

    def resolve_alert_with_notes(self):
        if not self.authority_token or not self.resolve_alert_id:
            return
            
        headers = {"Authorization": f"Bearer {self.authority_token}"}
        payload = {"dispatch_notes": self.dispatch_notes_input}
        try:
            res = requests.post(
                f"{BACKEND_URL}/api/trips/authority/alerts/{self.resolve_alert_id}/resolve",
                json=payload,
                headers=headers
            )
            if res.status_code == 200:
                self.load_alerts()
                self.operator_success = f"Alert #{self.resolve_alert_id} marked as resolved."
                self.show_resolve_modal = False
                self.dispatch_notes_input = ""
            else:
                self.auth_error = res.json().get("detail", "Failed to resolve alert")
        except Exception as e:
            self.auth_error = f"Backend Connection Error: {str(e)}"

    def export_resolved_csv(self):
        url = f"{BACKEND_URL}/api/alerts/export?from={self.report_from_date}&to={self.report_to_date}&token={self.authority_token}"
        return rx.redirect(url)

    @rx.var
    def resolved_alerts_filtered(self) -> List[AlertItem]:
        res = [a for a in self.alerts if a.status == "resolved"]
        if self.report_from_date:
            try:
                from_dt = datetime.datetime.strptime(self.report_from_date, "%Y-%m-%d")
                res = [a for a in res if datetime.datetime.strptime(a.timestamp, "%Y-%m-%d %H:%M:%S") >= from_dt]
            except Exception:
                pass
        if self.report_to_date:
            try:
                to_dt = datetime.datetime.strptime(self.report_to_date, "%Y-%m-%d") + datetime.timedelta(days=1)
                res = [a for a in res if datetime.datetime.strptime(a.timestamp, "%Y-%m-%d %H:%M:%S") < to_dt]
            except Exception:
                pass
        return res

    def open_feedback_modal(self):
        self.feedback_rating = 5
        self.feedback_felt_unsafe = False
        self.feedback_unsafe_location = ""
        self.feedback_suggestions = ""
        self.show_feedback_modal = True

    def close_feedback_modal(self):
        self.show_feedback_modal = False

    def set_feedback_rating(self, val: int):
        self.feedback_rating = val

    def set_feedback_felt_unsafe(self, val: bool):
        self.feedback_felt_unsafe = val

    def set_feedback_unsafe_location(self, val: str):
        self.feedback_unsafe_location = val

    def set_feedback_suggestions(self, val: str):
        self.feedback_suggestions = val

    def submit_feedback_and_end_trip(self):
        if not self.active_trip_id or not self.tourist_token:
            return
            
        headers = {"Authorization": f"Bearer {self.tourist_token}"}
        feedback_payload = {
            "rating": self.feedback_rating,
            "felt_unsafe": self.feedback_felt_unsafe,
            "unsafe_location": self.feedback_unsafe_location if self.feedback_felt_unsafe else None,
            "suggestions": self.feedback_suggestions
        }
        try:
            res_fb = requests.post(f"{BACKEND_URL}/api/trips/{self.active_trip_id}/feedback", json=feedback_payload, headers=headers)
            if res_fb.status_code != 201:
                print("Failed to save feedback:", res_fb.text)
        except Exception as e:
            print("Feedback connection error:", e)
            
        try:
            res_end = requests.post(f"{BACKEND_URL}/api/trips/{self.active_trip_id}/end", headers=headers)
            if res_end.status_code == 200:
                self.active_trip_id = 0
                self.active_trip_region = ""
                self.active_trip_status = ""
                self.tourist_map_url = ""
                self.sos_active = False
                self.show_feedback_modal = False
                self.tourist_success = "Trip ended successfully. Return home safely! Thank you for your feedback."
                return rx.redirect("/")
            else:
                self.tourist_error = res_end.json().get("detail", "Failed to end trip")
        except Exception as e:
            self.tourist_error = f"Backend Connection Error: {str(e)}"

    def load_feedback_summary(self):
        if not self.authority_token:
            return
        headers = {"Authorization": f"Bearer {self.authority_token}"}
        try:
            res = requests.get(f"{BACKEND_URL}/api/trips/authority/feedback-summary", headers=headers)
            if res.status_code == 200:
                data = res.json()
                self.feedback_regions = data.get("region_avg_ratings") or []
                self.feedback_zones = data.get("zone_felt_unsafe_counts") or []
                self.feedback_suggestions_list = data.get("latest_suggestions") or []
            else:
                print("Failed to load feedback summary:", res.text)
        except Exception as e:
            print("Connection error loading feedback summary:", e)

    def change_dashboard_tab(self, tab: str):
        self.dashboard_tab = tab
        if tab == "feedback":
            self.load_feedback_summary()

# --- UI COMPONENTS & PAGES ---

# Navigation / Headers
def nav_bar(title: str, user_name: str, on_logout: rx.event.EventHandler) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.heading(title, size="6", color="#3b82f6", font_weight="bold"),
            rx.spacer(),
            rx.hstack(
                rx.text(f"Logged in: {user_name}", size="3", color="#cbd5e1"),
                rx.button("Logout", on_click=on_logout, size="2", variant="outline", color_scheme="red"),
                spacing="3",
                align="center",
            ),
            align="center",
            width="100%",
        ),
        padding="4",
        background_color="rgba(15, 23, 42, 0.9)",
        border_bottom="1px solid rgba(255, 255, 255, 0.05)",
        width="100%",
    )

# 1. Start Trip Screen (Index Page)
def language_toggle() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.button(
                "EN",
                on_click=State.change_language("en"),
                variant=rx.cond(State.language == "en", "solid", "outline"),
                size="1",
                color_scheme="blue",
            ),
            rx.button(
                "हिं",
                on_click=State.change_language("hi"),
                variant=rx.cond(State.language == "hi", "solid", "outline"),
                size="1",
                color_scheme="blue",
            ),
            rx.button(
                "मर",
                on_click=State.change_language("mr"),
                variant=rx.cond(State.language == "mr", "solid", "outline"),
                size="1",
                color_scheme="blue",
            ),
            spacing="1",
        ),
        position="fixed",
        top="10px",
        right="10px",
        z_index="10000",
        background="rgba(30, 41, 59, 0.8)",
        padding="6px",
        border_radius="md",
        backdrop_filter="blur(4px)",
        border="1px solid rgba(255, 255, 255, 0.1)",
    )

def index() -> rx.Component:
    return rx.box(
        language_toggle(),
        rx.container(
            rx.vstack(
                # Header Logo
                rx.box(
                    rx.vstack(
                        rx.heading("SafeTrip Tourist Hub", size="8", color="#3b82f6", font_weight="bold"),
                        rx.text("Safety Monitoring & Emergency Geofencing", size="3", color="#94a3b8"),
                        align="center",
                        spacing="2",
                    ),
                    margin_bottom="6",
                    text_align="center",
                ),

                # Login panel or Start Trip form
                rx.cond(
                    State.tourist_token == "",
                    # LOGIN PANEL (OTP)
                    rx.box(
                        rx.vstack(
                            rx.heading(State.translation["login"], size="4", color="#f8fafc", margin_bottom="4"),
                            rx.text(State.translation["enter_phone"], size="2", color="#94a3b8", margin_bottom="4"),
                            
                            rx.input(
                                placeholder=State.translation["enter_phone"],
                                value=State.tourist_phone,
                                on_change=State.set_tourist_phone,
                                size="3",
                                margin_bottom="3",
                                bg="#0b0f19",
                                border="1px solid rgba(255, 255, 255, 0.1)",
                                color="white",
                                width="100%",
                            ),

                            # OTP Verification input (conditionally shown)
                            rx.cond(
                                State.otp_sent,
                                rx.vstack(
                                    rx.input(
                                        placeholder=State.translation["enter_otp"] + " (backdoor '123456')",
                                        value=State.tourist_otp,
                                        on_change=State.set_tourist_otp,
                                        size="3",
                                        margin_bottom="3",
                                        bg="#0b0f19",
                                        border="1px solid rgba(255, 255, 255, 0.1)",
                                        color="white",
                                        width="100%",
                                    ),
                                    rx.button(State.translation["verify"], on_click=State.verify_otp, size="3", color_scheme="blue", width="100%", height="12"),
                                    width="100%",
                                ),
                                rx.button(State.translation["verify"], on_click=State.request_otp, size="3", color_scheme="blue", width="100%", height="12"),
                            ),
                            
                            # Error Messages
                            rx.cond(
                                State.tourist_error != "",
                                rx.text(State.tourist_error, color="#ef4444", size="2", margin_top="3", font_weight="semibold"),
                            ),
                            rx.cond(
                                State.tourist_success != "",
                                rx.text(State.tourist_success, color="#10b981", size="2", margin_top="3", font_weight="semibold"),
                            ),
                            width="100%",
                        ),
                        background_color="rgba(30, 41, 59, 0.7)",
                        border="1px solid rgba(255, 255, 255, 0.05)",
                        border_radius="12px",
                        padding="8",
                        width="100%",
                        max_width="450px",
                        backdrop_filter="blur(8px)",
                    ),
                    
                    # START TRIP FORM
                    rx.box(
                        rx.vstack(
                            rx.heading(State.translation["start_trip"], size="5", color="#f8fafc", margin_bottom="2"),
                            rx.text(f"Logged in as {State.tourist_phone}. Ready to register your safe boundary monitoring?", size="2", color="#94a3b8", margin_bottom="6"),
                            
                            rx.text(State.translation["trip_region"], size="2", font_weight="bold", color="#cbd5e1", width="100%", margin_bottom="1"),
                            rx.box(
                                rx.input(
                                    placeholder="Search destination (e.g. Mumbai, Yosemite)",
                                    value=State.search_query,
                                    on_change=State.handle_search_change,
                                    size="3",
                                    bg="#0b0f19",
                                    border="1px solid rgba(255, 255, 255, 0.1)",
                                    color="white",
                                    width="100%",
                                ),
                                rx.cond(
                                    State.search_suggestions.length() > 0,
                                    rx.vstack(
                                        rx.foreach(
                                            State.search_suggestions,
                                            lambda sugg: rx.box(
                                                rx.text(sugg["display_name"], color="white", size="2", cursor="pointer"),
                                                padding="2",
                                                width="100%",
                                                _hover={"bg": "rgba(255, 255, 255, 0.1)"},
                                                on_click=lambda: State.select_suggestion(sugg),
                                            )
                                        ),
                                        bg="#0f172a",
                                        border="1px solid rgba(255, 255, 255, 0.1)",
                                        border_radius="6px",
                                        width="100%",
                                        max_height="200px",
                                        overflow_y="auto",
                                        z_index="10",
                                        margin_top="1",
                                    )
                                ),
                                width="100%",
                                margin_bottom="4",
                            ),

                            rx.text(State.translation["trip_dates"], size="2", font_weight="bold", color="#cbd5e1", width="100%", margin_bottom="1"),
                            rx.input(
                                type="datetime-local",
                                value=State.form_start_date,
                                on_change=State.set_form_start_date,
                                size="3",
                                margin_bottom="4",
                                bg="#0b0f19",
                                border="1px solid rgba(255, 255, 255, 0.1)",
                                color="white",
                                width="100%",
                            ),

                            rx.text("Estimated End Date", size="2", font_weight="bold", color="#cbd5e1", width="100%", margin_bottom="1"),
                            rx.input(
                                type="datetime-local",
                                value=State.form_end_date,
                                on_change=State.set_form_end_date,
                                size="3",
                                margin_bottom="6",
                                bg="#0b0f19",
                                border="1px solid rgba(255, 255, 255, 0.1)",
                                color="white",
                                width="100%",
                            ),

                            rx.text("Check-In Interval (Timer)", size="2", font_weight="bold", color="#cbd5e1", width="100%", margin_bottom="1"),
                            rx.select(
                                ["None", "1 Hour", "2 Hours", "4 Hours"],
                                value=State.form_checkin_interval,
                                on_change=State.set_form_checkin_interval,
                                size="3",
                                margin_bottom="6",
                                width="100%",
                            ),

                            rx.button(State.translation["start_trip"], on_click=State.request_briefing, size="3", color_scheme="green", width="100%", height="12"),
                            
                            # Error Messages
                            rx.cond(
                                State.tourist_error != "",
                                rx.text(State.tourist_error, color="#ef4444", size="2", margin_top="3", font_weight="semibold"),
                            ),
                            rx.cond(
                                State.tourist_success != "",
                                rx.text(State.tourist_success, color="#10b981", size="2", margin_top="3", font_weight="semibold"),
                            ),
                            
                            # Logout option
                            rx.button("Logout", on_click=State.tourist_logout, size="2", variant="ghost", color_scheme="red", margin_top="4"),
                            width="100%",
                        ),
                        background_color="rgba(30, 41, 59, 0.7)",
                        border="1px solid rgba(255, 255, 255, 0.05)",
                        border_radius="12px",
                        padding="8",
                        width="100%",
                        max_width="450px",
                        backdrop_filter="blur(8px)",
                    )
                ),
                align="center",
                justify="center",
                min_height="90vh",
            ),
        ),
        
        # Pre-Trip Risk Briefing Modal Overlay
        rx.cond(
            State.show_briefing_card,
            rx.box(
                rx.vstack(
                    rx.box(
                        rx.heading("🚨 ", State.translation["risk_briefing"], size="6", color="#3b82f6", font_weight="bold", margin_bottom="1"),
                        rx.text(f"Region: {State.form_region}", size="3", color="#cbd5e1", font_weight="bold"),
                        border_bottom="1px solid rgba(255, 255, 255, 0.1)",
                        padding_bottom="3",
                        width="100%",
                        margin_bottom="4",
                    ),
                    
                    rx.cond(
                        State.briefing_destination_photo != "",
                        rx.image(
                            src=State.briefing_destination_photo,
                            width="100%",
                            height="180px",
                            object_fit="cover",
                            border_radius="8px",
                            margin_bottom="4",
                            alt="Destination Banner"
                        )
                    ),
                    
                    # Safe hours & Weather details
                    rx.vstack(
                        rx.hstack(
                            rx.text("Estimated Safe Hours:", size="2", color="#94a3b8"),
                            rx.text(State.briefing_safe_hours, size="3", color="#10b981", font_weight="bold"),
                            spacing="2",
                            align="center",
                        ),
                        rx.hstack(
                            rx.text("Current Weather:", size="2", color="#94a3b8"),
                            rx.text(f"{State.briefing_temp}°C | {State.briefing_cond}", size="3", color="white", font_weight="semibold"),
                            spacing="2",
                            align="center",
                        ),
                        rx.hstack(
                            rx.text("Precipitation Rate:", size="2", color="#94a3b8"),
                            rx.text(State.briefing_rain_status, size="3", color=rx.cond(State.briefing_weather_warning, "#ef4444", "#10b981"), font_weight="bold"),
                            spacing="2",
                            align="center",
                        ),
                        align_items="start",
                        spacing="2",
                        width="100%",
                        bg="rgba(15, 23, 42, 0.5)",
                        padding="4",
                        border_radius="10px",
                        border="1px solid rgba(255, 255, 255, 0.05)",
                        margin_bottom="4",
                    ),
                    
                    # Danger Zones in Region
                    rx.vstack(
                        rx.text(State.briefing_title, size="2", font_weight="bold", color="#94a3b8"),
                        rx.cond(
                            State.briefing_zones.length() > 0,
                            rx.vstack(
                                rx.foreach(
                                    State.briefing_zones,
                                    lambda z: rx.hstack(
                                        rx.cond(
                                            z.photo_url != "",
                                            rx.image(
                                                src=z.photo_url,
                                                width="75px",
                                                height="75px",
                                                object_fit="cover",
                                                border_radius="6px",
                                                margin_right="2",
                                            ),
                                            rx.image(
                                                src="https://images.unsplash.com/photo-1524661135-423995f22d0b?auto=format&fit=crop&w=800&q=80",
                                                width="75px",
                                                height="75px",
                                                object_fit="cover",
                                                border_radius="6px",
                                                margin_right="2",
                                            )
                                        ),
                                        rx.vstack(
                                            rx.hstack(
                                                rx.text(z.name, color="white", size="2", font_weight="bold"),
                                                rx.spacer(),
                                                rx.text(f"Score: {z.risk_score} ({z.risk_level.upper()})", color=rx.cond(z.risk_score >= 70, "#ef4444", rx.cond(z.risk_score >= 40, "#f59e0b", "#10b981")), size="2", font_weight="bold"),
                                                width="100%",
                                                align="center",
                                            ),
                                            rx.cond(
                                                z.avoid_caption != "",
                                                rx.text(z.avoid_caption, size="2", color="#cbd5e1", font_style="italic"),
                                                rx.text(f"Risk Score: {z.risk_score}/100. Exercise caution.", size="2", color="#cbd5e1")
                                            ),
                                            rx.cond(
                                                (z.hazard_type != "") & (z.hazard_type != "curated_danger_zone"),
                                                rx.text("Illustrative image", size="1", color="#64748b", font_style="italic")
                                            ),
                                            align_items="start",
                                            spacing="1",
                                            width="100%",
                                        ),
                                        width="100%",
                                        bg="rgba(15, 23, 42, 0.4)",
                                        padding="3",
                                        border_radius="8px",
                                        border="1px solid rgba(255, 255, 255, 0.05)",
                                        margin_bottom="2",
                                        align_items="center",
                                    )
                                ),
                                width="100%",
                                spacing="1",
                            ),
                            rx.text("No active danger zones detected in this region.", size="2", font_style="italic", color="#64748b")
                        ),
                        align_items="start",
                        width="100%",
                        margin_bottom="4",
                    ),
                    
                    # Safety Tips (Rule-Based)
                    rx.vstack(
                        rx.text("Safety Recommendations:", size="2", font_weight="bold", color="#94a3b8"),
                        rx.vstack(
                            rx.foreach(
                                State.briefing_safety_tips,
                                lambda tip: rx.hstack(
                                    rx.text("💡", size="3"),
                                    rx.text(tip, size="2", color="#cbd5e1"),
                                    align="start",
                                    spacing="2",
                                    width="100%",
                                )
                            ),
                            width="100%",
                            spacing="2",
                        ),
                        align_items="start",
                        width="100%",
                        margin_bottom="4",
                    ),
                    
                    # Warnings Box (if any)
                    rx.cond(
                        State.briefing_warnings.length() > 0,
                        rx.vstack(
                            rx.text("⚠️ Risk Warnings:", size="2", font_weight="bold", color="#ef4444"),
                            rx.vstack(
                                rx.foreach(
                                    State.briefing_warnings,
                                    lambda w: rx.text(f"• {w}", size="2", color="#fca5a5")
                                ),
                                width="100%",
                                align_items="start",
                                spacing="1",
                            ),
                            width="100%",
                            align_items="start",
                            bg="rgba(220, 38, 38, 0.1)",
                            padding="3",
                            border_radius="8px",
                            border="1px solid rgba(239, 68, 68, 0.2)",
                            margin_bottom="4",
                        )
                    ),
                    
                    # Action buttons
                    rx.hstack(
                        rx.button("Confirm & Start Trip", on_click=State.confirm_start_trip, color_scheme="green", size="3", width="48%", height="12"),
                        rx.button("Cancel / Go Back", on_click=State.cancel_briefing, variant="outline", color_scheme="red", size="3", width="48%", height="12"),
                        justify="between",
                        width="100%",
                        margin_top="4",
                    ),
                    align="center",
                    justify="center",
                    max_width="520px",
                    width="100%",
                    padding="6",
                    background_color="rgba(30, 41, 59, 0.95)",
                    border="1px solid rgba(255, 255, 255, 0.1)",
                    border_radius="16px",
                    box_shadow="0 8px 32px rgba(0, 0, 0, 0.5)",
                    backdrop_filter="blur(12px)",
                ),
                position="absolute",
                top="0",
                left="0",
                width="100%",
                height="100%",
                background_color="rgba(15, 23, 42, 0.7)",
                backdrop_filter="blur(6px)",
                display="flex",
                align_items="center",
                justify_content="center",
                z_index="3000",
            )
        ),
        background_color="#0f172a",
        min_height="100vh",
        background_image="radial-gradient(ellipse at top, #1e293b, #0f172a)",
    )

# 2. Active Trip Screen
def active_trip() -> rx.Component:
    return rx.box(
        language_toggle(),
        rx.cond(
            State.tourist_token == "",
            # Redirect back if not logged in
            rx.vstack(
                rx.text("Redirecting to login...", color="white"),
                rx.button("Go to Login", on_click=lambda: rx.redirect("/")),
                padding="8",
            ),
            # MAIN VIEW
            rx.vstack(
                nav_bar("SafeTrip active monitor", State.tourist_phone, State.tourist_logout),
                
                # Proactive Warning Banner
                rx.cond(
                    State.tourist_warning != "",
                    rx.box(
                        rx.hstack(
                            rx.text(State.tourist_warning, color="white", font_weight="bold", size="3"),
                            rx.spacer(),
                            rx.button("Dismiss", on_click=lambda: State.set_tourist_warning(""), size="1", variant="outline", color_scheme="gray"),
                            width="100%",
                            align="center",
                        ),
                        bg="#d97706",
                        padding_y="3",
                        padding_x="6",
                        width="100%",
                    )
                ),
                
                # Overdue Check-in Warning Banner
                rx.cond(
                    State.is_checkin_overdue,
                    rx.box(
                        rx.hstack(
                            rx.text("⚠️ WARNING: Your check-in is overdue! Please click 'I'm Safe' immediately to avoid triggering emergency responses.", color="white", font_weight="bold", size="3"),
                            width="100%",
                            align="center",
                        ),
                        bg="#ef4444",
                        padding_y="3",
                        padding_x="6",
                        width="100%",
                    )
                ),
                
                # Active Trip Info bar
                rx.hstack(
                    rx.vstack(
                        rx.heading(f"Active Trip in {State.active_trip_region}", size="4", color="white"),
                        rx.text(f"Trip ID: #{State.active_trip_id} | End Date: {State.active_trip_end}", size="2", color="#94a3b8"),
                        rx.cond(
                            State.active_checkin_interval > 0,
                            rx.vstack(
                                rx.text(f"Check-In: every {State.active_checkin_interval}h | Last: {State.active_last_checkin}", size="2", color="#10b981", font_weight="semibold"),
                                rx.text(State.checkin_countdown_msg, size="2", color="#fbbf24", font_weight="bold"),
                                align_items="start",
                                spacing="1",
                            ),
                        ),
                        align_items="start",
                    ),
                    rx.spacer(),
                    rx.cond(
                        State.active_checkin_interval > 0,
                        rx.button(State.translation["im_safe"], on_click=State.confirm_safe, color_scheme="green", size="3", margin_right="4"),
                    ),
                    rx.button(State.translation["trip_ended"], on_click=State.open_feedback_modal, color_scheme="red", size="3"),
                    width="100%",
                    padding_x="6",
                    padding_y="4",
                    background_color="#1e293b",
                    border_bottom="1px solid rgba(255, 255, 255, 0.05)",
                ),
                
                # Trip Buddy Group Bar
                rx.hstack(
                    rx.cond(
                        ~State.has_group,
                        # Not in group: show Create and Join inputs
                        rx.hstack(
                            rx.heading("Trip Buddy Group:", size="3", color="#cbd5e1", font_weight="bold"),
                            rx.input(
                                placeholder="Enter 6-digit Join Code",
                                value=State.group_code_input,
                                on_change=State.set_group_code_input,
                                size="2",
                                width="200px",
                                bg="#0b0f19",
                                border="1px solid rgba(255, 255, 255, 0.1)",
                                color="white",
                            ),
                            rx.button("Join Group", on_click=State.join_group_trip, color_scheme="blue", size="2"),
                            rx.text("or", color="#94a3b8", size="2"),
                            rx.button("Create Group Trip", on_click=State.create_group_trip, color_scheme="green", size="2"),
                            # Show group error if any
                            rx.cond(
                                State.group_error != "",
                                rx.text(State.group_error, color="#ef4444", size="2", font_weight="semibold"),
                            ),
                            # Show group success if any
                            rx.cond(
                                State.group_success != "",
                                rx.text(State.group_success, color="#10b981", size="2", font_weight="semibold"),
                            ),
                            spacing="3",
                            align="center",
                        ),
                        # In a group: show current group code & leave button
                        rx.hstack(
                            rx.heading("Trip Buddy Group Active:", size="3", color="#10b981", font_weight="bold"),
                            rx.box(
                                rx.hstack(
                                    rx.text("Join Code:", size="2", color="#94a3b8"),
                                    rx.text(State.group_join_code, size="3", color="white", font_weight="bold", font_family="monospace"),
                                    spacing="1",
                                    align="center",
                                ),
                                bg="#0f172a",
                                padding_x="3",
                                padding_y="1",
                                border_radius="6px",
                                border="1px solid rgba(16, 185, 129, 0.3)",
                            ),
                            rx.text("|", color="#334155"),
                            rx.text("Members:", size="2", color="#94a3b8"),
                            rx.hstack(
                                rx.foreach(
                                    State.group_members,
                                    lambda m: rx.hstack(
                                        rx.box(width="8px", height="8px", border_radius="50%", bg=m["color"]),
                                        rx.text(m["phone_number"], size="2", color="white"),
                                        spacing="1",
                                        align="center",
                                        bg="#0f172a",
                                        padding_x="2",
                                        padding_y="0.5",
                                        border_radius="4px",
                                    )
                                ),
                                spacing="2",
                            ),
                            rx.spacer(),
                            rx.button("Leave Group", on_click=State.leave_group_trip, variant="outline", color_scheme="red", size="2"),
                            spacing="3",
                            align="center",
                            width="100%",
                        ),
                    ),
                    width="100%",
                    padding_x="6",
                    padding_y="3",
                    background_color="rgba(15, 23, 42, 0.8)",
                    border_bottom="1px solid rgba(255, 255, 255, 0.05)",
                    align="center",
                ),

                # Map Embed and large SOS button
                rx.box(
                    # The Iframe Map
                    rx.el.iframe(
                        src=State.tourist_map_url,
                        width="100%",
                        height="100%",
                        style={"border": "none"},
                    ),
                    
                    # Large Floating SOS target
                    rx.box(
                        rx.button(
                            State.translation["sos_button"],
                            on_click=State.handle_client_sos(
                                rx.vars.LiteralVar("window.navigator.onLine"),
                                rx.vars.LiteralVar("parseFloat(localStorage.getItem('last_lat') || '37.7456')"),
                                rx.vars.LiteralVar("parseFloat(localStorage.getItem('last_lng') || '-119.5332')")
                            ),
                            background_color="#dc2626",
                            color="white",
                            font_weight="bold",
                            font_size="24px",
                            border_radius="50%",
                            width="90px",
                            height="90px",
                            box_shadow="0 0 20px rgba(220, 38, 38, 0.8)",
                            cursor="pointer",
                        ),
                        position="absolute",
                        bottom="30px",
                        right="30px",
                        z_index="1000",
                    ),
                    
                    # 4. SOS Confirmation overlay screen
                    rx.cond(
                        State.sos_active,
                        rx.box(
                            rx.vstack(
                                rx.box(
                                    rx.heading("🚨 ", State.translation["sos_button"], " ALERT TRANSMITTING 🚨", size="7", color="#ef4444", font_weight="black", margin_bottom="3"),
                                    rx.cond(
                                        State.sos_queued,
                                        rx.text(State.translation["offline_banner"], size="3", color="#f59e0b", text_align="center", font_weight="bold"),
                                        rx.text(State.translation["sos_sent"], size="3", color="#cbd5e1", text_align="center"),
                                    ),
                                    margin_bottom="6",
                                    text_align="center",
                                ),
                                rx.vstack(
                                    rx.text("TRANS-ID", size="1", color="#64748b", font_weight="bold"),
                                    rx.text(f"TRIP-{State.active_trip_id}-SOS", size="4", color="white", font_family="monospace"),
                                    spacing="1",
                                    align="center",
                                    margin_bottom="6",
                                ),
                                rx.button(
                                    "Cancel SOS Emergency",
                                    on_click=State.cancel_sos,
                                    color_scheme="red",
                                    size="4",
                                    width="100%",
                                    height="14",
                                    font_weight="bold",
                                    border="1px solid rgba(255, 0, 0, 0.2)",
                                ),
                                align="center",
                                justify="center",
                                max_width="450px",
                                width="100%",
                                padding="8",
                                background_color="rgba(15, 23, 42, 0.95)",
                                border="1px solid rgba(239, 68, 68, 0.3)",
                                border_radius="16px",
                                box_shadow="0 0 40px rgba(0, 0, 0, 0.8)",
                            ),
                            position="absolute",
                            top="0",
                            left="0",
                            width="100%",
                            height="100%",
                            background_color="rgba(15, 23, 42, 0.75)",
                            backdrop_filter="blur(6px)",
                            display="flex",
                            align_items="center",
                            justify_content="center",
                            z_index="2000",
                        )
                    ),
                    
                    # Trip Buddy Distress alert overlay screen
                    rx.cond(
                        State.group_alerts.length() > 0,
                        rx.box(
                            rx.vstack(
                                rx.box(
                                    rx.heading("🚨 TRIP BUDDY IN DISTRESS 🚨", size="7", color="#ef4444", font_weight="black", margin_bottom="3"),
                                    rx.text(
                                        f"Your group member {State.active_group_alert_phone} is in distress!",
                                        size="3", color="white", font_weight="bold", text_align="center"
                                    ),
                                    rx.text(
                                        f"Type: {State.active_group_alert_type.upper()} | Last known location: {State.active_group_alert_coords}",
                                        size="2", color="#cbd5e1", text_align="center", margin_top="2"
                                    ),
                                    margin_bottom="6",
                                    text_align="center",
                                ),
                                rx.hstack(
                                    rx.button(
                                        "🙋‍♂️ I'm going to help",
                                        on_click=lambda: State.respond_to_group_alert(State.active_group_alert_id, "going_to_help"),
                                        color_scheme="green",
                                        size="4",
                                        width="48%",
                                        height="14",
                                        font_weight="bold",
                                    ),
                                    rx.button(
                                        "📞 Call authorities",
                                        on_click=lambda: State.respond_to_group_alert(State.active_group_alert_id, "call_authorities"),
                                        color_scheme="red",
                                        size="4",
                                        width="48%",
                                        height="14",
                                        font_weight="bold",
                                    ),
                                    justify="between",
                                    width="100%",
                                    margin_bottom="4",
                                ),
                                rx.button(
                                    "Acknowledge / Dismiss",
                                    on_click=lambda: State.respond_to_group_alert(State.active_group_alert_id, "acknowledged"),
                                    variant="ghost",
                                    color_scheme="gray",
                                    size="2",
                                    width="100%",
                                ),
                                align="center",
                                justify="center",
                                max_width="480px",
                                width="100%",
                                padding="8",
                                background_color="rgba(15, 23, 42, 0.95)",
                                border="2px solid #ef4444",
                                border_radius="16px",
                                box_shadow="0 0 50px rgba(220, 38, 38, 0.5)",
                            ),
                            position="absolute",
                            top="0",
                            left="0",
                            width="100%",
                            height="100%",
                            background_color="rgba(15, 23, 42, 0.8)",
                            backdrop_filter="blur(8px)",
                            display="flex",
                            align_items="center",
                            justify_content="center",
                            z_index="2500",
                        )
                    ),
                    width="100%",
                    height="calc(100vh - 145px)",
                    position="relative",
                ),
                width="100%",
                spacing="0",
            ),
        ),
        # Post-Trip Feedback Modal
        rx.cond(
            State.show_feedback_modal,
            rx.box(
                rx.vstack(
                    rx.box(
                        rx.heading("Post-Trip Feedback", size="6", color="white", font_weight="bold", margin_bottom="2"),
                        rx.text("Thank you for using SafeTrip. Please help us improve safety for others.", size="2", color="#94a3b8", margin_bottom="6"),
                        
                        # 1. Overall Safety Rating
                        rx.text("Overall Safety Rating", size="2", font_weight="bold", color="#cbd5e1", margin_bottom="2"),
                        rx.hstack(
                            rx.foreach(
                                [1, 2, 3, 4, 5],
                                lambda i: rx.button(
                                    "⭐",
                                    bg=rx.cond(State.feedback_rating >= i, "#f59e0b", "transparent"),
                                    color=rx.cond(State.feedback_rating >= i, "white", "#64748b"),
                                    border="1px solid rgba(255, 255, 255, 0.1)",
                                    on_click=lambda: State.set_feedback_rating(i),
                                    size="2",
                                    width="40px",
                                )
                            ),
                            spacing="2",
                            margin_bottom="4",
                        ),
                        
                        # 2. Did you feel unsafe?
                        rx.text("Did you feel unsafe at any point during your trip?", size="2", font_weight="bold", color="#cbd5e1", margin_bottom="2"),
                        rx.hstack(
                            rx.button(
                                "Yes",
                                bg=rx.cond(State.feedback_felt_unsafe, "#ef4444", "transparent"),
                                color=rx.cond(State.feedback_felt_unsafe, "white", "#94a3b8"),
                                border="1px solid rgba(255, 255, 255, 0.1)",
                                on_click=lambda: State.set_feedback_felt_unsafe(True),
                                size="2",
                            ),
                            rx.button(
                                "No",
                                bg=rx.cond(~State.feedback_felt_unsafe, "#10b981", "transparent"),
                                color=rx.cond(~State.feedback_felt_unsafe, "white", "#94a3b8"),
                                border="1px solid rgba(255, 255, 255, 0.1)",
                                on_click=lambda: State.set_feedback_felt_unsafe(False),
                                size="2",
                            ),
                            spacing="3",
                            margin_bottom="4",
                        ),
                        
                        # 3. Where? (If Yes)
                        rx.cond(
                            State.feedback_felt_unsafe,
                            rx.vstack(
                                rx.text("Where?", size="2", font_weight="bold", color="#cbd5e1", margin_bottom="1"),
                                rx.input(
                                    placeholder="e.g. Near Glacier Point, Mist Trail...",
                                    value=State.feedback_unsafe_location,
                                    on_change=State.set_feedback_unsafe_location,
                                    size="3",
                                    margin_bottom="4",
                                    bg="#0b0f19",
                                    color="white",
                                    border="1px solid rgba(255,255,255,0.1)",
                                    width="100%",
                                ),
                                align_items="start",
                                width="100%",
                            )
                        ),
                        
                        # 4. Suggestions
                        rx.text("Any suggestions for improving safety in this area?", size="2", font_weight="bold", color="#cbd5e1", margin_bottom="1"),
                        rx.text_area(
                            placeholder="Suggestions...",
                            value=State.feedback_suggestions,
                            on_change=State.set_feedback_suggestions,
                            size="3",
                            margin_bottom="6",
                            bg="#0b0f19",
                            color="white",
                            border="1px solid rgba(255,255,255,0.1)",
                            width="100%",
                            height="80px",
                        ),
                        
                        # Buttons
                        rx.hstack(
                            rx.button(
                                "Cancel",
                                on_click=State.close_feedback_modal,
                                variant="outline",
                                color_scheme="gray",
                                size="3",
                                width="50%",
                            ),
                            rx.button(
                                "Submit & End Trip",
                                on_click=State.submit_feedback_and_end_trip,
                                color_scheme="red",
                                size="3",
                                width="50%",
                            ),
                            spacing="3",
                            width="100%",
                        ),
                        text_align="left",
                        width="100%",
                    ),
                    max_width="450px",
                    width="100%",
                    padding="8",
                    background_color="rgba(15, 23, 42, 0.98)",
                    border="1px solid rgba(255, 255, 255, 0.1)",
                    border_radius="16px",
                    box_shadow="0 0 40px rgba(0, 0, 0, 0.8)",
                ),
                position="absolute",
                top="0",
                left="0",
                width="100%",
                height="100%",
                background_color="rgba(15, 23, 42, 0.85)",
                backdrop_filter="blur(6px)",
                display="flex",
                align_items="center",
                justify_content="center",
                z_index="3000",
            )
        ),
        background_color="#0f172a",
        height="100vh",
        overflow="hidden",
    )

# 3. Authority Login Screen
def authority_login() -> rx.Component:
    return rx.box(
        language_toggle(),
        rx.container(
            rx.vstack(
                # Header Logo
                rx.box(
                    rx.vstack(
                        rx.heading("SafeTrip Operations Portal", size="8", color="#ef4444", font_weight="bold"),
                        rx.text("Search & Rescue Emergency Dispatch Terminal", size="3", color="#94a3b8"),
                        align="center",
                        spacing="2",
                    ),
                    margin_bottom="6",
                    text_align="center",
                ),

                # Login panel
                rx.box(
                    rx.vstack(
                        rx.heading("Operator Authorization", size="4", color="#f8fafc", margin_bottom="4"),
                        
                        rx.input(
                            placeholder="Operator Email (operator@safetrip.gov)",
                            value=State.auth_email,
                            on_change=State.set_auth_email,
                            size="3",
                            margin_bottom="3",
                            bg="#0b0f19",
                            border="1px solid rgba(255, 255, 255, 0.1)",
                            color="white",
                            width="100%",
                        ),

                        rx.input(
                            type="password",
                            placeholder="Password (password123)",
                            value=State.auth_password,
                            on_change=State.set_auth_password,
                            size="3",
                            margin_bottom="4",
                            bg="#0b0f19",
                            border="1px solid rgba(255, 255, 255, 0.1)",
                            color="white",
                            width="100%",
                        ),

                        rx.button("Sign In to Control Room", on_click=State.login_operator, size="3", color_scheme="red", width="100%", height="12"),
                        
                        # Error Messages
                        rx.cond(
                            State.auth_error != "",
                            rx.text(State.auth_error, color="#ef4444", size="2", margin_top="3", font_weight="semibold"),
                        ),
                        rx.cond(
                            State.operator_success != "",
                            rx.text(State.operator_success, color="#10b981", size="2", margin_top="3", font_weight="semibold"),
                        ),
                        width="100%",
                    ),
                    background_color="rgba(30, 41, 59, 0.7)",
                    border="1px solid rgba(255, 255, 255, 0.05)",
                    border_radius="12px",
                    padding="8",
                    width="100%",
                    max_width="450px",
                    backdrop_filter="blur(8px)",
                ),
                align="center",
                justify="center",
                min_height="90vh",
            ),
        ),
        background_color="#0b0f19",
        min_height="100vh",
        background_image="radial-gradient(ellipse at top, #1e1b4b, #09090b)",
    )

# 4. Operator Dashboard Screen (Map & Alert Feed tabs)
def authority_dashboard() -> rx.Component:
    # Single Alert Row helper
    def alert_row(alert: AlertItem) -> rx.Component:
        # Determine background and badges based on alert status/type
        is_open = alert.status == "open"
        is_sos = alert.type == "sos"
        
        type_label = rx.cond(
            alert.type == "sos",
            "SOS",
            rx.cond(
                alert.type == "geofence",
                "GEOFENCE",
                "DISTRESS"
            )
        )

        badge_color = rx.cond(
            alert.type == "geofence",
            "#f59e0b",
            "#ef4444"
        )
        
        return rx.box(
            rx.hstack(
                # Details
                rx.vstack(
                    rx.hstack(
                        rx.box(
                            type_label,
                            font_weight="bold",
                            font_size="10px",
                            bg=badge_color,
                            color="white",
                            padding_x="2",
                            padding_y="1",
                            border_radius="4px",
                        ),
                        rx.text(f"Trip ID: #{alert.trip_id} (Phone: {alert.phone_number})", size="3", font_weight="bold", color="white"),
                        align="center",
                        spacing="2",
                    ),
                    rx.text(f"Coordinates: {alert.lat} , {alert.lng} | Triggered at: {alert.timestamp}", size="2", color="#94a3b8"),
                    align_items="start",
                    spacing="2",
                ),
                rx.spacer(),
                # Action
                rx.cond(
                    is_open,
                    rx.button(
                        "Resolve",
                        on_click=lambda: State.open_resolve_modal(
                            alert.id,
                            alert.type,
                            alert.lat,
                            alert.lng,
                            alert.phone_number,
                            alert.timestamp
                        ),
                        color_scheme="green",
                        size="2",
                    ),
                    rx.box(
                        "Resolved",
                        font_size="11px",
                        color="#64748b",
                        border="1px solid #334155",
                        padding_x="3",
                        padding_y="1.5",
                        border_radius="4px",
                    )
                ),
                align="center",
                width="100%",
            ),
            padding="4",
            border_bottom="1px solid rgba(255, 255, 255, 0.05)",
            background_color=rx.cond(is_open, "rgba(30, 41, 59, 0.3)", "transparent"),
        )

    return rx.box(
        language_toggle(),
        rx.cond(
            State.authority_token == "",
            # Redirect if not logged in
            rx.vstack(
                rx.text("Redirecting to operator login...", color="white"),
                rx.button("Go to Operator Login", on_click=lambda: rx.redirect("/authority")),
                padding="8",
            ),
            # Dashboard Main View
            rx.vstack(
                nav_bar("SafeTrip dispatcher terminal", State.authority_name, State.operator_logout),
                
                # Tab bar selector
                rx.hstack(
                    rx.button(
                        "Live Dispatch Map",
                        on_click=lambda: State.change_dashboard_tab("map"),
                        bg=rx.cond(State.dashboard_tab == "map", "#ef4444", "transparent"),
                        color=rx.cond(State.dashboard_tab == "map", "white", "#94a3b8"),
                        border_radius="6px",
                        padding_x="4",
                        size="3",
                    ),
                    rx.button(
                        "Emergency Alert Feed",
                        on_click=lambda: State.change_dashboard_tab("alerts"),
                        bg=rx.cond(State.dashboard_tab == "alerts", "#ef4444", "transparent"),
                        color=rx.cond(State.dashboard_tab == "alerts", "white", "#94a3b8"),
                        border_radius="6px",
                        padding_x="4",
                        size="3",
                    ),
                    rx.button(
                        "Incident Reports",
                        on_click=lambda: State.change_dashboard_tab("reports"),
                        bg=rx.cond(State.dashboard_tab == "reports", "#ef4444", "transparent"),
                        color=rx.cond(State.dashboard_tab == "reports", "white", "#94a3b8"),
                        border_radius="6px",
                        padding_x="4",
                        size="3",
                    ),
                    rx.button(
                        "Feedback Summary",
                        on_click=lambda: State.change_dashboard_tab("feedback"),
                        bg=rx.cond(State.dashboard_tab == "feedback", "#ef4444", "transparent"),
                        color=rx.cond(State.dashboard_tab == "feedback", "white", "#94a3b8"),
                        border_radius="6px",
                        padding_x="4",
                        size="3",
                    ),
                    rx.spacer(),
                    rx.button(
                        "Sync Alerts",
                        on_click=State.load_alerts,
                        variant="outline",
                        color_scheme="gray",
                        size="2",
                    ),
                    width="100%",
                    padding_x="6",
                    padding_y="3",
                    background_color="#111827",
                    border_bottom="1px solid rgba(255, 255, 255, 0.05)",
                ),
                
                # Dynamic tab pages
                rx.cond(
                    State.dashboard_tab == "map",
                    # Live Map Frame or Empty State Message
                    rx.cond(
                        State.active_trips_count > 0,
                        rx.box(
                            rx.el.iframe(
                                src=State.authority_map_url,
                                width="100%",
                                height="100%",
                                style={"border": "none"},
                            ),
                            width="100%",
                            height="calc(100vh - 138px)",
                        ),
                        # Empty state message
                        rx.box(
                            rx.vstack(
                                rx.text("🗺️", font_size="56px", margin_bottom="2"),
                                rx.heading("No active trips right now", size="6", color="white", font_weight="bold"),
                                rx.text("There are currently no active tourist monitoring sessions in progress.", size="3", color="#94a3b8"),
                                spacing="3",
                                align="center",
                            ),
                            width="100%",
                            height="calc(100vh - 138px)",
                            display="flex",
                            align_items="center",
                            justify_content="center",
                            background_color="#09090b",
                        ),
                    ),
                    rx.cond(
                        State.dashboard_tab == "alerts",
                        # Alert Feed List
                        rx.box(
                            rx.vstack(
                                rx.box(
                                    rx.heading("Triggered Emergency Alerts", size="4", color="white", margin_bottom="1"),
                                    rx.text("Active distress signals, geofence breaches, and tourist manual SOS transmissions", size="2", color="#64748b"),
                                    padding="4",
                                    border_bottom="1px solid rgba(255, 255, 255, 0.05)",
                                    width="100%",
                                ),
                                # Loop over alerts
                                rx.cond(
                                    rx.State.is_hydrated,
                                    rx.box(
                                        rx.vstack(
                                            rx.foreach(
                                                State.alerts,
                                                alert_row
                                            ),
                                            width="100%",
                                            spacing="0",
                                        ),
                                        width="100%",
                                        overflow_y="auto",
                                        height="calc(100vh - 225px)",
                                    ),
                                    rx.text("Loading alerts...", color="#94a3b8", padding="8"),
                                ),
                                width="100%",
                                spacing="0",
                            ),
                            width="100%",
                            background_color="#09090b",
                        ),
                        # Incident Reports or Feedback Tab
                        rx.cond(
                            State.dashboard_tab == "reports",
                            # Incident Reports Tab
                            rx.box(
                                rx.vstack(
                                    rx.hstack(
                                        rx.vstack(
                                            rx.text("From Date", size="2", font_weight="bold", color="#cbd5e1"),
                                            rx.input(
                                                type="date",
                                                value=State.report_from_date,
                                                on_change=State.set_report_from_date,
                                                size="2",
                                                bg="#0b0f19",
                                                color="white",
                                                border="1px solid rgba(255,255,255,0.1)",
                                            ),
                                            align_items="start",
                                        ),
                                        rx.vstack(
                                            rx.text("To Date", size="2", font_weight="bold", color="#cbd5e1"),
                                            rx.input(
                                                type="date",
                                                value=State.report_to_date,
                                                on_change=State.set_report_to_date,
                                                size="2",
                                                bg="#0b0f19",
                                                color="white",
                                                border="1px solid rgba(255,255,255,0.1)",
                                            ),
                                            align_items="start",
                                        ),
                                        rx.vstack(
                                            rx.text("Action", size="2", font_weight="bold", color="transparent"),
                                            rx.button(
                                                "Export CSV",
                                                on_click=State.export_resolved_csv,
                                                color_scheme="green",
                                                size="2",
                                            ),
                                            align_items="start",
                                        ),
                                        spacing="4",
                                        padding="4",
                                        align="end",
                                        width="100%",
                                        border_bottom="1px solid rgba(255, 255, 255, 0.05)",
                                    ),
                                    # Resolved alerts list
                                    rx.box(
                                        rx.cond(
                                            State.resolved_alerts_filtered.length() > 0,
                                            rx.vstack(
                                                rx.foreach(
                                                    State.resolved_alerts_filtered,
                                                    lambda alert: rx.box(
                                                        rx.vstack(
                                                            rx.hstack(
                                                                rx.box(
                                                                    alert.type.upper(),
                                                                    font_weight="bold",
                                                                    font_size="10px",
                                                                    bg="#64748b",
                                                                    color="white",
                                                                    padding_x="2",
                                                                    padding_y="1",
                                                                    border_radius="4px",
                                                                ),
                                                                rx.text(f"Trip ID: #{alert.trip_id} (Phone: {alert.phone_number})", size="3", font_weight="bold", color="white"),
                                                                rx.spacer(),
                                                                rx.text(f"Resolved at: {alert.timestamp}", size="2", color="#94a3b8"),
                                                                align="center",
                                                                width="100%",
                                                            ),
                                                            rx.text(f"Location: {alert.lat}, {alert.lng}", size="2", color="#cbd5e1"),
                                                            rx.cond(
                                                                alert.dispatch_notes != "",
                                                                rx.text(f"Dispatch Notes: {alert.dispatch_notes}", size="2", color="#a3a3a3", font_style="italic", margin_top="1"),
                                                                rx.text("Dispatch Notes: None", size="2", color="#737373", font_style="italic", margin_top="1"),
                                                            ),
                                                            align_items="start",
                                                            spacing="1",
                                                        ),
                                                        padding="4",
                                                        border_bottom="1px solid rgba(255, 255, 255, 0.05)",
                                                        width="100%",
                                                    )
                                                ),
                                                width="100%",
                                                spacing="0",
                                            ),
                                            rx.box(
                                                rx.text("No resolved incidents found matching filters.", color="#64748b", size="3"),
                                                padding="8",
                                                text_align="center",
                                                width="100%",
                                            )
                                        ),
                                        width="100%",
                                        overflow_y="auto",
                                        height="calc(100vh - 225px)",
                                    ),
                                    width="100%",
                                    spacing="0",
                                ),
                                width="100%",
                                background_color="#09090b",
                            ),
                            # Feedback Summary Tab
                            rx.box(
                                rx.vstack(
                                    rx.box(
                                        rx.heading("Tourist Post-Trip Feedback Analysis", size="4", color="white", margin_bottom="1"),
                                        rx.text("Aggregated safety ratings, danger zone reports, and traveler suggestions", size="2", color="#64748b"),
                                        padding="4",
                                        border_bottom="1px solid rgba(255, 255, 255, 0.05)",
                                        width="100%",
                                    ),
                                    rx.grid(
                                        # Card 1: Regional Ratings
                                        rx.box(
                                            rx.heading("Average Safety Rating by Region", size="3", color="white", margin_bottom="3"),
                                            rx.cond(
                                                State.feedback_regions.length() > 0,
                                                rx.vstack(
                                                    rx.foreach(
                                                        State.feedback_regions,
                                                        lambda r: rx.hstack(
                                                            rx.text(r["region"], color="white", font_weight="semibold"),
                                                            rx.spacer(),
                                                            rx.text(f"⭐ {r['avg_rating']}", color="#f59e0b", font_weight="bold"),
                                                            width="100%",
                                                            padding="2",
                                                            border_bottom="1px solid rgba(255, 255, 255, 0.02)",
                                                        )
                                                    ),
                                                    width="100%",
                                                ),
                                                rx.text("No regional ratings recorded yet.", color="#64748b", size="2")
                                            ),
                                            bg="#111827",
                                            padding="4",
                                            border_radius="8px",
                                            border="1px solid rgba(255, 255, 255, 0.05)",
                                        ),
                                        # Card 2: Felt Unsafe Reports
                                        rx.box(
                                            rx.heading("Felt Unsafe Reports per Danger Zone", size="3", color="white", margin_bottom="3"),
                                            rx.cond(
                                                State.feedback_zones.length() > 0,
                                                rx.vstack(
                                                    rx.foreach(
                                                        State.feedback_zones,
                                                        lambda z: rx.hstack(
                                                            rx.text(z["zone_name"], color="white", font_weight="semibold"),
                                                            rx.spacer(),
                                                            rx.box(
                                                                f"{z['felt_unsafe_count']} reports",
                                                                bg=rx.cond(z["felt_unsafe_count"].to(int) > 0, "rgba(239, 68, 68, 0.2)", "rgba(16, 185, 129, 0.2)"),
                                                                color=rx.cond(z["felt_unsafe_count"].to(int) > 0, "#ef4444", "#10b981"),
                                                                padding_x="2.5",
                                                                padding_y="0.5",
                                                                border_radius="12px",
                                                                font_size="11px",
                                                                font_weight="bold",
                                                            ),
                                                            width="100%",
                                                            padding="2",
                                                            border_bottom="1px solid rgba(255, 255, 255, 0.02)",
                                                        )
                                                    ),
                                                    width="100%",
                                                ),
                                                rx.text("No danger zones registered.", color="#64748b", size="2")
                                            ),
                                            bg="#111827",
                                            padding="4",
                                            border_radius="8px",
                                            border="1px solid rgba(255, 255, 255, 0.05)",
                                        ),
                                        columns="2",
                                        spacing="4",
                                        padding="4",
                                        width="100%",
                                    ),
                                    # Suggestions
                                    rx.box(
                                        rx.heading("Latest Tourist Suggestions & Comments", size="3", color="white", margin_bottom="3"),
                                        rx.cond(
                                            State.feedback_suggestions_list.length() > 0,
                                            rx.vstack(
                                                rx.foreach(
                                                    State.feedback_suggestions_list,
                                                    lambda s: rx.box(
                                                        rx.vstack(
                                                            rx.hstack(
                                                                rx.text(f"Trip ID: #{s['trip_id']}", size="2", font_weight="bold", color="#cbd5e1"),
                                                                rx.spacer(),
                                                                rx.text(s["created_at"], size="1", color="#64748b"),
                                                                width="100%",
                                                            ),
                                                            rx.text(s["suggestions"], size="2", color="#cbd5e1", margin_top="1"),
                                                            align_items="start",
                                                        ),
                                                        bg="#111827",
                                                        padding="3",
                                                        border_radius="6px",
                                                        border="1px solid rgba(255, 255, 255, 0.03)",
                                                        width="100%",
                                                    )
                                                ),
                                                width="100%",
                                                spacing="2",
                                            ),
                                            rx.text("No suggestions submitted yet.", color="#64748b", size="2")
                                        ),
                                        padding="4",
                                        width="100%",
                                    ),
                                    width="100%",
                                    spacing="0",
                                ),
                                width="100%",
                                background_color="#09090b",
                                overflow_y="auto",
                                height="calc(100vh - 138px)",
                            )
                        )
                    )
                ),
                width="100%",
                spacing="0",
            ),
        ),
        # Alert Resolution Modal overlay
        rx.cond(
            State.show_resolve_modal,
            rx.box(
                rx.vstack(
                    rx.box(
                        rx.heading(f"Resolve Alert #{State.resolve_alert_id}", size="6", color="white", font_weight="bold", margin_bottom="4"),
                        
                        # Alert Summary
                        rx.vstack(
                            rx.text(f"Type: {State.resolve_alert_type}", size="2", color="#cbd5e1"),
                            rx.text(f"Location: {State.resolve_alert_lat}, {State.resolve_alert_lng}", size="2", color="#cbd5e1"),
                            rx.text(f"Tourist Phone: {State.resolve_alert_phone}", size="2", color="#cbd5e1"),
                            rx.text(f"Triggered: {State.resolve_alert_time}", size="2", color="#cbd5e1"),
                            align_items="start",
                            spacing="1",
                            margin_bottom="4",
                            background_color="rgba(255, 255, 255, 0.05)",
                            padding="3",
                            border_radius="6px",
                            width="100%",
                        ),
                        
                        # Text Area for Dispatch Notes
                        rx.text("Dispatch Notes", size="2", font_weight="bold", color="#cbd5e1", margin_bottom="1"),
                        rx.text_area(
                            placeholder="Enter details of action taken, resources sent, and outcome (minimum 10 characters)...",
                            value=State.dispatch_notes_input,
                            on_change=State.set_dispatch_notes_input,
                            size="3",
                            height="100px",
                            margin_bottom="6",
                            bg="#0b0f19",
                            border="1px solid rgba(255, 255, 255, 0.1)",
                            color="white",
                            width="100%",
                        ),
                        
                        # Buttons
                        rx.hstack(
                            rx.button(
                                "Cancel",
                                on_click=State.close_resolve_modal,
                                variant="outline",
                                color_scheme="gray",
                                size="3",
                                width="50%",
                            ),
                            rx.button(
                                "Mark Resolved",
                                on_click=State.resolve_alert_with_notes,
                                color_scheme="green",
                                disabled=State.dispatch_notes_input.length() < 10,
                                size="3",
                                width="50%",
                            ),
                            spacing="3",
                            width="100%",
                        ),
                        text_align="left",
                        width="100%",
                    ),
                    max_width="450px",
                    width="100%",
                    padding="8",
                    background_color="rgba(15, 23, 42, 0.98)",
                    border="1px solid rgba(255, 255, 255, 0.1)",
                    border_radius="16px",
                    box_shadow="0 0 40px rgba(0, 0, 0, 0.8)",
                ),
                position="absolute",
                top="0",
                left="0",
                width="100%",
                height="100%",
                background_color="rgba(15, 23, 42, 0.85)",
                backdrop_filter="blur(6px)",
                display="flex",
                align_items="center",
                justify_content="center",
                z_index="10000",
            ),
        ),
        background_color="#0b0f19",
        height="100vh",
        overflow="hidden",
    )

app = rx.App(
    style={
        "body": {
            "background_color": "#0f172a",
        }
    }
)

# Wire up the pages
app.add_page(index, route="/", on_load=[State.check_active_trip, State.load_language_preference])
app.add_page(active_trip, route="/tourist/active", on_load=[State.poll_tourist_alerts, State.load_language_preference])
app.add_page(authority_login, route="/authority", on_load=State.load_language_preference)
app.add_page(authority_dashboard, route="/authority/dashboard", on_load=[State.poll_operator_alerts, State.load_language_preference])
