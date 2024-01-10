import os
from glob import glob

import click
import pytest
from loguru import logger

from erddap_checks.erddap import Erddap


@click.command()
@click.argument(
    "datasets_xml",
    envvar="ERDDAP_DATASETS_XML",
    type=str,
    nargs=-1,
)
@click.option("-k", "--test-filter", help="Run tests by keyword expressions", type=str)
def main(datasets_xml, test_filter):
    """Run a series of tests on ERDDAP datasets"""
    if not datasets_xml and glob("**/datasets.xml", recursive=True):
        logger.info("Load **/datasets.xml")
        datasets_xml = "**/datasets.xml"
    elif not datasets_xml and glob("**/datasets.d/*.xml", recursive=True):
        logger.info("Load **/datasets.d/*.xml folder")
        datasets_xml = "**/datasets.d/*.xml"
    else:
        raise ValueError("No datasets.xml found")

    os.environ["ERDDAP_DATASETS_XML"] = datasets_xml
    args = []
    if test_filter:
        args.extend(["-k", test_filter])
    pytest.main(args)


if __name__ == "__main__":
    main()
