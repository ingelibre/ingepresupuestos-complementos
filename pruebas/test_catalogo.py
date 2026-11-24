import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

E = importlib.util.spec_from_file_location(
    'cat', Path(__file__).parent.parent / 'herramientas' / 'catalogo.py')
cat = importlib.util.module_from_spec(E)
E.loader.exec_module(cat)
LIMPIO = 'from ingepresupuestos import api\ndef registrar(app): pass\n'


class Sitio:
    def __init__(self, tmp):
        self.tmp, self.web = tmp, {}

    def poner(self, id_='mi-prueba', version='1.0', py=LIMPIO, licencia='MIT', **k):
        from core.complementos import paquete
        d = self.tmp / 'src' / f'{id_}-{version}-{len(self.web)}'
        d.mkdir(parents=True)
        (d / 'complemento.json').write_text(json.dumps({
            'esquema': 1, 'id': id_, 'nombre': id_, 'version': version, 'autor': 'Ana',
            'licencia': licencia, 'api_version': 1, 'codigo': 'complemento.py'}))
        (d / 'complemento.py').write_text(py)
        z = paquete.empaquetar(d, d.with_suffix('.zip'))
        url = f'https://autor.example/{z.name}'
        self.web[url] = z.read_bytes()
        x = {'id': id_, 'cuenta': 'ana', 'repositorio': 'https://github.com/ana/r',
             'descarga': url, 'sha256': hashlib.sha256(self.web[url]).hexdigest(), **k}
        (cat.RAIZ / 'fichas' / f'{id_}.toml').write_text(
            ''.join(f'{a} = {json.dumps(b)}\n' for a, b in x.items()))
        return url


@pytest.fixture
def s(tmp_path, monkeypatch):
    (tmp_path / 'fichas').mkdir()
    (tmp_path / 'revisados.toml').write_text('')
    monkeypatch.setattr(cat, 'RAIZ', tmp_path)
    x = Sitio(tmp_path)
    monkeypatch.setattr(cat, 'bajar', lambda u, _t: x.web[u])
    return x


def _lista():
    return json.loads((cat.RAIZ / 'catalogo.json').read_text())['complementos']


def test_limpio(s):
    s.poner()
    assert cat.comprobar() == 0
    cat.armar()
    assert _lista()[0]['ficha']['version'] == '1.0' and not _lista()[0]['revisado']


@pytest.mark.parametrize('py', [
    'import os\n', 'import urllib.request\n', 'x = eval\n', 'open("x")\n',
    'y = ().__class__\n', 'from core import db\n', 'import sqlite3\n',
    'import re\nre.sys\n', 'from re import sys\n', 'from json import codecs as c\n'])
def test_lo_que_una_persona_debe_leer(s, py):
    s.poner(py=py + LIMPIO)
    assert cat.comprobar() == 3


@pytest.mark.parametrize('k', [
    {'sha256': '0' * 64}, {'sha256': 'x'}, {'descarga': 'http://a.example/x.zip'},
    {'descarga': 'https://raw.githubusercontent.com/a/b/main/x.zip'},
    {'licencia': 'Propietaria'}, {'cuenta': '@ana'}, {'otra': 'cosa'},
    {'py': 'def registrar(:\n'}, {'py': 'x = 1\n'}])
def test_mal(s, k):
    s.poner(**k)
    assert cat.comprobar() == 1


def test_un_incluido_es_solo_del_proyecto(s):
    s.poner('pais-brasil')
    assert cat.comprobar() == 1
    s.poner('pais-brasil', cuenta='ingelibre')
    assert cat.comprobar() == 0


def test_la_version_tiene_que_subir(s):
    s.poner()
    cat.armar()
    s.poner(py=LIMPIO + 'x = 1\n')
    assert cat.comprobar() == 1
    s.poner(version='1.1')
    assert cat.comprobar() == 0


def test_revisado_es_de_ese_archivo(s):
    s.poner()
    sha = cat.leer_toml(cat.RAIZ / 'fichas/mi-prueba.toml')['sha256']
    (cat.RAIZ / 'revisados.toml').write_text(f'[mi-prueba]\nsha256 = "{sha}"\n')
    cat.armar()
    assert _lista()[0]['revisado']
    s.poner(version='1.1')
    cat.armar()
    assert not _lista()[0]['revisado'] and _lista()[0]['ficha']['version'] == '1.1'


def test_un_autor_sin_servicio_no_tumba_a_los_demas(s):
    s.poner()
    cat.armar()
    u = s.poner(version='1.1')
    s.poner('otro-mas')
    del s.web[u]
    cat.armar()
    assert {e['ficha']['id']: e['ficha']['version'] for e in _lista()} == {
        'mi-prueba': '1.0', 'otro-mas': '1.0'}


def test_decidir(s):
    s.poner()
    f = 'fichas/mi-prueba.toml'
    assert cat.decidir('Ana', [('modified', f)])[0] == 'mi-prueba'
    for cuenta, c in (('eva', [('modified', f)]), ('ana', [('added', f)]),
                      ('ana', [('removed', f)]), ('ana', []),
                      ('ana', [('modified', f), ('modified', 'revisados.toml')]),
                      ('ana', [('modified', '.github/workflows/x.yml')]),
                      ('ana', [('modified', 'fichas/../x.toml')])):
        assert not cat.decidir(cuenta, c)[0]


def test_el_programa_lee_lo_que_se_arma(s):
    from core.complementos import catalogo
    if not hasattr(catalogo, 'descargar'):
        pytest.skip("programa anterior al catálogo")
    s.poner()
    cat.armar()
    x, = catalogo.leer_catalogo((cat.RAIZ / 'catalogo.json').read_bytes())
    assert x['ficha']['id'] == 'mi-prueba'
