import os
from glob import glob

import click
import pytest
from loguru import logger

from erddap_checks.erddap import Erddap


@click.command()
@click.argument("datasets_xml", envvar="ERDDAP_DATASETS_XML", type=str, nargs=-1)
@click.option("-k", "--test-filter", help="Run tests by keyword expressions", type=str)
def main(datasets_xml, test_filter):
    """Run a series of tests on ERDDAP datasets"""
    if datasets_xml:
        if len(datasets_xml) > 1:
            raise ValueError("Only one path can be specified")
        datasets_xml = datasets_xml[0]
    elif glob("**/datasets.xml", recursive=True):
        logger.info("Load **/datasets.xml")
        datasets_xml = "**/datasets.xml"
    elif glob("**/datasets.d/*.xml", recursive=True):
        logger.info("Load **/datasets.d/*.xml folder")
        datasets_xml = "**/datasets.d/*.xml"
    else:
        raise ValueError("No datasets.xml found")

    logger.info(f"Load datasets_xml={datasets_xml}")
    os.environ["ERDDAP_DATASETS_XML"] = datasets_xml
    args = ["--pyargs", "erddap_checks"]
    if test_filter:
        args.extend(["-k", test_filter])
    logger.info(f"Run pytest.main({args})")
    return pytest.main(args)


if __name__ == "__main__":
    main()
