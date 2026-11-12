import os
from PIL import Image, ImageDraw

def create_wifi_sentinel_icon(output_path="assets/icon.ico"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Render at high resolution with anti-aliasing
    canvas_size = 512
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 1. Background rounded rectangle (Dark slate with cyan accent border)
    pad = 28
    rect_bbox = [pad, pad, canvas_size - pad, canvas_size - pad]
    corner_radius = 90
    
    # Dark tech background
    draw.rounded_rectangle(rect_bbox, radius=corner_radius, fill=(15, 23, 42, 255), outline=(56, 189, 248, 240), width=16)
    
    # Inner glow / accent line
    inner_pad = pad + 18
    draw.rounded_rectangle([inner_pad, inner_pad, canvas_size - inner_pad, canvas_size - inner_pad], 
                           radius=corner_radius - 12, outline=(14, 165, 233, 70), width=8)
    
    # 2. Wi-Fi Arcs (Concentric arcs)
    cx = canvas_size // 2
    cy = 370
    
    # Outer Arc (Band 3)
    r3 = 230
    draw.arc([cx - r3, cy - r3, cx + r3, cy + r3], start=215, end=325, fill=(56, 189, 248, 255), width=32)
    
    # Middle Arc (Band 2)
    r2 = 160
    draw.arc([cx - r2, cy - r2, cx + r2, cy + r2], start=210, end=330, fill=(6, 182, 212, 255), width=32)
    
    # Inner Arc (Band 1)
    r1 = 95
    draw.arc([cx - r1, cy - r1, cx + r1, cy + r1], start=205, end=335, fill=(20, 184, 166, 255), width=32)
    
    # Center Pulse / Sentinel Node (Emerald Beacon)
    dot_r = 36
    # Glowing halo around beacon
    draw.ellipse([cx - dot_r - 14, cy - dot_r - 14, cx + dot_r + 14, cy + dot_r + 14], fill=(16, 185, 129, 80))
    draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=(16, 185, 129, 255), outline=(255, 255, 255, 240), width=10)

    # Standard Windows icon sizes (16, 24, 32, 48, 64, 128, 256)
    target_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    
    # In Pillow, passing sizes=[...] creates a true multi-resolution Windows ICO
    img.save(
        output_path,
        format="ICO",
        sizes=target_sizes
    )
    print(f"Successfully generated multi-resolution icon: {output_path} with sizes: {target_sizes}")

if __name__ == "__main__":
    create_wifi_sentinel_icon()
