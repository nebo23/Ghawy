from PIL import Image

def remove_black_bg(input_path, output_path):
    img = Image.open(input_path).convert('RGBA')
    pixels = img.load()
    width, height = img.size
    
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            alpha = max(r, g, b)
            
            if alpha == 0:
                pixels[x, y] = (0, 0, 0, 0)
            else:
                new_r = min(255, int(r * 255 / alpha))
                new_g = min(255, int(g * 255 / alpha))
                new_b = min(255, int(b * 255 / alpha))
                pixels[x, y] = (new_r, new_g, new_b, alpha)
                
    img.save(output_path, 'PNG')

remove_black_bg('frontend/imgs/ghawy-new-logo.png', 'frontend/imgs/ghawy-new-logo-transparent.png')
print('Transparent image created successfully!')
