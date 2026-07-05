import gi, json, locale as locale_mod, logging, os, random, socket, subprocess, threading
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("vpn-tray")
gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as AppIndicator
gi.require_version("WebKit2", "4.1")
from gi.repository import Gtk, GLib, WebKit2

ICON_ON = "security-high-symbolic"
ICON_OFF = "security-low-symbolic"
POLL_SECONDS = 8
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# ─── i18n ────────────────────────────────────────────────────────────────────

I18N = {
    "en": {
        "interval_disabled": "Disabled",
        "interval_15m": "15 minutes",
        "interval_30m": "30 minutes",
        "interval_1h": "1 hour",
        "interval_6h": "6 hours",
        "interval_1d": "1 day",
        "interval_1w": "1 week",
        "tray_title": "Mullvad VPN",
        "status_off": "🔓 VPN disabled (real IP)",
        "status_on": "🔒 {} / {}",
        "status_auto": " · auto {}",
        "menu_off": "Disable VPN",
        "menu_random": "🎲 Random node (world)",
        "menu_fast": "⚡ Fast random (top nodes)",
        "menu_choose": "🌍 Choose node…",
        "menu_rotation": "🔁 Auto-rotation",
        "menu_country_lock": "Stay in current country",
        "menu_refresh": "↻ Refresh node list",
        "menu_quit": "Quit",
        "menu_lang": "🌐 Language",
        "lang_en": "English",
        "lang_it": "Italiano",
        "picker_title": "Choose VPN node",
        "picker_search": "Search country, city or server…",
        "picker_legend": "★ = Mullvad quality (higher = recommended). Best nodes on top.",
        "picker_active": "✓",
        "picker_no_vpn": "🔓 No VPN active",
    },
    "it": {
        "interval_disabled": "Disattivata",
        "interval_15m": "15 minuti",
        "interval_30m": "30 minuti",
        "interval_1h": "1 ora",
        "interval_6h": "6 ore",
        "interval_1d": "1 giorno",
        "interval_1w": "1 settimana",
        "tray_title": "Mullvad VPN",
        "status_off": "🔓 VPN disattivata (IP reale)",
        "status_on": "🔒 {} / {}",
        "status_auto": " · auto {}",
        "menu_off": "Disattiva VPN",
        "menu_random": "🎲 Nodo casuale (mondo)",
        "menu_fast": "⚡ Random veloce (top nodi)",
        "menu_choose": "🌍 Scegli nodo…",
        "menu_rotation": "🔁 Rotazione automatica",
        "menu_country_lock": "Resta nel paese attuale",
        "menu_refresh": "↻ Aggiorna lista nodi",
        "menu_quit": "Esci",
        "menu_lang": "🌐 Lingua",
        "lang_en": "English",
        "lang_it": "Italiano",
        "picker_title": "Scegli nodo VPN",
        "picker_search": "Cerca paese, città o server…",
        "picker_legend": "★ = qualità Mullvad (più alto = consigliato). Nodi migliori in cima.",
        "picker_active": "✓",
        "picker_no_vpn": "🔓 Nessuna VPN attiva",
    }
}

INTERVALS = [
    ("interval_disabled", 0),
    ("interval_15m", 15),
    ("interval_30m", 30),
    ("interval_1h", 60),
    ("interval_6h", 360),
    ("interval_1d", 1440),
    ("interval_1w", 10080),
]


def _detect_lang():
    cfg = {}
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "r") as f:
            cfg = json.load(f)
    except Exception:
        pass
    if cfg.get("lang") in ("en", "it"):
        return cfg["lang"]
    lang = os.environ.get("LANG", "") or os.environ.get("LC_ALL", "")
    if lang.startswith("it"):
        return "it"
    return "en"


_LANG = _detect_lang()


def t(key):
    return I18N[_LANG].get(key, I18N["en"].get(key, key))


# ─── Config helpers ───────────────────────────────────────────────────────────

def load_config():
    cfg = {"interval_min": 0, "country_lock": False, "lang": _LANG}
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "r") as f:
            loaded = json.load(f)
            cfg.update(loaded)
    except Exception:
        logger.warning("load_config failed, using defaults", exc_info=True)
    return cfg


def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        logger.warning("save_config failed", exc_info=True)


# ─── Tailscale helpers ───────────────────────────────────────────────────────

def sd_notify(state):
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s.connect(addr)
        s.sendall(state.encode())
        s.close()
    except Exception:
        logger.warning("systemd watchdog failed", exc_info=True)


def ts_status_peers():
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)
        return [p for p in data.get("Peer", {}).values() if p.get("ExitNodeOption")]
    except Exception:
        logger.warning("ts_status_peers failed", exc_info=True)
        return []


