import io, random
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def quantize_image(img: Image.Image, max_colors: int):
    q = img.convert('RGB').quantize(colors=max_colors, method=Image.Quantize.MEDIANCUT)
    rgb = q.convert('RGB')
    arr = np.array(rgb)
    colors = np.unique(arr.reshape(-1, 3), axis=0)
    return rgb, [tuple(map(int, c)) for c in colors]


def regions_from_image(img: Image.Image, min_area: int):
    arr = np.array(img.convert('RGB'))
    colors = np.unique(arr.reshape(-1, 3), axis=0)
    regions = []
    rid = 1
    for color_id, c in enumerate(colors, start=1):
        mask = np.all(arr == c, axis=2).astype(np.uint8) * 255
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        for label in range(1, n):
            x, y, ww, hh, area = stats[label]
            if area < min_area:
                continue
            comp = (labels == label).astype(np.uint8) * 255
            contours, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            contour = max(contours, key=cv2.contourArea)
            dist = cv2.distanceTransform(comp, cv2.DIST_L2, 5)
            _, maxv, _, maxloc = cv2.minMaxLoc(dist)
            px, py = maxloc
            eps = 0.0025 * cv2.arcLength(contour, True)
            simp = cv2.approxPolyDP(contour, eps, True)
            pts = [(int(p[0][0]), int(p[0][1])) for p in simp]
            regions.append({
                'id': rid, 'color_id': color_id, 'color': tuple(map(int, c)),
                'area': int(area), 'bbox': (int(x), int(y), int(ww), int(hh)),
                'label_position': (int(px), int(py)), 'label_radius': float(maxv),
                'polygon': pts,
            })
            rid += 1
    return regions


def assign_values(colors, max_value):
    vals = list(range(1, min(len(colors), max_value) + 1))
    return {i + 1: vals[i] for i in range(len(vals))}


def exercise_for_value(v, mode, operand_max, rng):
    if mode == 'Nombre':
        return str(v)
    choices = []
    if mode in ('Addition', 'Mélange'):
        for a in range(0, min(v, operand_max) + 1):
            b = v - a
            if b <= operand_max:
                choices.append(f'{a} + {b}')
    if mode in ('Soustraction', 'Mélange'):
        for b in range(0, operand_max + 1):
            a = v + b
            if a <= operand_max:
                choices.append(f'{a} - {b}')
    if mode in ('Multiplication', 'Mélange'):
        for a in range(1, operand_max + 1):
            if v % a == 0:
                b = v // a
                if b <= operand_max:
                    choices.append(f'{a} × {b}')
    if mode in ('Division', 'Mélange') and v > 0:
        for b in range(1, operand_max + 1):
            a = v * b
            if a <= operand_max:
                choices.append(f'{a} ÷ {b}')
    return rng.choice(choices) if choices else str(v)


def render_coloring(size, regions, value_map, mode, operand_max, seed, show_fill=False):
    w, h = size
    img = Image.new('RGB', (w, h), 'white')
    draw = ImageDraw.Draw(img)
    rng = random.Random(seed)
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', max(13, min(w, h) // 45))
    except Exception:
        font = ImageFont.load_default()
    region_exercises = {}
    for r in regions:
        if len(r['polygon']) < 3:
            continue
        draw.polygon(r['polygon'], fill=r['color'] if show_fill else 'white', outline='black')
        value = value_map.get(r['color_id'])
        if value is None:
            continue
        ex = exercise_for_value(value, mode, operand_max, rng)
        region_exercises[r['id']] = ex
        x, y = r['label_position']
        bbox = draw.textbbox((0, 0), ex, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.rectangle((x - tw / 2 - 2, y - th / 2 - 1, x + tw / 2 + 2, y + th / 2 + 1), fill='white')
        draw.text((x - tw / 2, y - th / 2), ex, fill='black', font=font)
    return img, region_exercises


def svg_export(size, regions, exercises):
    w, h = size
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">', '<rect width="100%" height="100%" fill="white"/>']
    for r in regions:
        if len(r['polygon']) < 3:
            continue
        pts = ' '.join(f'{x},{y}' for x, y in r['polygon'])
        lines.append(f'<polygon points="{pts}" fill="white" stroke="black" stroke-width="1.5"/>')
        ex = exercises.get(r['id'], '')
        x, y = r['label_position']
        lines.append(f'<text x="{x}" y="{y}" text-anchor="middle" dominant-baseline="middle" font-family="Arial" font-size="18">{ex.replace("&", "&amp;")}</text>')
    lines.append('</svg>')
    return '\n'.join(lines).encode('utf-8')


def pdf_export(img: Image.Image, palette_rows, title='Coloriage magique'):
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=A4)
    pw, ph = A4
    c.setFont('Helvetica-Bold', 18)
    c.drawCentredString(pw / 2, ph - 40, title)
    temp_png = io.BytesIO(); img.save(temp_png, format='PNG'); temp_png.seek(0)
    iw, ih = img.size
    scale = min((pw - 80) / iw, (ph - 180) / ih)
    dw, dh = iw * scale, ih * scale
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(temp_png), (pw - dw) / 2, ph - 70 - dh, width=dw, height=dh, preserveAspectRatio=True)
    y, x = 70, 45
    c.setFont('Helvetica', 10)
    for rgb, value in palette_rows:
        rr, gg, bb = [v / 255 for v in rgb]
        c.setFillColorRGB(rr, gg, bb); c.rect(x, y, 12, 12, fill=1, stroke=1)
        c.setFillColorRGB(0, 0, 0); c.drawString(x + 18, y + 2, f'= {value}')
        x += 70
        if x > pw - 90:
            x = 45; y -= 18
    c.showPage(); c.save(); out.seek(0)
    return out.getvalue()
