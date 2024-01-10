import click
import pytest
from erddap_checks.erddap import Erddap
import os


def datasets():
    if datasets_xml := os.environ.get("ERDDAP_DATASETS_XML"):
        return Erddap(datasets_xml=datasets_xml).datasets
    elif datasets_d := os.environ.get("ERDDAP_DATASETS_D"):
        return Erddap(datasets_d=datasets_d).datasets
    elif Path("datasets.d").exists():
        return Erddap(datasets_d="datasets.d/*.xml").datasets
    elif datasets_xml := list(Path(".").glob("**/datasets.xml")):
        return Erddap(datasets_xml=datasets_xml[0]).datasets
    elif datasets_d := list(Path(".").glob("**/datasets.d")):
        return Erddap(datasets_d=str(datasets_d[0]) + "/*.xml").datasets
    else:
        raise ValueError("No datasets specified")


@click.command()
@click.option("--datasets-xml", help="Path to datasets.xml", type=str)
@click.option("--datasets-d", help="Glob expression to datasets.d/*.xml", type=str)
def main(datasets_xml,datasets_d):
    if datasets_d:
        os.environ['ERDDAP_DATASETS_D'] = datasets_d
    if datasets_xml:
        os.environ['ERDDAP_DATASETS_XML'] = datasets_xml
    pytest.main([])

if __name__ == "__main__":
    main()