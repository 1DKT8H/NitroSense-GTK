"""Frame-clock animation with cached impellers; bounded telemetry charts."""
from collections import deque
import math
import time
import cairo
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Gtk, Gdk, GLib, Graphene, Pango
from . import settings

PURPLE = (.68, .52, .92)
CYAN = (.44, .72, .79)
MAX_FAN_RPM = 6000


def animation_active(native):
    app = native.get_application() if native and hasattr(native, "get_application") else None
    return any(win.is_active() for win in app.get_windows()) if app else bool(native and native.is_active())


def centred(cr, value, x, y, size, colour, weight=cairo.FONT_WEIGHT_NORMAL):
    cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, weight)
    cr.set_font_size(size)
    ext = cr.text_extents(value)
    cr.set_source_rgb(*colour)
    cr.move_to(x - ext.width / 2 - ext.x_bearing, y)
    cr.show_text(value)


class FanDial(Gtk.Widget):
    __gtype_name__ = "NitroSenseFanDial"

    def __init__(self):
        super().__init__(hexpand=True)
        self.content_height = 240
        self.rpm = None
        self.temperature = None
        self.phase = 0
        self.last_frame = 0
        self.rotor = None
        self.face = None
        self.display_rpm = 0.0
        self.rpm_layout = None
        self.layout_key = None
        self.max_fps = 30 if settings.read().get("animation_power_save") else 60
        self.add_tick_callback(self.animate)

    def set_content_height(self, height):
        self.content_height = height
        self.queue_resize()

    def do_measure(self, orientation, for_size):
        size = 250 if orientation == Gtk.Orientation.HORIZONTAL else self.content_height
        return size, size, -1, -1

    def update(self, rpm, temperature):
        if temperature != self.temperature or rpm != self.rpm:
            self.face = None
        self.rpm, self.temperature = rpm, temperature
        self.queue_draw()

    def animate(self, widget, clock):
        now = clock.get_frame_time() / 1e6
        elapsed = now - self.last_frame
        if elapsed < 1 / (self.max_fps + 1):
            return True
        self.last_frame = now
        native = self.get_native()
        surface = native.get_surface() if native else None
        if not self.rpm or not self.get_mapped() or (surface and surface.get_state() & Gdk.ToplevelState.MINIMIZED):
            return True
        self.display_rpm += (self.rpm - self.display_rpm) * min(1, elapsed * 5)
        self.phase = (self.phase + min(elapsed, .05) * math.tau * self.display_rpm / 10000) % math.tau
        self.queue_draw()
        return True

    def do_snapshot(self, snapshot):
        # Only transforms are animated. Cairo rasterisation happens on sensor
        # changes, never at display refresh rate; GSK reuses the three textures.
        if self.rotor is None:
            self.rotor = self.texture(self.make_rotor())
        if self.face is None:
            self.face = self.make_face()
        width, height = self.get_width(), self.get_height()
        radius = min(width * .45, height * .46)
        rect = Graphene.Rect().init(-radius, -radius, radius * 2, radius * 2)
        snapshot.save()
        snapshot.translate(Graphene.Point().init(width / 2, height / 2 - 6))
        snapshot.append_texture(self.face[0], rect)
        snapshot.save()
        snapshot.rotate(math.degrees(self.phase))
        snapshot.append_texture(self.rotor, rect)
        snapshot.restore()
        snapshot.append_texture(self.face[1], rect)
        key = (self.rpm, radius)
        if self.layout_key != key:
            self.rpm_layout = self.create_pango_layout("—" if self.rpm is None else f"{self.rpm:,}".replace(",", " "))
            font = Pango.FontDescription.from_string("Sans Bold")
            font.set_absolute_size(25 * radius / 108 * Pango.SCALE)
            self.rpm_layout.set_font_description(font)
            self.layout_key = key
        label_width, label_height = self.rpm_layout.get_pixel_size()
        snapshot.translate(Graphene.Point().init(-label_width / 2, 4 * radius / 108 - label_height / 2))
        colour = Gdk.RGBA()
        colour.parse("#ede8fc")
        snapshot.append_layout(self.rpm_layout, colour)
        snapshot.restore()

    @staticmethod
    def texture(surface):
        surface.flush()
        return Gdk.MemoryTexture.new(surface.get_width(), surface.get_height(),
            Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED,
            GLib.Bytes.new(bytes(surface.get_data())), surface.get_stride())

    def canvas(self):
        scale = max(1, self.get_scale_factor())
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 216 * scale, 216 * scale)
        cr = cairo.Context(surface)
        cr.translate(108 * scale, 108 * scale)
        cr.scale(scale, scale)
        return surface, cr

    def make_face(self):
        surface, cr = self.canvas()
        glow = cairo.RadialGradient(0, 0, 54, 0, 0, 116)
        glow.add_color_stop_rgba(0, .45, .28, .73, .15)
        glow.add_color_stop_rgba(.7, .28, .18, .47, .08)
        glow.add_color_stop_rgba(1, .09, .10, .14, 0)
        cr.set_source(glow)
        cr.arc(0, 0, 116, 0, math.tau)
        cr.fill()
        cr.set_line_width(2)
        cr.set_source_rgb(.19, .22, .28)
        cr.arc(0, 0, 104, math.radians(135), math.radians(405))
        cr.stroke()
        if self.rpm is not None:
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_source_rgb(*PURPLE)
            progress = max(0, min(MAX_FAN_RPM, self.rpm)) / MAX_FAN_RPM
            start = math.radians(135)
            cr.arc(0, 0, 104, start, start + math.radians(270) * progress)
            cr.stroke()
        cr.set_line_width(1)
        for tick in range(60):
            angle = math.tau * tick / 60
            cr.set_source_rgba(.56, .49, .71, .20 if tick % 5 else .45)
            cr.move_to(math.cos(angle) * 96, math.sin(angle) * 96)
            cr.line_to(math.cos(angle) * (100 if tick % 5 == 0 else 98),
                       math.sin(angle) * (100 if tick % 5 == 0 else 98))
            cr.stroke()
        cr.set_source_rgb(.08, .095, .13)
        cr.arc(0, 0, 89, 0, math.tau)
        cr.fill()
        background = self.texture(surface)
        surface, cr = self.canvas()
        cr.set_source_rgb(.067, .079, .107)
        cr.arc(0, 0, 49, 0, math.tau)
        cr.fill_preserve()
        cr.set_source_rgb(.25, .23, .33)
        cr.set_line_width(1)
        cr.stroke()
        centred(cr, "RPM", 0, -14, 9, (.6, .64, .73))
        return background, self.texture(surface)

    def make_rotor(self):
        surface, cr = self.canvas()
        for blade in range(25):
            cr.save()
            cr.rotate(math.tau * blade / 25)
            cr.move_to(41, -4)
            cr.curve_to(56, -18, 72, -26, 83, -24)
            cr.curve_to(90, -21, 90, -14, 86, -9)
            cr.curve_to(73, -12, 55, -5, 44, 6)
            cr.close_path()
            gradient = cairo.LinearGradient(40, 0, 88, -16)
            gradient.add_color_stop_rgb(0, .22, .18, .32)
            gradient.add_color_stop_rgb(.50, .48, .35, .64)
            gradient.add_color_stop_rgb(.78, .32, .26, .43)
            gradient.add_color_stop_rgb(1, .12, .14, .20)
            cr.set_source(gradient)
            cr.fill_preserve()
            cr.set_source_rgba(.76, .64, .97, .25)
            cr.set_line_width(.7)
            cr.stroke()
            cr.restore()
        return surface


