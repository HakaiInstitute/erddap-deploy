import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from git import Repo
from loguru import logger

load_dotenv()


@click.command()
@click.option(
    "-r",
    "--repo-url",
    help="Path to git repo",
    type=str,
    default=None,
    envvar="ERDDAP_DATASETS_REPO_URL",
)
@click.option(
    "-b",
    "--branch",
    help="Branch to sync from",
    type=str,
    default=None,
    envvar="ERDDAP_DATASETS_REPO_BRANCH",
)
@click.option(
    "--pull",
    help="Pull from remote",
    type=bool,
    default=False,
    is_flag=True,
    envvar="ERDDAP_DATASETS_REPO_PULL",
)
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
    default="{bigParentDirectory}/hardFlag",
    envvar="ERDDAP_HARD_FLAG_DIR",
    show_default=True,
)
@click.pass_context
@logger.catch(reraise=True)
def sync(
    ctx,
    repo_url,
    branch,
    pull,
    local_repo_path,
    hard_flag,
    hard_flag_dir,
):
    """Sync datasets.xml from a git repo"""

    # Format paths with context
    path_vars = get_erddap_env_variables()
    path_vars.update(ctx.obj)
    local_repo_path = local_repo_path.format(**path_vars)
    hard_flag_dir = Path(hard_flag_dir.format(**path_vars))

    # Get repo if not available and checkout branch and pull
    update_local_repository(repo_url, branch, pull, local_repo_path)

    # compare active dataset vs HEAD
    logger.info("Compare active dataset vs HEAD")
    ctx.obj["erddap"].load()
    erddap = ctx.obj["erddap"]
    active_erddap = ctx.obj["active_erddap"]

    if not erddap.datasets_xml:
        logger.error("Unable to sync since no datasets.xml found")
        sys.exit(1)

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
            logger.info("Generate hard flag for {}", datasetID)
            logger.debug("Diff: {}", datasetDiff)
            (hard_flag_dir / datasetID).write_text("")

    logger.info("datasets.xml updated")


def update_local_repository(repo_url, branch, pull, local):
    """Get repo if not available and checkout branch and pull"""

    logger.debug(
        "List local repository files: {} ls  = {}", local, list(Path(local).glob("*"))
    )
    if repo_url and repo_url[-1] == "/":
        logger.debug("Remove trailing / from repo_url")
        repo_url = repo_url[:-1]

    # Clone or load repo
    if not repo_url and not Path(local).exists():
        raise ValueError("Repo or local path is required")
    if not Path(local).exists() or not list(Path(local).glob("**/*")):
        logger.info(f"Clone repo {repo_url} to {local}")
        repo = Repo.clone_from(repo_url, local)
    else:
        repo = Repo(local)
        origin_url = repo.git.remote("get-url", "origin")
        if repo_url and origin_url != repo_url:
            logger.warning(
                f"Local [{local}] repo.remote.origin.get-url = {origin_url}  is not the same repo={repo_url}"
            )

    # Checkout branch and pull
    if branch:
        logger.info(f"Checkout branch {branch}")
        repo.git.checkout(branch)

    # Pull from remote
    if pull:
        logger.info(f"Pull from remote")
        repo.git.pull()


if __name__ == "__main__":
    sync()
