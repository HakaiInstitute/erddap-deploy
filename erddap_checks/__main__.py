import os
import sys
from glob import glob

import click
import pytest
from git import Repo
from loguru import logger

from erddap_checks.erddap import Erddap


@click.group()
@click.option(
    "--datasets-xml", envvar="ERDDAP_DATASET_XML", type=str, help="Path to datasets.xml"
)
@click.option(
    "--datasets-d",
    envvar="ERDDAP_DATASETS_XML",
    type=str,
    multiple=True,
    help="Glob expresion to datasets.d xmls",
    default=None,
    show_default=True,
)
@click.option(
    "--recursive",
    "-r",
    envvar="ERDDAP_DATASETS_XML_RECURSIVE",
    type=bool,
    is_flag=True,
    default=True,
    show_default=True,
    help="Search for datasets.d xmls recursively",
)
@click.option("--log-level", default="INFO", help="Logging level", type=str)
@click.pass_context
def main(ctx, datasets_xml, datasets_d, recursive, log_level):
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
    )

    logger.debug("Load erddap dataset")
    if datasets_xml:
        logger.info("Load datasets_xml={datasets_xml}")
        erddap = Erddap(datasets_xml)
    elif datasets_d:
        logger.info("Load datasets_d={datasets_d}")
        erddap = Erddap(datasets_d, recursive=recursive)
    elif glob("**/datasets.xml", recursive=recursive):
        logger.info("Load **/datasets.xml")
        erddap = Erddap(glob("**/datasets.xml", recursive=recursive))
    elif glob("**/datasets.d/*.xml", recursive=recursive):
        logger.info("Load **/datasets.d/*.xml folder")
        erddap = Erddap(glob("**/datasets.d/*.xml", recursive=recursive))
    else:
        logger.error("No datasets.xml found")
        erddap = None
    logger.info("Load datasets_xml={datasets_xml}")

    ctx.ensure_object(dict)
    ctx.obj["erddap"] = erddap


@main.command()
@click.option("-o", "--output", help="Output file", type=str)
@click.pass_context
def save(ctx, output):
    """Save datasets.xml"""
    logger.info("Convert to xml")
    secrets = {
        key: value for key, value in os.environ if key.startswith("ERDDAP_SECRET_")
    }
    logger.info(" Include secrets={}", secrets.keys())
    return ctx["erddap"].to_xml(output=output, secrets=secrets)


@main.command()
@click.option("-r", "--repo", help="Path to git repo", type=str)
@click.option("-b", "--branch", help="Branch to sync from", type=str)
@click.option(
    "-p",
    "--local-repo-path",
    help="Where were to clone the repo",
    type=str,
    default="erddap-datasets",
    envvar="ERDDAP_DATASETS_DIR",
)
@click.option(
    "-f",
    "--hard-flag",
    help="Generate Hard flag for modified datasets",
    type=bool,
    default=False,
)
@click.option(
    "--hard-flag-dir",
    help="Directory to save hard flag",
    type=str,
    default="{ERDDAP_DATA}/erddap/hardFlag",
)
@click.pass_context
def sync(ctx, repo, branch, path, hard_flag, hard_flag_dir):
    """Sync datasets.xml from a git repo"""

    if not path.exists():
        logger.info(f"Clone repo {repo} to {path}")
        repo = Repo.clone_from(repo, path)
    else:
        repo = Repo(path)

    logger.info(f"Checkout branch {branch}")
    repo.git.checkout(branch)

    logger.info("Compare active dataset vs HEAD")
    intial_erddap = ctx["erddap"].copy()
    repo.pull()
    updated_erddap = ctx.obj["datasets_xml"]

    diff = intial_erddap.diff(updated_erddap)

    if diff:
        logger.info("Update datasets.xml")
        updated_erddap.to_xml(path)

    if diff and hard_flag:
        for datatset in diff:
            logger.info("Generate hard flag for {datatset.dataset_id}")
            (hard_flag_dir / datatset.dataset_id).write_text("")

    logger.info("Erddap datasets.xml has been updated")


@main.command()
@click.option("-k", "--test-filter", help="Run tests by keyword expressions", type=str)
@click.pass_context
def test(ctx, test_filter):
    """Run a series of tests on repo ERDDAP datasets"""

    @pytest.fixture(scope="session")
    def erddap():
        return ctx.obj["erddap"]

    args = ["--pyargs", "erddap_checks"]
    if test_filter:
        args.extend(["-k", test_filter])
    logger.info(f"Run pytest.main({args})")
    result = pytest.main(args).value
    if result:
        raise SystemExit(result)


if __name__ == "__main__":
    main()
