
# ERDDAP-deploy

`ERDDAP-deploy` combines different utilities useful when managing ERDDAP instances.

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

`ERDDAP-deploy` is primarily designed for continuous integration to simplify the management of various ERDDAP deployments from a GitHub repository. This can be achieved using the following GitHub Actions:

### Test datasets.xml

`erddap_deploy test` action tests an ERDDAP `datasets.xml`. Typically use on
`push` or `pull_requests` within a GitHub repo with the following action:

```yaml
      - uses: hakaiinstitute/erddap-deploy/test@v1
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

See [test/action.yml](test/action.yml) for further details.

### Sync Deployment datasets.xml

`erdda_deploy sync` can be used to synchronize an ERDDAP deployment `datasets.xml` configuration. The action executes the following steps:

1. SSH to the remote server
2. Retrieve the local container running ERDDAP
3. Clone within the deployed ERDDAP container the present repository
4. `git checkout ...` the given branch
5. `git pull` to the latest commit
6. Generate `datasets.xml` from the local XMLs and environment variables available
7. Replace the ERDDAP `datasets.xml` with the newly generated one.
8. (if hard_flag=true) Generate `hard_flag` for each modified dataset

To run the sync action add the following command to your action:

``` yaml
    - uses:  hakaiinstitute/erddap-deploy/sync@v1
      with:
        ssh_host: ${{ secrets.SSH_HOST }}
        ssh_username: ${{ secrets.SSH_USERNAME }}
        ssh_key: ${{ secrets.SSH_KEY }}
        ssh_port: ${{ secrets.SSH_PORT }}
        container_name: ${{ vars.ERDDAP_CONTAINER }}
        hard_flag: true
        monitor: true # (optional) Update related uptime-kuma server instance (see section below for details)
```

*See [sync/action.yml](sync/action.yml) for further details.*

To handle multiple deployments, we recommend using `GitHub Environments` which maintains environment-specific secrets.

### Monitor ERDDAP server and datasets

In some cases, an ERDDAP deployment can be monitored, we recommend using [Uptime-Kuma](https://github.com/louislam/uptime-kuma) which can easily be deployed via `CapRover`. If an `uptime-kuma` instance is deployed we can maintain a series of automatically generated-url checks via the `sync` (see above) or `monitor` actions.

To handle this action you can pass the Uptime Kuma parameters:

- (recommended) As environment variables on the deployed server 

    ```env
    # Uptime Kuma settings (optional)
    UPTIME_KUMA_URL=https://uptime-kuma.server.some.app/
    UPTIME_KUMA_USERNAME=admin 
    UPTIME_KUMA_PASSWORD=password
    UPTIME_KUMA_TOKEN=token_generated_by_uptime_kuma
    ```

- As input to the `monitor` method via the [monitor](monitor/action.yml) action.

    ``` yaml
      - uses:  hakaiinstitute/erddap-deploy/monitor@v1
        with:
          uptime_kuma_url: ${{ secrets.uptime_kuma_url }}
          uptime_kuma_username: ${{ secrets.uptime_kuma_username }}
          uptime_kuma_password: ${{ secrets.uptime_kuma_password }}
          uptime_kuma_token: ${{ secrets.uptime_kuma_token }}
          erddap_name: ${{ vars.erddap_name }}
          erddap_url: ${{ vars.erddap_url }}
    ```

  *See [monitor/action.yml](monitor/action.yml) for further details.*
