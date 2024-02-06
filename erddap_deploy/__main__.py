import os
from pathlib import Path

import click
import pytest
from git import Repo
from loguru import logger

from erddap_deploy.erddap import Erddap


@click.group()
@click.option(
    "--datasets-xml",
    type=str,
    help="Glob expression path to datasets.xml (or multiple dataset xmls) use to generate ERDDAP datasets.xml. If not provided, ERDDAP will use the datasets.xml in the ERDDAP content directory.",
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
    envvar="bigParentDirectory",
)
@click.pass_context
@logger.catch
def main(
    ctx,
    datasets_xml,
    recursive,
    active_datasets_xml,
    big_parent_directory,
):
    logger.debug("Run in debug mode")
    logger.debug("ERDDAP ENV VARS: {}", [var for var in os.environ.keys() if "ERDDAP" in var])
    logger.info("Load datasets.xml={} recursive={}", datasets_xml, recursive)

    erddap = Erddap(datasets_xml, recursive=recursive)
    logger.info("Load active datasets.xml")
    active_erddap = (
        Erddap(active_datasets_xml) if Path(active_datasets_xml).exists() else None
    )
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


@main.command()
@click.option("-o", "--output", help="Output file", type=str, default="{datasets_xml}")
@click.pass_context
@logger.catch
def save(ctx, output):
    """Save reference datasets.xml to active datasets.xml and include secrets."""
    logger.info("Convert to xml")
    output = output.format(**ctx.obj)
    return ctx.obj["erddap"].save(output=output)


@main.command()
@click.option("-r", "--repo", help="Path to git repo", type=str, default=None, envvar="ERDDAP_DATASETS_REPO")
@click.option("-b", "--branch", help="Branch to sync from", type=str, default=None, envvar="ERDDAP_DATASETS_REPO_BRANCH")
@click.option("--pull", help="Pull from remote", type=bool, default=False, is_flag=True, envvar="ERDDAP_DATASETS_REPO_PULL")
@click.option(
    "-p",
    "--local-repo-path",
    help="Where were to clone the repo",
    type=str,
    default="datasets-repo",
    envvar="ERDDAP_DATASETS_REPO_DIR",
)
@click.option(
    "-f",
    "--hard-flag",
    help="Generate Hard flag for modified datasets",
    type=bool,
    default=False,
    is_flag=True,
    envvar="ERDDAP_HARD_FLAG",
)
@click.option(
    "--hard-flag-dir",
    help="Directory to save hard flag",
    type=str,
    default="{bigParentDirectory}/erddap/hardFlag",
    envvar="ERDDAP_HARD_FLAG_DIR",
    show_default=True,
)
@click.pass_context
@logger.catch
def sync(ctx, repo, branch, pull, local_repo_path, hard_flag, hard_flag_dir):
    """Sync datasets.xml from a git repo"""

    # Format paths with context
    local_repo_path = local_repo_path.format(**ctx.obj)
    hard_flag_dir = Path(hard_flag_dir.format(**ctx.obj))

    # Get repo if not available and checkout branch and pull
    _link_repo(repo, branch, pull, local_repo_path)

    # compare active dataset vs HEAD
    logger.info("Compare active dataset vs HEAD")
    erddap = ctx.obj["erddap"]
    erddap.load()
    active_erddap = ctx.obj["active_erddap"]

    if not erddap.datasets_xml:
        raise ImportError("Unable to sync since no datasets.xml found")

    if not active_erddap:
        logger.info("Save active datasets.xml")
        erddap.save(ctx.obj["active_datasets_xml"])
        diff = {id: None for id in erddap.datasets.keys()}
    else:
        diff = erddap.diff(active_erddap)

    # If any differences, update datasets.xml
    if diff:
        logger.info("Update datasets.xml")
        erddap.save(ctx.obj["active_datasets_xml"])

    if hard_flag:
        for datasetID, datasetDiff in diff.items():
            logger.info("Generate hard flag for {datatset.dataset_id}")
            logger.debug("Diff: {}", datasetDiff)
            (hard_flag_dir / datasetID).write_text("")

    logger.info("datasets.xml updated")


def _link_repo(repo, branch, pull, local):
    """Get repo if not available and checkout branch and pull"""
    if not repo and not Path(local).exists():
        raise ValueError("Repo or local path is required")
    if not Path(local).exists() or not list(Path(local).glob("**/*")):
        logger.info(f"Clone repo {repo} to {local}")
        repo = Repo.clone_from(repo, local)
    else:
        repo = Repo(local)

    if branch:
        logger.info(f"Checkout branch {branch}")
        repo.git.checkout(branch)
    if pull:
        logger.info(f"Pull from remote")
        repo.git.origin.pull()


@main.command()
@click.option("-k", "--test-filter", help="Run tests by keyword expressions", type=str, default=None, envvar="ERDDAP_TEST_FILTER")
@click.option(
    "--active",
    help="Run tests on active datasets.xml, otherwise default to reference",
    type=bool,
    default=False,
    is_flag=True,
    envvar="ERDDAP_TEST_ACTIVE",
)
@click.pass_context
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


if __name__ == "__main__":
    main(auto_var_prefix="ERDDAP")