class HistoryPlot(Gtk.DrawingArea):
    def __init__(self):
        super().__init__(content_width=200, content_height=70, hexpand=True)
        self.samples = deque(maxlen=360)
        self.cpu_threshold = None
        self.gpu_threshold = None
        self.last_frame = 0
        self.max_fps = 30 if settings.read().get("animation_power_save") else 60
        self.set_draw_func(self.draw)
        self.add_tick_callback(self.animate)

    def add(self, cpu, gpu):
        self.samples.append((cpu, gpu, time.monotonic()))
        self.queue_draw()

    def animate(self, widget, clock):
        now = clock.get_frame_time() / 1e6
        elapsed = now - self.last_frame
        if elapsed < 1 / (self.max_fps + 1):
            return True
        self.last_frame = now
        native = self.get_native()
        surface = native.get_surface() if native else None
        active = animation_active(native)
        if not self.samples or not self.get_mapped() or not active or (surface and surface.get_state() & Gdk.ToplevelState.MINIMIZED):
            return True
        self.queue_draw()
        return True

    def draw(self, _widget, cr, width, height):
        cr.set_line_width(1)
        plot_width = width - 32
        duration = 60
        lower = min(30, max(0, math.floor(min((v for s in self.samples for v in s[:2] if v is not None), default=40) / 10) * 10 - 10))
        def ordinate(value):
            return height - 20 - (min(110, max(lower, value)) - lower) * (height - 45) / (110 - lower)
        for value in range(lower, 101, 20):
            y = ordinate(value)
            cr.set_source_rgb(.16, .19, .25)
            cr.move_to(0, y)
            cr.line_to(plot_width, y)
            cr.stroke()
            centred(cr, str(value), width - 11, y + 3, 8, (.52, .57, .66))
        for limit, label, colour in ((self.cpu_threshold, "CPU", PURPLE), (self.gpu_threshold, "GPU", CYAN)):
            if limit is None:
                continue
            y = ordinate(limit)
            cr.set_source_rgba(*colour, .8)
            cr.set_dash([4, 4])
            cr.move_to(0, y)
            cr.line_to(plot_width, y)
            cr.stroke()
            cr.set_dash([])
            # Dedicated header band: labels never intersect data or limit lines.
            centred(cr, f"{label} throttle {limit:.0f}°C", 75 if label == "CPU" else plot_width - 75, 12, 10, colour)
        if self.samples:
            now = min(time.monotonic(), self.samples[-1][2] + 1.0)
            cr.save()
            cr.rectangle(0, 0, plot_width, height - 15)
            cr.clip()
            for field, colour in ((0, PURPLE), (1, CYAN)):
                cr.set_source_rgb(*colour)
                cr.set_line_width(1.8)
                drawing = False
                last_drawn_pt = None
                for sample in self.samples:
                    value = sample[field]
                    if value is None:
                        drawing = False
                        continue
                    age = now - sample[2]
                    if age > duration + 5.0:
                        continue
                    x = plot_width * (1 - age / duration)
                    y = ordinate(value)
                    if drawing:
                        cr.line_to(x, y)
                    else:
                        cr.move_to(x, y)
                    drawing = True
                    last_drawn_pt = (x, y)
                if drawing and last_drawn_pt is not None and last_drawn_pt[0] < plot_width:
                    cr.line_to(plot_width, last_drawn_pt[1])
                cr.stroke()
            cr.restore()
        for fraction, label in ((0, f"-{duration} s"), (.5, f"-{duration // 2} s"), (1, "0 s")):
            centred(cr, label, 22 + fraction * (plot_width - 42), height - 3, 9, (.52, .57, .66))
        if not self.samples:
            centred(cr, "Oczekiwanie na czujniki", width / 2, height / 2, 11, (.53, .58, .67))


