# Keyboard protocol provenance

The keyboard bridge uses the Acer Gaming WMI protocol documented/implemented in
https://github.com/JafarAkhondali/acer-predator-turbo-and-rgb-keyboard-linux-module
at commit 6eafee25668cf2ffb8a79fd376a638e9ca4dc6db (src/facer.c).
That source is SPDX GPL-2.0-or-later; the repository also distributes GPLv3.
Original authors include Carlos Corbacho, E.M. Smith, Bernhard Rosenkraenzer
and the contributors of JafarAkhondali's module.

Our adapted driver is GPL-2.0-or-later. It only exposes RGB methods 2/5/6/20
on an exact Acer AN515-55 DMI match; it does not replace acer_wmi, change radio
state or register global WMI event handlers. Device files are root-only.
Sizes and copy_from_user results are checked before invoking firmware.
No firmware writes are performed during module initialization.
