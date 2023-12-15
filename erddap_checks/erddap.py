import glob
import xml.etree.ElementTree as ET
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
        vars = {var.destination_name: xr.DataArray(data=None, attrs=var.attrs) for var in self.variables.values()}
        return xr.Dataset(vars=vars, attrs=self.attrs)


class Erddap:
    def __init__(self, datasets_xml=None, datasets_d=None):
        self.datasets_xml = datasets_xml
        self.datasets_d = datasets_d
        self.tree = self._parse_datasets()
        self.datasets = {
            item.attrib["datasetID"]: Dataset(item) for item in self._get_datasets()
        }

    def _parse_datasets(self):
        if self.datasets_xml:
            datasets_xml = Path(self.datasets_xml).read_text(encoding="UTF-8")
        elif self.datasets_d:
            datasets_xml = self._concatenate_xml(self.datasets_d)
        else:
            raise ValueError("Must provide either datasets_xml or datasets_d")
        return ET.fromstring(datasets_xml)

    def _concatenate_xml(self, datasets_d):
        xml_files = glob.glob(datasets_d)
        datasets_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        datasets_xml += "<erddapDatasets>\n"
        datasets_xml += "n".join(
            [Path(file).read_text(encoding="UTF-8") for file in xml_files]
        )
        datasets_xml += "</erddapDatasets>\n"
        return datasets_xml

    def _get_datasets(self):
        return self.tree.findall("dataset")

    def _get_dataset_variables(self, dataset, key="destinationName"):
        return [item.text for item in dataset.findall(f".//dataVariable/{key}")]
