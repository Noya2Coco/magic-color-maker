import base64
import io
import json
import mimetypes
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image

from core import (
    assign_values,
    image_to_bytes,
    pdf_export,
    quantize_image,
    regions_from_image,
    render_coloring,
    svg_export,
)

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'
SESSIONS = {}
MAX_UPLOAD = 15 * 1024 * 1024


def data_url(img):
    raw = image_to_bytes(img, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(raw).decode('ascii')


def json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False).encode('utf-8')


def decode_image_data_url(value):
    if ',' in value:
        value = value.split(',', 1)[1]
    raw = base64.b64decode(value)
    if len(raw) > MAX_UPLOAD:
        raise ValueError('Image trop volumineuse (15 Mo maximum).')
    img = Image.open(io.BytesIO(raw)).convert('RGB')
    if max(img.size) > 1800:
        img.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
    return img


class Handler(BaseHTTPRequestHandler):
    server_version = 'ColoriageTermux/1.0'

    def log_message(self, fmt, *args):
        print(f'[{self.log_date_time_string()}] {fmt % args}')

    def send_json(self, obj, status=200):
        body = json_bytes(obj)
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get('Content-Length', '0'))
        if length > MAX_UPLOAD * 2:
            raise ValueError('Requête trop volumineuse.')
        return json.loads(self.rfile.read(length).decode('utf-8'))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/':
            return self.serve_file(STATIC / 'index.html', 'text/html; charset=utf-8')
        if parsed.path.startswith('/static/'):
            target = STATIC / parsed.path[len('/static/'):]
            if '..' in target.parts:
                return self.send_error(403)
            return self.serve_file(target)
        if parsed.path.startswith('/download/'):
            parts = parsed.path.strip('/').split('/')
            if len(parts) != 3:
                return self.send_error(404)
            _, sid, kind = parts
            return self.download(sid, kind)
        return self.send_error(404)

    def serve_file(self, path, content_type=None):
        if not path.exists() or not path.is_file():
            return self.send_error(404)
        body = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', content_type or mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            if self.path == '/api/upload':
                body = self.read_json()
                img = decode_image_data_url(body['image'])
                sid = secrets.token_hex(12)
                SESSIONS[sid] = {'original': img}
                return self.send_json({'session': sid, 'width': img.width, 'height': img.height, 'original': data_url(img)})

            if self.path == '/api/simplify':
                body = self.read_json(); s = SESSIONS[body['session']]
                target = max(2, min(int(body.get('target_colors', 8)), int(body.get('max_value', 10))))
                simp, colors = quantize_image(s['original'], target)
                s.update({'simplified': simp, 'colors': colors, 'max_value': int(body.get('max_value', 10))})
                s.pop('regions', None); s.pop('final', None)
                return self.send_json({
                    'simplified': data_url(simp),
                    'colors': [list(c) for c in colors],
                    'count': len(colors),
                    'max_value': s['max_value'],
                })

            if self.path == '/api/regions':
                body = self.read_json(); s = SESSIONS[body['session']]
                if 'simplified' not in s:
                    raise ValueError('Simplification non validée.')
                min_area = int(body.get('min_area', 350))
                regions = regions_from_image(s['simplified'], min_area)
                s['regions'] = regions
                value_map = assign_values(s['colors'], s['max_value'])
                preview, _ = render_coloring(s['original'].size, regions, value_map, 'Nombre', s['max_value'], 42, False)
                tiny = sum(1 for r in regions if r['label_radius'] < 10)
                return self.send_json({'preview': data_url(preview), 'region_count': len(regions), 'small_labels': tiny})

            if self.path == '/api/generate':
                body = self.read_json(); s = SESSIONS[body['session']]
                if 'regions' not in s:
                    raise ValueError('Cellules non validées.')
                mode = body.get('mode', 'Nombre')
                operand_max = int(body.get('operand_max', s['max_value']))
                seed = int(body.get('seed', 42))
                value_map = assign_values(s['colors'], s['max_value'])
                student, exercises = render_coloring(s['original'].size, s['regions'], value_map, mode, operand_max, seed, False)
                corrected, _ = render_coloring(s['original'].size, s['regions'], value_map, mode, operand_max, seed, True)
                palette = [(color, value_map[idx + 1]) for idx, color in enumerate(s['colors']) if idx + 1 in value_map]
                s['final'] = {
                    'student': student,
                    'corrected': corrected,
                    'exercises': exercises,
                    'palette': palette,
                    'svg': svg_export(s['original'].size, s['regions'], exercises),
                    'pdf': pdf_export(student, palette),
                }
                return self.send_json({
                    'student': data_url(student),
                    'corrected': data_url(corrected),
                    'palette': [{'color': list(c), 'value': v} for c, v in palette],
                })

            return self.send_error(404)
        except KeyError as exc:
            return self.send_json({'error': f'Donnée ou session manquante : {exc}'}, 400)
        except Exception as exc:
            return self.send_json({'error': str(exc)}, 400)

    def download(self, sid, kind):
        s = SESSIONS.get(sid)
        if not s or 'final' not in s:
            return self.send_error(404)
        final = s['final']
        mapping = {
            'png': ('coloriage.png', 'image/png', image_to_bytes(final['student'], 'PNG')),
            'corrige.png': ('coloriage_corrige.png', 'image/png', image_to_bytes(final['corrected'], 'PNG')),
            'svg': ('coloriage.svg', 'image/svg+xml; charset=utf-8', final['svg']),
            'pdf': ('coloriage.pdf', 'application/pdf', final['pdf']),
        }
        if kind not in mapping:
            return self.send_error(404)
        filename, ctype, body = mapping[kind]
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    host = os.environ.get('COLORIAGE_HOST', '127.0.0.1')
    port = int(os.environ.get('COLORIAGE_PORT', '8000'))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f'Coloriage magique Termux : http://{host}:{port}')
    print('Ctrl+C pour arrêter.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
