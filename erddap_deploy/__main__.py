import os
import sys
from pathlib import Path

import click
import pytest
from git import Repo
from loguru import logger

from erddap_deploy.erddap import Erddap


@click.group()
@click.option(
    "--datasets-xml",
    envvar="ERDDAP_DATASET_XML",
    type=str,
    help="Path to datasets.xml",
    default="/usr/local/tomcat/content/erddap/datasets.xml",
)
@click.option(
    "--datasets-d",
    envvar="ERDDAP_DATASETS_XML",
    type=str,
    multiple=True,
    help="Glob expresion to datasets.d xmls",
    default="datasets.d/*.xml",
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
@click.option(
    "--bigParentDirectory",
    envvar="ERDDAP_BIG_PARENT_DIRECTORY",
    help="ERDDAP bigParentDirectory",
    type=str,
    default="/erddapData",
    show_default=True,
)
@click.option("--log-level", default="INFO", help="Logging level", type=str)
@click.pass_context
def main(
    ctx,
    datasets_xml,
    datasets_d,
    recursive,
    bigParentDirectory,
    log_level,
):
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
    )

    logger.debug("Load erddap dataset")
    if datasets_d:
        logger.info("Load datasets_d={}", datasets_d)
        erddap = Erddap(datasets_d, recursive=recursive)
    elif Path(datasets_xml).exists():
        logger.info("Load datasets_xml={}", datasets_xml)
        erddap = Erddap(datasets_xml)
    else:
        logger.error("No datasets.xml found")
        erddap = None
    logger.info("Load datasets_xml={datasets_xml}")

    ctx.ensure_object(dict)
    ctx.obj.update(
        dict(
            erddap=erddap,
            datasets_xml=datasets_xml,
            datasets_d=datasets_d,
            recursive=recursive,
            bigParentDirectory=bigParentDirectory,
        )
    )


@main.command()
@click.option("-o", "--output", help="Output file", type=str, default="{dataset_xml}")
@click.pass_context
def save(ctx, output):
    """Save datasets.xml"""
    logger.info("Convert to xml")
    secrets = {
        key: value for key, value in os.environ if key.startswith("ERDDAP_SECRET_")
    }
    logger.info(" Include secrets={}", secrets.keys())
    output = output.format(**ctx.obj)
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
    envvar="ERDDAP_DATASETS_REPO_DIR",
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
def sync(ctx, repo, branch, local_repo_path, hard_flag=True, hard_flag_dir="hardFlag"):
    """Sync datasets.xml from a git repo"""

    if not Path(local_repo_path).exists() or not list(
        Path(local_repo_path).glob("**/*")
    ):
        logger.info(f"Clone repo {repo} to {local_repo_path}")
        repo = Repo.clone_from(repo, local_repo_path)
    else:
        repo = Repo(local_repo_path)

    logger.info(f"Checkout branch {branch}")
    repo.git.checkout(branch)

    logger.info("Compare active dataset vs HEAD")
    erddap = ctx.obj["erddap"]
    intial_erddap = erddap.copy()
    repo.git.pull()
    erddap.load()

    diff = erddap.diff(intial_erddap)

    # If any differences, save datasets.xml
    if any(diff.values()):
        logger.info("Update datasets.xml")
        erddap.to_xml(local_repo_path)

        if hard_flag:
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

    args = ["--pyargs", "erddap_deploy"]
    if test_filter:
        args.extend(["-k", test_filter])
    logger.info(f"Run pytest.main({args})")
    result = pytest.main(args).value
    if result:
        raise SystemExit(result)


if __name__ == "__main__":
    main()
