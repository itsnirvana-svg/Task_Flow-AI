"""Pruebas de los archivos de despliegue (deploy/ y backend/Dockerfile).

No levantan contenedores (eso lo hace el trabajo «Despliegue» del CI): comprueban que las decisiones
de seguridad y de operación no se pierdan con un cambio, por ejemplo que la base de datos nunca
quede publicada en internet o que un secreto acabe escrito en el archivo.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
DEPLOY = RAIZ / "deploy"
COMPOSE_TEXTO = (DEPLOY / "docker-compose.yml").read_text(encoding="utf-8")
COMPOSE = yaml.safe_load(COMPOSE_TEXTO)
SERVICIOS = COMPOSE["services"]
DOCKERFILE = (RAIZ / "backend" / "Dockerfile").read_text(encoding="utf-8")


def variables_de(texto: str) -> set[str]:
    return set(re.findall(r"^([A-Z][A-Z0-9_]*)=", texto, re.M))


# ---------------------------------------------------------------- red y exposición


def test_los_cuatro_servicios_esperados():
    assert set(SERVICIOS) == {"caddy", "api", "postgres", "n8n"}


def test_solo_caddy_publica_puertos_y_son_los_de_https():
    publicados = {nombre: s["ports"] for nombre, s in SERVICIOS.items() if "ports" in s}
    assert set(publicados) == {"caddy"}
    assert {p.split(":")[0] for p in publicados["caddy"]} == {"80", "443"}


def test_la_base_de_datos_no_es_alcanzable_desde_internet():
    assert list(SERVICIOS["postgres"]["networks"]) == ["internal"]
    assert COMPOSE["networks"]["internal"]["internal"] is True  # esa red no tiene salida a internet
    assert "ports" not in SERVICIOS["postgres"]


def test_la_api_y_n8n_solo_hablan_con_la_base_por_la_red_interna():
    for nombre in ("api", "n8n"):
        assert "internal" in SERVICIOS[nombre]["networks"]


def test_caddy_responde_por_los_nombres_publicos_dentro_de_la_red():
    """La API llama al webhook por https://n8n.<dominio>: llega a Caddy sin salir a internet."""
    alias = SERVICIOS["caddy"]["networks"]["edge"]["aliases"]
    assert "n8n.${DOMAIN}" in alias and "api.${DOMAIN}" in alias


# ---------------------------------------------------------------- secretos


def test_ninguna_variable_obligatoria_tiene_valor_por_defecto_inseguro():
    """Las claves usan ${VAR:?mensaje}: si falta una, `docker compose` se niega a arrancar."""
    for secreto in (
        "POSTGRES_PASSWORD", "N8N_DB_PASSWORD", "N8N_ENCRYPTION_KEY", "N8N_WEBHOOK_SECRET",
        "API_KEYS", "ADMIN_PASSWORD_HASH", "AUTH_SECRET_KEY", "DOMAIN", "ACME_EMAIL",
    ):
        assert "${" + secreto + ":?" in COMPOSE_TEXTO, f"{secreto} debe ser obligatoria"
        con_defecto = "${" + secreto + ":-"
        assert con_defecto not in COMPOSE_TEXTO, f"{secreto} no debe tener valor por defecto"


def test_el_compose_no_contiene_secretos_escritos():
    entorno = [
        valor for s in SERVICIOS.values() for valor in (s.get("environment") or {}).values()
    ]
    for valor in map(str, entorno):
        escrito = re.fullmatch(r"[A-Za-z0-9_\-]{32,}", valor)
        assert not escrito, "parece un secreto escrito en el archivo"


def test_toda_variable_del_compose_esta_documentada_en_env_example():
    usadas = set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", COMPOSE_TEXTO))
    documentadas = variables_de((DEPLOY / ".env.example").read_text(encoding="utf-8"))
    documentadas |= set(re.findall(r"^# ([A-Z][A-Z0-9_]*)=", (DEPLOY / ".env.example").read_text(
        encoding="utf-8"), re.M))  # las opcionales comentadas (TZ)
    assert usadas - documentadas == set()


def test_el_hash_de_contrasena_de_la_plantilla_va_entre_comillas_simples():
    """Sin comillas, Compose interpretaría los "$" del hash como variables."""
    ejemplo = (DEPLOY / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^ADMIN_PASSWORD_HASH='[^']*'$", ejemplo, re.M)


def test_el_env_real_y_las_copias_no_se_pueden_subir_a_git():
    ignorado = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    assert re.search(r"^\.env$", ignorado, re.M) and re.search(r"^backups/$", ignorado, re.M)


# ---------------------------------------------------------------- operación


def test_todo_se_reinicia_solo_y_tiene_comprobacion_de_salud():
    for nombre, servicio in SERVICIOS.items():
        assert servicio["restart"] == "unless-stopped", nombre
    for nombre in ("api", "postgres", "n8n"):
        assert "healthcheck" in SERVICIOS[nombre], f"{nombre} sin healthcheck"


