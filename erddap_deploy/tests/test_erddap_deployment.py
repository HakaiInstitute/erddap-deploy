import os

import pytest

from erddap_deploy.erddap import EDD_TYPES, Erddap

erddap_test = Erddap(
    os.environ.get("ERDDAP_DATASETS_XML", "tests/data/datasets.d/*.xml")
)


@pytest.fixture(scope="module")
def erddap():
    yield erddap_test


class TestDatasets:
    def test_datasets_ids(self, erddap):
        """Test that dataset_ids are unique"""
        assert len(erddap.datasets.keys()) == len(
            set(erddap.datasets.keys())
        ), "Dataset IDs are not unique"

    def test_datasets_xml(self, erddap):
        """Test that datasets_xml is not empty"""
        assert erddap.datasets_xml, "datasets_xml is empty"

    def test_datasets(self, erddap):
        """Test that datasets is not empty"""
        assert erddap.datasets, "datasets is empty"

    def test_datasets_types(self, erddap):
        """Test that datasets types are valid"""
        for dataset in erddap.datasets.values():
            assert (
                dataset.type in EDD_TYPES
            ), f"Dataset {dataset.dataset_id} has invalid type {dataset.type}"