def _get_ipv4(ts_ips):
    for ip in ts_ips:
        if ":" not in ip:
            return ip
    return ts_ips[0] if ts_ips else ""


def list_nodes():
    try:
        nodes = []
        for p in ts_status_peers():
            loc = p.get("Location", {})
            if not loc:
                continue
            ts_ips = p.get("TailscaleIPs", [])
            ip = _get_ipv4(ts_ips)
            nodes.append({
                "host": p.get("HostName", ""),
                "ip": ip,
                "country": loc.get("Country", ""),
                "country_code": loc.get("CountryCode", ""),
                "city": loc.get("City", ""),
                "priority": loc.get("Priority", 0)
            })
        nodes.sort(key=lambda x: (x["country"], x["city"]))
        return nodes
    except Exception:
        logger.warning("list_nodes failed", exc_info=True)
        return []


def current_node():
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)
        for p in data.get("Peer", {}).values():
            if p.get("ExitNode"):
                loc = p.get("Location", {})
                ts_ips = p.get("TailscaleIPs", [])
                return {
                    "country": loc.get("Country", ""),
                    "country_code": loc.get("CountryCode", ""),
                    "city": loc.get("City", ""),
                    "ip": _get_ipv4(ts_ips),
                    "host": p.get("HostName", "")
                }
        return None
    except Exception:
        logger.warning("current_node failed", exc_info=True)
        return None


def set_node(ip):
    try:
        subprocess.run(
            ["tailscale", "set", "--exit-node=" + ip, "--exit-node-allow-lan-access"],
            timeout=20
        )
    except Exception:
        logger.error("set_node(%s) failed", ip, exc_info=True)


def clear_node():
    try:
        subprocess.run(
            ["tailscale", "set", "--exit-node="],
            timeout=20
        )
    except Exception:
        logger.error("clear_node failed", exc_info=True)


# ─── Main class ───────────────────────────────────────────────────────────────