def test_la_api_espera_a_la_base_de_datos_y_comprueba_la_disponibilidad_real():
    assert SERVICIOS["api"]["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert "/health/ready" in " ".join(SERVICIOS["api"]["healthcheck"]["test"])


def test_la_api_arranca_en_modo_produccion():
    assert SERVICIOS["api"]["environment"]["APP_ENV"] == "production"


def test_las_imagenes_estan_fijadas_a_una_version():
    for nombre, servicio in SERVICIOS.items():
        imagen = servicio["image"]
        if nombre == "api":  # se construye desde el Dockerfile
            continue
        assert ":" in imagen and not imagen.endswith(":latest"), f"{nombre}: {imagen}"
    assert re.search(r"^FROM [^:\s]+:[^\s]+", DOCKERFILE, re.M) and ":latest" not in DOCKERFILE


def test_los_datos_viven_en_volumenes_con_nombre():
    assert {"pgdata", "n8n_data", "caddy_data"} <= set(COMPOSE["volumes"])
    montajes = " ".join(SERVICIOS["postgres"]["volumes"])
    assert "pgdata:/var/lib/postgresql/data" in montajes


def test_la_base_de_datos_se_inicializa_con_el_esquema_del_repositorio():
    montajes = SERVICIOS["postgres"]["volumes"]
    assert any("../backend/db/schema.sql" in m for m in montajes)
    assert any("01-n8n.sh" in m for m in montajes)
    assert (DEPLOY / "postgres" / "init" / "01-n8n.sh").is_file()
    assert (RAIZ / "backend" / "db" / "schema.sql").is_file()


def test_los_registros_tienen_limite_de_tamano():
    for nombre in ("caddy", "api", "postgres", "n8n"):
        opciones = SERVICIOS[nombre]["logging"]["options"]
        assert opciones["max-size"] and opciones["max-file"], nombre


# ---------------------------------------------------------------- imagen de la API


def test_la_imagen_no_se_ejecuta_como_administrador():
    usuario = re.findall(r"^USER\s+(\S+)", DOCKERFILE, re.M)
    assert usuario and usuario[-1] not in ("root", "0")


def test_la_imagen_solo_lleva_el_codigo_de_la_aplicacion():
    copias = re.findall(r"^COPY\s+(\S+)", DOCKERFILE, re.M)
    assert set(copias) == {"requirements.txt", "app"}
    ignorados = (RAIZ / "backend" / ".dockerignore").read_text(encoding="utf-8")
    for excluido in (".env", "tests/", "*.db"):
        assert excluido in ignorados


def test_la_api_respeta_la_ip_real_del_cliente_detras_de_caddy():
    assert "--proxy-headers" in DOCKERFILE and "--forwarded-allow-ips" in DOCKERFILE
    assert "ports" not in SERVICIOS["api"]  # por eso "*" es seguro: nadie de fuera llega al 8000


# ---------------------------------------------------------------- Caddy


def test_caddy_sirve_la_api_y_n8n_con_hsts():
    caddy = (DEPLOY / "Caddyfile").read_text(encoding="utf-8")
    assert "api.{$DOMAIN}" in caddy and "n8n.{$DOMAIN}" in caddy
    assert "reverse_proxy api:8000" in caddy and "reverse_proxy n8n:5678" in caddy
    assert "Strict-Transport-Security" in caddy


# ---------------------------------------------------------------- scripts


SCRIPTS = [DEPLOY / "backup.sh", DEPLOY / "restore.sh", DEPLOY / "postgres" / "init" / "01-n8n.sh"]


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_los_scripts_fallan_ante_el_primer_error(script):
    assert re.search(r"^set -eu(o pipefail)?$", script.read_text(encoding="utf-8"), re.M)


@pytest.mark.skipif(shutil.which("bash") is None, reason="no hay bash")
@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_los_scripts_tienen_sintaxis_valida(script):
    resultado = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stderr


def test_la_copia_de_seguridad_nunca_deja_un_archivo_a_medias():
    backup = (DEPLOY / "backup.sh").read_text(encoding="utf-8")
    assert ".tmp" in backup and "gzip -t" in backup and "mv " in backup
    assert "pg_dump" in backup and "taskflow" in backup and "n8n" in backup
    assert "umask 077" in backup  # las copias contienen datos: solo las lee quien las crea


def test_la_restauracion_pide_confirmacion_y_detiene_el_servicio():
    restore = (DEPLOY / "restore.sh").read_text(encoding="utf-8")
    assert "read -r" in restore and '"$respuesta" = "$base"' in restore
    assert "docker compose stop" in restore and "docker compose start" in restore
    assert "ON_ERROR_STOP=1" in restore


def test_la_contrasena_de_n8n_se_pasa_a_psql_como_variable_no_en_el_texto_sql():
    """Con :'clave' psql la entrecomilla bien aunque lleve comillas u otros caracteres raros."""
    init = (DEPLOY / "postgres" / "init" / "01-n8n.sh").read_text(encoding="utf-8")
    assert ":'clave'" in init and "<<'SQL'" in init and "$N8N_DB_PASSWORD" in init
    assert "PASSWORD '$" not in init


# ---------------------------------------------------------------- finales de línea


def test_los_archivos_de_despliegue_se_fijan_a_lf_en_git():
    """Con CRLF (Windows) fallan los scripts de shell y los Dockerfile dentro de Linux."""
    atributos = (RAIZ / ".gitattributes").read_text(encoding="utf-8")
    for patron in ("*.sh", "Dockerfile", "Caddyfile", "*.yml", "*.sql"):
        assert re.search(rf"^{re.escape(patron)}\s+text eol=lf$", atributos, re.M), patron


EN_LF = [*SCRIPTS, DEPLOY / "Caddyfile", RAIZ / "backend" / "Dockerfile"]


@pytest.mark.parametrize("archivo", EN_LF, ids=lambda p: p.name)
def test_los_archivos_de_despliegue_no_tienen_retorno_de_carro(archivo):
    assert b"\r" not in archivo.read_bytes()
