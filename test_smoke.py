from PIL import Image, ImageDraw
from core import quantize_image, regions_from_image, assign_values, exercise_for_value, render_coloring, svg_export, pdf_export
import random

img = Image.new('RGB',(200,200),'white')
d = ImageDraw.Draw(img)
d.rectangle((10,10,90,90), fill='red')
d.rectangle((110,10,190,90), fill='red')
d.rectangle((10,110,190,190), fill='blue')
q, colors = quantize_image(img, 3)
assert len(colors) <= 3
regs = regions_from_image(q, 50)
assert len(regs) >= 3, len(regs)
vals = assign_values(colors, 10)
assert max(vals.values()) <= 10
for mode in ['Nombre','Addition','Soustraction','Multiplication','Division','Mélange']:
    ex = exercise_for_value(5, mode, 10, random.Random(1))
    assert isinstance(ex,str) and ex
student, exs = render_coloring(img.size, regs, vals, 'Mélange', 10, 42, False)
svg = svg_export(img.size, regs, exs)
assert svg.startswith(b'<svg')
pdf = pdf_export(student, [(colors[cid-1], val) for cid,val in vals.items()])
assert pdf.startswith(b'%PDF')
student.save('generated/smoke_student.png')
open('generated/smoke.svg','wb').write(svg)
open('generated/smoke.pdf','wb').write(pdf)
print('Smoke tests OK:', len(colors), 'colors,', len(regs), 'regions, exports OK')
