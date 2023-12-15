import pytest
from erddap import Erddap


class TestCdmDataType:
    @pytest.mark.parametrize(
        "dataset",
        Erddap(datasets_d="tests/data/datasets.d/*.xml").datasets.values(),
    )
    def test_dataset_cdm_data_type(self, dataset):
        """Test that cdm_data_type is valid"""
        assert dataset.attrs["cdm_data_type"] in (
            "Grid",
            "Point",
            "Trajectory",
            "Profile",
            "TimeSeries",
            "Timeseries",  # TODO should we accept that?
            "TimeSeriesProfile",
        ), f"Dataset {dataset.dataset_id} has invalid cdm_data_type {dataset.attrs['cdm_data_type']}"

    @pytest.mark.parametrize(
        "dataset",
        Erddap(datasets_d="tests/data/datasets.d/*.xml").datasets.values(),
    )
    def test_dataset_subset_variables(self, dataset):
        """Test that subsetVariables are valid variables in the dataset"""
        subset_variables = dataset.attrs.get("subsetVariables", "").split(",")
        unknown_variables = [
            var
            for var in subset_variables
            if var.strip() not in dataset.variables and var
        ]
        assert (
            not unknown_variables
        ), f"Dataset {dataset.dataset_id} has invalid subsetVariables {unknown_variables}"

    @pytest.mark.parametrize(
        "dataset",
        [
            dataset
            for dataset in Erddap(
                datasets_d="tests/data/datasets.d/*.xml"
            ).datasets.values()
            if dataset.attrs["cdm_data_type"] in ("TimeSeries", "TimeSeriesProfile")
        ],
    )
    def test_dataset_cdm_timeseries_variables(self, dataset):
        """Test that cdm_timeseries_variables are valid variables in the dataset"""
        cdm_timeseries_variables = dataset.attrs.get(
            "cdm_timeseries_variables", ""
        ).split(",")
        assert (
            cdm_timeseries_variables
        ), f"Dataset {dataset.dataset_id} has no cdm_timeseries_variables"
        unknown_variables = [
            var
            for var in cdm_timeseries_variables
            if var.strip() not in dataset.variables and var
        ]
        assert (
            not unknown_variables
        ), f"Dataset {dataset.dataset_id} has invalid cdm_timeseries_variables {unknown_variables}"

    @pytest.mark.parametrize(
        "dataset",
        [
            dataset
            for dataset in Erddap(
                datasets_d="tests/data/datasets.d/*.xml"
            ).datasets.values()
            if dataset.attrs["cdm_data_type"] in ("Profile", "TimeSeriesProfile")
        ],
    )
    def test_dataset_cdm_profile_variables(self, dataset):
        """Test that cdm_profile_variables are valid variables in the dataset"""
        cdm_profile_variables = dataset.attrs.get("cdm_profile_variables", "").split(
            ","
        )
        assert (
            cdm_profile_variables
        ), f"Dataset {dataset.dataset_id} has no cdm_profile_variables"
        unknown_variables = [
            var
            for var in cdm_profile_variables
            if var.strip() not in dataset.variables and var
        ]
        assert (
            not unknown_variables
        ), f"Dataset {dataset.dataset_id} has invalid cdm_profile_variables {unknown_variables}"
