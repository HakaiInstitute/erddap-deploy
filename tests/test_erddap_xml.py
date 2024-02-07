import pytest

from erddap_deploy.erddap import Erddap


@pytest.fixture
def erddap():
    return Erddap(datasets_xml_dir="tests/data/datasets.d/*.xml", recursive=False)


def test_erddap_init(erddap):
    assert erddap.datasets_xml_dir == "tests/data/datasets.d/*.xml"
    assert erddap.recursive == False
    assert erddap.encoding == "UTF-8"
    assert erddap.secrets == {}


def test_erddap_load(erddap):
    erddap.load()
    assert len(erddap.datasets) == 3
    assert "dataset1" in erddap.datasets
    assert "dataset2" in erddap.datasets
    assert "dataset3" in erddap.datasets
    assert "dataset4" not in erddap.datasets


def test_erddap_load_recursive():
    erddap = Erddap(datasets_xml_dir="tests/data/**/*.xml", recursive=True)
    erddap.load()
    assert len(erddap.datasets) == 4
    assert "dataset1" in erddap.datasets
    assert "dataset2" in erddap.datasets
    assert "dataset3" in erddap.datasets
    assert "dataset4" in erddap.datasets


def test_erddap_load_lazy():
    erddap = Erddap(
        datasets_xml_dir="tests/data/**/*.xml", recursive=True, lazy_load=True
    )
    assert len(erddap.datasets) == 0
    erddap.load()
    assert len(erddap.datasets) == 4
    assert "dataset1" in erddap.datasets
    assert "dataset2" in erddap.datasets
    assert "dataset3" in erddap.datasets
    assert "dataset4" in erddap.datasets


def test_erddap_load_secrets():
    erddap = Erddap(
        datasets_xml_dir="tests/data/**/*.xml", recursive=True, secrets={"test": "test"}
    )
    assert len(erddap.secrets) == 1
    assert "test" in erddap.secrets
    assert erddap.secrets["test"] == "test"


def test_erddap_load_secrets_env(monkeypatch):
    monkeypatch.setenv("ERDDAP_SECRET_test", "test")
    erddap = Erddap(datasets_xml_dir="tests/data/**/*.xml", recursive=True)
    assert len(erddap.secrets) == 1
    assert "test" in erddap.secrets
    assert erddap.secrets["test"] == "test"
    monkeypatch.delenv("ERDDAP_SECRET_test")


def test_erddap_load_secrets_env_override(monkeypatch):
    monkeypatch.setenv("ERDDAP_SECRET_test", "test")
    erddap = Erddap(
        datasets_xml_dir="tests/data/**/*.xml",
        recursive=True,
        secrets={"test": "test2"},
    )
    assert len(erddap.secrets) == 1
    assert "test" in erddap.secrets
    assert erddap.secrets["test"] == "test2"


def test_erddap_load_secrets_env_prefix(monkeypatch):
    monkeypatch.setenv("ERDDAP_SECRET_test", "test")
    monkeypatch.setenv("ERDDAP_SECRET_test2", "test2")
    erddap = Erddap(datasets_xml_dir="tests/data/**/*.xml", recursive=True)
    assert len(erddap.secrets) == 2
    assert "test" in erddap.secrets
    assert erddap.secrets["test"] == "test"
    assert "test2" in erddap.secrets
    assert erddap.secrets["test2"] == "test2"
    monkeypatch.delenv("ERDDAP_SECRET_test")
    monkeypatch.delenv("ERDDAP_SECRET_test2")


def test_secret_in_datasets_xml():
    """Verify that secrets are replaced in datasets_xml"""
    erddap = Erddap(
        datasets_xml_dir="tests/data/datasets.d/*.xml",
        recursive=False,
        secrets={"TEST_SECRET": "TEST_VALUE"},
    )
    erddap.load()
    assert "TEST_SECRET" not in erddap.datasets_xml
    assert "TEST_VALUE" in erddap.datasets_xml
