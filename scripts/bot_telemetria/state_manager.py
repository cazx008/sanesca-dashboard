"""
Módulo de Gestión de Estado e Idempotencia
Previene doble despacho, audita envíos y rastrea sesiones activas de planta
"""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

STATE_FILE = Path(__file__).resolve().parent / "dispatch_state.json"
VENEZUELA_TZ = timezone(timedelta(hours=-4))

class StateManager:
    def __init__(self):
        self._load_state()

    def _load_state(self):
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except Exception:
                self.state = {}
        else:
            self.state = {}

        # Valores por defecto de automatizaciones
        if "automations" not in self.state:
            self.state["automations"] = {
                "alerta_matutina": True,
                "prealerta_corte": True,
                "monitor_horometro": True
            }

        # Estado de sesión de planta
        if "planta_session" not in self.state:
            self.state["planta_session"] = {
                "is_active": False,
                "start_iso": None,
                "page_id": None
            }

    def _save_state(self):
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando estado: {e}")

    def get_local_now(self):
        return datetime.now(VENEZUELA_TZ)

    # --- Despacho de WhatsApp ---
    def is_dispatched_today(self):
        today = self.get_local_now().strftime("%Y-%m-%d")
        return self.state.get("last_production_date") == today

    def record_production_dispatch(self, message_id=None):
        now = self.get_local_now()
        self.state["last_production_date"] = now.strftime("%Y-%m-%d")
        self.state["last_production_time"] = now.strftime("%I:%M:%S %p")
        self.state["last_production_message_id"] = message_id
        self._save_state()

    def record_sandbox_test(self, message_id=None):
        now = self.get_local_now()
        self.state["last_test_time"] = now.strftime("%I:%M:%S %p")
        self.state["last_test_message_id"] = message_id
        self._save_state()

    # --- Control de Automatizaciones ---
    def is_automation_enabled(self, name):
        return self.state.get("automations", {}).get(name, True)

    def toggle_automation(self, name):
        current = self.is_automation_enabled(name)
        self.state.setdefault("automations", {})[name] = not current
        self._save_state()
        return not current

    # --- Sesión de Planta (Planta ON / OFF) ---
    def is_planta_active(self):
        return self.state.get("planta_session", {}).get("is_active", False)

    def get_planta_session(self):
        return self.state.get("planta_session", {})

    def set_planta_on(self, page_id, start_iso):
        self.state["planta_session"] = {
            "is_active": True,
            "start_iso": start_iso,
            "page_id": page_id
        }
        self._save_state()

    def set_planta_off(self):
        sess = self.state.get("planta_session", {})
        self.state["planta_session"] = {
            "is_active": False,
            "start_iso": None,
            "page_id": None,
            "last_completed": sess.get("start_iso")
        }
        self._save_state()

state_mgr = StateManager()
