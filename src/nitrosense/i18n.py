"""Small EN/PL catalog. No locale dependency; preserves source text for live switching."""
from . import settings

language = settings.read().get("language", "en")
CATALOG = {
    "Limity CPU": "CPU limits", "Efekt": "Effect", "Opcje": "Options",
    "Efekty klawiatury": "Keyboard effects", "Tempo animacji": "Animation speed",
    "Kierunek": "Direction", "Od prawej do lewej": "Right to left", "Od lewej do prawej": "Left to right",
    "Zastosuj efekt": "Apply effect",
    "Efekty generuje firmware klawiatury; nie wymagają pętli animacji działającej w tle.": "Effects run in keyboard firmware; no background animation loop is needed.",
    "GRY I LAUNCHERY": "GAMES & LAUNCHERS",
    "Nie wykryto gier ani launcherów. Wybierz plik poniżej.": "No games or launchers found. Choose an executable below.",
    "Ten sandbox wymaga osobnej integracji.": "This sandbox needs a separate integration.",
    "Uruchomienie z MangoHud dla Vulkan. Zamknij działający launcher przed uruchomieniem; OpenGL może wymagać osobnej konfiguracji.": "Launch with MangoHud for Vulkan. Close an already running launcher first; OpenGL may need separate configuration.",
    "Konfiguracja dodatku MangoHud dla runtime tej aplikacji.": "Set up the MangoHud extension matching this application's runtime.",
    "Ten runtime nie ma jeszcze zweryfikowanego adaptera MangoHud.": "This runtime does not have a verified MangoHud adapter yet.",
    "Dobór pakietu przez ubuntu-drivers do GPU i wersji systemu; nie przez najwyższy numer wersji NVIDIA.": "ubuntu-drivers selects a package for this GPU and OS version, not by the highest NVIDIA version number.",
    "Pakiet musi pasować do GPU, kernela i repozytoriów tej dystrybucji. Automatyczna instalacja jest wyłączona bez zweryfikowanego adaptera; NitroSense nie uruchomi poleceń Ubuntu na tym systemie.": "The package must match the GPU, kernel and distribution repositories. Automatic installation is disabled without a verified adapter; NitroSense will not run Ubuntu commands on this system.",
    "Moc pakietu CPU względem PL1. PL1 jest limitem uśrednianym; krótkie skoki może dopuszczać PL2.": "CPU package power relative to PL1. PL1 is an averaged limit; PL2 may allow short bursts.",
    "PRZYCISK NITRO • N": "NITRO BUTTON · N", "Akcja przycisku N": "N button action",
    "Wykryto przycisk Nitro": "Nitro button detected", "Odczytaj UV": "Read UV",
    "Odczytywanie…": "Reading…", "UV: nie odczytano": "UV: not read yet",
    "Moc pakietu": "Package power", "Średni zegar": "Average clock", "Wentylator": "Fan",
    "Okno PL1": "PL1 window", "Throttling termiczny": "Thermal throttling",
    "Zegar rdzenia": "Core clock", "Limit mocy": "Power limit", "Zajęta VRAM": "Used VRAM",
    "Cała VRAM": "Total VRAM", "Limit mocy / prądu": "Power / current limit", "Sterownik": "Driver",
    "Odczyt core/cache pochodzi z OC mailbox, nie z pola wpisanej wartości. Offset nie jest napięciem Vcore. Zero oznacza brak odczytanego offsetu, a nie dowód, że BIOS pozwala na zmianę.": "Core/cache readback comes from the OC mailbox, not the input fields. An offset is not Vcore voltage. Zero means no offset was read, not proof that BIOS permits changes.",
    "Zalecany pakiet": "Compatible package",
    "Ubuntu dobiera pakiet z własnych repozytoriów do modelu GPU i wersji systemu. To wersja utrzymywana dla tej dystrybucji, niekoniecznie najnowszy numer wydany przez NVIDIA.": "Ubuntu selects a package from its repositories for your GPU model and OS version. It is maintained for this distribution, not necessarily NVIDIA's newest release number.",
    "CHŁODZENIE I ZASILANIE": "COOLING & POWER", "Automatyczne zarządzanie energią": "Automatic power management",
    "Okno PL1 (s)": "PL1 window (s)", "Zmienić okno uśredniania PL1?": "Change the PL1 averaging window?",
    "Krótsze okno szybciej ogranicza średnią moc. Sprzęt zaokrągla tę wartość do obsługiwanych kroków; aktualny odczyt jest pokazany powyżej.": "A shorter window limits average power sooner. Hardware rounds to supported steps; the actual value is shown above.",
    "Przycisk Nitro": "Nitro button", "Sterowniki": "Drivers", "Nakładka": "Overlay",
    "WENTYLATOR": "FAN", "TEMPERATURA": "TEMPERATURE", "OBCIĄŻENIE": "LOAD", "MOC": "POWER",
    "ZEGAR": "CLOCK", "STEROWNIK": "DRIVER", "Maks.": "Peak", "Maksimum": "Maximum", "Ręcznie": "Manual",
    "Zastosuj": "Apply", "PAMIĘĆ SYSTEMOWA": "SYSTEM MEMORY", "LIMIT MOCY GPU": "GPU POWER LIMIT",
    "BATERIA": "BATTERY", "Szczegóły baterii": "Battery details", "TRYB PRACY": "POWER MODE",
    "Cichy": "Quiet", "Zrównoważony": "Balanced", "Wydajność": "Performance", "Sprawdzanie…": "Checking…",
    "PODŚWIETLENIE KLAWIATURY": "KEYBOARD LIGHTING", "Wszystkie strefy": "All zones",
    "Strefa 1": "Zone 1", "Strefa 2": "Zone 2", "Strefa 3": "Zone 3", "Strefa 4": "Zone 4",
    "Ustaw": "Apply", "Wybierz kolor": "Choose colour", "Kolor klawiatury": "Keyboard colour",
    "Sterownik klawiatury niedostępny": "Keyboard driver unavailable", "Uruchom moduł RGB": "Set up RGB module",
    "Wygaszanie po 30 s": "Turn off after 30 s", "Limit ładowania 80%": "80% charge limit",
    "Wygaszanie klawiatury po 30 s": "Keyboard backlight off after 30 s",
    "Brak usługi sprzętowej": "Hardware service unavailable", "TEMPERATURY • OSTATNIE 2 MIN": "TEMPERATURES · LAST 2 MIN",
    "Diagnostyka": "Diagnostics", "Bateria": "Battery", "Kondycja": "Health", "Cykle": "Cycles",
    "Pełna pojemność": "Full capacity", "Pojemność projektowa": "Design capacity", "Moc baterii": "Battery power",
    "Napięcie": "Voltage", "Naładowana": "Fully charged", "Ładowanie": "Charging", "Rozładowywanie": "Discharging",
    "Podłączona": "Plugged in", "Brak odczytu": "No reading", "Brak danych": "Unavailable", "Tak": "Yes", "Nie": "No",
    "CPU • ZASILANIE I CZĘSTOTLIWOŚĆ": "CPU · POWER & FREQUENCY", "Maksymalna wydajność (%)": "Maximum performance (%)",
    "Preferencja energii / wydajności": "Energy preference", "Zastosuj PL1 / PL2": "Apply PL1 / PL2",
    "CPU • NAPIĘCIE": "CPU · VOLTAGE", "GPU • ZEGARY": "GPU · CLOCKS", "Rdzeń (MHz)": "Core (MHz)",
    "VRAM (MHz transferu)": "VRAM (transfer MHz)", "Historia pomiarów": "Sensor history", "Temperatura": "Temperature",
    "Moc": "Power", "Obciążenie": "Load", "Zegary": "Clocks", "CPU throttling termiczny": "CPU thermal throttling",
    "GPU throttling termiczny": "GPU thermal throttling", "GPU limit mocy / prądu": "GPU power / current limit",
    "Wyzeruj maksymalne temperatury": "Reset peak temperatures", "Sterowniki GPU": "GPU drivers",
    "Zainstalowany": "Installed", "Sprawdzanie rekomendacji dystrybucji…": "Checking compatible driver packages…",
    "Zainstaluj / zaktualizuj rekomendowany sterownik": "Install / update compatible driver",
    "Nakładka w grach": "In-game overlay", "INTEGRACJA Z GRAMI": "GAME INTEGRATION",
    "Automatycznie w aplikacjach Vulkan": "Automatically in Vulkan apps", "LAUNCHERY": "LAUNCHERS",
    "Wykrywanie launcherów…": "Detecting launchers…", "Skonfiguruj": "Set up", "Uruchom": "Launch",
    "Nie wykryto obsługiwanych launcherów Flatpak": "No supported Flatpak launchers found",
    "Plik wykonywalny gry lub launchera": "Game or launcher executable", "Wybierz plik": "Choose file",
    "Uruchom z nakładką": "Launch with overlay", "Wybierz grę lub launcher": "Choose a game or launcher",
    "Zapisz": "Save", "Pokaż / ukryj HUD": "Show / hide HUD", "Zainstaluj MangoHud": "Install overlay component",
    "MangoHud jest zainstalowany": "MangoHud installed", "Brak składnika nakładki": "Overlay component missing",
    "PRZYPISANIE": "ASSIGNMENT", "Akcja": "Action", "Sygnał przycisku": "Button signal",
    "Naciśnij przycisk Nitro…": "Press the Nitro button…", "Wykryto przycisk": "Button detected",
    "Zapisz i włącz obsługę klawisza": "Save and enable Nitro button", "Pokaż NitroSense": "Show NitroSense",
    "Pokaż / ukryj nakładkę w grze": "Show / hide in-game overlay", "Otwórz diagnostykę": "Open diagnostics",
    "Otwórz tuning": "Open tuning", "Wentylatory: Auto": "Fans: Auto", "Wentylatory: maksimum": "Fans: maximum",
    "Instalacja nakładki": "Overlay installation", "Instalacja modułu RGB": "RGB module installation",
    "Instalacja sterownika GPU": "GPU driver installation", "Stosowanie ustawień": "Applying settings",
    "Stosowanie ustawień…": "Applying settings…", "Potwierdź uprawnienia w oknie systemowym…": "Confirm permission in the system dialog…",
    "Zamknij": "Close", "Gotowe": "Done", "Anuluj": "Cancel", "Zastosować zmianę?": "Apply this change?",
    "Poczekaj na zakończenie poprzedniej zmiany": "Wait for the current operation to finish",
    "Zmiana zastosowana": "Settings applied", "Konfiguracja nakładki zapisana": "Overlay settings saved",
    "Przełączono nakładkę": "Overlay toggled", "Uruchom grę z włączoną nakładką": "Start a game with the overlay enabled",
    "Profil zasilania zmieniony": "Power mode changed", "Przypisanie klawisza zapisane": "Nitro button configured",
    "Skonfigurowano nakładkę. Zamknij launcher i uruchom go ponownie.": "Overlay configured. Close and restart the launcher.",
    "Najpierw kliknij Skonfiguruj": "Click Set up first", "Uruchamianie gry z nakładką": "Launching with overlay",
    "Pobieranie dodatku MangoHud dla Flatpaka…": "Downloading the MangoHud Flatpak extension…",
    "Konfigurowanie nakładki dla launchera…": "Configuring the launcher overlay…",
    "Pobieranie i instalowanie pakietów…": "Downloading and installing packages…", "Odświeżanie listy pakietów…": "Refreshing package lists…",
    "Budowanie modułu RGB dla kernela — może potrwać kilka minut…": "Building the RGB kernel module — this may take a few minutes…",
    "Ładowanie modułu RGB…": "Loading the RGB module…", "Ustawienia": "Preferences", "Język": "Language",
    "Animacje wentylatorów": "Fan animations", "Pełna płynność": "Smooth", "Oszczędzanie energii": "Power saving",
    "Wersja aplikacji": "Application version", "Moc GPU": "GPU power", "Moc CPU": "CPU power",
    "Temperatura GPU": "GPU temperature", "Temperatura CPU": "CPU temperature", "Obciążenie CPU": "CPU load",
    "Obciążenie GPU": "GPU load", "Zegar CPU": "CPU clock", "Zegar GPU": "GPU clock", "Zegar VRAM": "VRAM clock",
    "Limit mocy GPU": "GPU power limit", "Wentylator GPU (jeśli dostępny)": "GPU fan (if available)",
    "Obciążenie rdzeni CPU": "Per-core CPU load", "Model GPU": "GPU model", "Sterownik Vulkan": "Vulkan driver",
    "Pamięć procesu": "Process memory", "Odczyt dysku gry": "Game disk reads", "Zapis dysku gry": "Game disk writes",
    "Wykres frametime": "Frametime graph", "Ograniczenia GPU (temperatura / moc)": "GPU thermal / power limits",
    "Ograniczenia GPU na wykresie": "GPU limits on graph",
    "intel_pstate jest częścią kernela. Nie ma niezależnego numeru wersji.": "intel_pstate is part of the kernel and has no independent version number.",
    "Pozwala CPU przekraczać częstotliwość bazową, w granicach temperatur i mocy.": "Allows CPU clocks above base frequency, within thermal and power limits.",
    "Górny limit wydajności intel_pstate. To nie jest procent obciążenia CPU ani limit watów.": "Upper intel_pstate performance limit. This is not CPU usage or a wattage limit.",
    "EPP określa kompromis między reakcją CPU a zużyciem energii.": "EPP balances CPU responsiveness against energy use.",
    "PL1 ogranicza średnią moc w oknie czasu, PL2 dopuszcza krótkie skoki. Aby ograniczyć także skoki, ustaw oba limity na tę samą wartość. Firmware może nadpisywać limity.": "PL1 limits average power over a time window; PL2 permits short bursts. Set both limits to the same value to limit bursts too. Firmware may override these settings.",
    "Wartość 0 przywraca offset fabryczny. BIOS może blokować undervolt. Wymaga narzędzia undervolt. Zbyt niskie napięcie może zawiesić system.": "0 restores the stock offset. Requires the undervolt utility; BIOS may lock voltage control. Too little voltage can freeze the system.",
    "Offsety wymagają NVIDIA Coolbits / X11. Na Waylandzie ta ścieżka jest niedostępna. Edytor krzywej V/F nie jest udostępniony przez używany interfejs sterownika.": "Offsets require NVIDIA Coolbits / X11. This interface is unavailable on Wayland. The driver interface does not expose a voltage/frequency curve editor.",
    "Najedź na wykres, aby sprawdzić konkretną próbkę. Min / avg / max dotyczą wybranego zakresu. Linia przerywana oznacza próg termiczny, nie każdą przyczynę throttlingu.": "Hover to inspect a sample. Min / avg / max use the selected time range. Dashed lines mark thermal thresholds, not every throttling cause.",
    "Naciśnij fizyczny przycisk Nitro. Gdy sterownik przekaże zdarzenie, kod zostanie dobrany automatycznie. To zdarzenie klawiatury, nie rejestr prędkości wentylatora.": "Press the physical Nitro button. Its code is selected automatically when the driver reports an event. This is a keyboard event, not a fan-speed register.",
    "Obsługa przycisku działa również po zamknięciu NitroSense. Jeśli kod nie zostanie wykryty, w ustawieniach skrótów pulpitu przypisz przycisk do polecenia nitrosense-hotkey. Nie zgadujemy mapowania firmware.": "The button listener also works with NitroSense closed. If no code is detected, assign nitrosense-hotkey to the button in your desktop shortcut settings. Firmware mappings are not guessed.",
    "Działa dla nowych aplikacji Vulkan poza sandboxem, także Wine/Proton używających DXVK lub VKD3D. Nie wymaga ustawień wewnątrz gry. Obejmuje też inne programy Vulkan. Flatpaki skonfiguruj poniżej. Wyłączenie działa po restarcie gry.": "Enables the overlay for newly started native Vulkan apps, including Wine/Proton with DXVK or VKD3D. No in-game settings required. This includes non-game Vulkan apps. Set up Flatpaks below. Restart the game after disabling.",
    "Prawy Shift + F12 pokazuje/ukrywa nakładkę. Zmiany statystyk mogą wymagać restartu gry. Dostępność mocy, zegarów i wentylatora zależy od sterownika. Flagi throttlingu w MangoHud dotyczą GPU. Nakładki mogą być blokowane przez anti-cheat.": "Right Shift + F12 toggles the HUD. Changed metrics may require restarting the game. Power, clocks and fan readings depend on the driver. MangoHud throttling flags refer to the GPU. Anti-cheat may block overlays.",
}


