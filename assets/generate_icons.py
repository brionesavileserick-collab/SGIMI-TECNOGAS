"""
Script para generar iconos de aplicación para SGIMI TECNOGAS.
Genera iconos para Windows (.ico), macOS (.icns) y Linux (.png).

Requiere: pip install pillow
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_app_icon():
    """Crea un icono simple para la aplicación."""
    size = 512
    image = Image.new('RGBA', (size, size), (33, 150, 243, 255))  # Blue background
    draw = ImageDraw.Draw(image)
    
    # Draw a simple inventory box icon
    margin = 100
    box_size = size - 2 * margin
    
    # Draw box outline
    draw.rectangle([margin, margin, margin + box_size, margin + box_size], 
                  outline=(255, 255, 255, 255), width=20)
    
    # Draw horizontal lines (shelves)
    for i in range(1, 4):
        y = margin + (box_size * i // 4)
        draw.line([margin, y, margin + box_size, y], 
                 fill=(255, 255, 255, 255), width=15)
    
    # Draw vertical lines (dividers)
    for i in range(1, 4):
        x = margin + (box_size * i // 4)
        draw.line([x, margin, x, margin + box_size], 
                 fill=(255, 255, 255, 255), width=15)
    
    return image

def save_icon_variations():
    """Guarda el icono en diferentes formatos para cada plataforma."""
    base_icon = create_app_icon()
    
    # Crear directorio assets si no existe
    os.makedirs('assets', exist_ok=True)
    
    # Windows .ico (múltiples tamaños)
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon_images = []
    for size in sizes:
        resized = base_icon.resize(size, Image.Resampling.LANCZOS)
        icon_images.append(resized)
    
    icon_images[0].save('assets/icon.ico', format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
    print("[OK] Icono Windows creado: assets/icon.ico")
    
    # Linux .png (512x512)
    base_icon.save('assets/icon.png', format='PNG')
    print("[OK] Icono Linux creado: assets/icon.png")
    
    # macOS .icns (requiere múltiples tamaños específicos)
    mac_sizes = [(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)]
    mac_images = []
    for size in mac_sizes:
        if size[0] <= 512:  # Solo hasta 512 para el icono base
            resized = base_icon.resize(size, Image.Resampling.LANCZOS)
            mac_images.append(resized)
    
    # Guardar como PNG temporal para convertir a .icns
    base_icon.save('assets/icon_temp.png', format='PNG')
    
    # Nota: Para crear .icns real se necesita iconutil en macOS
    # Aquí guardamos el PNG que se puede convertir
    print("[OK] Icono macOS base creado: assets/icon_temp.png")
    print("  (Para .icns final, ejecutar en macOS: iconutil -c icns assets/icon.iconset)")
    
    # Crear versión más pequeña para favicon
    favicon = base_icon.resize((32, 32), Image.Resampling.LANCZOS)
    favicon.save('assets/favicon.ico', format='ICO')
    print("[OK] Favicon creado: assets/favicon.ico")

if __name__ == '__main__':
    try:
        save_icon_variations()
        print("\n[OK] Todos los iconos creados exitosamente en la carpeta assets/")
    except ImportError:
        print("Error: Se requiere la librería Pillow")
        print("Instala con: pip install pillow")
    except Exception as e:
        print(f"Error creando iconos: {e}")
