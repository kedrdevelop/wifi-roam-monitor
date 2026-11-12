import os
from PIL import Image, ImageDraw

def create_wifi_sentinel_icon(output_path="assets/icon.ico"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    images = []
    
    # Design at 512x512 with anti-aliasing, then downsample to each target size
    canvas_size = 512
    
    for w, h in sizes:
        img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 1. Background rounded rectangle (Dark slate with subtle gradient / border)
        pad = 28
        rect_bbox = [pad, pad, canvas_size - pad, canvas_size - pad]
        corner_radius = 90
        
        # Dark tech background
        draw.rounded_rectangle(rect_bbox, radius=corner_radius, fill=(15, 23, 42, 255), outline=(56, 189, 248, 200), width=14)
        
        # Inner glow / accent line
        inner_pad = pad + 16
        draw.rounded_rectangle([inner_pad, inner_pad, canvas_size - inner_pad, canvas_size - inner_pad], 
                               radius=corner_radius - 12, outline=(14, 165, 233, 60), width=6)
        
        # 2. Wi-Fi Arcs (Concentric arcs)
        # Center origin near bottom of the icon
        cx = canvas_size // 2
        cy = 370
        
        # Outer Arc (Band 3)
        r3 = 230
        draw.arc([cx - r3, cy - r3, cx + r3, cy + r3], start=215, end=325, fill=(56, 189, 248, 255), width=28)
        
        # Middle Arc (Band 2)
        r2 = 160
        draw.arc([cx - r2, cy - r2, cx + r2, cy + r2], start=210, end=330, fill=(6, 182, 212, 255), width=28)
        
        # Inner Arc (Band 1)
        r1 = 95
        draw.arc([cx - r1, cy - r1, cx + r1, cy + r1], start=205, end=335, fill=(20, 184, 166, 255), width=28)
        
        # Center Pulse / Sentinel Node (Emerald Beacon)
        dot_r = 34
        # Glowing halo around beacon
        draw.ellipse([cx - dot_r - 12, cy - dot_r - 12, cx + dot_r + 12, cy + dot_r + 12], fill=(16, 185, 129, 70))
        draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=(16, 185, 129, 255), outline=(255, 255, 255, 230), width=8)

        # Downsample cleanly using Lanczos
        resized = img.resize((w, h), Image.Resampling.LANCZOS)
        images.append(resized)
    
    # Save as multi-resolution ICO file
    images[0].save(
        output_path,
        format="ICO",
        sizes=[(im.width, im.height) for im in images],
        append_images=images[1:]
    )
    print(f"Generated multi-size icon: {output_path} ({len(images)} resolutions)")

if __name__ == "__main__":
    create_wifi_sentinel_icon()

