"""Genera la versión de producción de la interfaz en taskflow-web/dist/.

Qué hace:
- Une los 11 scripts de index.html en UN solo archivo y lo minifica (rjsmin).
- Minifica el CSS (rcssmin).
- Quita comentarios y espacios sobrantes del HTML.
- Añade al nombre de los archivos un resumen de su contenido (app.<hash>.js): el navegador
  puede guardarlos en caché por mucho tiempo y los descarga de nuevo solo si cambian.

Resultado: de 13 peticiones a 3. El código fuente (taskflow-web/js y css) no se modifica;
dist/ se genera y no se versiona.

Uso (desde la raíz del proyecto):
    pip install -r tools/requirements.txt
    python tools/build_web.py
"""

import gzip
import hashlib
import re
import shutil
import sys
from pathlib import Path

import rcssmin
import rjsmin

WEB = Path(__file__).resolve().parent.parent / "taskflow-web"
DIST = WEB / "dist"

SCRIPT_TAG = re.compile(r'[ \t]*<script src="(js/[^"]+)"></script>\n?')
CSS_LINK = re.compile(r'<link rel="stylesheet" href="(css/[^"]+)" />')
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def gzip_size(data: bytes) -> int:
    return len(gzip.compress(data, 9))


def minify_html(html: str) -> str:
    """Quita comentarios y espacios entre etiquetas. index.html no usa <pre> ni <textarea>."""
    html = HTML_COMMENT.sub("", html)
    html = re.sub(r">\s+<", "><", html)
    return re.sub(r"\s{2,}", " ", html).strip()


def build() -> None:
    source_html = (WEB / "index.html").read_text(encoding="utf-8")
    script_paths = SCRIPT_TAG.findall(source_html)
    css_paths = CSS_LINK.findall(source_html)
    if not script_paths or len(css_paths) != 1:
        sys.exit("No se encontraron los <script> o la hoja de estilos esperados en index.html")

    # Los scripts se concatenan en el orden en que los carga index.html.
    js = ";\n".join(rjsmin.jsmin((WEB / p).read_text(encoding="utf-8")) for p in script_paths)
    css = rcssmin.cssmin((WEB / css_paths[0]).read_text(encoding="utf-8"))
    js_name = f"app.{short_hash(js)}.js"
    css_name = f"styles.{short_hash(css)}.css"

    html = CSS_LINK.sub(f'<link rel="stylesheet" href="{css_name}" />', source_html)
    # El primer <script> se sustituye por el paquete; los demás se eliminan.
    scripts = iter([f'<script src="{js_name}"></script>\n'])
    html = SCRIPT_TAG.sub(lambda _: next(scripts, ""), html)
    html = minify_html(html)

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    (DIST / js_name).write_text(js, encoding="utf-8")
    (DIST / css_name).write_text(css, encoding="utf-8")
    (DIST / "index.html").write_text(html, encoding="utf-8")

    names = (js_name, css_name)
    report(source_html, script_paths, css_paths[0], (js, css, html), names)


def report(source_html, script_paths, css_path, built_texts, names) -> None:
    js, css, html = built_texts
    js_name, css_name = names
    sources = {
        "JS": [(WEB / p).read_bytes() for p in script_paths],
        "CSS": [(WEB / css_path).read_bytes()],
        "HTML": [source_html.encode("utf-8")],
    }
    built = {"JS": [js.encode()], "CSS": [css.encode()], "HTML": [html.encode()]}
    print(f"{'':6}{'antes':>10}{'después':>10}{'gzip antes':>12}{'gzip después':>14}")
    totals = [0, 0, 0, 0]
    for kind in ("JS", "CSS", "HTML"):
        a, b = sum(map(len, sources[kind])), sum(map(len, built[kind]))
        ga = sum(gzip_size(x) for x in sources[kind])
        gb = sum(gzip_size(x) for x in built[kind])
        for i, value in enumerate((a, b, ga, gb)):
            totals[i] += value
        print(f"{kind:6}{a:>10}{b:>10}{ga:>12}{gb:>14}")
    print(f"{'TOTAL':6}{totals[0]:>10}{totals[1]:>10}{totals[2]:>12}{totals[3]:>14}  (bytes)")
    antes = len(script_paths) + 2  # los scripts, la hoja de estilos y el HTML
    print(f"Peticiones al cargar: {antes} -> 3  ({js_name}, {css_name}, index.html)")


if __name__ == "__main__":
    build()
