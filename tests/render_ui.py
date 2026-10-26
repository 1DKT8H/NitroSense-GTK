"""Render our own GTK widget tree (not the desktop), with real or labelled demo data."""
import argparse
import json
from pathlib import Path
import sys
import os
import traceback

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Gdk, GLib, Graphene, Gsk, Gtk

from nitrosense.app import NitroApplication
from nitrosense.telemetry import Snapshot, read_snapshot

parser = argparse.ArgumentParser()
parser.add_argument("--demo", action="store_true")
parser.add_argument("--width", type=int, default=1220)
parser.add_argument("--height", type=int, default=900)
parser.add_argument("--expanded", action="store_true")
parser.add_argument("--bottom", action="store_true")
parser.add_argument("--panel", choices=["tuning", "diagnostics", "battery", "overlay", "key", "colour", "preferences", "keyboard-effects"])
parser.add_argument("--output", default="/tmp/nitrosense-ui.png")
args = parser.parse_args()
app = NitroApplication(preview=True)
app.set_application_id("io.github.nitrosense.QA.p" + str(os.getpid()))
errors = []
def capture_error(typ, value, tb):
    errors.append(str(value))
    traceback.print_exception(typ, value, tb)
sys.excepthook = capture_error


def setup():
    global preview_paintable
    app.window.set_default_size(args.width, args.height)
    if args.demo:
        app.update(Snapshot(cpu_usage=24, cpu_temp=62, cpu_fan=2850, cpu_power=18.6, cpu_clock=3600,
                            gpu_usage=73, gpu_temp=67, gpu_fan=3240, gpu_power=72.4, gpu_clock=1530,
                            gpu_name="NVIDIA GeForce RTX 2060", gpu_driver="580.82", gpu_limit=90,
                            ram_used=8.4, ram_total=15.5, vram_used=4200, vram_total=6144, battery=80))
        app.live.set_text("PODGLĄD • DANE PRZYKŁADOWE")
    else:
        app.update(read_snapshot(app.profile))
        app.poll()
        GLib.timeout_add(700, lambda: (app.poll(), False)[1])
    app._profile_loaded(app._load_profiles())
    if args.expanded:
        app.panels.tuning()
    if args.panel:
        {"tuning": app.panels.tuning, "diagnostics": app.panels.diagnostics,
         "battery": app.panels.battery, "overlay": app.panels.overlay_window,
         "key": app.panels.key_window, "colour": app.panels.colour_window,
         "preferences": app.panels.preferences, "keyboard-effects": app.panels.keyboard_effects}[args.panel]()
    app.qa_phases = {k: f.phase for k, f in app.fans.items()}
    target = app.panels.windows.get(args.panel) if args.panel else app.window
    root = target.get_child() if args.panel else app.window.get_content()
    preview_paintable = Gtk.WidgetPaintable.new(root)
    root.queue_draw()
    if args.bottom and args.panel:
        def bottom():
            adjustment = target.get_child().get_vadjustment()
            adjustment.set_value(adjustment.get_upper() - adjustment.get_page_size())
            return False
        GLib.timeout_add(1200, bottom)
    GLib.timeout_add(2000, render)
    return False


def render():
    try:
        target_window = app.panels.windows.get(args.panel) if args.panel else app.window
        root = target_window.get_child() if args.panel else app.window.get_content()
        width, height = root.get_width(), root.get_height()
        print("LAYOUT", width, height, "mapped", root.get_mapped(), "visible", root.get_visible(),
              "window", target_window.get_mapped(), "active", target_window.is_active(), flush=True)
        assert app.scroll.get_height() > 500, "Main content collapsed"
        assert all(f.get_height() >= 200 and f.get_width() >= 240 for f in app.fans.values()), "Fans clipped"
        assert all(not window.get_resizable() for window in app.get_windows()), "Resizable application window"
        if args.panel and target_window.is_active():
            assert all(f.phase != app.qa_phases[k] for k, f in app.fans.items() if f.rpm), "Fans froze with a secondary window active"
        if not args.panel:
            assert app.keyboard_preview.get_height() >= 65, "Keyboard preview compressed"
            assert app.switches["keyboard_timeout"].get_parent().get_parent() != app.keyboard_preview.get_parent(), "Timeout still crowds keyboard card"
            assert "cpu_turbo" not in app.switches, "Turbo shortcut still occupies timeout position"
            assert app.content.get_width() <= width, "Dashboard wider than window"
            assert app.content.get_height() <= app.scroll.get_height(), "Dashboard clipped vertically"
            if args.demo:
                assert abs(app.vram_bar.get_fraction() - (4200 / 6144)) < 0.01, "VRAM progress bar fraction mismatch"
                assert app.metrics["vram_percent"].get_text() == "68 %", "VRAM percentage text mismatch"
                assert "4.1 / 6.0 GiB" in app.metrics["vram"].get_text(), "VRAM usage label mismatch"
        paintable = preview_paintable
        snapshot = Gtk.Snapshot.new()
        paintable.snapshot(snapshot, width, height)
        node = snapshot.to_node()
        renderer = target_window.get_renderer()
        rect = Graphene.Rect().init(0, 0, width, height)
        texture = renderer.render_texture(node, rect)
        assert texture.save_to_png(args.output)
        report = {"width": width, "height": height,
                  "scroll_height": app.scroll.get_height(),
                  "fan_sizes": {k: [v.get_width(), v.get_height()] for k, v in app.fans.items()},
                  "errors": errors, "image": args.output}
        print(json.dumps(report))
    except Exception as error:
        traceback.print_exc()
        errors.append(str(error))
        print("RENDER FAILED:", repr(error))
    app.window.close()
    app.quit()
    return False


app.connect("activate", lambda *_: GLib.timeout_add(100, setup))
app.run(["nitrosense-qa"])
if errors:
    print(errors, file=sys.stderr)
    raise SystemExit(1)