class VpnTray:
    def __init__(self):
        self.ind = AppIndicator.Indicator.new(
            "vpn-toggle", ICON_OFF, AppIndicator.IndicatorCategory.SYSTEM_SERVICES
        )
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.ind.set_title(t("tray_title"))

        self.cfg = load_config()
        self.nodes = list_nodes()
        self.rotate_source = None
        self._building = False

        self.build_menu()
        self.refresh()
        GLib.timeout_add_seconds(2, self._initial_nodes_refresh)
        GLib.timeout_add_seconds(POLL_SECONDS, self._tick)

        sd_notify("WATCHDOG=1")
        GLib.timeout_add_seconds(15, self._watchdog)

        if self.cfg["interval_min"] > 0:
            self.apply_rotation()

    def _watchdog(self):
        sd_notify("WATCHDOG=1")
        return True

    def _initial_nodes_refresh(self):
        self.nodes = list_nodes()
        self.build_menu()
        return False

    def build_menu(self):
        self._building = True
        self.menu = Gtk.Menu()
        cur = current_node()

        self.item_status = Gtk.MenuItem(label="")
        self.item_status.set_sensitive(False)
        self.menu.append(self.item_status)

        item_off = Gtk.MenuItem(label=t("menu_off"))
        item_off.connect("activate", self.on_off)
        self.menu.append(item_off)

        self.menu.append(Gtk.SeparatorMenuItem())

        item_random = Gtk.MenuItem(label=t("menu_random"))
        item_random.connect("activate", self.on_random)
        self.menu.append(item_random)

        item_fast = Gtk.MenuItem(label=t("menu_fast"))
        item_fast.connect("activate", self.on_random_fast)
        self.menu.append(item_fast)

        item_choose = Gtk.MenuItem(label=t("menu_choose"))
        item_choose.connect("activate", self.on_choose_node)
        self.menu.append(item_choose)

        self.menu.append(Gtk.SeparatorMenuItem())

        rot_menu = Gtk.Menu()
        item_rot = Gtk.MenuItem(label=t("menu_rotation"))
        item_rot.set_submenu(rot_menu)

        for key, minutes in INTERVALS:
            item = Gtk.CheckMenuItem(label=t(key))
            item.set_draw_as_radio(True)
            item.set_active(minutes == self.cfg["interval_min"])
            item.connect("activate", lambda _, m=minutes: self.set_interval(m))
            rot_menu.append(item)

        rot_menu.append(Gtk.SeparatorMenuItem())

        item_lock = Gtk.CheckMenuItem(label=t("menu_country_lock"))
        item_lock.set_active(self.cfg["country_lock"])
        item_lock.connect("toggled", self.toggle_country_lock)
        rot_menu.append(item_lock)

        self.menu.append(item_rot)
        self.menu.append(Gtk.SeparatorMenuItem())

        item_refresh = Gtk.MenuItem(label=t("menu_refresh"))
        item_refresh.connect("activate", self.on_refresh_nodes)
        self.menu.append(item_refresh)

        # ─── Language submenu ───────────────────────────────────────────────
        lang_menu = Gtk.Menu()
        item_lang = Gtk.MenuItem(label=t("menu_lang"))
        item_lang.set_submenu(lang_menu)

        item_lang_en = Gtk.CheckMenuItem(label=t("lang_en"))
        item_lang_en.set_draw_as_radio(True)
        item_lang_en.set_active(_LANG == "en")
        item_lang_en.connect("activate", lambda _: self.set_lang("en"))
        lang_menu.append(item_lang_en)

        item_lang_it = Gtk.CheckMenuItem(label=t("lang_it"))
        item_lang_it.set_draw_as_radio(True)
        item_lang_it.set_active(_LANG == "it")
        item_lang_it.connect("activate", lambda _: self.set_lang("it"))
        lang_menu.append(item_lang_it)

        self.menu.append(item_lang)
        self.menu.append(Gtk.SeparatorMenuItem())

        item_quit = Gtk.MenuItem(label=t("menu_quit"))
        item_quit.connect("activate", lambda *_: Gtk.main_quit())
        self.menu.append(item_quit)

        self.menu.show_all()
        self.ind.set_menu(self.menu)
        self._building = False

    def _do_connect(self, ip):
        set_node(ip)
        GLib.idle_add(self.after_change)

    def refresh(self):
        cur = current_node()
        on = cur is not None
        tooltip = t("tray_title")
        if on:
            self.ind.set_icon_full(ICON_ON, tooltip)
            label = t("status_on").format(cur["country"], cur["city"])
            if self.cfg["interval_min"] > 0:
                for key, mins in INTERVALS:
                    if mins == self.cfg["interval_min"]:
                        label += t("status_auto").format(t(key))
                        break
            self.item_status.set_label(label)
        else:
            self.ind.set_icon_full(ICON_OFF, tooltip)
            self.item_status.set_label(t("status_off"))

    def on_off(self, _):
        threading.Thread(target=self._do_off, daemon=True).start()

    def _do_off(self):
        clear_node()
        GLib.idle_add(self.after_change)

    def on_random(self, _):
        if not self.nodes:
            return
        ip = random.choice([n["ip"] for n in self.nodes])
        self.connect_to(ip)

    def on_random_fast(self, _):
        if not self.nodes:
            return
        ranked = sorted(self.nodes, key=lambda n: n.get("priority", 0), reverse=True)
        top_n = max(10, len(ranked) // 10)
        ip = random.choice(ranked[:top_n])["ip"]
        self.connect_to(ip)

    def connect_to(self, ip):
        threading.Thread(target=self._do_connect, args=(ip,), daemon=True).start()

    def on_choose_node(self, _):
        if getattr(self, "_chooser", None):
            self._chooser.present()
            return

        win = Gtk.Window(title=t("picker_title"))
        win.set_default_size(440, 620)
        win.set_keep_above(True)
        self._chooser = win

        manager = WebKit2.UserContentManager()
        manager.register_script_message_handler("connect")
        manager.connect("script-message-received::connect", self._on_web_connect)

        webview = WebKit2.WebView.new_with_user_content_manager(manager)
        webview.load_html(self._chooser_html(), "file:///")
        win.add(webview)

        win.connect("destroy", lambda *_: setattr(self, "_chooser", None))
        win.show_all()
        win.present()

    def _on_web_connect(self, _manager, result):
        try:
            ip = result.get_js_value().to_string()
        except Exception:
            ip = ""
        if ip:
            self.connect_to(ip)
        chooser = getattr(self, "_chooser", None)
        if chooser:
            chooser.destroy()

    @staticmethod
    def _flag(country_code):
        cc = (country_code or "").upper()
        if len(cc) != 2 or not cc.isalpha():
            return "🌍"
        return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in cc)

    def _chooser_html(self):
        cur = current_node()
        cur_ip = cur.get("ip") if cur else ""

        countries = {}
        for n in self.nodes:
            countries.setdefault(n["country"], []).append(n)

        rows = []
        for country in sorted(countries.keys()):
            group = countries[country]
            city_count = {}
            for n in group:
                city_count[n["city"]] = city_count.get(n["city"], 0) + 1

            group = sorted(group, key=lambda n: (-n.get("priority", 0), n["city"]))

            cities_html = []
            for n in group:
                city = n["city"]
                label = city if city_count[city] == 1 else "{} · {}".format(city, n["host"])
                active = " active" if n["ip"] == cur_ip else ""
                check = " " + t("picker_active") if n["ip"] == cur_ip else ""
                prio = n.get("priority", 0)
                badge = '<span class="prio">★{}</span>'.format(prio) if prio else ""
                cities_html.append(
                    '<div class="city{active}" data-ip="{ip}" data-s="{search}" '
                    'onclick="pick(\'{ip}\')">{label}{check}{badge}</div>'.format(
                        active=active, ip=n["ip"],
                        search=(country + " " + city + " " + n["host"]).lower(),
                        label=label, check=check, badge=badge)
                )

            open_attr = " open" if any(n["ip"] == cur_ip for n in group) else ""
            flag = self._flag(group[0].get("country_code", ""))
            rows.append(
                '<details class="country"{open} data-s="{cs}">'
                '<summary><span class="flag">{flag}</span> {country} '
                '<span class="cnt">{count}</span></summary>'
                '{cities}</details>'.format(
                    open=open_attr, cs=country.lower(), flag=flag, country=country,
                    count=len(group), cities="".join(cities_html))
            )

        if cur:
            cur_label = "🔒 {} {} / {}".format(
                self._flag(cur.get("country_code", "")), cur["country"], cur["city"])
        else:
            cur_label = t("picker_no_vpn")

        return """<!doctype html><html><head><meta charset="utf-8"><style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: system-ui, sans-serif; background: #1e1e2e; color: #cdd6f4; font-size: 14px; }}
.top {{ position: sticky; top: 0; background: #181825; padding: 12px; border-bottom: 1px solid #313244; z-index: 10; }}
.status {{ font-size: 13px; color: #a6e3a1; margin-bottom: 8px; }}
#q {{ width: 100%; padding: 9px 12px; border-radius: 8px; border: 1px solid #313244; background: #313244; color: #cdd6f4; font-size: 14px; outline: none; }}
#q:focus {{ border-color: #89b4fa; }}
.legend {{ font-size: 11px; color: #7f849c; margin-top: 8px; }}
.list {{ padding: 6px 8px 16px; }}
details.country {{ margin: 3px 0; border-radius: 8px; overflow: hidden; background: #24273a; }}
summary {{ padding: 10px 12px; cursor: pointer; font-weight: 600; list-style: none; display: flex; justify-content: space-between; align-items: center; }}
summary::-webkit-details-marker {{ display: none; }}
summary:hover {{ background: #313244; }}
.cnt {{ font-size: 11px; color: #7f849c; background: #181825; padding: 1px 8px; border-radius: 10px; }}
.flag {{ font-size: 16px; }}
summary > span:nth-child(1) {{ margin-right: 4px; }}
.city {{ padding: 8px 12px 8px 28px; cursor: pointer; border-top: 1px solid #313244; font-size: 13px; display: flex; justify-content: space-between; align-items: center; }}
.city:hover {{ background: #45475a; }}
.city.active {{ color: #a6e3a1; font-weight: 600; }}
.prio {{ font-size: 11px; color: #f9e2af; margin-left: 8px; white-space: nowrap; }}
.hidden {{ display: none !important; }}
</style></head><body>
<div class="top">
  <div class="status">{cur_label}</div>
  <input id="q" placeholder="{search}" autofocus>
  <div class="legend">{legend}</div>
</div>
<div class="list" id="list">{rows}</div>
<script>
function pick(ip) {{ window.webkit.messageHandlers.connect.postMessage(ip); }}
const q = document.getElementById('q');
q.addEventListener('input', () => {{
  const s = q.value.trim().toLowerCase();
  document.querySelectorAll('details.country').forEach(d => {{
    let any = false;
    d.querySelectorAll('.city').forEach(c => {{
      const hit = !s || c.dataset.s.includes(s);
      c.classList.toggle('hidden', !hit);
      if (hit) any = true;
    }});
    const dhit = !s || d.dataset.s.includes(s) || any;
    d.classList.toggle('hidden', !dhit);
    if (s && any) d.open = true;
    if (!s) d.open = d.querySelector('.city.active') !== null;
  }});
}});
</script></body></html>""".format(
            cur_label=cur_label, search=t("picker_search"), legend=t("picker_legend"), rows="".join(rows))

    def after_change(self):
        self.refresh()
        self.build_menu()
        return False


if __name__ == "__main__":
    VpnTray()
    Gtk.main()
