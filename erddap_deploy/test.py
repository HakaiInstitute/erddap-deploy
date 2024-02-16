import os

import click
import pytest
from loguru import logger


@click.command()
@click.option(
    "-k",
    "--test-filter",
    help="Run tests by keyword expressions",
    type=str,
    default=None,
    envvar="ERDDAP_TEST_FILTER",
)
@click.option(
    "--active",
    help="Run tests on active datasets.xml, otherwise default to reference",
    type=bool,
    default=False,
    is_flag=True,
    envvar="ERDDAP_TEST_ACTIVE",
)
@click.pass_context
@logger.catch(reraise=True)
def test(ctx, test_filter, active):
    """Run a series of tests on repo ERDDAP datasets"""

    os.environ["ERDDAP_DATASETS_XML"] = (
        ctx.obj["active_datasets_xml"] if active else ctx.obj["datasets_xml"]
    )

    args = ["--pyargs", "erddap_deploy"]
    if test_filter:
        args.extend(["-k", test_filter])
    logger.info(f"Run pytest.main({args})")
    result = pytest.main(args).value
    if result:
        raise SystemExit(result)
