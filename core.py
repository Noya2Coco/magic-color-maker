import html
import io
import random
from typing import Dict, List, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def quantize_image(img: Image.Image, max_colors: int):
    max_colors = max(2, int(max_colors))
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
                'id': rid,
                'color_id': color_id,
                'color': tuple(map(int, c)),
                'area': int(area),
                'bbox': (int(x), int(y), int(ww), int(hh)),
                'label_position': (int(px), int(py)),
                'label_radius': float(maxv),
                'polygon': pts,
            })
            rid += 1
    return regions


def assign_values(colors, max_value):
    values = list(range(1, min(len(colors), int(max_value)) + 1))
    return {idx + 1: values[idx] for idx in range(len(values))}


def exercise_for_value(v, mode, operand_max, rng):
    operand_max = int(operand_max)
    if mode == 'Nombre':
        return str(v)
    choices = []
    if mode in ('Addition', 'Mélange'):
        for a in range(0, min(v, operand_max) + 1):
            b = v - a
            if 0 <= b <= operand_max:
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


def _font_for(size):
    w, h = size
    target = max(14, min(w, h) // 42)
    for name in ('DejaVuSans.ttf', '/system/fonts/Roboto-Regular.ttf'):
        try:
            return ImageFont.truetype(name, target)
        except Exception:
            pass
    return ImageFont.load_default()


def render_coloring(size, regions, value_map, mode, operand_max, seed, show_fill=False):
    w, h = size
    img = Image.new('RGB', (w, h), 'white')
    draw = ImageDraw.Draw(img)
    rng = random.Random(int(seed))
    font = _font_for(size)
    region_exercises = {}
    for r in regions:
        poly = r['polygon']
        if len(poly) < 3:
            continue
        draw.polygon(poly, fill=r['color'] if show_fill else 'white', outline='black')
        value = value_map.get(r['color_id'])
        if value is None:
            continue
        ex = exercise_for_value(value, mode, operand_max, rng)
        region_exercises[r['id']] = ex
        x, y = r['label_position']
        bbox = draw.textbbox((0, 0), ex, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.rectangle((x - tw / 2 - 3, y - th / 2 - 2, x + tw / 2 + 3, y + th / 2 + 2), fill='white')
        draw.text((x - tw / 2, y - th / 2), ex, fill='black', font=font)
    return img, region_exercises


def svg_export(size, regions, exercises):
    w, h = size
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<rect width="100%" height="100%" fill="white"/>'
    ]
    for r in regions:
        if len(r['polygon']) < 3:
            continue
        pts = ' '.join(f'{x},{y}' for x, y in r['polygon'])
        lines.append(f'<polygon points="{pts}" fill="white" stroke="black" stroke-width="1.5"/>')
        ex = html.escape(exercises.get(r['id'], ''))
        x, y = r['label_position']
        lines.append(
            f'<text x="{x}" y="{y}" text-anchor="middle" dominant-baseline="middle" '
            f'font-family="Arial,sans-serif" font-size="18">{ex}</text>'
        )
    lines.append('</svg>')
    return '\n'.join(lines).encode('utf-8')


def image_to_bytes(img: Image.Image, fmt='PNG'):
    out = io.BytesIO()
    img.save(out, format=fmt)
    return out.getvalue()


def pdf_export(img: Image.Image, palette_rows, title='Coloriage magique'):
    # Pillow-only PDF export to avoid ReportLab on Termux.
    page_w, page_h = 1240, 1754  # approx A4 @ 150 dpi
    page = Image.new('RGB', (page_w, page_h), 'white')
    draw = ImageDraw.Draw(page)
    try:
        title_font = ImageFont.truetype('/system/fonts/Roboto-Bold.ttf', 38)
        text_font = ImageFont.truetype('/system/fonts/Roboto-Regular.ttf', 24)
    except Exception:
        title_font = _font_for((page_w, page_h))
        text_font = _font_for((page_w, page_h))

    title_box = draw.textbbox((0, 0), title, font=title_font)
    draw.text(((page_w - (title_box[2] - title_box[0])) / 2, 36), title, fill='black', font=title_font)

    max_w, max_h = page_w - 120, page_h - 330
    picture = img.copy()
    picture.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    px = (page_w - picture.width) // 2
    py = 110
    page.paste(picture, (px, py))

    legend_y = min(page_h - 170, py + picture.height + 45)
    x = 70
    for rgb, value in palette_rows:
        if x > page_w - 180:
            x = 70
            legend_y += 48
        draw.rectangle((x, legend_y, x + 28, legend_y + 28), fill=tuple(rgb), outline='black')
        draw.text((x + 38, legend_y - 2), f'= {value}', fill='black', font=text_font)
        x += 150

    out = io.BytesIO()
    page.save(out, format='PDF', resolution=150.0)
    return out.getvalue()
