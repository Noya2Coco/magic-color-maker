import io, json, math, random, zipfile
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

st.set_page_config(page_title='Coloriage magique', layout='wide')

APP_DIR = Path(__file__).parent
TMP = APP_DIR / 'generated'
TMP.mkdir(exist_ok=True)


def pil_to_np(img: Image.Image):
    return np.array(img.convert('RGB'))


def quantize_image(img: Image.Image, max_colors: int):
    # Pillow median-cut gives deterministic and robust color quantization for flat illustrations.
    q = img.convert('RGB').quantize(colors=max_colors, method=Image.Quantize.MEDIANCUT)
    rgb = q.convert('RGB')
    arr = np.array(rgb)
    colors = np.unique(arr.reshape(-1, 3), axis=0)
    return rgb, [tuple(map(int, c)) for c in colors]


def regions_from_image(img: Image.Image, min_area: int):
    arr = np.array(img.convert('RGB'))
    h, w = arr.shape[:2]
    colors = np.unique(arr.reshape(-1, 3), axis=0)
    regions = []
    rid = 1
    for color_id, c in enumerate(colors, start=1):
        mask = np.all(arr == c, axis=2).astype(np.uint8) * 255
        n, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
        for label in range(1, n):
            x, y, ww, hh, area = stats[label]
            if area < min_area:
                continue
            comp = (labels == label).astype(np.uint8) * 255
            contours, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            contour = max(contours, key=cv2.contourArea)
            # Best label point = pixel with maximum distance from boundary.
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
    # Values are unique and never exceed max_value.
    vals = list(range(1, min(len(colors), max_value) + 1))
    return {i+1: vals[i] for i in range(len(vals))}


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
    if not choices:
        return str(v)
    return rng.choice(choices)


def render_coloring(size, regions, value_map, mode, operand_max, seed, show_fill=False):
    w, h = size
    img = Image.new('RGB', (w, h), 'white')
    draw = ImageDraw.Draw(img)
    rng = random.Random(seed)
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', max(13, min(w, h)//45))
    except Exception:
        font = ImageFont.load_default()

    region_exercises = {}
    for r in regions:
        poly = r['polygon']
        if len(poly) < 3:
            continue
        fill = r['color'] if show_fill else 'white'
        draw.polygon(poly, fill=fill, outline='black')
        value = value_map.get(r['color_id'])
        if value is None:
            continue
        ex = exercise_for_value(value, mode, operand_max, rng)
        region_exercises[r['id']] = ex
        x, y = r['label_position']
        bbox = draw.textbbox((0,0), ex, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        draw.rectangle((x-tw/2-2, y-th/2-1, x+tw/2+2, y+th/2+1), fill='white')
        draw.text((x-tw/2, y-th/2), ex, fill='black', font=font)
    return img, region_exercises


def svg_export(size, regions, value_map, exercises):
    w, h = size
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">', '<rect width="100%" height="100%" fill="white"/>']
    for r in regions:
        if len(r['polygon']) < 3: continue
        pts = ' '.join(f'{x},{y}' for x,y in r['polygon'])
        lines.append(f'<polygon points="{pts}" fill="white" stroke="black" stroke-width="1.5"/>')
        ex = exercises.get(r['id'], '')
        x,y = r['label_position']
        lines.append(f'<text x="{x}" y="{y}" text-anchor="middle" dominant-baseline="middle" font-family="Arial" font-size="18">{ex.replace("&","&amp;")}</text>')
    lines.append('</svg>')
    return '\n'.join(lines).encode('utf-8')


def pdf_export(img: Image.Image, palette_rows, title='Coloriage magique'):
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=A4)
    pw, ph = A4
    c.setFont('Helvetica-Bold', 18)
    c.drawCentredString(pw/2, ph-40, title)
    temp_png = io.BytesIO(); img.save(temp_png, format='PNG'); temp_png.seek(0)
    iw, ih = img.size
    maxw, maxh = pw-80, ph-180
    scale = min(maxw/iw, maxh/ih)
    dw, dh = iw*scale, ih*scale
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(temp_png), (pw-dw)/2, ph-70-dh, width=dw, height=dh, preserveAspectRatio=True)
    y = 70
    c.setFont('Helvetica', 10)
    x = 45
    for rgb, value in palette_rows:
        rr,gg,bb = [v/255 for v in rgb]
        c.setFillColorRGB(rr,gg,bb); c.rect(x, y, 12, 12, fill=1, stroke=1)
        c.setFillColorRGB(0,0,0); c.drawString(x+18, y+2, f'= {value}')
        x += 70
        if x > pw-90:
            x = 45; y -= 18
    c.showPage(); c.save(); out.seek(0)
    return out.getvalue()


def reset_after(step):
    order = ['simplified','regions','final_img','corrected_img','exercises']
    if step in order:
        idx = order.index(step)
        for k in order[idx:]:
            st.session_state.pop(k, None)

st.title('🖍️ Générateur de coloriage magique')
st.caption('MVP local : simplification des couleurs → validation → cellules → calculs → exports')

