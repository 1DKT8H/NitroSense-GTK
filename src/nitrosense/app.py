"""A single-screen desktop cockpit; all I/O runs outside GTK's main thread."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .runtime import configure, child_environment
configure()

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_foreign("cairo")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from . import APP_ID, VERSION
from .hardware import detect_profile, dmi_product_name
from .telemetry import Snapshot, inventory, power_profile, read_snapshot
from .widgets import FanDial, HistoryPlot, KeyboardPreview
from .panels import Panels
from .keyboard import available as keyboard_available
from . import i18n, settings


STYLE = """
window, .cockpit { background: #0c0f14; color: #eceef5; }
headerbar { background: #0e1117; box-shadow: none; border-bottom: 1px solid #222733; min-height: 46px; }
headerbar button { background: transparent; box-shadow: none; border: none; }
label { font-family: "Inter", "Noto Sans", sans-serif; }
.brand { font-weight: 850; font-size: 15px; letter-spacing: 2px; color: #ded4ff; }
.wordmark { color: #929aae; font-size: 11px; letter-spacing: 1px; }
.heading { font-size: 22px; font-weight: 750; }
.eyebrow { font-size: 10px; font-weight: 700; letter-spacing: 1.5px; color: #8c96ad; }
.muted { color: #949eb2; font-size: 11px; }
.accent { color: #b79bff; }
.cyan { color: #70b8c9; }
.legend { font-size: 12px; font-weight: 600; }
.help { border-radius: 50%; min-width: 14px; min-height: 14px; color: #b7a4d6; font-size: 10px; border: 1px solid #665a83; }
entry, spinbutton, spinbutton text { background: #1b202c; color: #eceef5; border: 1px solid #31394a; border-radius: 7px; }
checkbutton check { background: #1b202c; border: 1px solid #665a83; border-radius: 4px; }
checkbutton check:checked { background: #8664be; color: #fff; }
.swatch { padding: 0; min-width: 0; min-height: 0; border-radius: 4px; }
.battery-value { font-size: 38px; font-weight: 750; }
.success { color: #91d6b1; }
.metric { font-size: 20px; font-weight: 700; font-feature-settings: "tnum"; }
.smallmetric { font-size: 15px; font-weight: 700; font-feature-settings: "tnum"; }
.hardware { background: linear-gradient(165deg, #131720, #0e1219); border: 1px solid #29303d; border-radius: 16px; padding: 12px 20px; }
.chip-title { font-size: 16px; font-weight: 800; letter-spacing: 1px; }
.stats { border-top: 1px solid #252c38; padding-top: 12px; }
.centre { border-left: 1px solid #232936; border-right: 1px solid #232936; padding: 12px 20px; }
.card { background: #12161e; border: 1px solid #29303d; border-radius: 12px; padding: 12px; }
.profilebar { background: #12161e; border: 1px solid #29303d; border-radius: 12px; padding: 12px 16px; }
button { background: #1b202c; color: #c9cfdf; border: 1px solid #31394a; border-radius: 7px; padding: 7px 13px; box-shadow: none; }
button:hover { background: #282d3e; border-color: #635583; }
button:disabled { opacity: .42; }
button.selected, button.suggested-action { background: linear-gradient(110deg, #302746, #252236); color: #d6c6ff; border-color: #8a69c7; }
.profilebutton { min-height: 31px; padding: 4px 18px; }
.flat { border: none; background: transparent; }
dropdown button { padding: 5px 9px; }
scale trough, progressbar trough { background: #252d3b; min-height: 5px; border-radius: 5px; }
scale highlight, progressbar progress { background: #a988ed; min-height: 5px; border-radius: 5px; border: none; }
scale slider { background: #d6c4ff; min-width: 20px; min-height: 20px; }
switch:checked { background: #8664be; }
.footer { padding: 6px 0; color: #8691a7; font-size: 11px; }
.notice { color: #c2b3de; font-size: 11px; }
.quick-option { border-bottom: 1px solid #252c38; padding: 4px 0; }
expander title { padding: 10px 0; }
"""


def text(value: str, style: str = "", *, wrap: bool = False) -> Gtk.Label:
    widget = Gtk.Label(label=value, xalign=0, wrap=wrap)
    for css in style.split():
        widget.add_css_class(css)
    return widget


def column(spacing: int = 8, **kwargs) -> Gtk.Box:
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing, **kwargs)


def button(title: str, callback, css: str = "") -> Gtk.Button:
    item = Gtk.Button(label=title, valign=Gtk.Align.CENTER)
    if css:
        item.add_css_class(css)
    item.connect("clicked", callback)
    return item


class NitroApplication(Adw.Application):
    def __init__(self, *, preview: bool = False) -> None:
        super().__init__(application_id=APP_ID + (".Preview" if preview else ""),
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.preview = preview
        self.profile = detect_profile()
        self.metrics: dict[str, Gtk.Label] = {}
        self.fans: dict[str, FanDial] = {}
        self.profile_buttons: dict[str, Gtk.Button] = {}
        self.last = Snapshot()
        self.polling = False
        self.sensors_asleep = False
        self.io_workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="nitro-io")
        self.sensor_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nitro-sensors")
        self.busy = False
        self.alive = True
        self.timer = 0
        self.overlay_process = None
        self.peaks = {"cpu": None, "gpu": None}
        self.timeline = deque(maxlen=1600)
        self.fan_controls = []
        self.driver_details_group = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.VERTICAL)
        self.pending_fans = {}
        self.fan_timer = 0
        self.switches = {}
        self.pending_switches = {}
        self.syncing = False
        self.auto_power_profile = bool(settings.read().get("auto_power_profile"))
        self.last_power_source = None
        self.current_profile = None
        self.driver_offered = False
        self.panels = Panels(self)
        self.info = inventory()
        self.ec_available = bool(self.profile and (
            Path("/dev/ec").exists() or Path("/sys/kernel/debug/ec/ec0/io").exists()))

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        GLib.set_application_name("NitroSense")
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        Gtk.Window.set_default_icon_name("nitrosense")
        if self.preview:
            icons = Path(__file__).resolve().parents[2] / "share/icons"
            if icons.is_dir():
                Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).add_search_path(str(icons))
        provider = Gtk.CssProvider()
        provider.load_from_string(STYLE)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self) -> None:
        existing = getattr(self, "window", None)
        if existing:
            existing.present()
            return
        self.window = Adw.ApplicationWindow(application=self, title="NitroSense",
                                           default_width=1220, default_height=900)
        self.window.set_resizable(False)
        self.toasts = Adw.ToastOverlay()
        self.toasts.set_child(self.build())
        self.window.set_content(self.toasts)
        self.window.connect("close-request", self._close)
        self.window.connect("notify::is-active", lambda *_: self.poll() if self.window.is_active() and not self.preview else None)
        self.window.present()
        self.syncing = True
        i18n.apply(self.window)
        self.syncing = False
        if not self.preview:
            self.poll()
            self.timer = GLib.timeout_add(500, self.poll)
            self._background(self._load_profiles, self._profile_loaded)

    def do_command_line(self, command_line):
        self.activate()
        args = command_line.get_arguments()
        if "--diagnostics" in args:
            self.panels.diagnostics()
        if "--tuning" in args:
            self.panels.tuning()
        return 0

    def build(self) -> Gtk.Widget:
        root = column(0)
        root.add_css_class("cockpit")
        # Gtk.HeaderBar supplies the draggable Gtk.WindowHandle and all window actions.
        header = Gtk.HeaderBar()
        header.set_decoration_layout(":minimize,close")
        header.set_show_title_buttons(True)
        logo = Gtk.Image.new_from_icon_name("nitrosense")
        logo.set_pixel_size(28)
        header.pack_start(logo)
        header.pack_start(text("NitroSense", "brand"))
        header.pack_end(button("Przycisk Nitro", self.panels.key_window))
        preferences = Gtk.Button(icon_name="preferences-system-symbolic")
        preferences.set_tooltip_text("Ustawienia")
        preferences.connect("clicked", self.panels.preferences)
        header.pack_end(button("Sterowniki", self.panels.driver_window))
        header.pack_end(button("Nakładka", self.panels.overlay_window))
        header.pack_end(preferences)
        header.set_title_widget(text(dmi_product_name(), "wordmark"))
        root.append(header)
        self.scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER, vscrollbar_policy=Gtk.PolicyType.NEVER)
        self.content = column(10, margin_start=20, margin_end=20, margin_top=10, margin_bottom=10)
        self.scroll.set_child(self.content)
        root.append(self.scroll)
        self.live = text("", "muted")
        self.live.set_visible(False)

        hardware = Gtk.Box(spacing=18, hexpand=True)
        hardware.add_css_class("hardware")
        hardware.append(self._chip("cpu", "CPU", self.info["cpu_name"]))
        hardware.append(self._memory())
        hardware.append(self._chip("gpu", "GPU", self.info["gpu_name"]))
        self.content.append(hardware)
        self.content.append(self._profiles())

        tools = Gtk.Box(spacing=12, vexpand=True, homogeneous=True)
        tools.append(self._lighting())
        tools.append(self._quick())
        tools.append(self._history())
        self.content.append(tools)
        self.hardware_details = text("")
        self.status = text("", "footer", wrap=True)
        self.status.set_visible(False)
        self.content.append(self.status)
        return root

    def metric(self, key: str, caption: str, *, small: bool = False) -> Gtk.Widget:
        item = column(3, hexpand=True)
        item.append(text(caption, "eyebrow"))
        value = text("—", "smallmetric" if small else "metric")
        self.metrics[key] = value
        item.append(value)
        return item

    def _chip(self, key: str, title: str, name: str) -> Gtk.Widget:
        panel = column(6, hexpand=True)
        panel.set_size_request(265, -1)
        heading = Gtk.Box(spacing=10)
        heading.append(text(title, "chip-title"))
        heading.append(Gtk.Box(hexpand=True))
        heading.append(text("WENTYLATOR", "eyebrow"))
        panel.append(heading)
        device = text(name, "muted")
        device.set_ellipsize(Pango.EllipsizeMode.END)
        device.set_max_width_chars(30)
        device.set_tooltip_text(name)
        self.metrics[key + "_name"] = device
        panel.append(device)
        dial = FanDial()
        dial.set_content_height(200)
        dial.set_tooltip_text("Prędkość wentylatora; zewnętrzny łuk pokazuje RPM")
        self.fans[key] = dial
        panel.append(dial)
        stats = Gtk.Box(spacing=14, homogeneous=True)
        stats.add_css_class("stats")
        for suffix, caption in (("temp", "TEMPERATURA"), ("usage", "OBCIĄŻENIE"), ("power", "MOC")):
            stats.append(self.metric(key + "_" + suffix, caption))
        panel.append(stats)
        peak = text("Maks. —", "muted")
        self.metrics[key + "_peak"] = peak
        panel.append(peak)
        details = Gtk.Box(spacing=12)
        self.driver_details_group.add_widget(details)
        details.append(self.metric(key + "_clock", "ZEGAR", small=True))
        driver = self.metric("cpu_driver" if key == "cpu" else "gpu_driver", "STEROWNIK", small=True)
        details.append(driver)
        panel.append(details)
        if key == "cpu":
            version = text("Kernel " + self.info["kernel"], "muted")
            version.set_tooltip_text("intel_pstate jest częścią kernela. Nie ma niezależnego numeru wersji.")
            driver.append(version)
        control = Gtk.Box(spacing=7, margin_top=8)
        mode = Gtk.DropDown.new_from_strings(["Auto", "Maksimum", "Ręcznie"])
        mode.set_hexpand(False)
        speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 30, 100, 1)
        speed.set_hexpand(True)
        speed.set_draw_value(True)
        speed.set_value_pos(Gtk.PositionType.RIGHT)
        speed.set_value(55)
        speed.set_sensitive(False)
        speed.set_tooltip_text("Docelowa prędkość wentylatora (%)")
        def changed(*_):
            speed.set_sensitive(mode.get_selected() == 2)
            if not self.syncing and not self.preview and self.ec_available:
                self.queue_fan(key, mode.get_selected(), int(speed.get_value()))
        mode.connect("notify::selected", changed)
        speed.connect("value-changed", lambda *_: changed() if mode.get_selected() == 2 else None)
        for widget in (mode, speed):
            control.append(widget)
        control.set_sensitive(self.ec_available)
        if not self.ec_available:
            control.set_tooltip_text("Brak dostępu do interfejsu EC dla tego modelu")
        panel.append(control)
        self.fan_controls.append((control, mode, speed))
        return panel

    def queue_fan(self, target, mode, speed):
        self.pending_fans[target] = {"action": "fan", "target": target,
                                    "mode": ("auto", "max", "manual")[mode], "speed": speed}
        if self.fan_timer:
            GLib.source_remove(self.fan_timer)
        self.fan_timer = GLib.timeout_add(250, self.flush_fans)

    def flush_fans(self):
        if not self.alive or not self.ec_available:
            self.pending_fans.clear()
        if self.busy:
            return True
        if self.pending_fans:
            target = next(iter(self.pending_fans))
            self._privileged(self.pending_fans.pop(target))
            return True
        self.fan_timer = 0
        return False

    def _memory(self) -> Gtk.Widget:
        middle = column(6, valign=Gtk.Align.CENTER)
        middle.add_css_class("centre")
        middle.set_size_request(180, -1)
        middle.append(self.metric("ram_percent", "RAM"))
        self.ram_bar = Gtk.ProgressBar()
        middle.append(self.ram_bar)
        self.metrics["ram"] = text("—", "muted")
        middle.append(self.metrics["ram"])
        middle.append(Gtk.Separator(margin_top=4, margin_bottom=4))
        middle.append(self.metric("vram_percent", "VRAM"))
        self.vram_bar = Gtk.ProgressBar()
        middle.append(self.vram_bar)
        self.metrics["vram"] = text("—", "muted")
        middle.append(self.metrics["vram"])
        middle.append(self.metric("gpu_limit", "LIMIT MOCY GPU", small=True))
        middle.append(Gtk.Separator(margin_top=4, margin_bottom=4))
        middle.append(self.metric("battery", "BATERIA", small=True))
        self.metrics["power_source"] = text("—", "muted")
        middle.append(self.metrics["power_source"])
        self.metrics["battery_health"] = text("Kondycja: —", "muted")
        middle.append(self.metrics["battery_health"])
        middle.append(button("Szczegóły baterii", self.panels.battery))
        return middle

    def _profiles(self) -> Gtk.Widget:
        row = Gtk.Box(spacing=10)
        row.add_css_class("profilebar")
        caption = column(2, valign=Gtk.Align.CENTER, margin_end=12)
        caption.append(text("TRYB PRACY", "eyebrow"))
        self.profile_label = text("Sprawdzanie…", "muted")
        caption.append(self.profile_label)
        row.append(caption)
        for key, name in (("power-saver", "Cichy"), ("balanced", "Zrównoważony"), ("performance", "Wydajność")):
            item = button(name, lambda _b, value=key: self.set_profile(value), "profilebutton")
            item.set_hexpand(True)
            item.set_sensitive(False)
            row.append(item)
            self.profile_buttons[key] = item
        custom = button("Tuning  ↗", self.panels.tuning)
        row.append(custom)
        return row

    def card(self, title: str) -> Gtk.Box:
        card = column(6, hexpand=True)
        card.add_css_class("card")
        card.append(text(title, "eyebrow"))
        return card

    def _lighting(self) -> Gtk.Widget:
        from .keyboard import MODES
        card = self.card("PODŚWIETLENIE KLAWIATURY")
        self.keyboard_preview = KeyboardPreview()
        card.append(self.keyboard_preview)
        self.keyboard_mode = Gtk.DropDown.new_from_strings(list(MODES))
        self.keyboard_mode.set_hexpand(True)
        self.keyboard_speed = 4
        self.keyboard_direction = 1
        card.append(self.panels.row("Efekt", self.keyboard_mode, button("Opcje", self.panels.keyboard_effects)))
        row = Gtk.Box(spacing=8)
        self.colour = button("●", self.panels.colour_window)
        rgba = Gdk.RGBA()
        rgba.parse("#ae8eea")
        self.keyboard_colour = rgba
        self.colour.set_tooltip_text("Wybierz kolor")
        row.append(self.colour)
        self.zone = Gtk.DropDown.new_from_strings(["Wszystkie strefy", "Strefa 1", "Strefa 2", "Strefa 3", "Strefa 4"])
        self.zone.set_hexpand(True)
        row.append(self.zone)
        def changed(*_):
            mode = self.keyboard_mode.get_selected()
            self.zone.set_sensitive(mode == 0)
            self.colour.set_sensitive(mode not in (2, 3))
        self.keyboard_mode.connect("notify::selected", changed)
        apply = button("Ustaw", self._apply_colour)
        available = keyboard_available()
        apply.set_sensitive(available)
        self.keyboard_apply = apply
        row.append(apply)
        card.append(row)
        self.keyboard_status = text("" if available else "Sterownik klawiatury niedostępny", "muted")
        card.append(self.keyboard_status)
        self.keyboard_status.set_visible(not available)
        self.keyboard_install = button("Uruchom moduł RGB", lambda *_: self._confirm(
            "Zbudować i załadować do kernela dołączony moduł RGB DKMS? Wymaga nagłówków kernela. "
            "Przy Secure Boot moduł musi mieć zaufany podpis.", {"action": "install_rgb"}))
        self.keyboard_install.set_visible(not available)
        card.append(self.keyboard_install)
        self.brightness = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
        self.brightness.set_draw_value(True)
        self.brightness.set_value_pos(Gtk.PositionType.RIGHT)
        self.brightness.set_value(100)
        self.brightness.set_tooltip_text("Jasność podświetlenia (%)")
        card.append(self.brightness)
        return card

    def _quick(self) -> Gtk.Widget:
        card = self.card("CHŁODZENIE I ZASILANIE")
        options = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, homogeneous=True,
                          spacing=0, vexpand=True)
        entries = (
            ("CoolBoost", "coolboost"),
            ("Limit ładowania 80%", "charge_limit"),
            ("Wygaszanie klawiatury po 30 s", "keyboard_timeout"),
        )
        for title, action in entries:
            choose = Gtk.Switch(valign=Gtk.Align.CENTER)
            choose.set_sensitive(self.ec_available)
            choose.connect("state-set", self._switch_setting, action, title)
            self.switches[action] = choose
            row = self.panels.row(title, choose)
            row.add_css_class("quick-option")
            options.append(row)
        automatic = Gtk.Switch(active=self.auto_power_profile, valign=Gtk.Align.CENTER)
        automatic.connect("state-set", self._auto_power_profile_toggle)
        self.switches["auto_power_profile"] = automatic
        options.append(self.panels.row("Automatyczne zarządzanie energią", automatic))
        card.append(options)
        self.hardware_status = text(
            "" if self.ec_available else "Brak usługi sprzętowej", "muted", wrap=True)
        card.append(self.hardware_status)
        self.hardware_status.set_visible(not self.ec_available)
        return card

    def _history(self) -> Gtk.Widget:
        card = self.card("TEMPERATURY • OSTATNIE 2 MIN")
        self.history = HistoryPlot()
        self.history.set_content_height(125)
        self.history.set_vexpand(True)
        card.set_vexpand(True)
        card.append(self.history)
        row = Gtk.Box(spacing=12)
        row.append(text("● CPU", "accent legend"))
        gpu = text("● GPU", "cyan legend")
        row.append(gpu)
        row.append(Gtk.Box(hexpand=True))
        row.append(button("Diagnostyka", self._diagnostics))
        card.append(row)
        return card

    def _advanced(self) -> Gtk.Widget:
        box = column(12, margin_top=8)
        lab = self.card("TUNING")
        for title, detail, low, high, step, action, field, available in (
            ("CPU • undervolt", "Offset core/cache (mV)", -150, 0, 5, "undervolt", "mv", bool(shutil.which("undervolt"))),
            ("GPU • zegar rdzenia", "Offset (MHz) • NVIDIA Coolbits / X11", -300, 250, 15, "gpu_offset", "mhz",
             bool(shutil.which("nvidia-settings")) and os.environ.get("XDG_SESSION_TYPE") == "x11")):
            row = Gtk.Box(spacing=12)
            description = column(3, hexpand=True)
            description.append(text(title))
            description.append(text(detail, "muted"))
            row.append(description)
            spin = Gtk.SpinButton.new_with_range(low, high, step)
            spin.set_value(0)
            row.append(spin)
            apply = button("Zastosuj", lambda _b, s=spin, a=action, f=field, t=title:
                           self._confirm(t + " — zmiana może powodować niestabilność.", {"action": a, f: int(s.get_value())}))
            apply.set_sensitive(available)
            apply.set_tooltip_text("Wymaga dostępnego narzędzia i wsparcia sterownika / BIOS-u")
            row.append(apply)
            lab.append(row)
        box.append(lab)
        detail = self.card("SPRZĘT I DIAGNOSTYKA")
        self.hardware_details = text("", "muted", wrap=True)
        self.hardware_details.set_selectable(True)
        detail.append(self.hardware_details)
        row = Gtk.Box(spacing=8)
        row.append(text("Panel diagnostyczny na pulpicie", "muted"))
        row.append(Gtk.Box(hexpand=True))
        row.append(button("Otwórz", self._start_overlay))
        row.append(button("Zamknij", self._stop_overlay))
        detail.append(row)
        detail.append(text("Panel pulpitu nie mierzy FPS i nie zastępuje nakładki renderowanej wewnątrz gry.", "muted", wrap=True))
        box.append(detail)
        return box

    def _preview_colour(self, *_args) -> None:
        colour = self.keyboard_colour
        self.keyboard_preview.colour = (colour.red, colour.green, colour.blue)
        self.keyboard_preview.queue_draw()

    def _apply_colour(self, *_args) -> None:
        colour = self.keyboard_colour
        self._confirm("Zastosować kolor klawiatury?", {"action": "keyboard", "zone": self.zone.get_selected(),
            "mode": self.keyboard_mode.get_selected(), "speed": self.keyboard_speed,
            "direction": self.keyboard_direction,
            "colour": [round(colour.red * 255), round(colour.green * 255), round(colour.blue * 255)],
            "brightness": int(self.brightness.get_value())})

    def _switch_setting(self, switch, state, action, title):
        if self.syncing or self.busy:
            return False
        previous = switch.get_active()
        self.pending_switches[action] = (switch, previous, state)
        self.syncing = True
        switch.set_state(previous)
        switch.set_active(previous)
        self.syncing = False
        self._confirm(title + (" — włączyć?" if state else " — wyłączyć?"), {"action": action, "enabled": state})
        return True

    def _auto_power_profile_toggle(self, _switch, state):
        self.auto_power_profile = state
        values = settings.read()
        values["auto_power_profile"] = state
        settings.save(values)
        if state and self.last.battery_status:
            self._apply_auto_power_profile(self.last.battery_status)
        return False

    def _choose_setting(self, dropdown, _param, action, title) -> None:
        choice = dropdown.get_selected()
        if choice:
            dropdown.set_selected(0)
            self._confirm(title + (" — włączyć?" if choice == 1 else " — wyłączyć?"),
                          {"action": action, "enabled": choice == 1})

    @staticmethod
    def _load_profiles():
        if not shutil.which("powerprofilesctl"):
            return ("unavailable", [])
        result = subprocess.run(["powerprofilesctl", "list"], capture_output=True, text=True, timeout=3)
        available = [key for key in ("power-saver", "balanced", "performance") if key + ":" in result.stdout]
        return power_profile(), available

    def _profile_loaded(self, result) -> None:
        if isinstance(result, Exception):
            result = ("unavailable", [])
        current, available = result
        self.current_profile = current
        names = {"power-saver": "Cichy", "balanced": "Zrównoważony", "performance": "Wydajność"}
        self.profile_label.set_text(names.get(current, "Usługa niedostępna"))
        for key, item in self.profile_buttons.items():
            item.set_sensitive(key in available)
            if key == current:
                item.add_css_class("selected")
            else:
                item.remove_css_class("selected")

    def set_profile(self, value: str) -> None:
        if self.busy:
            return
        self.busy = True
        def work():
            result = subprocess.run(["powerprofilesctl", "set", value], capture_output=True, text=True, timeout=8)
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or "Zmiana profilu odrzucona")
            return self._load_profiles()
        def done(result):
            self.busy = False
            if isinstance(result, Exception):
                self.notify(str(result))
            else:
                self._profile_loaded(result)
                self.notify("Profil zasilania zmieniony")
        self._background(work, done)

    def _apply_auto_power_profile(self, battery_status: str) -> None:
        if self.preview or not self.auto_power_profile or self.busy:
            return
        target = "performance" if battery_status in ("Charging", "Full", "Not charging") else "balanced"
        if target == self.current_profile or target == self.last_power_source:
            return
        self.last_power_source = target
        self.set_profile(target)

    def poll(self) -> bool:
        if not self.alive:
            return False
        minimized = self.window.get_surface().get_state() & Gdk.ToplevelState.MINIMIZED
        if self.polling:
            return True
        # Moving the window temporarily changes its active state on some
        # Wayland compositors. Keep sampling during that interaction.
        if minimized and not self.panels.windows:
            if not self.sensors_asleep:
                self.sensors_asleep = True
                from .nvidia import reader
                self._background(reader.disconnect, lambda _result: None, sensors=True)
            return True
        self.sensors_asleep = False
        self.polling = True
        def done(result):
            self.polling = False
            if isinstance(result, Exception):
                self.notify(str(result))
            else:
                self.update(result)
        self._background(lambda: read_snapshot(self.profile), done, sensors=True)
        return True

    def update(self, snap: Snapshot) -> None:
        self.last = snap
        self.timeline.append((time.monotonic(), snap))
        self._apply_auto_power_profile(snap.battery_status)
        values = {}
        for key in ("cpu", "gpu"):
            temperature = getattr(snap, key + "_temp")
            if temperature is not None:
                self.peaks[key] = temperature if self.peaks[key] is None else max(temperature, self.peaks[key])
            values[key + "_peak"] = "Maks. " + self.unit(self.peaks[key], "°C")
            for suffix, unit, decimals in (("temp", "°C", 0), ("usage", "%", 0), ("power", "W", 1), ("clock", "MHz", 0)):
                values[key + "_" + suffix] = self.unit(getattr(snap, key + "_" + suffix), unit, decimals)
            self.fans[key].update(getattr(snap, key + "_fan"), getattr(snap, key + "_temp"))
        values["cpu_driver"] = self.info["cpu_driver"]
        values["gpu_driver"] = snap.gpu_driver or self.info["gpu_driver"]
        values["gpu_name"] = snap.gpu_name or self.info["gpu_name"]
        values["gpu_limit"] = self.unit(snap.gpu_limit, "W", 0)
        values["battery"] = self.unit(snap.battery, "%", 0)
        values["power_source"] = {"Charging": "Ładowanie", "Discharging": "Rozładowywanie",
            "Full": "Naładowana", "Not charging": "Podłączona"}.get(snap.battery_status, "—")
        values["battery_health"] = "Kondycja: " + self.unit(snap.battery_health, "%", 1)
        values["ram"] = "Brak odczytu" if snap.ram_total is None or snap.ram_used is None else f"{snap.ram_used:.1f} / {snap.ram_total:.1f} GiB"
        percent = 100 * snap.ram_used / snap.ram_total if snap.ram_total and snap.ram_used is not None else None
        values["ram_percent"] = self.unit(percent, "%", 0)
        self.ram_bar.set_fraction((percent or 0) / 100)
        values["vram"] = "Brak odczytu" if snap.vram_used is None or snap.vram_total is None else f"{snap.vram_used / 1024:.1f} / {snap.vram_total / 1024:.1f} GiB"
        vram_percent = 100 * snap.vram_used / snap.vram_total if snap.vram_total and snap.vram_used is not None else None
        values["vram_percent"] = self.unit(vram_percent, "%", 0)
        self.vram_bar.set_fraction((vram_percent or 0) / 100)
        for key, value in values.items():
            if key in self.metrics:
                self.metrics[key].set_text(value)
                self.metrics[key].set_tooltip_text(value)
        self.history.add(snap.cpu_temp, snap.gpu_temp)
        self.history.cpu_threshold = snap.cpu_critical
        self.history.gpu_threshold = snap.gpu_critical
        self.ec_available = snap.ec_available
        self.syncing = True
        for key, (control, mode, speed) in zip(("cpu", "gpu"), self.fan_controls):
            control.set_sensitive(self.ec_available)
            control.set_tooltip_text(None if self.ec_available else "Brak usługi sprzętowej")
            if not self.busy and key not in self.pending_fans:
                raw = getattr(snap, key + "_fan_mode")
                mask = 0x0c if key == "cpu" else 0x30
                modes = {0: 0, 0x04: 0, 0x08: 1, 0x0c: 2} if key == "cpu" else {0: 0, 0x10: 0, 0x20: 1, 0x30: 2}
                if raw is not None and raw & mask in modes:
                    mode.set_selected(modes[raw & mask])
                target = getattr(snap, key + "_fan_target")
                if mode.get_selected() == 2 and target is not None:
                    speed.set_value(target)
            speed.set_sensitive(self.ec_available and mode.get_selected() == 2)
        self.syncing = True
        for key, widget in self.switches.items():
            if key == "auto_power_profile":
                widget.set_sensitive(bool(shutil.which("powerprofilesctl")))
                widget.set_state(self.auto_power_profile)
                widget.set_active(self.auto_power_profile)
                continue
            state = getattr(snap, key)
            widget.set_sensitive(state is not None and (key == "cpu_turbo" or self.ec_available))
            if state is not None:
                widget.set_state(state)
                widget.set_active(state)
        self.syncing = False
        self.hardware_status.set_text("" if self.ec_available else "Brak usługi sprzętowej")
        self.hardware_status.set_visible(not self.ec_available)
        available = keyboard_available()
        self.keyboard_apply.set_sensitive(available)
        self.keyboard_status.set_text("" if available else "Sterownik klawiatury niedostępny")
        self.keyboard_status.set_visible(not available)
        self.keyboard_install.set_visible(not available)
        self.panels.update(snap)
        if not self.preview and not self.driver_offered and snap.gpu_error:
            self.driver_offered = True
            from .drivers import nvidia_present
            if nvidia_present() and self.info["gpu_driver"] == "Niedostępny":
                self.panels.driver_window()
        self.hardware_details.set_text(
            f"Model: {dmi_product_name()}\nCPU: {self.info['cpu_name']}\nGPU: {values['gpu_name']}\n"
            f"Sterownik NVIDIA: {values['gpu_driver']}\nVBIOS: {snap.gpu_vbios or 'Brak odczytu'}\n"
            f"Kernel: {self.info['kernel']} • Sesja: {self.info['session']}\n"
            f"Interfejs EC: {'dostępny' if self.ec_available else 'niedostępny'}\n"
            f"Diagnostyka GPU: {snap.gpu_error or 'Odczyt działa'}")
        self.syncing = True
        i18n.apply(self.window)
        self.syncing = False

    @staticmethod
    def unit(value, suffix: str, decimals: int = 0) -> str:
        return "—" if value is None else f"{value:.{decimals}f} {suffix}"

    def _background(self, work, done, *, sensors=False) -> None:
        def run():
            try:
                result = work()
            except Exception as error:
                result = error
            def finish():
                if self.alive:
                    done(result)
                return False
            GLib.idle_add(finish)
        if self.alive:
            (self.sensor_worker if sensors else self.io_workers).submit(run)

    def notify(self, message: str) -> None:
        self.toasts.add_toast(Adw.Toast.new(i18n.tr(message)[:180]))

    def _confirm(self, question: str, request: dict) -> None:
        if self.busy:
            self.notify("Poczekaj na zakończenie poprzedniej zmiany")
            return
        from .routine import ALLOWED
        if request.get("action") in ALLOWED:
            self._privileged(request)
            return
        dialog = Adw.MessageDialog.new(self.get_active_window() or self.window, "Zastosować zmianę?", question)
        dialog.set_resizable(False)
        dialog.set_modal(True)
        dialog.add_response("cancel", "Anuluj")
        dialog.add_response("apply", "Zastosuj")
        dialog.set_default_response("cancel")
        dialog.connect("response", lambda _d, response: self._privileged(request) if response == "apply" else None)
        dialog.present()
        i18n.apply(dialog)

    def _privileged(self, request: dict, callback=None) -> None:
        if self.preview or self.busy:
            return
        self.busy = True
        from .routine import ALLOWED
        routine = request["action"] in ALLOWED
        self.panels.operation_started(request["action"], routine)
        def work():
            helper = "/usr/bin/nitrosense-routine" if routine else "/usr/bin/nitrosense-helper"
            # Helper emits phases, not an invented percentage. Drain stderr together
            # with stdout so a package manager cannot deadlock on a full pipe.
            with subprocess.Popen(["pkexec", helper], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, env=child_environment()) as process:
                process.stdin.write(json.dumps(request))
                process.stdin.close()
                reply, errors = {}, []
                for line in process.stdout:
                    try:
                        message = json.loads(line)
                    except ValueError:
                        errors.append(line.strip())
                        errors = errors[-12:]
                        continue
                    if "progress" in message:
                        GLib.idle_add(self.panels.operation_progress, message["progress"])
                    else:
                        reply = message
                code = process.wait()
            if code or not reply.get("ok"):
                raise RuntimeError(reply.get("error", "\n".join(errors) or "Anulowano autoryzację"))
            return reply.get("data")
        def done(result):
            self.busy = False
            pending = self.pending_switches.pop(request["action"], None)
            if pending:
                switch, previous, desired = pending
                self.syncing = True
                switch.set_state(desired if not isinstance(result, Exception) else previous)
                switch.set_active(desired if not isinstance(result, Exception) else previous)
                self.syncing = False
            self.panels.operation_finished(result)
            if callback:
                callback(result)
            elif isinstance(result, Exception) or request["action"] != "fan":
                self.notify(str(result) if isinstance(result, Exception) else "Zmiana zastosowana")
            self.poll()
            if request["action"] == "undervolt":
                self.panels.uv_result = None
                if "diagnostics" in self.panels.windows:
                    self.panels.read_uv()
        self._background(work, done)

    def _diagnostics(self, *_args) -> None:
        self.panels.diagnostics()

    def reset_peaks(self, *_args):
        self.peaks = {"cpu": self.last.cpu_temp, "gpu": self.last.gpu_temp}
        self.update(self.last)

    def _start_overlay(self, *_args) -> None:
        self.panels.overlay_window()

    def _stop_overlay(self, *_args) -> None:
        if self.overlay_process and self.overlay_process.poll() is None:
            self.overlay_process.terminate()
            self.overlay_process = None

    def _close(self, *_args) -> bool:
        if self.busy:
            self.notify("Poczekaj na zakończenie poprzedniej zmiany")
            return True
        for window in list(self.panels.windows.values()):
            window.close()
        self.alive = False
        self.sensor_worker.shutdown(wait=False, cancel_futures=True)
        self.io_workers.shutdown(wait=False, cancel_futures=True)
        if self.fan_timer:
            GLib.source_remove(self.fan_timer)
            self.fan_timer = 0
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = 0
        self._stop_overlay()
        return False


def main() -> None:
    NitroApplication().run(sys.argv)


if __name__ == "__main__":
    main()
