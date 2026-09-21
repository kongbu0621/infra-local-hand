# Isolated build and verification

Use Python 3.12 and a clean committed checkout. Build and runtime environments
must be newly created directories. Choose a new absolute work directory first;
the following names are examples, not live deployment defaults.

```sh
python3.12 -m venv /absolute/new-work/build-venv
/absolute/new-work/build-venv/bin/python -m pip install -r requirements-build.txt
/absolute/new-work/build-venv/bin/python -m pytest -q
/absolute/new-work/build-venv/bin/python -m compileall -q tools tests
/absolute/new-work/build-venv/bin/python -m build --wheel --no-isolation --outdir /absolute/new-work/dist
python3.12 -m venv /absolute/new-work/runtime-venv
/absolute/new-work/runtime-venv/bin/python -m pip install --no-deps /absolute/new-work/dist/infra_local_hand-0.1.0a1-py3-none-any.whl
cd /absolute/new-work
/absolute/new-work/runtime-venv/bin/python -I /absolute/checkout/tools/verify_installed.py --wheel /absolute/new-work/dist/infra_local_hand-0.1.0a1-py3-none-any.whl --run-root /absolute/new-work/acceptance
```

On Windows, venv Python is `Scripts/python.exe`. The source test suite and
installed direct-action tests are portable; the installed CLI transport fixture
is POSIX-specific and reports SKIP on Windows. Preserve its report and logs.
For a second candidate, retain prior artifacts and use new build/runtime paths.

## Explicit admission

Node Profile requires exactly `profile_schema`, `node_id`, `projects_root`,
`repositories`, `transport_policy`. The schema is `local-hand-profile/v2`.
Each repository requires `path`, boolean `single_writer`, and `validations`.
Each validation has fixed `argv`, finite numeric `timeout_seconds` in (0,3600],
and boolean `replay_safe`. Missing and unknown keys are rejected.

Transport policy requires exactly `schema_version`, `remote_url`,
`allowed_remote_urls`, `branch`; schema is `local-hand-git-mailbox/v1`.
Supported remotes are explicit `user@host:owner/repository.git` or
`ssh://user@host[:port]/owner/repository.git`. Every admitted spelling must be
listed and name the same SSH user/host/port/repository. No local/file/HTTP remote
or implicit branch is accepted. Synthetic examples are in the test fixtures.

Use `python -m local_hand.config --profile PROFILE --repository NAME` to check
a profile before installation. Controller `init`, `submit`, `wait`, and `call`
require `--policy FILE`. `build` remains offline. A controller mailbox has a
create-only admission marker; changing policy requires a newly admitted clone.
Worker's optional `--mailbox-branch` is an assertion against the profile.
`wait` and `call` additionally require `--expected-provenance-file`; that file
must contain the exact admitted `implementation_commit`, `package_digest`, and
`profile_digest`. A result is never accepted without this source policy.

## Installation provenance

An installed worker requires a create-only record from
`python -m local_hand.installation --help`. Supply the retained original wheel,
profile, installation UUID, runtime Git/SSH/key/known_hosts absolute paths,
state and mailbox roots. Match these bindings at startup using
`LOCAL_HAND_INSTALL_RECORD`, `LOCAL_HAND_INSTALL_INSTANCE_ID`, and the runtime
path variables shown in that module. Do not modify an existing installation
record to migrate an environment. Every returned result binds the actual build
commit, core digest and raw profile digest.

The Linux/Windows service bootstrap scripts remain source-staging installers:
they require a clean Git checkout and stamp copied source, not a wheel install.
Their required profile/repository/state/run-user inputs replace deployment
defaults. Their presence inside the wheel does not make them wheel installers.
Do not invoke them for S1 live deployment; service cutover is S2 scope.

Old profiles, controller markers and state directories are not silently
upgraded. Preserve them and use an explicit separately authorized migration.
