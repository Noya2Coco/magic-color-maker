from pathlib import Path
from PIL import Image, ImageDraw
from core import quantize_image, regions_from_image, assign_values, render_coloring, svg_export, pdf_export

out = Path(__file__).parent / 'generated'
out.mkdir(exist_ok=True)
img = Image.new('RGB', (480, 360), 'white')
d = ImageDraw.Draw(img)
d.rectangle((30, 30, 200, 160), fill=(240, 60, 60))
d.rectangle((280, 30, 450, 160), fill=(240, 60, 60))
d.ellipse((120, 190, 360, 340), fill=(50, 100, 230))
q, colors = quantize_image(img, 4)
regions = regions_from_image(q, 80)
assert len(colors) <= 4
assert len(regions) >= 3
values = assign_values(colors, 10)
student, ex = render_coloring(img.size, regions, values, 'Mélange', 10, 42, False)
corrected, _ = render_coloring(img.size, regions, values, 'Mélange', 10, 42, True)
palette = [(c, values[i+1]) for i, c in enumerate(colors) if i+1 in values]
student.save(out / 'termux_smoke.png')
corrected.save(out / 'termux_smoke_corrected.png')
(out / 'termux_smoke.svg').write_bytes(svg_export(img.size, regions, ex))
(out / 'termux_smoke.pdf').write_bytes(pdf_export(student, palette))
print(f'OK: {len(colors)} colors, {len(regions)} regions')
