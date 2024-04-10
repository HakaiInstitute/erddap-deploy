import os

import pytest
from loguru import logger

from erddap_deploy.erddap import CDM_DATA_TYPES, IOOS_CATEGORIES, Erddap

erddap = Erddap(os.environ.get("ERDDAP_DATASETS_XML", "tests/data/datasets.d/*.xml"))


@pytest.fixture(
    scope="module",
    params=erddap.datasets.values(),
    ids=erddap.datasets.keys(),
)
def dataset(request):
    yield request.param
    logger.info(f"Finished testing {request.param.dataset_id}")


class TestDatasetGlobalAttributes:
    def test_dataset_cdm_data_type(self, dataset):
        """Test that cdm_data_type is valid"""
        if dataset.type == "EDDTableFromErddap" or dataset.type.startswith("EDDGrid"):
            return
        assert dataset.attrs["cdm_data_type"].lower() in [
            item.lower() for item in CDM_DATA_TYPES
        ], f"Dataset {dataset.dataset_id} has invalid cdm_data_type {dataset.attrs['cdm_data_type']}"
        # TODO should cdm_data_type be case insensitive?

    def test_dataset_subset_variables(self, dataset):
        """Test that subsetVariables are valid variables in the dataset"""
        if dataset.type in ("EDDTableFromErddap") or dataset.type.startswith("EDDGrid"):
            return
        subset_variables = dataset.attrs.get("subsetVariables", "").split(",")
        unknown_variables = [
            var
            for var in subset_variables
            if var.strip() not in dataset.get_variables_destination_names() and var
        ]
        assert (
            not unknown_variables
        ), f"Dataset {dataset.dataset_id} has invalid subsetVariables {unknown_variables}"

    def test_dataset_cdm_timeseries_variables(self, dataset):
        """Test that cdm_timeseries_variables are valid variables in the dataset"""

        if dataset.type in (
            "EDDTableFromErddap",
            "EDDTableFromSOS",
        ) or dataset.type.startswith("EDDGrid"):
            return
        elif dataset.attrs["cdm_data_type"] not in ("TimeSeries", "TimeSeriesProfile"):
            return

        cdm_timeseries_variables = dataset.attrs.get(
            "cdm_timeseries_variables", ""
        ).split(",")
        assert (
            cdm_timeseries_variables
        ), f"{dataset.dataset_id=} has no cdm_timeseries_variables"
        unknown_variables = [
            var
            for var in cdm_timeseries_variables
            if var.strip() not in dataset.get_variables_destination_names() and var
        ]
        assert (
            not unknown_variables
        ), f"{dataset.dataset_id=} has invalid cdm_timeseries_variables {unknown_variables}"

    def test_dataset_cdm_profile_variables(self, dataset):
        """Test that cdm_profile_variables are valid variables in the dataset"""
        if dataset.type == "EDDTableFromErddap" or dataset.type.startswith("EDDGrid"):
            return
        elif dataset.attrs["cdm_data_type"] not in ("Profile", "TimeSeriesProfile"):
            return
        cdm_profile_variables = dataset.attrs.get("cdm_profile_variables", "").split(
            ","
        )
        assert (
            cdm_profile_variables
        ), f"{dataset.dataset_id=} has no cdm_profile_variables"
        unknown_variables = [
            var
            for var in cdm_profile_variables
            if var.strip() not in dataset.get_variables_destination_names() and var
        ]
        assert (
            not unknown_variables
        ), f"{dataset.dataset_id=} has invalid cdm_profile_variables {unknown_variables}"


class TestDatasetsVariablesAttributes:
    def test_variable_ioos_category(self, dataset):
        """Test that ERDDAP ioos_category is valid"""
        ioos_category_required = os.getenv(
            "ERDDAP_variablesMustHaveIoosCategory", "false"
        ) in ("true", "True", 1, "1")
        if not ioos_category_required:
            return

        for variable in dataset.variables.values():
            if variable.destination_name in ("latitude", "longitude", "time", "depth"):
                continue
            assert (
                variable.attrs.get("ioos_category") in IOOS_CATEGORIES
            ), f"{variable.destination_name=} in {dataset.dataset_id=} has invalid {variable.attrs.get('ioos_category')=}"


if __name__ == "__main__":
    pytest.main()
