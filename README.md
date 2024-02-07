
# erddap-deploy

`erddap-deploy` combines different utilities useful when managing ERDDAP instances.

- `erddap_deploy test`: Test `datasets.xml` or separated `datasets.d/*.xml` files of common configuration issues.
- `erddap_deploy sync`: Synchronize datasets XML from a git repository available within the ERDDAP instance container.

Both methods can be used locally via the CLI command line or GitHub actions.

## Use locally

Install locally the package with:

```console
pip install git+https://github.com/HakaiInstitute/erddap-deploy.git
```

For documentation:

```console
erddap_deploy --help
```

## Gitub Action

### Test datasets.xml

You can add the `erddap_deploy test` action to test an ERDDAP `datasets.xml` on
changes or PRs within a GitHub repo with the following action:

```yaml
      - uses: hakaiinstitute/erddap-deploy/actions/test@v1
```

We also recommend running an XML linter to detect XML-specific issues. SuperLinter is great for this!

```yaml
      - name: Lint Code Base
        uses: github/super-linter/slim@v4
        env:
          VALIDATE_ALL_CODEBASE: false
          DEFAULT_BRANCH: main
          VALIDATE_XML: true
          LOG_LEVEL: WARN
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Sync Deployment datasets.xml

Typically, `datasets.xml` configuration is maintained within a Git repository. You can sync deployed ERDDAP container instances via SSH and the GitHub Action:

``` yaml
    - uses:  hakaiinstitute/erddap-deploy/actions/sync@v1
      with:
        ssh_host: ${{ secrets.SSH_HOST }}
        ssh_username: ${{ secrets.SSH_USERNAME }}
        ssh_key: ${{ secrets.SSH_KEY }}
        ssh_port: ${{ secrets.SSH_PORT }}
        container_name: ${{ vars.ERDDAP_CONTAINER }}
        hard_flag: true
```

To handle multiple deployments, we recommend using `GitHub Environments` which maintains environment-specific secrets.
