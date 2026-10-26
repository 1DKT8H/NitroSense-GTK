"""Secondary windows; dashboard remains uncluttered."""
import os
from pathlib import Path
import shutil
import subprocess
import time
from gi.repository import Gtk, GLib, Gdk
from . import drivers, settings, overlay, hotkeys, i18n, VERSION
from .widgets import DiagnosticPlot
from .telemetry import read_text
from .runtime import child_environment


class Panels:
    def __init__(self, app):
        self.app = app
        self.windows = {}
        self.diag_metrics = {}
        self.diag_plot = None
        self.battery_label = None
        self.battery_metrics = {}
        self.operation = None
        self.uv_result = None
        self.uv_time = None

    def window(self, key, title, width=780, height=650):
        from .app import column, text
        if key in self.windows:
            self.windows[key].present()
            return None, None
        win = Gtk.ApplicationWindow(application=self.app, transient_for=self.app.window,
                                   title=title, default_width=width, default_height=height, resizable=False)
        header = Gtk.HeaderBar()
        header.set_decoration_layout(":minimize,close")
        header.set_title_widget(text(title, "chip-title"))
        win.set_titlebar(header)
        content = column(16, margin_top=20, margin_bottom=20, margin_start=22, margin_end=22)
        content.add_css_class("cockpit")
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(content)
        win.set_child(scroll)
        self.windows[key] = win
        win.connect("close-request", lambda *_: self._closed(key))
        win.connect("map", lambda *_: i18n.apply(win))
        return win, content

    def preferences(self, *_):
        from .app import text
        win, box = self.window("preferences", "Ustawienia", 510, 240)
        if not win:
            return
        win.set_resizable(False)
        lang = Gtk.DropDown.new_from_strings(["English", "Polski"])
        lang.set_selected(1 if i18n.language == "pl" else 0)
        def change_language(*_):
            values = settings.read()
            i18n.language = "pl" if lang.get_selected() == 1 else "en"
            values["language"] = i18n.language
            settings.save(values)
            self.app.syncing = True
            for window in self.app.get_windows():
                i18n.apply(window)
            self.app.syncing = False
        lang.connect("notify::selected", change_language)
        box.append(self.row("Język", lang))
        animation = Gtk.DropDown.new_from_strings(["Pełna płynność", "Oszczędzanie energii"])
        animation.set_selected(1 if settings.read().get("animation_power_save") else 0)
        def change_animation(*_):
            values = settings.read()
            values["animation_power_save"] = bool(animation.get_selected())
            settings.save(values)
            for fan in self.app.fans.values():
                fan.max_fps = 30 if animation.get_selected() else 60
        animation.connect("notify::selected", change_animation)
        box.append(self.row("Animacje wentylatorów", animation))
        box.append(self.row("Wersja aplikacji", text(VERSION, "smallmetric")))
        win.present()

    def colour_window(self, *_):
        import colorsys
        from .app import text, button
        win, box = self.window("colour", "Kolor klawiatury", 550, 390)
        if not win:
            return
        win.set_resizable(False)
        win.get_child().set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        swatches = Gtk.Grid(column_spacing=6, row_spacing=6, column_homogeneous=True)
        spins = [Gtk.SpinButton.new_with_range(0, 255, 1) for _ in range(3)]
        colour = self.app.keyboard_colour
        for spin, value in zip(spins, (colour.red, colour.green, colour.blue)):
            spin.set_value(round(value * 255))
        hexcode = Gtk.Entry(max_length=7, width_chars=9)
        preview = Gtk.DrawingArea(content_height=44)
        def draw(_w, cr, width, height):
            cr.set_source_rgb(*(s.get_value() / 255 for s in spins))
            cr.rectangle(0, 0, width, height)
            cr.fill()
        preview.set_draw_func(draw)
        def update(*_):
            hexcode.set_text("#" + "".join(f"{int(s.get_value()):02X}" for s in spins))
            preview.queue_draw()
        for s in spins:
            s.connect("value-changed", update)
        def select(rgb):
            for spin, value in zip(spins, rgb):
                spin.set_value(round(value * 255))
        for row in range(3):
            for index in range(12):
                rgb = colorsys.hsv_to_rgb(index / 12, (1, .65, .25)[row], 1)
                swatch = Gtk.Button()
                area = Gtk.DrawingArea(content_width=28, content_height=22)
                def paint(_a, cr, width, height, rgb=rgb):
                    cr.set_source_rgb(*rgb)
                    cr.paint()
                area.set_draw_func(paint)
                swatch.set_child(area)
                swatch.set_tooltip_text("#" + "".join(f"{round(v*255):02X}" for v in rgb))
                swatch.connect("clicked", lambda _b, rgb=rgb: select(rgb))
                swatch.add_css_class("swatch")
                swatches.attach(swatch, index, row, 1, 1)
        box.append(swatches)
        box.append(preview)
        box.append(self.row("RGB", *spins))
        def parse(*_):
            candidate = Gdk.RGBA()
            if candidate.parse(hexcode.get_text()):
                select((candidate.red, candidate.green, candidate.blue))
        hexcode.connect("activate", parse)
        box.append(self.row("HEX", hexcode, button("Ustaw", parse)))
        def apply(*_):
            self.app.keyboard_colour.red, self.app.keyboard_colour.green, self.app.keyboard_colour.blue = [s.get_value()/255 for s in spins]
            self.app._preview_colour()
            win.close()
        box.append(button("Zastosuj", apply))
        update()
        win.present()

    @staticmethod
    def help(message):
        item = Gtk.Label(label="?", valign=Gtk.Align.CENTER)
        item.add_css_class("help")
        item.set_tooltip_text(message)
        return item

    def keyboard_effects(self, *_):
        from .app import button
        win, box = self.window("keyboard-effects", "Efekty klawiatury", 520, 260)
        if not win:
            return
        speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 9, 1)
        speed.set_hexpand(True)
        speed.set_draw_value(True)
        speed.set_value(self.app.keyboard_speed)
        direction = Gtk.DropDown.new_from_strings(["Od prawej do lewej", "Od lewej do prawej"])
        direction.set_selected(self.app.keyboard_direction - 1)
        box.append(self.row("Tempo animacji", self.help("Efekty generuje firmware klawiatury; nie wymagają pętli animacji działającej w tle."), speed))
        box.append(self.row("Kierunek", direction))
        def apply(*_):
            self.app.keyboard_speed = int(speed.get_value())
            self.app.keyboard_direction = direction.get_selected() + 1
            self.app._apply_colour()
        box.append(button("Zastosuj efekt", apply))
        win.present()

    def operation_started(self, action, routine=False):
        from .app import column, text, button
        if routine:
            self.operation = None
            return
        title = {"install_overlay": "Instalacja nakładki", "install_rgb": "Instalacja modułu RGB",
                 "install_drivers": "Instalacja sterownika GPU"}.get(action, "Stosowanie ustawień")
        win = Gtk.ApplicationWindow(application=self.app, title=title,
                                   transient_for=self.app.get_active_window(), modal=True,
                                   default_width=520, default_height=220, resizable=False)
        box = column(14, margin_start=24, margin_end=24, margin_top=24, margin_bottom=24)
        box.append(text(title, "heading"))
        spinner = Gtk.Spinner(spinning=True)
        box.append(spinner)
        status = text("Stosowanie ustawień…" if routine else "Potwierdź uprawnienia w oknie systemowym…", wrap=True)
        box.append(status)
        elapsed = text("", "muted")
        box.append(elapsed)
        close = button("Zamknij", lambda *_: win.close())
        close.set_sensitive(False)
        box.append(close)
        win.set_child(box)
        started = time.monotonic()
        win.connect("close-request", lambda *_: self.app.busy)
        self.operation = (win, spinner, status, close, elapsed)
        def tick():
            if not self.app.busy:
                return False
            elapsed.set_text(f"{int(time.monotonic() - started)} s")
            return True
        GLib.timeout_add_seconds(1, tick)
        win.present()
        i18n.apply(win)

    def operation_progress(self, message):
        if self.operation:
            self.operation[2].set_text(i18n.tr(message))
        return False

    def operation_finished(self, result):
        if not self.operation:
            return
        win, spinner, status, close, elapsed = self.operation
        spinner.stop()
        spinner.set_visible(False)
        close.set_sensitive(True)
        status.set_selectable(True)
        status.set_text(str(result) if isinstance(result, Exception) else i18n.tr("Gotowe"))
        if not isinstance(result, Exception):
            status.add_css_class("success")
            GLib.timeout_add(900, lambda: (win.close(), False)[1])
        if "overlay" in self.windows:
            self.refresh_overlay_status()

    def _closed(self, key):
        self.windows.pop(key, None)
        if key == "diagnostics":
            self.diag_metrics.clear()
            self.diag_plot = None
        if key == "battery":
            self.battery_label = None
            self.battery_metrics.clear()
        return False

    def tuning(self, *_):
        from .app import column, text, button
        win, box = self.window("tuning", "Tuning", 790, 690)
        if not win:
            return
        cpu = self.app.card("CPU • ZASILANIE I CZĘSTOTLIWOŚĆ")
        turbo = Gtk.Switch(valign=Gtk.Align.CENTER)
        turbo_file = Path("/sys/devices/system/cpu/intel_pstate/no_turbo")
        turbo.set_active(read_text(str(turbo_file)) == "0")
        turbo.set_sensitive(turbo_file.exists())
        self.turbo = turbo
        turbo.connect("state-set", lambda _s, state: False if self.app.syncing else self.confirm(
            "Przełączyć Intel Turbo Boost?", {"action": "cpu_turbo", "enabled": state}))
        cpu.append(self.row("Intel Turbo Boost", self.help("Pozwala CPU przekraczać częstotliwość bazową, w granicach temperatur i mocy."), turbo))
        maximum = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 20, 100, 1)
        maximum.set_hexpand(True)
        maximum.set_draw_value(True)
        maximum.set_value(float(read_text("/sys/devices/system/cpu/intel_pstate/max_perf_pct") or "100"))
        cpu.append(self.row("Maksymalna wydajność (%)", self.help("Górny limit wydajności intel_pstate. To nie jest procent obciążenia CPU ani limit watów."), maximum, button("Zastosuj", lambda *_:
            self.app._confirm("Ustawić limit wydajności CPU?", {"action": "cpu_performance", "percent": int(maximum.get_value())}))))
        epp = Gtk.DropDown.new_from_strings(["performance", "balance_performance", "balance_power", "power"])
        epp.set_sensitive(Path("/sys/devices/system/cpu/cpufreq/policy0/energy_performance_preference").exists())
        cpu.append(self.row("Preferencja energii / wydajności", self.help("EPP określa kompromis między reakcją CPU a zużyciem energii."), epp, button("Zastosuj", lambda *_:
            self.app._confirm("Ustawić EPP?", {"action": "cpu_epp", "value": epp.get_selected_item().get_string()}))))
        pl1, pl2 = Gtk.SpinButton.new_with_range(10, 45, 1), Gtk.SpinButton.new_with_range(10, 90, 1)
        pl1.set_value(self.app.last.pl1 or 45)
        pl2.set_value(self.app.last.pl2 or 90)
        apply = button("Zastosuj PL1 / PL2", lambda *_: self.app._confirm(
            "Zmienić limity mocy pakietu CPU?", {"action": "cpu_power_limits", "pl1": int(pl1.get_value()), "pl2": int(pl2.get_value())}))
        apply.set_sensitive(bool(self.app.profile and self.app.last.pl1 is not None))
        cpu.append(self.row("PL1 (W) / PL2 (W)", self.help("PL1 ogranicza średnią moc w oknie czasu, PL2 dopuszcza krótkie skoki. Aby ograniczyć także skoki, ustaw oba limity na tę samą wartość. Firmware może nadpisywać limity."), pl1, pl2, apply))
        self.power_readback = text("", "smallmetric")
        cpu.append(self.power_readback)
        tau = Gtk.SpinButton.new_with_range(1, 128, 1)
        tau.set_value(self.app.last.pl1_window or 28)
        apply_tau = button("Zastosuj", lambda *_: self.app._confirm("Zmienić okno uśredniania PL1?",
                                        {"action": "cpu_power_window", "seconds": int(tau.get_value())}))
        apply_tau.set_sensitive(self.app.last.pl1_window is not None)
        cpu.append(self.row("Okno PL1 (s)", self.help("Krótsze okno szybciej ogranicza średnią moc. Sprzęt zaokrągla tę wartość do obsługiwanych kroków; aktualny odczyt jest pokazany powyżej."), tau, apply_tau))
        box.append(cpu)
        volt = self.app.card("CPU • NAPIĘCIE")
        uv = Gtk.SpinButton.new_with_range(-150, 0, 5)
        cache_uv = Gtk.SpinButton.new_with_range(-150, 0, 5)
        cache_uv.set_value(0)
        uv.set_value(0)
        apply_uv = button("Zastosuj", lambda *_: self.app._confirm(
            "Offset core/cache. Zbyt niskie napięcie może powodować zawieszenie systemu.",
            {"action": "undervolt", "core_mv": int(uv.get_value()), "cache_mv": int(cache_uv.get_value())}))
        uv_ok = bool(shutil.which("undervolt"))
        apply_uv.set_sensitive(uv_ok)
        volt.append(self.row("Core / cache (mV)", self.help("Wartość 0 przywraca offset fabryczny. BIOS może blokować undervolt. Wymaga narzędzia undervolt. Zbyt niskie napięcie może zawiesić system."), uv, cache_uv, apply_uv))
        box.append(volt)
        gpu = self.app.card("GPU • ZEGARY")
        supported = bool(shutil.which("nvidia-settings")) and os.environ.get("XDG_SESSION_TYPE") == "x11"
        for caption, action, low, high in (("Rdzeń (MHz)", "gpu_offset", -300, 250),
                                          ("VRAM (MHz transferu)", "gpu_memory_offset", -500, 1000)):
            value = Gtk.SpinButton.new_with_range(low, high, 25)
            value.set_value(0)
            apply = button("Zastosuj", lambda _b, v=value, a=action: self.app._confirm(
                "Zastosować offset GPU? Sprawdź stabilność pod obciążeniem.", {"action": a, "mhz": int(v.get_value())}))
            apply.set_sensitive(supported)
            gpu.append(self.row(caption, self.help("Offsety wymagają NVIDIA Coolbits / X11. Na Waylandzie ta ścieżka jest niedostępna. Edytor krzywej V/F nie jest udostępniony przez używany interfejs sterownika."), value, apply))
        box.append(gpu)
        self.update(self.app.last)
        win.present()

    def confirm(self, title, request):
        self.app._confirm(title, request)
        return True

    @staticmethod
    def row(title, *widgets):
        from .app import text
        row = Gtk.Box(spacing=12)
        description = text(title, wrap=True)
        caption = Gtk.Box(spacing=5, hexpand=True, valign=Gtk.Align.CENTER)
        caption.append(description)
        for widget in widgets:
            if widget.has_css_class("help"):
                caption.append(widget)
        widgets = [widget for widget in widgets if not widget.has_css_class("help")]
        row.append(caption)
        for widget in widgets:
            row.append(widget)
        return row

    def diagnostics(self, *_):
        from .app import column, text, button
        win, box = self.window("diagnostics", "Diagnostyka", 1040, 900)
        if not win:
            return
        mode = Gtk.DropDown.new_from_strings(["Temperatura", "Moc", "Obciążenie", "Zegary"])
        period = Gtk.DropDown.new_from_strings(["30 s", "2 min", "10 min"])
        period.set_selected(0)
        self.diag_plot = DiagnosticPlot(self.app.timeline)
        self.diag_plot.set_content_height(260)
        mode.connect("notify::selected", lambda *_: self.set_graph(mode.get_selected(), period.get_selected()))
        period.connect("notify::selected", lambda *_: self.set_graph(mode.get_selected(), period.get_selected()))
        box.append(self.row("Historia pomiarów", mode, period, self.help("Najedź na wykres, aby sprawdzić konkretną próbkę. Min / avg / max dotyczą wybranego zakresu. Linia przerywana oznacza próg termiczny, nie każdą przyczynę throttlingu.")))
        box.append(self.diag_plot)
        tables = Gtk.Box(spacing=20, homogeneous=True)
        self.diag_units = {}
        groups = (
            ("CPU", (("cpu_temp", "Temperatura", "°C"), ("cpu_power", "Moc pakietu", "W"),
                ("cpu_usage", "Obciążenie", "%"), ("cpu_clock", "Średni zegar", "MHz"),
                ("cpu_fan", "Wentylator", "RPM"), ("pl1", "PL1", "W"), ("pl2", "PL2", "W"),
                ("pl1_window", "Okno PL1", "s"), ("cpu_voltage", "Vcore", "V"),
                ("cpu_epp", "EPP", ""), ("cpu_governor", "Governor", ""),
                ("cpu_turbo", "Turbo Boost", ""), ("cpu_throttled", "Throttling termiczny", ""))),
            ("GPU", (("gpu_temp", "Temperatura", "°C"), ("gpu_power", "Moc", "W"),
                ("gpu_usage", "Obciążenie", "%"), ("gpu_clock", "Zegar rdzenia", "MHz"),
                ("gpu_fan", "Wentylator", "RPM"), ("gpu_limit", "Limit mocy", "W"),
                ("gpu_memory_clock", "Zegar VRAM", "MHz"), ("vram_used", "Zajęta VRAM", "MiB"),
                ("vram_total", "Cała VRAM", "MiB"), ("gpu_pstate", "P-state", ""),
                ("gpu_driver", "Sterownik", ""), ("gpu_throttled", "Throttling termiczny", ""),
                ("gpu_power_limited", "Limit mocy / prądu", ""))))
        for heading, fields in groups:
            table = self.app.card(heading)
            table.set_spacing(3)
            for key, caption, suffix in fields:
                value = text("—", "muted")
                value.set_selectable(True)
                self.diag_metrics[key] = value
                self.diag_units[key] = suffix
                table.append(self.row(caption, value))
            tables.append(table)
        box.append(tables)
        self.uv_label = text("UV: nie odczytano", "smallmetric", wrap=True)
        box.append(self.row("Offset UV", self.help("Odczyt core/cache pochodzi z OC mailbox, nie z pola wpisanej wartości. Offset nie jest napięciem Vcore. Zero oznacza brak odczytanego offsetu, a nie dowód, że BIOS pozwala na zmianę."),
                           self.uv_label, button("Odczytaj UV", self.read_uv)))
        self.details = text("", "muted", wrap=True)
        self.details.set_selectable(True)
        box.append(self.details)
        box.append(button("Wyzeruj maksymalne temperatury", self.app.reset_peaks))
        self.update(self.app.last)
        win.present()
        if not self.app.preview and not self.app.busy:
            self.read_uv()

    def read_uv(self, *_):
        if self.app.busy:
            self.app.notify("Poczekaj na zakończenie poprzedniej zmiany")
            return
        self.uv_label.set_text(i18n.tr("Odczytywanie…"))
        def done(result):
            self.uv_result = result
            self.uv_time = time.strftime("%H:%M:%S")
            if "diagnostics" in self.windows:
                self.update(self.app.last)
        self.app._privileged({"action": "read_uv"}, done)

    def set_graph(self, mode, period):
        self.diag_plot.mode = list(DiagnosticPlot.MODES)[mode]
        self.diag_plot.seconds = (30, 120, 600)[period]
        self.diag_plot.queue_draw()

    def battery(self, *_):
        from .app import text
        win, box = self.window("battery", "Bateria", 620, 510)
        if not win:
            return
        hero = self.app.card("BATERIA")
        self.battery_label = text("", "muted")
        hero.append(self.battery_label)
        self.battery_level = text("—", "battery-value")
        self.battery_bar = Gtk.ProgressBar()
        hero.append(self.battery_level)
        hero.append(self.battery_bar)
        box.append(hero)
        grid = Gtk.Grid(column_spacing=12, row_spacing=12, column_homogeneous=True)
        for index, (key, caption) in enumerate((("battery_health", "Kondycja"), ("battery_cycles", "Cykle"),
                  ("battery_full_wh", "Pełna pojemność"), ("battery_design_wh", "Pojemność projektowa"),
                  ("battery_power", "Moc baterii"), ("battery_voltage", "Napięcie"))):
            card = self.app.card(caption)
            value = text("—", "metric")
            card.append(value)
            self.battery_metrics[key] = value
            grid.attach(card, index % 2, index // 2, 1, 1)
        box.append(grid)
        self.update(self.app.last)
        win.present()

    def update(self, snap):
        unit = self.app.unit
        if "tuning" in self.windows:
            self.power_readback.set_text(f"PL1 {unit(snap.pl1, 'W')}   ·   PL2 {unit(snap.pl2, 'W')}   ·   τ {unit(snap.pl1_window, 's', 1)}   ·   CPU {unit(snap.cpu_power, 'W', 1)}")
            actual = read_text("/sys/devices/system/cpu/intel_pstate/no_turbo")
            if actual:
                self.app.syncing = True
                self.turbo.set_state(actual == "0")
                self.turbo.set_active(actual == "0")
                self.app.syncing = False
        if "diagnostics" in self.windows:
            self.diag_plot.queue_draw()
            for key, widget in self.diag_metrics.items():
                value = getattr(snap, key)
                widget.set_text("Brak danych" if value is None else
                    ("Tak" if value else "Nie") if isinstance(value, bool) else value if isinstance(value, str)
                    else (f"P{value}" if key == "gpu_pstate" else unit(value, self.diag_units[key],
                         3 if key == "cpu_voltage" else 1 if self.diag_units[key] in ("W", "s") else 0)))
            if isinstance(self.uv_result, Exception):
                self.uv_label.set_text(i18n.tr("Brak odczytu"))
                self.uv_label.set_tooltip_text(str(self.uv_result))
            elif isinstance(self.uv_result, dict):
                self.uv_label.set_text(f"Core {self.uv_result['core_mv']:+.2f} mV  /  Cache {self.uv_result['cache_mv']:+.2f} mV  ·  {self.uv_time}")
                self.uv_label.set_tooltip_text(None)
            self.details.set_text(
                f"{self.app.info['cpu_name']}  ·  Microcode {self.app.info['microcode']}  ·  {self.app.info['cpu_driver']}\n"
                f"{snap.gpu_name or '—'}  ·  NVML  ·  VBIOS {snap.gpu_vbios or '—'}  ·  Kernel {self.app.info['kernel']}\n"
                f"CPU MHz [0–{max(0, len(snap.cpu_clocks)-1)}]: " + ' / '.join(map(str, snap.cpu_clocks)) + "\n" +
                f"RAM {unit(snap.ram_used, 'GiB', 1)} / {unit(snap.ram_total, 'GiB', 1)}  ·  "
                f"{i18n.tr('Maks.')} CPU: {unit(self.app.peaks['cpu'], '°C')} • GPU: {unit(self.app.peaks['gpu'], '°C')}")
        if self.battery_label:
            self.battery_label.set_text(f"{snap.battery_model or '—'}   ·   {snap.battery_status or '—'}")
            self.battery_level.set_text(unit(snap.battery, "%"))
            self.battery_bar.set_fraction(min(1, max(0, (snap.battery or 0) / 100)))
            for key, value in self.battery_metrics.items():
                suffix = {"battery_health": "%", "battery_cycles": "", "battery_full_wh": "Wh",
                          "battery_design_wh": "Wh", "battery_power": "W", "battery_voltage": "V"}[key]
                value.set_text(unit(getattr(snap, key), suffix, 0 if key == "battery_cycles" else 1))
        for win in self.windows.values():
            i18n.apply(win)

    def driver_window(self, *_):
        from .app import text, button
        win, box = self.window("drivers", "Sterowniki GPU", 670, 430)
        if not win:
            return
        box.append(self.row("Zainstalowany: " + (self.app.last.gpu_driver or self.app.info["gpu_driver"]),
            self.help(drivers.driver_help())))
        result_label = text("Sprawdzanie rekomendacji dystrybucji…", "muted", wrap=True)
        box.append(result_label)
        apply = button("Zainstaluj / zaktualizuj rekomendowany sterownik", lambda *_:
            self.app._confirm("Zainstalować sterownik z repozytoriów dystrybucji? Po instalacji może być wymagany restart.",
                              {"action": "install_drivers"}))
        apply.set_sensitive(False)
        box.append(apply)
        def done(result):
            if isinstance(result, Exception):
                result_label.set_text(str(result))
            else:
                result_label.set_text(result["detail"])
                apply.set_sensitive(result["supported"])
        self.app._background(drivers.recommendation, done)
        win.present()

    def overlay_window(self, *_):
        from .app import text, button
        win, box = self.window("overlay", "Nakładka w grach", 940, 900)
        if not win:
            return
        config = settings.read()
        fields = config.get("overlay_fields", overlay.DEFAULT)
        checks = {}
        state = self.app.card("INTEGRACJA Z GRAMI")
        self.overlay_status = text("", "smallmetric")
        state.append(self.overlay_status)
        automatic = Gtk.Switch(valign=Gtk.Align.CENTER)
        automatic.set_active(overlay.global_enabled())
        automatic.set_sensitive(bool(shutil.which("mangohud")))
        def toggle_global(widget, enabled):
            try:
                overlay.set_global(enabled)
            except Exception as error:
                self.app.notify(str(error))
                return True
            self.refresh_overlay_status()
            return False
        automatic.connect("state-set", toggle_global)
        state.append(self.row("Automatycznie w aplikacjach Vulkan", self.help(
            "Działa dla nowych aplikacji Vulkan poza sandboxem, także Wine/Proton używających DXVK lub VKD3D. Nie wymaga ustawień wewnątrz gry. Obejmuje też inne programy Vulkan. Flatpaki skonfiguruj poniżej. Wyłączenie działa po restarcie gry."), automatic))
        box.append(state)
        integration_box = self.app.card("GRY I LAUNCHERY")
        integration_status = text("Wykrywanie launcherów…", "muted")
        integration_box.append(integration_status)
        box.append(integration_box)
        def integrations_ready(result):
            if "overlay" not in self.windows:
                return
            integration_status.set_text(str(result) if isinstance(result, Exception) else
                                        ("" if result else "Nie wykryto gier ani launcherów. Wybierz plik poniżej."))
            integration_status.set_visible(isinstance(result, Exception) or not result)
            if isinstance(result, Exception):
                return
            entries = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            viewport = Gtk.ScrolledWindow(min_content_height=130, max_content_height=130,
                                          propagate_natural_height=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
            viewport.set_size_request(-1, 130)
            viewport.set_child(entries)
            integration_box.append(viewport)
            for item in result:
                actions = [self.help(i18n.tr(item.detail) + ("\n" + item.runtime if item.runtime else ""))]
                if item.kind == "Flatpak":
                    configure = button("Skonfiguruj", lambda _b, a=item.id: self.configure_launcher(a))
                    configure.set_sensitive(item.supported)
                    actions.append(configure)
                start = button("Uruchom", lambda _b, item=item: self.start_integration(item))
                start.set_sensitive(item.supported and (item.kind == "Flatpak" or bool(shutil.which("mangohud"))))
                actions.append(start)
                entries.append(self.row(item.name + " · " + item.kind, *actions))
        self.app._background(overlay.integrations, integrations_ready)
        launch = Gtk.Entry(placeholder_text="Plik wykonywalny gry lub launchera", hexpand=True)
        def choose(*_):
            dialog = Gtk.FileChooserDialog(title=i18n.tr("Wybierz grę lub launcher"), transient_for=win,
                modal=True, action=Gtk.FileChooserAction.OPEN, resizable=False, default_width=720, default_height=520)
            dialog.add_button(i18n.tr("Anuluj"), Gtk.ResponseType.CANCEL)
            dialog.add_button(i18n.tr("Wybierz plik"), Gtk.ResponseType.ACCEPT)
            def chosen(dialog, response):
                if response == Gtk.ResponseType.ACCEPT and dialog.get_file():
                    launch.set_text(dialog.get_file().get_path() or "")
                dialog.destroy()
            dialog.connect("response", chosen)
            dialog.present()
        def run(*_):
            save()
            try:
                overlay.launch_game([launch.get_text()] if launch.get_text() else [])
                self.app.notify("Uruchamianie gry z nakładką")
            except Exception as error:
                self.app.notify(str(error))
        box.append(self.row("", launch, button("Wybierz plik", choose), button("Uruchom z nakładką", run)))
        grid = Gtk.Grid(column_spacing=18, row_spacing=8, column_homogeneous=True)
        for index, (key, label) in enumerate(overlay.FIELDS.items()):
            check = Gtk.CheckButton(label=label)
            check.set_active(key in fields)
            grid.attach(check, index % 3, index // 3, 1, 1)
            checks[key] = check
        box.append(grid)
        def save(*_):
            overlay.save_config([key for key, widget in checks.items() if widget.get_active()])
            self.app.notify("Konfiguracja nakładki zapisana")
        box.append(self.row("", self.help("Prawy Shift + F12 pokazuje/ukrywa nakładkę. Zmiany statystyk mogą wymagać restartu gry. Dostępność mocy, zegarów i wentylatora zależy od sterownika. Flagi throttlingu w MangoHud dotyczą GPU. Nakładki mogą być blokowane przez anti-cheat."), button("Zapisz", save),
            button("Pokaż / ukryj HUD", lambda *_: self.app.notify(
                "Przełączono nakładkę" if overlay.toggle() else "Uruchom grę z włączoną nakładką"))))
        if not shutil.which("mangohud"):
            box.append(button("Zainstaluj MangoHud", lambda *_: self.app._confirm(
                "Zainstalować MangoHud z repozytorium dystrybucji?", {"action": "install_overlay"})))
        self.refresh_overlay_status()
        win.present()

    def start_integration(self, item):
        if item.kind == "Flatpak":
            self.start_flatpak(item.id)
        else:
            self.app._background(lambda: overlay.launch_desktop(item.id), lambda result:
                self.app.notify(str(result) if isinstance(result, Exception) else "Uruchamianie gry z nakładką"))

    def refresh_overlay_status(self):
        if "overlay" in self.windows:
            self.overlay_status.set_text("MangoHud jest zainstalowany" if shutil.which("mangohud") else "Brak składnika nakładki")

    def configure_launcher(self, app_id):
        if self.app.busy:
            self.app.notify("Poczekaj na zakończenie poprzedniej zmiany")
            return
        self.app.busy = True
        self.operation_started("install_overlay")
        def work():
            overlay.configure_flatpak(app_id, lambda message: GLib.idle_add(self.operation_progress, message))
        def done(result):
            self.app.busy = False
            self.operation_finished(result)
            if not isinstance(result, Exception):
                self.app.notify("Skonfigurowano nakładkę. Zamknij launcher i uruchom go ponownie.")
        self.app._background(work, done)

    def start_flatpak(self, app_id):
        if app_id not in settings.read().get("flatpak_integrations", []):
            self.app.notify("Najpierw kliknij Skonfiguruj")
            return
        subprocess.Popen(["flatpak", "run", app_id], start_new_session=True, env=child_environment())

    def key_window(self, *_):
        from .app import text, button
        from .broker import query
        win, box = self.window("key", "Przycisk Nitro", 620, 300)
        if not win:
            return
        config = settings.read()
        choices = list(hotkeys.ACTIONS)
        choice = Gtk.DropDown.new_from_strings(list(hotkeys.ACTIONS.values()))
        choice.set_selected(choices.index(config.get("hotkey_action", "window")) if config.get("hotkey_action", "window") in choices else 0)
        from .keyfilter import APPLICATION_KEYS
        detected_code = [config.get("hotkey_code") if config.get("hotkey_code") in APPLICATION_KEYS else None]
        card = self.app.card("PRZYCISK NITRO • N")
        card.append(self.row("Akcja przycisku N", self.help("Naciśnij fizyczny przycisk Nitro. Gdy sterownik przekaże zdarzenie, kod zostanie dobrany automatycznie. To zdarzenie klawiatury, nie rejestr prędkości wentylatora."), choice))
        self.key_status = text("Naciśnij przycisk Nitro…", "smallmetric", wrap=True)
        card.append(self.key_status)
        box.append(card)
        self.key_sequence = query().get("key_sequence")
        def check_key():
            if "key" not in self.windows:
                return False
            detected = query()
            if detected.get("key_sequence") != self.key_sequence and detected.get("key_code") in APPLICATION_KEYS:
                self.key_sequence = detected["key_sequence"]
                detected_code[0] = detected["key_code"]
                self.key_status.set_text(i18n.tr("Wykryto przycisk Nitro"))
            elif not detected.get("hotkey_available"):
                self.key_status.set_text("Sterownik nie udostępnia urządzenia Acer WMI")
            return True
        GLib.timeout_add(500, check_key)
        def save(*_):
            values = settings.read()
            values.update(hotkey_action=choices[choice.get_selected()], hotkey_code=detected_code[0])
            settings.save(values)
            def enable():
                result = subprocess.run(["systemctl", "--user", "enable", "--now", "nitrosense-hotkeys.service"],
                                        capture_output=True, text=True, timeout=8)
                if result.returncode:
                    raise RuntimeError(result.stderr)
            self.app._background(enable, lambda result: self.app.notify(str(result) if isinstance(result, Exception)
                                                                          else "Przypisanie klawisza zapisane"))
        box.append(button("Zapisz i włącz obsługę klawisza", save))
        box.append(self.row("", self.help("Obsługa przycisku działa również po zamknięciu NitroSense. Jeśli kod nie zostanie wykryty, w ustawieniach skrótów pulpitu przypisz przycisk do polecenia nitrosense-hotkey. Nie zgadujemy mapowania firmware.")))
        win.present()
