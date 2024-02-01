from click.testing import CliRunner

from erddap_deploy.__main__ import main

TEST_REPO = "https://github.com/HakaiInstitute/erddap-deploy.git"


def run_cli(*args):
    runner = CliRunner()
    return runner.invoke(main, args, catch_exceptions=False)


def test_erddap_deploy_help():
    result = run_cli("--help")
    assert result.exit_code == 0


class TestErddapDeployTest:
    def test_test(self):
        result = run_cli("test")
        assert result.exit_code == 0

    def test_test_help(self):
        result = run_cli("test", "--help")
        assert result.exit_code == 0


class TestErddapDeploySync:
    def test_sync(self, tmp_path):
        result = run_cli(
            "sync",
            "--repo",
            TEST_REPO,
            "--branch",
            "main",
            "--local-repo-path",
            str(tmp_path),
        )
        assert result.exit_code == 0

    def test_sync_help(self):
        result = run_cli("sync", "--help")
        assert result.exit_code == 0


class TestErddapDeploySave:
    def test_save(self):
        result = run_cli("save")
        assert result.exit_code == 0

    def test_save_help(self):
        result = run_cli("save", "--help")
        assert result.exit_code == 0
