import difflib
import xml.etree.ElementTree as ET
from copy import copy
from glob import glob
from pathlib import Path

import xarray as xr


class Variable:
    def __init__(self, variable):
        self.variable = variable
        self.destination_name = self.variable.find("destinationName").text
        self.source_name = self.variable.find("sourceName").text
        self.data_type = self.variable.find("dataType").text
        self.attrs = self._get_attrs()

    def _get_attrs(self):
        return {
            item.tag: item.text for item in self.variable.findall("addAttributes/att")
        }


class Dataset:
    def __init__(self, dataset: ET.Element):
        self.dataset = dataset
        self.type = self.dataset.attrib["type"]
        self.dataset_id = self.dataset.attrib["datasetID"]
        self.active = self.dataset.attrib.get("active", "true") == "true"
        self.attrs = self._get_global_attributes()
        self.variables = self._get_variables()

    def _get_global_attributes(self):
        return {
            item.attrib["name"]: item.text
            for item in self.dataset.findall(".//addAttributes/att")
        }

    def _get_variables(self):
        return {
            item.find("destinationName").text: Variable(item)
            for item in self.dataset.findall(".//dataVariable")
        }

    def to_xarray(self):
        """Convert a Dataset object to an xarray Dataset"""
        # TODO generate an empty netcdf sample of the resulting dataset and run compliance checker on it
        vars = {
            var.destination_name: xr.DataArray(data=None, attrs=var.attrs)
            for var in self.variables.values()
        }
        return xr.Dataset(vars=vars, attrs=self.attrs)

    def to_xml(self, output=None):
        return ET.tostring(self.dataset).decode("UTF-8")


class Erddap:
    def __init__(self, datasets_xml=None, encoding="UTF-8", recursive: bool = True):
        self.datasets_xml = datasets_xml
        self.recursive = recursive
        self.encoding = encoding
        self.load()

    def diff(self, other):
        """Compare two Erddap objects and return a list of datasets that are different"""
        other_erddap = other if isinstance(other, Erddap) else Erddap(other)
        return {
            datasetID: difflib.context_diff(
                dataset.to_xml(), other_erddap.datasets.get(datasetID).to_xml()
            )
            for datasetID, dataset in self.datasets.items()
            if dataset == other_erddap.datasets.get(datasetID)
        }

    def to_xml(self, output=None, secrets: dict = None):
        """Write the Erddap object to xml"""
        xml = f'<?xml version="1.0" encoding="{self.encoding}"?>\n' + ET.tostring(
            self.tree, encoding=self.encoding
        ).decode(self.encoding)

        # handle secrets
        for key, value in (secrets or {}).items():
            xml = xml.replace(f"{{{key}}}", value)

        if output is None:
            return xml
        Path(output).write_text(xml, encoding=self.encoding)

    def copy(self):
        """Get a copy of the Erddap object"""
        return copy(self)

    def _parse_datasets(self):
        datasets_xml = "\n".join(
            [
                Path(file).read_text(encoding=self.encoding)
                for file in (
                    self.datasets_xml
                    if isinstance(self.datasets_xml, list)
                    else glob(self.datasets_xml, recursive=self.recursive)
                )
            ]
        )
        if (
            "<erddapDatasets>" not in datasets_xml
            and "</erddapDatasets>" not in datasets_xml
        ):
            datasets_xml = self._wrap_datasets(datasets_xml)
        try:
            return ET.fromstring(datasets_xml)
        except ET.ParseError as e:
            raise ValueError("Failed to parse datasets.xml: {}", e)

    def _wrap_datasets(self, datasets: str, encoding="UTF-8"):
        return f'<?xml version="1.0" encoding="{encoding}"?><erddapDatasets>{datasets}</erddapDatasets>'

    def _get_datasets(self):
        return self.tree.findall("dataset")

    def _get_dataset_variables(self, dataset, key="destinationName"):
        return [item.text for item in dataset.findall(f".//dataVariable/{key}")]

    def load(self):
        self.tree = self._parse_datasets()
        self.datasets = {
            item.attrib["datasetID"]: Dataset(item) for item in self._get_datasets()
        }