def tr(value):
    if not value or language == "pl":
        return value
    if value in CATALOG:
        return CATALOG[value]
    # Dynamic readings have a small number of source prefixes, not free-form prose.
    for prefix in ("Maks.", "Kondycja", "Zainstalowany", "Wykryto przycisk", "Zalecany pakiet"):
        if value.startswith(prefix):
            return CATALOG[prefix] + value[len(prefix):]
    return value


def apply(root):
    from gi.repository import Gtk
    def change(widget, getter, setter, cache):
        current = getter()
        old = getattr(widget, cache, None)
        source = old[0] if old and old[1] == current else current
        translated = tr(source)
        if translated != current:
            setter(translated)
        setattr(widget, cache, (source, translated))
    def visit(widget):
        if isinstance(widget, Gtk.Label):
            change(widget, widget.get_label, widget.set_label, "_nitro_label")
        if isinstance(widget, Gtk.Window):
            change(widget, widget.get_title, widget.set_title, "_nitro_title")
        if widget.get_tooltip_text():
            change(widget, widget.get_tooltip_text, widget.set_tooltip_text, "_nitro_tip")
        if isinstance(widget, Gtk.Entry) and widget.get_placeholder_text():
            change(widget, widget.get_placeholder_text, widget.set_placeholder_text, "_nitro_placeholder")
        if isinstance(widget, Gtk.DropDown) and isinstance(widget.get_model(), Gtk.StringList):
            model = widget.get_model()
            source = getattr(widget, "_nitro_choices", None)
            if source is None:
                source = [model.get_string(i) for i in range(model.get_n_items())]
                widget._nitro_choices = source
            translated = [tr(s) for s in source]
            if translated != [model.get_string(i) for i in range(model.get_n_items())]:
                selected = widget.get_selected()
                widget.freeze_notify()
                model.splice(0, model.get_n_items(), translated)
                widget.set_selected(selected)
                widget.thaw_notify()
        child = widget.get_first_child()
        while child:
            visit(child)
            child = child.get_next_sibling()
    visit(root)
