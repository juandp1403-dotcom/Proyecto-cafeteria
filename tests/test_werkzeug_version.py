"""
Regresion HU-42: Werkzeug 3.0.3 tenia dos CVE publicos (CVE-2024-49766,
CVE-2024-49767), corregidos en 3.0.6.
"""
from importlib.metadata import version
from packaging.version import Version


def test_werkzeug_version_corrige_cve_conocidos():
    assert Version(version('werkzeug')) >= Version('3.0.6')
