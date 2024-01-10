import os
from glob import glob

import click
import pytest

from erddap_checks.erddap import Erddap


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
@click.option(
    "--datasets-xml",
    help="Path to datasets.xml",
    default="**/datasets.xml",
    envvar="ERDDAP_DATASETS_XML",
    show_default=True,
    type=str,
)
@click.option(
    "--datasets-d",
    help="Glob expression to datasets.d/*.xml",
    default="datasets.d/*.xml",
    envvar="ERDDAP_DATASETS_D",
    show_default=True,
    type=str,
)
@click.option("-k", help="Run tests by keyword expressions", type=str)
def main(datasets_xml, datasets_d, k):
    """Run a series of tests on ERDDAP datasets"""
    if datasets_d and glob(datasets_d):
        os.environ["ERDDAP_DATASETS_D"] = datasets_d
    if datasets_xml and glob(datasets_xml):
        os.environ["ERDDAP_DATASETS_XML"] = glob(datasets_xml)[0]
    args = []
    if k:
        args.extend(["-k", k])
    pytest.main(args)


if __name__ == "__main__":
    main()
