import pytest
from erddap import Erddap

erddap = Erddap()


@pytest.fixture(
    scope="module",
    params=erddap.datasets.values(),
    ids=erddap.datasets.keys(),
)
def dataset(request):
    yield request.param
    print(f"Finished testing {request.param.dataset_id}")


@pytest.mark.skipif(dataset == None, reason="No datasets specified")
class TestDatasetGlobalAttributes:
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

    def test_dataset_cdm_timeseries_variables(self, dataset):
        """Test that cdm_timeseries_variables are valid variables in the dataset"""

        if dataset.attrs["cdm_data_type"] not in ("TimeSeries", "TimeSeriesProfile"):
            return

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

    def test_dataset_cdm_profile_variables(self, dataset):
        """Test that cdm_profile_variables are valid variables in the dataset"""
        if dataset.attrs["cdm_data_type"] not in ("Profile", "TimeSeriesProfile"):
            return
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


if __name__ == "__main__":
    pytest.main()
