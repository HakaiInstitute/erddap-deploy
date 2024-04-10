import difflib
import os
import xml.etree.ElementTree as ET
from copy import copy
from glob import glob
from pathlib import Path
from typing import Union

import xarray as xr
from loguru import logger


class Variable:
    @logger.catch(reraise=True)
    def __init__(self, variable):
        self.variable = variable

        destination_name = self.variable.find("destinationName")
        self.destination_name = (
            destination_name.text.strip() if destination_name is not None else None
        )

        source_name = self.variable.find("sourceName")
        self.source_name = source_name.text.strip() if source_name is not None else None

        data_type = self.variable.find("dataType")
        self.data_type = data_type.text.strip() if data_type is not None else None

        self.attrs = self._get_attrs()

    def __repr__(self) -> str:
        return (
            f"<sourceName={self.source_name} destinationName={self.destination_name}>"
        )

    def _get_attrs(self):
        return {
            item.attrib["name"]: item.text
            for item in self.variable.findall(".//addAttributes/att")
        }


class Dataset:
    @logger.catch(reraise=True)
    def __init__(self, dataset: ET.Element):
        self.dataset = dataset
        self.type = self.dataset.attrib["type"]
        self.dataset_id = self.dataset.attrib["datasetID"]
        self.active = self.dataset.attrib.get("active", "true") == "true"
        self.attrs = self._get_global_attributes()
        self.variables = self._get_variables()

    def __repr__(self) -> str:
        return f"<datasetID={self.dataset_id}>"

    def __str__(self) -> str:
        return self.to_xml()

    def __equal__(self, other):
        if not isinstance(other, Erddap):
            return False
        return self.to_xml() == other.to_xml()

    def _get_global_attributes(self):
        return {
            item.attrib["name"]: item.text
            for item in self.dataset.findall(".//addAttributes/att")
        }

    def _get_variables(self):
        return [Variable(item) for item in self.dataset.findall(".//dataVariable")]

    def to_xarray(self):
        """Convert a Dataset object to an xarray Dataset"""
        # TODO generate an empty netcdf sample of the resulting dataset and
        # run compliance checker on it
        vars = {
            var.destination_name: xr.DataArray(data=None, attrs=var.attrs)
            for var in self.variables.values()
        }
        return xr.Dataset(vars=vars, attrs=self.attrs)

    def to_xml(self, output=None):
        return ET.tostring(self.dataset).decode("UTF-8")

    def get_variables_destination_names(self):
        return [var.destination_name or var.source_name for var in self.variables]

    def get_variables_source_names(self):
        return [var.source_name for var in self.variables]


class Erddap:
    def __init__(
        self,
        datasets_xml_dir,
        setup_xml_dir: str = "**/setup.xml",
        secrets: dict = None,
        encoding: str = "UTF-8",
        recursive: bool = True,
        lazy_load: bool = False,
    ):
        self.datasets_xml_dir = datasets_xml_dir
        self.setup_xml_dir = setup_xml_dir
        self.recursive = recursive
        self.encoding = encoding
        self.secrets = {**self._get_env_secrets(), **(secrets or {})}
        self.datasets_xml = None
        self.setup = None
        self.tree = None
        self.datasets = {}
        if not lazy_load:
            self.load()

    @staticmethod
    def _get_env_secrets():
        """Get secrets from environment variables and merge them with the provided secrets.
        Ignore ERDDAP_SECRET_ prefix."""
        secrets = {
            key.replace("ERDDAP_SECRET_", ""): value
            for key, value in os.environ.items()
            if key.startswith("ERDDAP_SECRET_")
        }
        if not secrets:
            return {}

        logger.debug("Found Environment Variables Secrets: {}", list(secrets.keys()))
        return secrets

    def _load_datasets_xml(self):
        """Load datasets.xml from dataset_xml_dir and wrap it in <erddapDatasets> if necessary"""
        search_path = [
            search
            for search in self.datasets_xml_dir.split("|")
            if glob(search, recursive=self.recursive)
        ]
        if not search_path:
            logger.warning(
                "No datasets.xml found with search path {} recursive={}",
                self.datasets_xml_dir.split("|"),
                self.recursive,
            )
            return
        xml_files = [files for files in glob(search_path[0], recursive=self.recursive)]
        logger.info(
            "Found {} files matching datasets.xml with search path {}: {}",
            len(xml_files),
            search_path[0],
            xml_files,
        )
        datasets_xml = "\n".join(
            [Path(file).read_text(encoding=self.encoding) for file in xml_files]
        )
        if (
            "<erddapDatasets>" not in datasets_xml
            and "</erddapDatasets>" not in datasets_xml
        ):
            datasets_xml = f'<?xml version="1.0" encoding="{self.encoding}"?><erddapDatasets>{datasets_xml}</erddapDatasets>'

        self.datasets_xml = datasets_xml

    def _replace_secrets(self):
        """Replace secrets in the datasets_xml"""
        for key, value in self.secrets.items():
            if key in self.datasets_xml:
                count = self.datasets_xml.count(key)
                logger.debug("Replace {} x {}", count, key)
                self.datasets_xml = self.datasets_xml.replace(key, value)
            else:
                logger.warning("Secret {} not found in datasets.xml", key)

    def _parse_datasets(self):
        """Parse datasets.xml and return the tree"""
        try:
            self.tree = ET.fromstring(self.datasets_xml)
        except ET.ParseError as e:
            raise ValueError("Failed to parse datasets.xml: {}", e)

    def _get_datasets(self):
        if self.tree is None:
            raise ValueError("No datasets.xml parsed")
        self.datasets = {
            item.attrib["datasetID"]: Dataset(item)
            for item in self.tree.findall("dataset")
        }

    @logger.catch(reraise=True)
    def load(self):
        """Load datasets.xml file(s), add secrets and parse it into a dictionary of Dataset objects"""
        self._load_datasets_xml()
        if self.datasets_xml is None:
            logger.warning(
                "No datasets.xml file(s) found for: {}, recursive={}",
                self.datasets_xml_dir,
                self.recursive,
            )
            return
        self._replace_secrets()
        self._parse_datasets()
        self._get_datasets()
        logger.info("Loaded {} datasets", len(self.datasets.keys()))
        return self

    @logger.catch
    def diff(self, other):
        """Compare two Erddap objects and return a list of datasets that are different"""
        other_erddap = other if isinstance(other, Erddap) else Erddap(other)
        datasetIDs = set(self.datasets.keys()) | set(other_erddap.datasets.keys())
        differences = {}
        for datasetID in datasetIDs:
            if datasetID not in self.datasets:
                differences[datasetID] = f"{datasetID} not in self"
            elif datasetID not in other_erddap.datasets:
                differences[datasetID] = f"{datasetID} not in other"
            elif (
                self.datasets.get(datasetID).to_xml()
                != other_erddap.datasets.get(datasetID).to_xml()
            ):
                differences[datasetID] = difflib.context_diff(
                    str(self.datasets.get(datasetID)),
                    str(other_erddap.datasets.get(datasetID)),
                )
        return differences

    @logger.catch
    def save(
        self, output: Union[str, Path], source: str = "original", encoding: str = None
    ):
        """Write datasets.xml to a file

        Args:
            output (str): Path to the output file
            source (str): Source of the datasets.xml. Can be "original" or "parsed"
            encoding (str): Encoding of the output file
        """
        encoding = encoding or self.encoding

        if self.datasets_xml is None:
            return logger.warning("No datasets.xml to save")
        elif source == "original":
            if encoding and encoding != self.encoding:
                raise ValueError(
                    f"Cannot change encoding from {self.encoding} to {encoding} when source is original"
                )

            Path(output).write_text(self.datasets_xml, encoding=self.encoding)
        elif source == "parsed":
            Path(output).write_text(
                f'<?xml version="1.0" encoding="{encoding}"?>\n'
                + ET.tostring(self.tree, encoding=encoding).decode(encoding),
                encoding=encoding,
            )

    def copy(self):
        """Get a copy of the Erddap object"""
        return copy(self)


