#!/usr/bin/env python3
"""Generate PWA PNG icons for Polaris Hub using Python standard library."""
import math, os, struct, zlib

def create_png(width, height, draw_func):
    """Generates an RGBA PNG file of given dimensions."""
    # PNG signature
    png = bytearray(b"\x89PNG\r\n\x1a\n")
    
    # IHDR chunk
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
    png.extend(struct.pack(">I", len(ihdr_data)))
    png.extend(b"IHDR")
    png.extend(ihdr_data)
    png.extend(struct.pack(">I", ihdr_crc))
    
    # Image raw scanlines
    raw_bytes = bytearray()
    for y in range(height):
        raw_bytes.append(0) # filter type 0 (None)
        for x in range(width):
            r, g, b, a = draw_func(x, y, width, height)
            raw_bytes.extend([max(0, min(255, int(r))),
                              max(0, min(255, int(g))),
                              max(0, min(255, int(b))),
                              max(0, min(255, int(a)))])
            
    # IDAT chunk
    idat_data = zlib.compress(bytes(raw_bytes), level=9)
    idat_crc = zlib.crc32(b"IDAT" + idat_data)
    png.extend(struct.pack(">I", len(idat_data)))
    png.extend(b"IDAT")
    png.extend(idat_data)
    png.extend(struct.pack(">I", idat_crc))
    
    # IEND chunk
    iend_crc = zlib.crc32(b"IEND")
    png.extend(struct.pack(">I", 0))
    png.extend(b"IEND")
    png.extend(struct.pack(">I", iend_crc))
    
    return bytes(png)

def draw_polaris_icon(x, y, w, h, maskable=False):
    # Normalized coordinates (-1 to +1)
    cx, cy = w / 2.0, h / 2.0
    nx = (x - cx) / (w / 2.0)
    ny = (y - cy) / (h / 2.0)
    dist = math.sqrt(nx*nx + ny*ny)
    
    # Background color: #05070E with subtle radial glow
    # RGB(5, 7, 14) -> radial glow towards center RGB(18, 24, 45)
    bg_r = 18 - int(13 * dist)
    bg_g = 24 - int(17 * dist)
    bg_b = 45 - int(31 * dist)
    
    # 4-pointed North Star math
    # Star shape: dist from center = r / ( |cos(theta)|^0.2 + |sin(theta)|^0.2 ) or similar astroid curve
    angle = math.atan2(ny, nx)
    # Scale star radius
    star_scale = 0.55 if maskable else 0.65
    
    # Sharp 4-point star curve: r(theta) = scale / (|cos(2*theta)|^0.8 + 1.2 * |sin(2*theta)|^0.8)
    cos2 = abs(math.cos(2 * angle))
    sin2 = abs(math.sin(2 * angle))
    # 4-point star equation
    star_r = star_scale * (0.15 + 0.85 * (cos2**3)) / (0.15 + 0.85 * (sin2**0.3) + 0.001)
    
    # Alternative precise 4-pointed star distance:
    # Main vertical/horizontal spikes + diagonal inner curves
    abs_x = abs(nx)
    abs_y = abs(ny)
    
    # Distance to star shape
    star_dist = (abs_x**0.5 + abs_y**0.5)**2
    
    # Colors: Gold/Star #F5E6C8 (245, 230, 200), Aurora #7DD3FC (125, 211, 252)
    star_threshold = 0.5 * star_scale
    
    if star_dist < star_threshold:
        # Inside star
        t = star_dist / star_threshold
        # Inner core glow towards center
        r = 245 * (1 - t * 0.2) + 125 * (t * 0.2)
        g = 230 * (1 - t * 0.2) + 211 * (t * 0.2)
        b = 200 * (1 - t * 0.2) + 252 * (t * 0.2)
        return (r, g, b, 255)
    elif star_dist < star_threshold + 0.15:
        # Glow edge
        edge_t = (star_dist - star_threshold) / 0.15
        alpha = (1.0 - edge_t) * 0.8
        r = 245 * (1 - edge_t) + bg_r * edge_t
        g = 230 * (1 - edge_t) + bg_g * edge_t
        b = 200 * (1 - edge_t) + bg_b * edge_t
        return (r, g, b, 255)
    else:
        # Outer background
        return (bg_r, bg_g, bg_b, 255)

def main():
    print("[*] Generating PWA Icon PNGs...")
    
    # 192x192
    p192 = create_png(192, 192, lambda x, y, w, h: draw_polaris_icon(x, y, w, h, False))
    # 512x512
    p512 = create_png(512, 512, lambda x, y, w, h: draw_polaris_icon(x, y, w, h, False))
    # 512x512 Maskable (padded)
    pmask = create_png(512, 512, lambda x, y, w, h: draw_polaris_icon(x, y, w, h, True))
    # Apple Touch Icon 180x180
    papple = create_png(180, 180, lambda x, y, w, h: draw_polaris_icon(x, y, w, h, False))

    targets = [
        ("pwa-192x192.png", p192),
        ("pwa-512x512.png", p512),
        ("pwa-maskable-512x512.png", pmask),
        ("apple-touch-icon.png", papple),
        ("favicon.ico", p192)
    ]
    
    out_dirs = [".", "html"]
    for out_dir in out_dirs:
        os.makedirs(out_dir, exist_ok=True)
        for fname, data in targets:
            path = os.path.join(out_dir, fname)
            with open(path, "wb") as f:
                f.write(data)
            print(f"    Written {path} ({len(data)} bytes)")

if __name__ == "__main__":
    main()
