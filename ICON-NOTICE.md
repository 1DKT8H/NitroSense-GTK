# NitroSense application icon

## Current icon (0.4.2)

`share/icons/hicolor/scalable/apps/nitrosense.svg` is a code-native vector redraw
of the requested Nitro silhouette, with a rounded graphite tile and clean purple
gradient. Real transparency outside the tile is inherent to SVG. The new icon name
is used by both the desktop entry and the application header to avoid the old
bitmap/icon-cache mismatch. Earlier generated raster versions are not used by
the current header. An attempted rounded bitmap was rejected because its
checkerboard was painted into RGB pixels, not stored as alpha transparency.

## Previous bitmap (0.4.1)

User-requested adaptation of Acer's Nitro emblem. Acer and Nitro are trademarks of
Acer; this is an unofficial Linux application, not an Acer product or endorsement.
The code license does not grant rights to Acer's marks. Forks should review branding
rights or substitute their own icon before public distribution.

Reference: https://i.pinimg.com/originals/04/12/d7/0412d7765733cf66cd96fad708859094.jpg

Created with the built-in image generation/editing tool (not CLI). The first edit
preserved the reference silhouette and introduced a satin lavender/violet metallic
finish. Its simulated transparency was rejected. The final production prompt was:

> Precise image edit. Preserve the exact existing Acer Nitro emblem geometry,
> silhouette, orientation, size, lavender metallic face and highlights. Change ONLY
> the checkerboard background: remove every checker square and all background
> texture, replace with a perfectly uniform flat dark graphite fill #10141d.
> This time output a completely opaque square PNG, not transparency. No checkerboard
> anywhere. No decorative shapes, no frame, no added light behind the emblem, no
> tile bevel, no extra text. The result is a clean desktop application icon:
> existing lavender Nitro mark centered over a flat solid graphite square,
> crisp and elegant.

Asset: `share/icons/hicolor/512x512/apps/io.github.nitrosense.NitroSense.png`.
Original generation output is preserved separately; no destructive source edits.
