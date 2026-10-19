"""Pruebas del despliegue de la interfaz: construcción (tools/build_web.py) y vercel.json."""

import json
import re
from pathlib import Path

import pytest

import build_web

RAIZ = Path(__file__).resolve().parent.parent
VERCEL = json.loads((RAIZ / "vercel.json").read_text(encoding="utf-8"))


def cabeceras(origen: str) -> dict[str, str]:
    regla = next(r for r in VERCEL["headers"] if r["source"] == origen)
    return {h["key"]: h["value"] for h in regla["headers"]}


@pytest.fixture()
def sitio(tmp_path, monkeypatch):
    """Construye la interfaz real en una carpeta temporal, sin tocar taskflow-web/dist."""
    monkeypatch.setattr(build_web, "DIST", tmp_path / "dist")
    return tmp_path / "dist"


# ---------------------------------------------------------------- vercel.json


def test_la_configuracion_de_vercel_apunta_a_lo_que_genera_la_construccion():
    assert VERCEL["framework"] is None  # sitio estático: sin detección automática de frameworks
    assert VERCEL["buildCommand"] == "python3 tools/build_web.py"
    assert (RAIZ / "tools" / "build_web.py").is_file()
    assert Path(VERCEL["outputDirectory"]) == Path("taskflow-web/dist")
    assert "tools/requirements.txt" in VERCEL["installCommand"]
    assert (RAIZ / "tools" / "requirements.txt").is_file()


def test_si_no_se_pueden_instalar_los_minificadores_el_despliegue_continua():
    assert "||" in VERCEL["installCommand"]


def test_la_politica_csp_no_permite_codigo_en_linea_ni_marcos():
    csp = cabeceras("/(.*)")["Content-Security-Policy"]
    directivas = dict(d.strip().split(" ", 1) for d in csp.split(";") if d.strip())
    assert directivas["script-src"] == "'self'"
    assert directivas["style-src"] == "'self'"
    assert directivas["frame-ancestors"] == "'none'"
    assert directivas["object-src"] == "'none'"
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp


def test_cabeceras_de_seguridad_basicas():
    seguras = cabeceras("/(.*)")
    assert seguras["X-Content-Type-Options"] == "nosniff"
    assert seguras["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in seguras and "Permissions-Policy" in seguras


def test_los_recursos_con_resumen_se_cachean_para_siempre():
    cache = cabeceras("/assets/(.*)")["Cache-Control"]
    assert "immutable" in cache and "max-age=31536000" in cache


def test_el_html_fuente_no_usa_estilos_ni_manejadores_en_linea():
    """Lo exige la política CSP (style-src 'self', script-src 'self')."""
    html = (RAIZ / "taskflow-web" / "index.html").read_text(encoding="utf-8")
    assert not re.search(r'\sstyle="', html)
    assert not re.search(r"\son[a-z]+=", html)
    assert not re.search(r"<script(?![^>]*\ssrc=)[^>]*>", html)  # ningún script en línea


# ---------------------------------------------------------------- menú y vistas


def contenido(nombre: str) -> str:
    return (RAIZ / "taskflow-web" / nombre).read_text(encoding="utf-8")


def test_cada_enlace_del_menu_tiene_su_vista_y_su_ruta():
    """Evita que un enlace del menú vuelva a quedar decorativo (href="#")."""
    html = contenido("index.html")
    enlaces = re.findall(r'<a href="(#/[^"]+)" class="nav-link[^"]*" data-nav="(\w+)"', html)
    assert len(enlaces) == 5
    codigo_del_router = contenido("js/router.js").split("const ROUTES")[1]
    rutas = set(re.findall(r'^\s+(\w+): "', codigo_del_router, re.M))
    vistas = set(re.findall(r'data-view="(\w+)"', html))
    for href, nombre in enlaces:
        assert href == f"#/{nombre}"
        assert nombre in vistas, f"el enlace '{nombre}' no tiene su sección data-view"
        assert nombre in rutas, f"el enlace '{nombre}' no está en las rutas de router.js"
    assert 'href="#"' not in html


def test_las_vistas_nuevas_estan_cargadas_en_el_orden_correcto():
    html = contenido("index.html")
    orden = re.findall(r'<script src="(js/[^"]+)"', html)
    for archivo in ("js/router.js", "js/components/task-list.js", "js/components/calendar-view.js"):
        assert archivo in orden
    # El arranque va el último; las utilidades se cargan antes que los componentes que las usan.
    assert orden[-1] == "js/app.js"
    assert orden.index("js/lib/dom.js") < orden.index("js/components/task-list.js")
    assert orden.index("js/lib/settings.js") < orden.index("js/components/settings-view.js")
    assert orden.index("js/store.js") < orden.index("js/router.js") < orden.index("js/app.js")


def test_el_codigo_de_las_vistas_no_usa_html_en_cadenas_ni_estilos_en_linea():
    """La política CSP y la seguridad (XSS) exigen crear el DOM con h() y textContent."""
    for archivo in (RAIZ / "taskflow-web" / "js").rglob("*.js"):
        texto = archivo.read_text(encoding="utf-8")
        assert "innerHTML" not in texto, f"{archivo.name} usa innerHTML"
        assert "insertAdjacentHTML" not in texto, f"{archivo.name} usa insertAdjacentHTML"
        assert not re.search(r"\.style\.\w+\s*=", texto), f"{archivo.name} asigna estilos en línea"
        assert "eval(" not in texto


def test_la_pagina_no_tiene_enlaces_vacios_ni_peticiones_a_otros_dominios():
    html = contenido("index.html")
    assert not re.search(r'href="#"', html)
    externos = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
    assert externos == [], f"recursos externos (la CSP solo permite 'self'): {externos}"


# ---------------------------------------------------------------- construcción


def test_la_construccion_genera_tres_recursos_en_la_carpeta_de_salida(sitio):
    build_web.build()

    html = (sitio / "index.html").read_text(encoding="utf-8")
    recursos = re.findall(r'(?:src|href)="(assets/[^"]+)"', html)
    assert len(recursos) == 2
    for recurso in recursos:
        assert (sitio / recurso).is_file()
    assert re.search(r"assets/app\.[0-9a-f]{8}\.js", html)
    assert re.search(r"assets/styles\.[0-9a-f]{8}\.css", html)
    assert "js/" not in html and "css/" not in html  # ya no quedan rutas de los archivos fuente


def test_la_construccion_funciona_sin_minificadores(sitio, monkeypatch):
    """En Vercel, si falla `pip install`, el despliegue no debe romperse."""
    monkeypatch.setattr(build_web, "rjsmin", None)
    monkeypatch.setattr(build_web, "rcssmin", None)

    build_web.build()

    assert any((sitio / "assets").glob("app.*.js"))
    assert any((sitio / "assets").glob("styles.*.css"))


def test_los_minificadores_reducen_el_tamano(sitio, monkeypatch):
    if build_web.rjsmin is None:
        pytest.skip("rjsmin/rcssmin no instalados")
    build_web.build()
    minificado = sum(f.stat().st_size for f in (sitio / "assets").iterdir())

    monkeypatch.setattr(build_web, "rjsmin", None)
    monkeypatch.setattr(build_web, "rcssmin", None)
    build_web.build()
    sin_minificar = sum(f.stat().st_size for f in (sitio / "assets").iterdir())

    assert minificado < sin_minificar


def test_el_nombre_cambia_solo_si_cambia_el_contenido(sitio):
    build_web.build()
    primero = sorted(p.name for p in (sitio / "assets").iterdir())
    build_web.build()
    assert sorted(p.name for p in (sitio / "assets").iterdir()) == primero


def test_otra_capitalizacion_falla_aunque_windows_encuentre_el_archivo(tmp_path, monkeypatch):
    web = tmp_path / "web"
    (web / "Js").mkdir(parents=True)  # la carpeta real se llama "Js"
    (web / "Js" / "app.js").write_text("var a = 1;", encoding="utf-8")
    monkeypatch.setattr(build_web, "WEB", web)

    with pytest.raises(SystemExit, match="capitalización"):
        build_web.read_source("js/app.js")  # pero el HTML pide "js/"


def test_todos_los_recursos_del_html_existen_con_su_capitalizacion_exacta():
    html = (RAIZ / "taskflow-web" / "index.html").read_text(encoding="utf-8")
    rutas = build_web.SCRIPT_TAG.findall(html) + build_web.CSS_LINK.findall(html)
    assert rutas
    for ruta in rutas:
        assert build_web.read_source(ruta)  # sale con error si hay una diferencia de mayúsculas
