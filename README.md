# NitroSense

Native Linux control center for Acer Nitro laptops built with GTK4 and Libadwaita.

Provides fan speed control, battery charging limits, keyboard backlight configuration, and real-time hardware telemetry.

## Requirements

Debian / Ubuntu:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
```

## Running

Run directly from source:

```bash
PYTHONPATH=src python3 -m nitrosense
```

## Building .deb

```bash
./packaging/build-deb.sh
sudo apt install ./packaging/nitrosense_*.deb
```
