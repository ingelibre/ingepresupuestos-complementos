#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari
"""Comprueba las fichas y arma catalogo.json. Lee los complementos, nunca los ejecuta.

    catalogo.py comprobar [ids…]        (en cada pull request)
    catalogo.py armar                   (en main)
    catalogo.py decidir CUENTA CAMBIOS  ¿versión nueva de su autor? → id=<id>

Los complementos se validan con el código de IngePresupuestos, en .programa/ (o en
la variable PROGRAMA). Códigos de `comprobar`: 0 limpio, 1 mal, 3 hay algo que leer.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
import tempfile
import tomllib
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.environ.get('PROGRAMA') or str(RAIZ / '.programa'))

CLAVES = ('id', 'cuenta', 'repositorio', 'descarga', 'sha256')
LICENCIAS = {
    'GPL-3.0-only', 'GPL-3.0-or-later', 'GPL-2.0-or-later', 'LGPL-2.1-or-later',
    'LGPL-3.0-only', 'LGPL-3.0-or-later', 'AGPL-3.0-only', 'AGPL-3.0-or-later',
    'MIT', 'BSD-2-Clause', 'BSD-3-Clause', 'Apache-2.0', 'MPL-2.0', 'ISC', 'Zlib',
    '0BSD', 'Unlicense', 'CC0-1.0'}
CAMPOS_FICHA = ('esquema', 'id', 'nombre', 'version', 'autor', 'licencia',
                'descripcion', 'web', 'api_version', 'codigo', 'categorias',
                'traducciones')
#: De la biblioteca estándar, lo que no merece que nadie lo mire.
SIN_RIESGO = {'ingepresupuestos', '__future__', 'math', 'decimal', 'fractions', 're',
              'datetime', 'collections', 'itertools', 'functools', 'dataclasses',
              'typing', 'json', 'csv', 'unicodedata', 'statistics', 'string',
              'textwrap', 'enum', 'bisect', 'calendar', 'copy'}
LLAMADAS = {'eval', 'exec', 'compile', '__import__', 'open', 'getattr', 'setattr',
            'globals', 'vars', 'locals', 'breakpoint'}
#: Módulos a los que se llega por otro (`re.sys`). No es una jaula: es un aviso.
PUERTAS = {'sys', 'os', 'io', 'builtins', 'codecs', 'modules', 'importlib', 'inspect',
           'subprocess', 'socket', 'ctypes', 'operator', 'attrgetter', 'types', 'system',
           'popen', 'unlink', 'rmtree', 'write_text', 'write_bytes'}
OFICIAL = 'ingelibre'


def leer_toml(f: Path) -> dict:
    return tomllib.loads(f.read_text(encoding='utf-8'))


def campos(x: dict, nombre: str) -> list[str]:
    mal = [f"falta «{k}»" for k in CLAVES if k not in x]
    mal += [f"«{k}» no se admite" for k in x if k not in CLAVES]
    mal += [f"«{k}» debe ser un texto" for k in CLAVES
            if k in x and not isinstance(x[k], str)]
    if mal:
        return mal
    if x['id'] != nombre:
        mal.append(f"el archivo debe llamarse {x['id']}.toml")
    if not re.fullmatch(r'[A-Za-z0-9-]{1,39}', x['cuenta']):
        mal.append("«cuenta» es tu usuario de GitHub, sin @")
    for k in ('repositorio', 'descarga'):
        if not re.fullmatch(r'https://[A-Za-z0-9.-]+/[!-~]{1,400}', x[k]):
            mal.append(f"«{k}» debe ser una dirección https://")
    if re.search(r'raw\.githubusercontent\.com/[^/]+/[^/]+/'
                 r'(refs/heads/|(main|master|dev|develop)/)|/archive/refs/heads/|'
                 r'/raw/(refs/heads/|(main|master|dev|develop)/)', x['descarga']):
        mal.append("«descarga» apunta a una rama, que cambia: usa una versión")
    if not re.fullmatch(r'[0-9a-f]{64}', x['sha256']):
        mal.append("«sha256» son 64 caracteres hexadecimales")
    return mal


def bajar(url: str, tope: int) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={
            'User-Agent': 'ingepresupuestos-complementos'}), timeout=60) as r:
        if not r.geturl().startswith('https://'):
            raise ValueError("no es https")
        b = r.read(tope + 1)
    if len(b) > tope:
        raise ValueError("demasiado grande")
    return b


def que_leer(paq) -> list[str]:
    """Lo que una persona debería mirar. Aquí mandar de más no estorba."""
    out = []
    for rel, b in paq.archivos.items():
        if not rel.endswith('.py'):
            continue
        propios = {Path(r).stem for r in paq.archivos if r.endswith('.py')}
        for n in ast.walk(ast.parse(b)):
            mods = ([a.name for a in n.names] if isinstance(n, ast.Import) else
                    [n.module or ''] if isinstance(n, ast.ImportFrom) and not n.level
                    else [])
            for m in mods:
                if m.split('.')[0] not in SIN_RIESGO | propios:
                    out.append(f"{rel}:{n.lineno} importa {m}")
            if isinstance(n, ast.ImportFrom):
                out += [f"{rel}:{n.lineno} importa {a.name}" for a in n.names
                        if a.name in PUERTAS | LLAMADAS]
            if isinstance(n, ast.Name) and n.id in LLAMADAS:
                out.append(f"{rel}:{n.lineno} usa {n.id}")
            if isinstance(n, (ast.Attribute, ast.Name)):
                t = n.attr if isinstance(n, ast.Attribute) else n.id
                if t in PUERTAS:
                    out.append(f"{rel}:{n.lineno} usa {t}")
                if t.startswith('__') and t.endswith('__') and t not in (
                        '__init__', '__name__', '__file__', '__doc__', '__post_init__'):
                    out.append(f"{rel}:{n.lineno} usa {t}")
    return out


def paquete_de(x: dict):
    """El paquete que está en la dirección de la ficha, comprobado."""
    from core.complementos import paquete
    b = bajar(x['descarga'], paquete.MAX_ZIP)
    sha = hashlib.sha256(b).hexdigest()
    if sha != x['sha256']:
        raise ValueError(f'la huella no coincide: ahí hay sha256 = "{sha}"')
    with tempfile.TemporaryDirectory() as d:
        z = Path(d) / 'x.zip'
        z.write_bytes(b)
        p = paquete.leer_zip(z)
    if p.id != x['id']:
        raise ValueError(f"el .zip es de «{p.id}»")
    if p.manifiesto['licencia'] not in LICENCIAS:
        raise ValueError("la licencia de complemento.json debe ser libre y en SPDX: "
                         + ", ".join(sorted(LICENCIAS)))
    return p


def publicados() -> dict:
    try:
        return {e['ficha']['id']: e for e in json.loads(
            (RAIZ / 'catalogo.json').read_text(encoding='utf-8'))['complementos']}
    except (OSError, ValueError, KeyError):
        return {}


def incluidos() -> set[str]:
    base = Path(sys.path[0]) / 'complementos'
    return {d.name for d in base.iterdir() if d.is_dir()} if base.is_dir() else set()


def comprobar(ids=()) -> int:
    from core.complementos import cli
    from core.complementos.gestor import es_mas_nueva
    mal, leer, antes = [], [], publicados()
    for f in sorted((RAIZ / 'fichas').iterdir()):
        if f.suffix != '.toml':
            if f.name != '.gitkeep':
                mal.append(f"{f.name}: en fichas/ solo van archivos .toml")
            continue
        if ids and f.stem not in ids:
            continue
        try:
            x = leer_toml(f)
            errores = campos(x, f.stem)
            if not errores:
                if f.stem in incluidos() and x['cuenta'] != OFICIAL:
                    errores.append("ese id es de un complemento incluido")
                p = paquete_de(x)
                e, avisos = cli.revisar(p)
                errores += e
                if p.manifiesto['autor'] == 'Tu nombre':
                    errores.append("autor: sigue siendo «Tu nombre»")
                v = antes.get(f.stem)
                if v and v['sha256'] != x['sha256'] and not es_mas_nueva(
                        p.manifiesto['version'], v['ficha']['version']):
                    errores.append("sube «version» en complemento.json: ya está "
                                   f"publicada la {v['ficha']['version']}")
                leer += [f"{f.stem}: {t}" for t in (*avisos, *que_leer(p))]
            mal += [f"{f.stem}: {e}" for e in errores]
        except Exception as e:  # noqa: BLE001 — todo lo ajeno se informa
            mal.append(f"{f.stem}: {e}")
    sin = set(leer_toml(RAIZ / 'revisados.toml')) - {
        f.stem for f in (RAIZ / 'fichas').glob('*.toml')}
    mal += [f"revisados.toml: «{k}» no tiene ficha" for k in sorted(sin)]
    if leer:
        print("Para leer antes de aprobar:", *leer, sep="\n  · ")
    if mal:
        print("Hay que corregir:", *mal, sep="\n  ✗ ")
        return 1
    print("Todo en orden.")
    return 3 if leer else 0


def armar() -> int:
    """Lo que no cambió no se vuelve a descargar; lo que falla se queda como
    estaba, para que un autor sin servicio no deje a los demás sin catálogo."""
    antes, rev, out = publicados(), leer_toml(RAIZ / 'revisados.toml'), []
    for f in sorted((RAIZ / 'fichas').glob('*.toml')):
        try:
            x = leer_toml(f)
            if campos(x, f.stem):
                raise ValueError("; ".join(campos(x, f.stem)))
            e = antes.get(f.stem)
            if not e or e['sha256'] != x['sha256']:
                p = paquete_de(x)
                e = {'ficha': {k: p.manifiesto[k] for k in CAMPOS_FICHA
                               if p.manifiesto[k] not in (None, '', [], {})},
                     'huella': p.huella}
            e = {**e, **{k: x[k] for k in ('repositorio', 'descarga', 'sha256')},
                 'revisado': rev.get(f.stem, {}).get('sha256') == x['sha256']}
            out.append(e)
        except Exception as e:  # noqa: BLE001
            print(f"{f.stem}: {e}", file=sys.stderr)
            if f.stem in antes:
                out.append({**antes[f.stem], 'revisado': False})
    (RAIZ / 'catalogo.json').write_text(
        json.dumps({'formato': 1, 'complementos': out}, ensure_ascii=False, indent=1,
                   sort_keys=True) + '\n', encoding='utf-8')
    print(len(out), "complementos")
    return 0


def decidir(cuenta: str, cambios: list[tuple[str, str]]) -> tuple[str, str]:
    """(id, '') si solo cambia la ficha que esa cuenta ya tiene en main."""
    if len(cambios) != 1:
        return '', "toca más de un archivo"
    estado, ruta = cambios[0]
    m = re.fullmatch(r'fichas/([a-z][a-z0-9-]{2,39})\.toml', ruta)
    if not m or estado != 'modified':
        return '', "no es la actualización de una ficha"
    try:
        x = leer_toml(RAIZ / 'fichas' / f'{m[1]}.toml')
    except (OSError, ValueError):
        return '', "su ficha no está en main"
    if str(x.get('cuenta', '')).lower() != cuenta.lower():
        return '', "la ficha es de otra cuenta"
    return m[1], ''


def main(a: list[str]) -> int:
    if a[:1] == ['comprobar']:
        return comprobar(a[1:])
    if a == ['armar']:
        return armar()
    if a[:1] == ['decidir'] and len(a) == 3:
        id_, por = decidir(a[1], [tuple(t.split('\t')) for t in Path(a[2]).read_text(
            encoding='utf-8').splitlines() if t])
        print(f"id={id_}") if id_ else print(f"Espera a una persona: {por}.",
                                             file=sys.stderr)
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
