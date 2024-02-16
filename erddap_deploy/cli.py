import json
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from loguru import logger

from erddap_deploy.erddap import Erddap
from erddap_deploy.monitor import monitor
from erddap_deploy.sync import sync
from erddap_deploy.test import test

# load .env file if available
load_dotenv(".env")


@click.group(chain=True)
@click.option(
    "--datasets-xml",
    type=str,
    help=(
        "Glob expression path to datasets.xml (or multiple dataset xmls) "
        "use to generate ERDDAP datasets.xml. If not provided, ERDDAP will "
        "use the datasets.xml in the ERDDAP content directory."
    ),
    default="**/datasets.d/*.xml|**/datasets.xml",
    envvar="ERDDAP_DATASETS_XML",
)
@click.option(
    "--recursive",
    "-r",
    type=bool,
    is_flag=True,
    default=True,
    show_default=True,
    help="Search for reference-datasets-xmls recursively",
    envvar="ERDDAP_RECURSIVE",
)
@click.option(
    "--active-datasets-xml",
    type=str,
    help="Path to active datasets.xml used by ERDDAP",
    default="/usr/local/tomcat/content/erddap/datasets.xml",
    show_default=True,
    envvar="ERDDAP_ACTIVE_DATASETS_XML",
)
@click.option(
    "--big-parent-directory",
    help="ERDDAP bigParentDirectory",
    type=str,
    default="/erddapData",
    show_default=True,
    envvar="ERDDAP_bigParentDirectory",
)
@click.option(
    "--secrets",
    help=(
        "JSON string of secrets to replace within `datasets.xml`. "
        "Secrets can also be defined via environment variables "
        "with the prefix `ERDDAP_SECRET_*` or "
        "the `ERDDAP_SECRETS` environment variable."
    ),
    type=str,
    envvar="ERDDAP_SECRETS",
)
@click.pass_context
@logger.catch(reraise=True)
def cli(
    ctx,
    datasets_xml,
    recursive,
    active_datasets_xml,
    big_parent_directory,
    secrets,
):
    logger.debug("Run in debug mode")
    logger.debug(
        "ERDDAP ENV VARS: {}",
        {
            var: (
                (value[:5] + "***" if len(var) > 5 else "***")
                if [sub in var for sub in ["secret", "token", "password"]]
                else var
            )
            for var, value in os.environ.items()
            if "ERDDAP" in var
        },
    )
    logger.info("Load datasets.xml={} recursive={}", datasets_xml, recursive)
    if secrets:
        logger.info("Load secrets")
        secrets = json.loads(secrets)

    # test datasets_xml string
    if '"' in datasets_xml:
        logger.warning("datasets_xml contains quotes, make sure it's properly escaped")

    erddap = Erddap(datasets_xml, recursive=recursive, secrets=secrets, lazy_load=True)
    logger.info("Load active datasets.xml")
    active_erddap = Erddap(active_datasets_xml, secrets=secrets, lazy_load=True)
    
    if not active_erddap:
        logger.info(f"Active datasets.xml not found in {active_datasets_xml}")

    ctx.ensure_object(dict)
    ctx.obj.update(
        dict(
            erddap=erddap,
            active_erddap=active_erddap,
            datasets_xml=datasets_xml,
            active_datasets_xml=active_datasets_xml,
            recursive=recursive,
            bigParentDirectory=big_parent_directory,
        )
    )


@cli.command()
@click.option("-o", "--output", help="Output file", type=str, default="{datasets_xml}")
@click.pass_context
@logger.catch
def save(ctx, output):
    """Save reference datasets.xml to active datasets.xml and include secrets."""
    logger.info("Convert to xml")
    output = output.format(**ctx.obj)
    ctx.obj["erddap"].load()
    return ctx.obj["erddap"].save(output=output)


cli.add_command(test)
cli.add_command(sync)
cli.add_command(monitor)


if __name__ == "__main__":
    try:
        cli()
    except Exception as e:
        logger.exception("Failed to execute command", exc_info=True)
        sys.exit(1)