# https://cfconventions.org/Data/cf-conventions/cf-conventions-1.8/cf-conventions.html#discrete-sampling-geometries
CDM_DATA_TYPES = (
    "Grid",
    "Point",
    "Trajectory",
    "Profile",
    "TimeSeries",
    "TimeSeriesProfile",
    "Other",
)

# https://coastwatch.pfeg.noaa.gov/erddap/download/setupDatasetsXml.html#ioos_category
IOOS_CATEGORIES = (
    "Bathymetry",
    "Biology",
    "Bottom Character",
    "CO2",
    "Colored Dissolved Organic Matter",
    "Contaminants",
    "Currents",
    "Dissolved Nutrients",
    "Dissolved O2",
    "Ecology",
    "Fish Abundance",
    "Fish Species",
    "Heat Flux",
    "Hydrology",
    "Ice Distribution",
    "Identifier",
    "Location",
    "Meteorology",
    "Ocean Color",
    "Optical Properties",
    "Other",
    "Pathogens",
    "Physical Oceanography",
    "Phytoplankton Species",
    "Pressure",
    "Productivity",
    "Quality",
    "Salinity",
    "Sea Level",
    "Statistics",
    "Stream Flow",
    "Surface Waves",
    "Taxonomy",
    "Temperature",
    "Time",
    "Total Suspended Matter",
    "Unknown",
    "Wind",
    "Zooplankton Species",
    "Zooplankton Abundance",
)

EDD_TYPES = (
    "EDDGridAggregateExistingDimension",
    "EDDGridFromEtopo",
    "EDDGridSideBySide",
    "EDDTableFromEML",
    "EDDGridFromAudioFiles",
    "EDDTableFromEMLBatch",
    "EDDGridFromDap",
    "EDDTableFromErddap",
    "EDDGridFromEDDTable",
    "EDDTableFromFileNames",
    "EDDGridFromErddap",
    "EDDTableFromHttpGet",
    "EDDGridFromMergeIRFiles",
    "EDDTableFromInPort",
    "EDDGridFromNcFiles",
    "EDDTableFromIoosSOS",
    "EDDGridFromNcFilesUnpacked",
    "EDDTableFromJsonlCSVFiles",
    "EDDGridFromThreddsCatalog",
    "EDDTableFromMultidimNcFiles",
    "EDDGridLonPM180FromErddapCatalog",
    "EDDTableFromNcFiles",
    "EDDGridLon0360FromErddapCatalog",
    "EDDTableFromNcCFFiles",
    "EDDTableFromAsciiFiles",
    "EDDTableFromNccsvFiles",
    "EDDTableFromAudioFiles",
    "EDDTableFromOBIS",
    "EDDTableFromAwsXmlFiles",
    "EDDTableFromSOS",
    "EDDTableFromBCODMO",
    "EDDTableFromThreddsFiles",
    "EDDTableFromCassandra",
    "EDDTableFromWFSFiles",
    "EDDTableFromColumnarAsciiFiles",
    "EDDsFromFiles",
    "EDDTableFromDapSequence",
    "EDDTableFromDatabase",
    "EDDTableFromEDDGrid",
)