with st.sidebar:
    st.header('Réglages')
    max_value = st.number_input('Valeur maximale / couleurs max', min_value=2, max_value=50, value=10, step=1)
    complexity = st.selectbox('Complexité', ['Très simple','Simple','Moyen','Détaillé'], index=1)
    min_area_map = {'Très simple': 650, 'Simple': 350, 'Moyen': 150, 'Détaillé': 50}
    min_area = min_area_map[complexity]
    mode = st.selectbox('Contenu des cellules', ['Nombre','Addition','Soustraction','Multiplication','Division','Mélange'])
    operand_max = st.number_input('Opérande maximum', min_value=1, max_value=100, value=int(max_value), step=1)
    seed = st.number_input('Seed', min_value=0, max_value=999999, value=42)

uploaded = st.file_uploader('Choisir une image', type=['png','jpg','jpeg','webp'])
if not uploaded:
    st.info('Importe une image simple pour commencer.')
    st.stop()

orig = Image.open(uploaded).convert('RGB')
if max(orig.size) > 1600:
    orig.thumbnail((1600,1600))
st.session_state['original'] = orig

st.subheader('1. Simplification des couleurs')
col1,col2 = st.columns(2)
with col1:
    st.markdown('**Image originale**')
    st.image(orig, use_container_width=True)
with col2:
    target_colors = st.slider('Nombre de couleurs proposé', 2, int(max_value), min(int(max_value), 8))
    simp, colors = quantize_image(orig, target_colors)
    st.session_state['simplified'] = simp
    st.session_state['colors'] = colors
    st.markdown(f'**Image simplifiée — {len(colors)} couleur(s) / max {max_value}**')
    st.image(simp, use_container_width=True)

st.write('Palette :')
palette_html = ''.join([f'<span style="display:inline-block;width:28px;height:28px;background:rgb{c};border:1px solid #444;margin-right:5px"></span>' for c in colors])
st.markdown(palette_html, unsafe_allow_html=True)

if st.button('✅ Cette simplification me convient', type='primary'):
    st.session_state['simplification_validated'] = True
    reset_after('regions')

if not st.session_state.get('simplification_validated'):
    st.warning('Valide la simplification pour continuer.')
    st.stop()

st.divider()
st.subheader('2. Détection des cellules')
regions = regions_from_image(st.session_state['simplified'], min_area)
st.session_state['regions'] = regions
st.write(f'**{len(colors)} couleurs • {len(regions)} cellules détectées • seuil {min_area}px**')

# Preview cells
preview, _ = render_coloring(orig.size, regions, assign_values(colors, int(max_value)), 'Nombre', int(operand_max), int(seed), show_fill=False)
st.image(preview, caption='Prévisualisation des cellules', use_container_width=True)

if st.button('✅ Valider les cellules', type='primary'):
    st.session_state['cells_validated'] = True

if not st.session_state.get('cells_validated'):
    st.warning('Valide les cellules pour générer les exercices.')
    st.stop()

st.divider()
st.subheader('3. Exercices et coloriage final')
value_map = assign_values(colors, int(max_value))
final_img, exercises = render_coloring(orig.size, regions, value_map, mode, int(operand_max), int(seed), show_fill=False)
corrected_img, _ = render_coloring(orig.size, regions, value_map, mode, int(operand_max), int(seed), show_fill=True)
st.session_state['final_img'] = final_img
st.session_state['corrected_img'] = corrected_img
st.session_state['exercises'] = exercises

c1,c2 = st.columns(2)
with c1:
    st.markdown('**Version élève**')
    st.image(final_img, use_container_width=True)
with c2:
    st.markdown('**Corrigé**')
    st.image(corrected_img, use_container_width=True)

st.markdown('**Légende**')
legend_cols = st.columns(min(5, max(1,len(value_map))))
for idx,(cid,val) in enumerate(value_map.items()):
    rgb = colors[cid-1]
    with legend_cols[idx % len(legend_cols)]:
        st.markdown(f'<div style="display:flex;align-items:center;gap:8px;margin:3px"><span style="width:22px;height:22px;background:rgb{rgb};border:1px solid #333;display:inline-block"></span><b>{val}</b></div>', unsafe_allow_html=True)

st.caption('Pour régénérer les calculs sans changer le dessin, modifie simplement la seed dans la barre latérale.')

# Exports
png_b = io.BytesIO(); final_img.save(png_b, 'PNG')
svg_b = svg_export(orig.size, regions, value_map, exercises)
palette_rows = [(colors[cid-1], val) for cid,val in value_map.items()]
pdf_b = pdf_export(final_img, palette_rows)
cor_b = io.BytesIO(); corrected_img.save(cor_b, 'PNG')

st.subheader('4. Exports')
a,b,c,d = st.columns(4)
with a: st.download_button('⬇️ PNG élève', png_b.getvalue(), 'coloriage_magique.png', 'image/png')
with b: st.download_button('⬇️ SVG', svg_b, 'coloriage_magique.svg', 'image/svg+xml')
with c: st.download_button('⬇️ PDF A4', pdf_b, 'coloriage_magique.pdf', 'application/pdf')
with d: st.download_button('⬇️ Corrigé PNG', cor_b.getvalue(), 'coloriage_corrige.png', 'image/png')