class DiagnosticPlot(Gtk.DrawingArea):
    """Ten-minute shared history with cursor inspection, auto scaling and statistics."""
    MODES = {"temperature": (("cpu_temp", "gpu_temp"), "°C", 110),
             "power": (("cpu_power", "gpu_power"), "W", None),
             "usage": (("cpu_usage", "gpu_usage"), "%", 100),
             "clock": (("cpu_clock", "gpu_clock"), "MHz", None)}

    def __init__(self, history, mode="temperature"):
        super().__init__(content_width=550, content_height=240, hexpand=True, vexpand=True)
        self.history, self.mode, self.seconds = history, mode, 30
        self.pointer = None
        self.last_frame = 0
        self.max_fps = 30 if settings.read().get("animation_power_save") else 60
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self.motion)
        motion.connect("leave", self.leave)
        self.add_controller(motion)
        self.set_draw_func(self.draw)
        self.add_tick_callback(self.animate)

    def motion(self, _controller, x, _y):
        self.pointer = x
        self.queue_draw()

    def leave(self, *_):
        self.pointer = None
        self.queue_draw()

    def animate(self, widget, clock):
        now = clock.get_frame_time() / 1e6
        elapsed = now - self.last_frame
        if elapsed < 1 / (self.max_fps + 1):
            return True
        self.last_frame = now
        native = self.get_native()
        surface = native.get_surface() if native else None
        active = animation_active(native)
        if not self.history or not self.get_mapped() or not active or (surface and surface.get_state() & Gdk.ToplevelState.MINIMIZED):
            return True
        self.queue_draw()
        return True

    def draw(self, _widget, cr, width, height):
        fields, unit, ceiling = self.MODES[self.mode]
        cr.set_source_rgb(.047, .059, .078)
        cr.paint()
        right, top, bottom = width - 18, 44, height - 28
        left = 48
        plot_w = right - left
        plot_h = bottom - top

        duration = self.seconds
        now = min(time.monotonic(), self.history[-1][0] + 1.0) if self.history else time.monotonic()
        data = [(ts, snap) for ts, snap in self.history if 0 <= now - ts <= duration]
        plot_data = [(ts, snap) for ts, snap in self.history if -1.0 <= now - ts <= duration + 5.0]

        numbers = [getattr(snap, key) for _, snap in data for key in fields if getattr(snap, key) is not None]
        maximum = ceiling or max(10, math.ceil(max(numbers, default=10) * 1.15 / 10) * 10)

        def point(ts, value):
            return (right - (now - ts) / duration * plot_w,
                    bottom - max(0, min(maximum, value)) / maximum * plot_h)

        cr.set_line_width(1)
        for index in range(6):
            value = maximum * index / 5
            y = point(now, value)[1]
            cr.set_source_rgb(.17, .2, .27)
            cr.move_to(left, y)
            cr.line_to(right, y)
            cr.stroke()
            centred(cr, f"{value:g}", 23, y + 4, 10, (.58, .63, .73))
            x = left + plot_w * index / 5
            cr.set_source_rgb(.17, .2, .27)
            cr.move_to(x, top)
            cr.line_to(x, bottom)
            cr.stroke()
            time_offset = duration * (5 - index) / 5
            if time_offset == 0:
                t_label = "0 s"
            elif duration >= 600:
                t_label = f"-{time_offset / 60:g} min"
            else:
                t_label = f"-{time_offset:g} s"
            centred(cr, t_label, x, height - 6, 10, (.58, .63, .73))

        for key, label, colour in zip(fields, ("CPU", "GPU"), (PURPLE, CYAN)):
            values = [getattr(s, key) for _, s in data if getattr(s, key) is not None]
            label_x = left + plot_w * (.25 if label == "CPU" else .75)
            summary = f"{label}   —" if not values else f"{label}   {values[-1]:.1f} {unit}    min {min(values):.1f} · avg {sum(values)/len(values):.1f} · max {max(values):.1f}"
            centred(cr, summary, label_x, 18, 10, colour)

        cr.save()
        cr.rectangle(left, top, plot_w, plot_h)
        cr.clip()

        for key, colour in zip(fields, (PURPLE, CYAN)):
            cr.set_source_rgb(*colour)
            cr.set_line_width(1.7)
            drawing = False
            last_pt = None
            for ts, snap in plot_data:
                value = getattr(snap, key)
                if value is None:
                    drawing = False
                    continue
                x, y = point(ts, value)
                if drawing:
                    cr.line_to(x, y)
                else:
                    cr.move_to(x, y)
                drawing = True
                last_pt = (x, y)
            if drawing and last_pt is not None and last_pt[0] < right:
                cr.line_to(right, last_pt[1])
            cr.stroke()

        if self.mode == "temperature" and data:
            for key, colour in (("cpu_critical", PURPLE), ("gpu_critical", CYAN)):
                limit = getattr(data[-1][1], key)
                if limit is not None:
                    y = point(now, limit)[1]
                    cr.set_source_rgba(*colour, .08)
                    cr.rectangle(left, top, plot_w, max(0, y - top))
                    cr.fill()
                    cr.set_source_rgba(*colour, .6)
                    cr.set_dash([4, 4])
                    cr.move_to(left, y)
                    cr.line_to(right, y)
                    cr.stroke()
                    cr.set_dash([])

        cr.restore()

        if self.pointer is not None and data:
            x = min(right, max(left, self.pointer))
            timestamp = now - (right - x) / plot_w * duration
            ts, snap = min(data, key=lambda item: abs(item[0] - timestamp))
            cr.set_source_rgba(.85, .85, .95, .65)
            cr.move_to(x, top)
            cr.line_to(x, bottom)
            cr.stroke()
            values = ["—" if getattr(snap, k) is None else f"{getattr(snap, k):.1f}" for k in fields]
            centred(cr, f"-{max(0.0, now - ts):.1f}s    CPU {values[0]} {unit}    GPU {values[1]} {unit}",
                    width / 2, 35, 10, (.93, .92, .99))

        if not data:
            centred(cr, "Oczekiwanie na czujniki", width / 2, height / 2, 11, (.53, .58, .67))


class KeyboardPreview(Gtk.DrawingArea):
    def __init__(self):
        super().__init__(content_width=190, content_height=65, hexpand=True)
        self.colour = PURPLE
        self.set_draw_func(self.draw)

    def draw(self, _widget, cr, width, height):
        keyw = min(19, (width - 12) / 15)
        cr.scale(1, min(1, height / 62))
        left = (width - keyw * 15) / 2
        for row in range(4):
            for key in range(15):
                if row == 3 and 4 <= key <= 8:
                    continue
                cr.rectangle(left + key * keyw, 5 + row * 14, keyw - 3, 10)
                cr.set_source_rgba(*self.colour, .15 + key / 75)
                cr.fill_preserve()
                cr.set_source_rgba(*self.colour, .6)
                cr.set_line_width(.8)
                cr.stroke()
        cr.rectangle(left + 4 * keyw, 47, keyw * 5 - 3, 10)
        cr.set_source_rgba(*self.colour, .23)
        cr.fill_preserve()
        cr.set_source_rgba(*self.colour, .7)
        cr.stroke()
