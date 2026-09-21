#!/usr/bin/env bash
set -Eeuo pipefail

# The coordinator preserves the invoking terminal's cached authorization, but
# neither it nor nested bootstrap commands may prompt or consume payload stdin.
# Direct, standalone bootstrap invocation retains its existing sudo behavior.
if [[ "${LOCAL_HAND_NONINTERACTIVE_SUDO:-}" == 1 ]]; then
  LOCAL_HAND_SUDO_BIN="$(type -P sudo)" || { echo "sudo required" >&2; exit 1; }
  readonly LOCAL_HAND_SUDO_BIN
  sudo() { "$LOCAL_HAND_SUDO_BIN" -n "$@"; }
fi

usage() {
  cat <<'EOF'
Usage: bootstrap_linux.sh --profile JSON --repository-name NAME --run-user USER --state-root PATH [options]
Security defaults:
  --profile JSON              required explicit Node Profile v2; includes transport and validation profiles
  --run-user USER              required; must own a dedicated same-name system group
  --state-root PATH            required, dedicated installation root
  --projects-root PATH         optional assertion; actual value comes from profile
  --mailbox-ssh-key PATH       required for SSH mailbox URL
  --known-hosts-file PATH      required for SSH mailbox URL
Other:
  --single-writer
  --seed-repository-from PATH  must be a trusted root-owned standalone local Git working copy
  --implementation-commit SHA  default: source HEAD
  --mailbox-url URL            optional assertion; must equal admitted profile remote
  --mailbox-branch BRANCH
  --service-name NAME
EOF
}

NODE_ID=""; REPOSITORY_NAME=""; REPOSITORY_PATH=""; SINGLE_WRITER=false; SEED_REPOSITORY_FROM=""
RUN_USER=""; STATE_ROOT=""; PROJECTS_ROOT=""; PROFILE_SOURCE=""
IMPLEMENTATION_COMMIT=""
MAILBOX_URL=""; MAILBOX_BRANCH=""
MAILBOX_SSH_KEY=""; KNOWN_HOSTS_FILE=""; SERVICE_NAME=local-hand
while [[ $# -gt 0 ]]; do case "$1" in
  --node-id) NODE_ID="$2"; shift 2;; --repository-name) REPOSITORY_NAME="$2"; shift 2;; --repository-path) REPOSITORY_PATH="$2"; shift 2;;
  --single-writer) SINGLE_WRITER=true; shift;; --seed-repository-from) SEED_REPOSITORY_FROM="$2"; shift 2;;
  --run-user) RUN_USER="$2"; shift 2;; --state-root) STATE_ROOT="$2"; shift 2;; --projects-root) PROJECTS_ROOT="$2"; shift 2;;
  --profile) PROFILE_SOURCE="$2"; shift 2;; --implementation-commit) IMPLEMENTATION_COMMIT="$2"; shift 2;;
  --mailbox-url) MAILBOX_URL="$2"; shift 2;; --mailbox-branch) MAILBOX_BRANCH="$2"; shift 2;;
  --mailbox-ssh-key) MAILBOX_SSH_KEY="$2"; shift 2;; --known-hosts-file) KNOWN_HOSTS_FILE="$2"; shift 2;;
  --service-name) SERVICE_NAME="$2"; shift 2;; -h|--help) usage; exit 0;; *) echo "Unknown argument: $1" >&2; exit 2;; esac
done
[[ -n "$PROFILE_SOURCE" && -n "$REPOSITORY_NAME" && -n "$RUN_USER" && -n "$STATE_ROOT" ]] || { usage >&2; exit 2; }
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
PROFILE_SOURCE="$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).absolute())' "$PROFILE_SOURCE")"
PROFILE_SETTINGS="$(env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SOURCE_REPO_ROOT/tools" python3 -B -m local_hand.config --profile "$PROFILE_SOURCE" --repository "$REPOSITORY_NAME" --match-node-id "$NODE_ID" --match-projects-root "$PROJECTS_ROOT" --match-repository-path "$REPOSITORY_PATH" --match-remote-url "$MAILBOX_URL" --match-branch "$MAILBOX_BRANCH")"
profile_field(){ python3 -c 'import json,sys; v=json.load(sys.stdin)[sys.argv[1]]; print(str(v).lower() if isinstance(v,bool) else v)' "$1" <<< "$PROFILE_SETTINGS"; }
NODE_ID="$(profile_field node_id)"; PROJECTS_ROOT="$(profile_field projects_root)"; REPOSITORY_PATH="$(profile_field repository_path)"
MAILBOX_URL="$(profile_field remote_url)"; MAILBOX_BRANCH="$(profile_field branch)"; ADMITTED_PROFILE_SHA="$(profile_field digest)"
[[ "$SINGLE_WRITER" != true || "$(profile_field single_writer)" == true ]] || { echo "single-writer assertion differs from profile" >&2; exit 2; }
for x in git ssh python3 systemctl sudo getent useradd groupadd cmp; do command -v "$x" >/dev/null || { echo "$x required" >&2; exit 1; }; done
GIT_BIN="$(command -v git)"; SSH_BIN="$(command -v ssh)"
[[ "$NODE_ID" =~ ^[A-Za-z0-9._-]{1,128}$ ]] || { echo "invalid node-id" >&2; exit 2; }
[[ "$REPOSITORY_NAME" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] || { echo "invalid repository-name" >&2; exit 2; }
[[ "$RUN_USER" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || { echo "invalid run-user" >&2; exit 2; }
[[ "$SERVICE_NAME" =~ ^[A-Za-z0-9_.@-]{1,128}$ ]] || { echo "invalid service-name" >&2; exit 2; }
"$GIT_BIN" check-ref-format "refs/heads/$MAILBOX_BRANCH" >/dev/null || { echo "invalid mailbox-branch" >&2; exit 2; }
[[ "$MAILBOX_BRANCH" != *%* ]] || { echo "mailbox-branch contains a systemd specifier marker" >&2; exit 2; }
[[ "$MAILBOX_BRANCH" =~ ^[A-Za-z0-9._/-]+$ ]] || { echo "mailbox-branch contains characters unsafe for the generated systemd unit" >&2; exit 2; }
[[ "$MAILBOX_URL" != *$'\n'* && "$MAILBOX_URL" != *$'\r'* ]] || { echo "invalid mailbox-url" >&2; exit 2; }
# SSH allowlist and branch were admitted by the shared profile validator above.

STATE_ROOT="$(python3 -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$STATE_ROOT")"
PROJECTS_ROOT="$(python3 -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$PROJECTS_ROOT")"

for value in "$STATE_ROOT" "$PROJECTS_ROOT" "$GIT_BIN" "$SSH_BIN"; do
  [[ "$value" != *[[:space:]]* ]] || { echo "v0.1 bootstrap paths must not contain whitespace: $value" >&2; exit 2; }
  [[ "$value" != *%* ]] || { echo "v0.1 systemd unit values must not contain '%': $value" >&2; exit 2; }
  [[ "$value" =~ ^/[A-Za-z0-9._/@:+-]+$ ]] || { echo "v0.1 systemd unit paths must use safe absolute ASCII syntax: $value" >&2; exit 2; }
done

while IFS='=' read -r n _; do case "$n" in GIT_*|SSH_*) unset "$n";; esac; done < <(env)
export GIT_TERMINAL_PROMPT=0 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
DISABLED_HOOKS="$(mktemp -d)"
STAGE_ROOT=""; TEMP_UNIT=""; OLD_UNIT_BACKUP=""; MAILBOX_ROOT=""; CREDENTIALS_ROOT=""
SWITCH_STARTED=false; SWITCH_COMMITTED=false; OLD_UNIT_EXISTS=false; OLD_WAS_ACTIVE=false; OLD_WAS_ENABLED=false
DEPLOYMENT_CREATED=false; UNSAFE_LIVE_PROCESS=false; ROLLBACK_FAILED=false
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

git_safe(){ "$GIT_BIN" --no-pager -c "core.hooksPath=$DISABLED_HOOKS" -c core.fsmonitor=false -c submodule.recurse=false -c credential.helper= -c protocol.ext.allow=never "$@"; }
reject_execution_config(){
  local r="$1" names rc name normalized
  set +e
  names="$(git_safe -c "safe.directory=$r" -C "$r" config --no-includes --name-only --get-regexp '.*' 2>&1)"
  rc=$?
  set -e
  if [[ $rc -eq 1 && -z "$names" ]]; then
    return 0
  fi
  [[ $rc -eq 0 ]] || {
    echo "cannot inspect Git execution config in $r" >&2
    exit 1
  }
  while IFS= read -r name; do
    normalized="${name,,}"
    case "$normalized" in
      filter.*.clean|filter.*.smudge|filter.*.process|include.path|includeif.*.path|uploadpack.packobjectshook|core.alternaterefscommand)
        echo "execution-capable Git config rejected in $r: $name" >&2
        exit 1
        ;;
    esac
  done <<< "$names"
}
service_is_confirmed_stopped(){
  local active_state
  active_state="$(sudo systemctl show "${SERVICE_NAME}.service" --property=ActiveState --value 2>/dev/null)" || return 1
  [[ "$active_state" == inactive || "$active_state" == failed ]]
}
assert_owned_existing_unit(){
  local load_state fragment_path drop_in_paths
  load_state="$(sudo systemctl show "${SERVICE_NAME}.service" --property=LoadState --value 2>/dev/null)" || { echo "cannot determine existing systemd service load state" >&2; exit 1; }
  [[ -n "$load_state" ]] || { echo "empty existing systemd service load state; refusing installation" >&2; exit 1; }
  if [[ "$load_state" != not-found ]]; then
    fragment_path="$(sudo systemctl show "${SERVICE_NAME}.service" --property=FragmentPath --value 2>/dev/null)" || { echo "cannot determine existing systemd service fragment path" >&2; exit 1; }
    [[ "$fragment_path" == "$UNIT_PATH" ]] || { echo "existing systemd service fragment is not the Local Hand unit path; refusing stop/replace: $fragment_path" >&2; exit 1; }
    drop_in_paths="$(sudo systemctl show "${SERVICE_NAME}.service" --property=DropInPaths --value 2>/dev/null)" || { echo "cannot determine existing systemd service drop-in paths" >&2; exit 1; }
    [[ -z "$drop_in_paths" ]] || { echo "existing systemd service has unowned drop-in configuration; refusing stop/replace: $drop_in_paths" >&2; exit 1; }
  fi
  if sudo test -e "$UNIT_PATH" || sudo test -L "$UNIT_PATH"; then
    sudo test -f "$UNIT_PATH" && ! sudo test -L "$UNIT_PATH" || { echo "existing systemd unit is not a regular owned file; refusing stop/replace" >&2; exit 1; }
    sudo grep -Fqx "# X-Local-Hand-Owner=$SERVICE_OWNER_TOKEN" "$UNIT_PATH" || { echo "existing systemd service ownership is not proven; refusing stop/replace" >&2; exit 1; }
  elif [[ "$load_state" != not-found ]]; then
    echo "loaded systemd service has no exact Local Hand unit file; refusing stop/replace" >&2
    exit 1
  fi
}
cleanup_files(){ [[ -n "$STAGE_ROOT" && -d "$STAGE_ROOT" ]] && rm -rf "$STAGE_ROOT" || true; [[ -n "$TEMP_UNIT" && -f "$TEMP_UNIT" ]] && rm -f "$TEMP_UNIT" || true; if [[ "$ROLLBACK_FAILED" != true && -n "$OLD_UNIT_BACKUP" && -f "$OLD_UNIT_BACKUP" ]]; then rm -f "$OLD_UNIT_BACKUP" || true; fi; rm -rf "$DISABLED_HOOKS" || true; }
rollback_switch(){
  local rollback_ok=true restored_active_state restored_unit_file_state restored_load_state
  echo "new Local Hand service failed health check; attempting rollback and restoring previous service state" >&2
  sudo systemctl stop "${SERVICE_NAME}.service" >/dev/null 2>&1 || true
  if ! service_is_confirmed_stopped; then
    UNSAFE_LIVE_PROCESS=true
    echo "Local Hand service did not stop during rollback; preserving new instance artifacts and not restarting the old service" >&2
    return 0
  fi
  if [[ "$OLD_UNIT_EXISTS" == true ]]; then
    if ! sudo install -m0644 "$OLD_UNIT_BACKUP" "$UNIT_PATH"; then rollback_ok=false; fi
  else
    if ! sudo systemctl disable "${SERVICE_NAME}.service" >/dev/null 2>&1; then rollback_ok=false; fi
    if ! sudo rm -f "$UNIT_PATH"; then rollback_ok=false; fi
  fi
  if ! sudo systemctl daemon-reload; then rollback_ok=false; fi
  if [[ "$OLD_UNIT_EXISTS" == true ]]; then
    if [[ "$OLD_WAS_ENABLED" == true ]]; then
      if ! sudo systemctl enable "${SERVICE_NAME}.service" >/dev/null 2>&1; then rollback_ok=false; fi
    elif ! sudo systemctl disable "${SERVICE_NAME}.service" >/dev/null 2>&1; then rollback_ok=false
    fi
    if [[ "$OLD_WAS_ACTIVE" == true ]]; then
      if ! sudo systemctl restart "${SERVICE_NAME}.service"; then rollback_ok=false; fi
    elif ! sudo systemctl stop "${SERVICE_NAME}.service" >/dev/null 2>&1; then rollback_ok=false
    fi
    if ! sudo cmp -s "$OLD_UNIT_BACKUP" "$UNIT_PATH"; then rollback_ok=false; fi
    restored_active_state="$(sudo systemctl show "${SERVICE_NAME}.service" --property=ActiveState --value 2>/dev/null)" || rollback_ok=false
    restored_unit_file_state="$(sudo systemctl show "${SERVICE_NAME}.service" --property=UnitFileState --value 2>/dev/null)" || rollback_ok=false
    if [[ "$OLD_WAS_ACTIVE" == true ]]; then [[ "$restored_active_state" == active ]] || rollback_ok=false; else [[ "$restored_active_state" == inactive || "$restored_active_state" == failed ]] || rollback_ok=false; fi
    if [[ "$OLD_WAS_ENABLED" == true ]]; then [[ "$restored_unit_file_state" == enabled ]] || rollback_ok=false; else [[ "$restored_unit_file_state" == disabled ]] || rollback_ok=false; fi
  else
    sudo test ! -e "$UNIT_PATH" && sudo test ! -L "$UNIT_PATH" || rollback_ok=false
    restored_load_state="$(sudo systemctl show "${SERVICE_NAME}.service" --property=LoadState --value 2>/dev/null)" || rollback_ok=false
    [[ "$restored_load_state" == not-found ]] || rollback_ok=false
  fi
  if [[ "$rollback_ok" != true ]]; then
    ROLLBACK_FAILED=true
    echo "Local Hand rollback could not be verified; preserving new instance artifacts for recovery" >&2
    if [[ "$OLD_UNIT_EXISTS" == true ]]; then echo "previous unit recovery copy preserved at: $OLD_UNIT_BACKUP" >&2; fi
  fi
}
cleanup_uncommitted(){
  [[ "$SWITCH_COMMITTED" == true ]] && return 0
  [[ "$UNSAFE_LIVE_PROCESS" == true ]] && return 0
  [[ "$ROLLBACK_FAILED" == true ]] && return 0
  [[ -n "$MAILBOX_ROOT" ]] && sudo rm -rf "$MAILBOX_ROOT" || true
  [[ -n "$CREDENTIALS_ROOT" ]] && sudo rm -rf "$CREDENTIALS_ROOT" || true
  [[ "$DEPLOYMENT_CREATED" == true && -n "${DEPLOYMENT_ROOT:-}" ]] && sudo rm -rf "$DEPLOYMENT_ROOT" || true
}
on_exit(){
  local rc=$?
  trap - EXIT
  if [[ $rc -ne 0 ]]; then
    if [[ "${LOCAL_HAND_OUTER_TRANSACTION:-}" == 1 ]]; then
      # Nested rollback can hide a lost sudo monitor behind the original
      # ordinary failure. Leave all service recovery to the outer coordinator,
      # which verifies command termination and owns durable unit backups.
      # Preserve inputs too: an unconfirmed child may still be using them.
      echo "bootstrap failed; preserving inputs for outer transaction recovery" >&2
      exit "$rc"
    fi
    if [[ "$SWITCH_STARTED" == true && "$SWITCH_COMMITTED" != true ]]; then
      rollback_switch
    fi
    cleanup_uncommitted
  fi
  cleanup_files
  exit "$rc"
}
trap on_exit EXIT

# The bootstrap may execute directly from a root-owned immutable seed. Trust only
# the exact worktree containing this script; never broaden safe.directory.
git_safe -c "safe.directory=$SOURCE_REPO_ROOT" -C "$SOURCE_REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null
reject_execution_config "$SOURCE_REPO_ROOT"
ACTUAL_SOURCE_HEAD="$(git_safe -c "safe.directory=$SOURCE_REPO_ROOT" -C "$SOURCE_REPO_ROOT" rev-parse HEAD | tr '[:upper:]' '[:lower:]')"
[[ -n "$IMPLEMENTATION_COMMIT" ]] || IMPLEMENTATION_COMMIT="$ACTUAL_SOURCE_HEAD"
IMPLEMENTATION_COMMIT="${IMPLEMENTATION_COMMIT,,}"
[[ "$IMPLEMENTATION_COMMIT" =~ ^[0-9a-f]{40,64}$ ]] || { echo "implementation commit invalid" >&2; exit 1; }
[[ "$IMPLEMENTATION_COMMIT" == "$ACTUAL_SOURCE_HEAD" ]] || { echo "implementation commit mismatch: claimed=$IMPLEMENTATION_COMMIT source_head=$ACTUAL_SOURCE_HEAD" >&2; exit 1; }
SOURCE_DIRTY="$(git_safe -c "safe.directory=$SOURCE_REPO_ROOT" -C "$SOURCE_REPO_ROOT" status --porcelain=v1 --untracked-files=all -- tools/local_hand)"
[[ -z "$SOURCE_DIRTY" ]] || { echo "tools/local_hand source tree is dirty" >&2; exit 1; }
TARGET_REPO="$(sudo env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SOURCE_REPO_ROOT/tools" python3 -B -m local_hand.bootstrap_safety validate-repository-target \
  --projects-root "$PROJECTS_ROOT" --repository-path "$REPOSITORY_PATH")"
TARGET_NEEDS_SEED=false
if ! sudo test -e "$TARGET_REPO/.git"; then
  TARGET_NEEDS_SEED=true
  [[ -n "$SEED_REPOSITORY_FROM" && -d "$SEED_REPOSITORY_FROM" ]] || { echo "--seed-repository-from must name a trusted root-owned standalone local Git working copy" >&2; exit 1; }
  SEED_REPOSITORY_FROM="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve(strict=True))' "$SEED_REPOSITORY_FROM")"
  [[ "$(git_safe -c "safe.directory=$SEED_REPOSITORY_FROM" -C "$SEED_REPOSITORY_FROM" rev-parse --is-inside-work-tree)" == true ]] || { echo "seed repository is not a Git working copy" >&2; exit 1; }
  [[ "$(git_safe -c "safe.directory=$SEED_REPOSITORY_FROM" -C "$SEED_REPOSITORY_FROM" rev-parse --show-toplevel)" == "$SEED_REPOSITORY_FROM" ]] || { echo "seed repository path must be the exact working-copy root" >&2; exit 1; }
  reject_execution_config "$SEED_REPOSITORY_FROM"
fi
INSTALL_INSTANCE_ID="$(PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SOURCE_REPO_ROOT/tools" python3 -B -m local_hand.bootstrap_safety new-install-instance-id)"
SERVICE_OWNER_TOKEN="$(PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SOURCE_REPO_ROOT/tools" python3 -B -m local_hand.bootstrap_safety service-owner-token --state-root "$STATE_ROOT" --node-id "$NODE_ID" --service-id "$SERVICE_NAME")"
assert_owned_existing_unit

sudo env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SOURCE_REPO_ROOT/tools" python3 -B -m local_hand.bootstrap_safety validate-roots \
  --state-root "$STATE_ROOT" --projects-root "$PROJECTS_ROOT"
STATE_ROOT_EXISTED=false
if sudo test -e "$STATE_ROOT"; then STATE_ROOT_EXISTED=true; fi
MARKER_ARGS=(ensure-root-marker --state-root "$STATE_ROOT" --node-id "$NODE_ID" --service-id "$SERVICE_NAME")
[[ "$STATE_ROOT_EXISTED" == true ]] || MARKER_ARGS+=(--allow-create)
sudo env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SOURCE_REPO_ROOT/tools" python3 -B -m local_hand.bootstrap_safety "${MARKER_ARGS[@]}"
ROOT_OWNER_MARKER="$STATE_ROOT/.local-hand-root-owner.json"
sudo chown root:root "$ROOT_OWNER_MARKER"
sudo chmod 0444 "$ROOT_OWNER_MARKER"
sudo chown root:root "$STATE_ROOT"
sudo chmod 0755 "$STATE_ROOT"
if ! getent group "$RUN_USER" >/dev/null; then
  sudo groupadd --system "$RUN_USER"
fi
if ! getent passwd "$RUN_USER" >/dev/null; then
  sudo useradd --system --gid "$RUN_USER" --home-dir "$STATE_ROOT/home" --no-create-home --shell /usr/sbin/nologin "$RUN_USER"
fi
RUN_GROUP="$(id -gn "$RUN_USER")"
[[ "$RUN_GROUP" == "$RUN_USER" ]] || { echo "run-user must have dedicated same-name primary group; user=$RUN_USER primary_group=$RUN_GROUP" >&2; exit 1; }
RUN_HOME="$STATE_ROOT/home"; CREDENTIALS_BASE="$STATE_ROOT/credentials"; CREDENTIALS_ROOT="$CREDENTIALS_BASE/$INSTALL_INSTANCE_ID"; RUNTIME_STATE="$STATE_ROOT/runtime"
DEPLOYMENTS_ROOT="$STATE_ROOT/deployments"; MAILBOXES_ROOT="$STATE_ROOT/mailboxes"
for root in "$RUN_HOME" "$CREDENTIALS_BASE" "$CREDENTIALS_ROOT" "$RUNTIME_STATE" "$DEPLOYMENTS_ROOT" "$MAILBOXES_ROOT" "$PROJECTS_ROOT"; do
  sudo env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SOURCE_REPO_ROOT/tools" python3 -B -m local_hand.bootstrap_safety validate-roots \
    --state-root "$STATE_ROOT" --projects-root "$root"
done
sudo install -d -m0555 -o root -g root "$RUN_HOME"
sudo install -d -m0555 -o root -g root "$CREDENTIALS_BASE"
sudo install -d -m0750 -o root -g "$RUN_GROUP" "$CREDENTIALS_ROOT"
sudo install -d -m0700 -o "$RUN_USER" -g "$RUN_GROUP" "$RUNTIME_STATE" "$PROJECTS_ROOT" "$MAILBOXES_ROOT"
sudo install -d -m0755 -o root -g root "$DEPLOYMENTS_ROOT"
for root in "$RUN_HOME" "$CREDENTIALS_BASE" "$CREDENTIALS_ROOT" "$RUNTIME_STATE" "$DEPLOYMENTS_ROOT" "$MAILBOXES_ROOT" "$PROJECTS_ROOT"; do
  sudo env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SOURCE_REPO_ROOT/tools" python3 -B -m local_hand.bootstrap_safety validate-roots \
    --state-root "$STATE_ROOT" --projects-root "$root"
done
[[ -n "$MAILBOX_SSH_KEY" && -f "$MAILBOX_SSH_KEY" ]] || { echo "--mailbox-ssh-key required for SSH mailbox URL" >&2; exit 1; }
[[ -n "$KNOWN_HOSTS_FILE" && -f "$KNOWN_HOSTS_FILE" ]] || { echo "--known-hosts-file required for SSH mailbox URL" >&2; exit 1; }
sudo install -m0440 -o root -g "$RUN_GROUP" "$MAILBOX_SSH_KEY" "$CREDENTIALS_ROOT/mailbox_id"
sudo install -m0440 -o root -g "$RUN_GROUP" "$KNOWN_HOSTS_FILE" "$CREDENTIALS_ROOT/known_hosts"
MAILBOX_KEY="$CREDENTIALS_ROOT/mailbox_id"; MAILBOX_KNOWN_HOSTS="$CREDENTIALS_ROOT/known_hosts"
SSH_COMMAND="$SSH_BIN -F /dev/null -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 -o IdentitiesOnly=yes -o IdentityAgent=none -o PermitLocalCommand=no -o ClearAllForwardings=yes -i $MAILBOX_KEY -o UserKnownHostsFile=$MAILBOX_KNOWN_HOSTS -o StrictHostKeyChecking=yes"

# Service-account subprocesses must not inherit a caller-owned or inaccessible working directory.
cd /

if [[ "$TARGET_NEEDS_SEED" == true ]]; then
  # Treat the caller-provided seed as immutable local Git server input.
  # Validate it in place; never chown it into the service account trust domain.
  sudo env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SOURCE_REPO_ROOT/tools" python3 -B -m local_hand.bootstrap_safety validate-roots \
    --state-root "$PROJECTS_ROOT" --projects-root "$TARGET_REPO"
    [[ -d "$SEED_REPOSITORY_FROM/.git" && ! -L "$SEED_REPOSITORY_FROM/.git" ]] || {
      echo "seed repository must be a standalone Git working copy with a real .git directory" >&2
      exit 1
    }

    [[ ! -e "$SEED_REPOSITORY_FROM/.git/objects/info/alternates" &&
       ! -e "$SEED_REPOSITORY_FROM/.git/objects/info/http-alternates" ]] || {
      echo "seed repository must not use external Git object alternates" >&2
      exit 1
    }

    SEED_METADATA_SPECIAL="$(
      sudo find "$SEED_REPOSITORY_FROM/.git" ! -type d ! -type f -print -quit
    )"
    [[ -z "$SEED_METADATA_SPECIAL" ]] || {
      echo "seed repository Git metadata must contain only regular files and directories: $SEED_METADATA_SPECIAL" >&2
      exit 1
    }

    SEED_ANCESTOR="$SEED_REPOSITORY_FROM"
    while [[ "$SEED_ANCESTOR" != "/" ]]; do
      SEED_ANCESTOR="$(dirname -- "$SEED_ANCESTOR")"
      SEED_ANCESTOR_UID="$(sudo stat -c '%u' -- "$SEED_ANCESTOR")"
      [[ "$SEED_ANCESTOR_UID" == 0 ]] || {
        echo "seed repository ancestors must be root-owned: $SEED_ANCESTOR" >&2
        exit 1
      }
      if sudo -u "$RUN_USER" test -w "$SEED_ANCESTOR"; then
        echo "seed repository ancestors must not be writable by run user: $SEED_ANCESTOR" >&2
        exit 1
      fi
    done

    SEED_OWNER_VIOLATION="$(
      sudo find "$SEED_REPOSITORY_FROM" ! -user root -print -quit
    )"
    [[ -z "$SEED_OWNER_VIOLATION" ]] || {
      echo "seed repository must be root-owned across its filesystem tree: $SEED_OWNER_VIOLATION" >&2
      exit 1
    }

    if ! SEED_WRITABLE_PATH="$(
      sudo -u "$RUN_USER" find "$SEED_REPOSITORY_FROM" -writable -print -quit
    )"; then
      echo "seed repository must be fully traversable by the run user for validation" >&2
      exit 1
    fi
    [[ -z "$SEED_WRITABLE_PATH" ]] || {
      echo "seed repository must not be writable by run user: $SEED_WRITABLE_PATH" >&2
      exit 1
    }

    if ! SEED_STATUS="$(
      GIT_OPTIONAL_LOCKS=0 git_safe -c "safe.directory=$SEED_REPOSITORY_FROM" -C "$SEED_REPOSITORY_FROM" \
        status --porcelain=v1 --untracked-files=all
    )"; then
      echo "cannot inspect seed repository status" >&2
      exit 1
    fi
    [[ -z "$SEED_STATUS" ]] || {
      echo "seed repository must be clean" >&2
      exit 1
    }

    if ! SEED_HEAD="$(
      git_safe -c "safe.directory=$SEED_REPOSITORY_FROM" -C "$SEED_REPOSITORY_FROM" rev-parse HEAD | tr '[:upper:]' '[:lower:]'
    )"; then
      echo "cannot resolve seed repository HEAD" >&2
      exit 1
    fi
    [[ "$SEED_HEAD" == "$IMPLEMENTATION_COMMIT" ]] || {
      echo "seed repository HEAD must equal implementation commit" >&2
      exit 1
    }

  (
    SEED_GIT_CONFIG="$(sudo mktemp "$STATE_ROOT/.local-hand-seed-git-config.XXXXXX")"
    case "$SEED_GIT_CONFIG" in
      "$STATE_ROOT"/.local-hand-seed-git-config.*) ;;
      *) echo "unsafe temporary seed Git config path: $SEED_GIT_CONFIG" >&2; exit 1 ;;
    esac
    trap 'sudo rm -f -- "$SEED_GIT_CONFIG" || true' EXIT

    sudo "$GIT_BIN" config --file "$SEED_GIT_CONFIG" --add safe.directory "$SEED_REPOSITORY_FROM"
    sudo chmod 0444 "$SEED_GIT_CONFIG"
    [[ "$(sudo stat -c '%u:%g:%a' -- "$SEED_GIT_CONFIG")" == 0:0:444 ]] || {
      echo "temporary seed Git config ownership/mode invalid" >&2
      exit 1
    }
    [[ "$(sudo "$GIT_BIN" config --file "$SEED_GIT_CONFIG" --get-all safe.directory)" == "$SEED_REPOSITORY_FROM" ]] || {
      echo "temporary seed Git config content invalid" >&2
      exit 1
    }
    sudo -u "$RUN_USER" test -r "$SEED_GIT_CONFIG" || {
      echo "temporary seed Git config is not readable by run user" >&2
      exit 1
    }

    sudo -u "$RUN_USER" env -i HOME="$RUN_HOME" PATH="$PATH" GIT_TERMINAL_PROMPT=0 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL="$SEED_GIT_CONFIG" \
      "$GIT_BIN" --no-pager -c core.hooksPath=/dev/null -c core.fsmonitor=false -c submodule.recurse=false -c credential.helper= -c protocol.ext.allow=never clone --no-local "$SEED_REPOSITORY_FROM" "$TARGET_REPO"
  )
fi
sudo env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SOURCE_REPO_ROOT/tools" python3 -B -m local_hand.bootstrap_safety validate-roots \
  --state-root "$PROJECTS_ROOT" --projects-root "$TARGET_REPO"
sudo env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SOURCE_REPO_ROOT/tools" python3 -B -m local_hand.bootstrap_safety validate-repository-target \
  --projects-root "$PROJECTS_ROOT" --repository-path "$REPOSITORY_PATH" >/dev/null
SOURCE_DIRTY_AFTER_PREPARATION="$(git_safe -c "safe.directory=$SOURCE_REPO_ROOT" -C "$SOURCE_REPO_ROOT" status --porcelain=v1 --untracked-files=all -- tools/local_hand)"
[[ -z "$SOURCE_DIRTY_AFTER_PREPARATION" ]] || { echo "tools/local_hand source tree became dirty during bootstrap preparation" >&2; exit 1; }
sudo chown -R "$RUN_USER:$RUN_GROUP" "$TARGET_REPO"

# Validation argv, timeout and replay_safe are admitted from the supplied profile.

STAGE_ROOT="$(mktemp -d)"
STAGE_WORKER_ROOT="$STAGE_ROOT/worker"; STAGE_PACKAGE_ROOT="$STAGE_WORKER_ROOT/local_hand"; STAGE_PROFILE="$STAGE_ROOT/node-profile.json"
mkdir -p "$STAGE_PACKAGE_ROOT"
PACKAGE_FILES=(__init__.py protocol.py paths.py config.py provenance.py installation.py observe.py act.py validate.py bounded_io.py git_safety.py mailbox_safety.py runtime_lock.py bootstrap_safety.py windows_runner.py worker.py)
for f in "${PACKAGE_FILES[@]}"; do [[ -f "$SCRIPT_DIR/$f" ]] || { echo "missing $f" >&2; exit 1; }; install -m0644 "$SCRIPT_DIR/$f" "$STAGE_PACKAGE_ROOT/$f"; done
cp -- "$PROFILE_SOURCE" "$STAGE_PROFILE"
[[ "$(sha256sum "$STAGE_PROFILE" | awk '{print $1}')" == "$ADMITTED_PROFILE_SHA" ]] || { echo "profile changed after admission" >&2; exit 1; }
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SOURCE_REPO_ROOT/tools" python3 -B -m local_hand.provenance --stamp "$STAGE_WORKER_ROOT" >/dev/null
PACKAGE_FILES+=(_build_metadata.json)
PYTHONPATH="$STAGE_WORKER_ROOT" python3 -m compileall -q "$STAGE_PACKAGE_ROOT"
sudo chgrp -R "$RUN_GROUP" "$STAGE_ROOT"
sudo chmod -R u=rwX,g=rX,o= "$STAGE_ROOT"
sudo -u "$RUN_USER" env -i HOME="$RUN_HOME" PATH="$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$STAGE_WORKER_ROOT" \
  python3 - "$STAGE_PROFILE" "$REPOSITORY_NAME" <<'PY'
from pathlib import Path
import sys
from local_hand.paths import load_profile, repository_root
from local_hand.worker import _package_digest
profile = load_profile(Path(sys.argv[1]))
assert profile.node_id and repository_root(profile, sys.argv[2]) and len(_package_digest()) == 64
PY
PROFILE_SHA="$(sha256sum "$STAGE_PROFILE" | awk '{print $1}')"
DEPLOYMENT_ID="$IMPLEMENTATION_COMMIT-${PROFILE_SHA:0:12}"
DEPLOYMENT_ROOT="$DEPLOYMENTS_ROOT/$DEPLOYMENT_ID"

if sudo test -e "$DEPLOYMENT_ROOT"; then
  python3 - "$STAGE_ROOT" "$DEPLOYMENT_ROOT" <<'PY'
from pathlib import Path
import hashlib,sys
stage,existing=map(Path,sys.argv[1:])
files=["node-profile.json"]+[str(p.relative_to(stage)) for p in (stage/"worker/local_hand").iterdir() if p.is_file()]
for rel in files:
    a,b=stage/rel,existing/rel
    if not b.is_file() or hashlib.sha256(a.read_bytes()).digest()!=hashlib.sha256(b.read_bytes()).digest():
        raise SystemExit(f"existing immutable deployment mismatch: {rel}")
PY
else
  sudo install -d -m0755 -o root -g root "$DEPLOYMENT_ROOT/worker/local_hand"
  for f in "${PACKAGE_FILES[@]}"; do sudo install -m0444 -o root -g root "$STAGE_PACKAGE_ROOT/$f" "$DEPLOYMENT_ROOT/worker/local_hand/$f"; done
  sudo install -m0444 -o root -g root "$STAGE_PROFILE" "$DEPLOYMENT_ROOT/node-profile.json"
  DEPLOYMENT_CREATED=true
fi
WORKER_ROOT="$DEPLOYMENT_ROOT/worker"; PROFILE_PATH="$DEPLOYMENT_ROOT/node-profile.json"

MAILBOX_ROOT="$MAILBOXES_ROOT/$INSTALL_INSTANCE_ID"
CLONE_ARGS=(clone --depth=1 --filter=blob:limit=8388608 --no-checkout --origin origin --single-branch --branch "$MAILBOX_BRANCH" "$MAILBOX_URL" "$MAILBOX_ROOT")
sudo -u "$RUN_USER" env -i HOME="$RUN_HOME" PATH="$PATH" GIT_TERMINAL_PROMPT=0 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_SSH_COMMAND="$SSH_COMMAND" "$GIT_BIN" --no-pager -c core.hooksPath=/dev/null -c core.fsmonitor=false -c submodule.recurse=false -c credential.helper= -c protocol.ext.allow=never "${CLONE_ARGS[@]}"
sudo -u "$RUN_USER" env -i HOME="$RUN_HOME" PATH="$PATH" PYTHONPATH="$WORKER_ROOT" GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null \
  python3 - "$MAILBOX_ROOT" "origin/$MAILBOX_BRANCH" <<'PY'
from pathlib import Path
import sys
from local_hand.git_safety import assert_no_execution_filters,sanitized_git_env
from local_hand.mailbox_safety import admit_remote_tree
r=Path(sys.argv[1]); assert_no_execution_filters(r,sanitized_git_env()); admit_remote_tree(r,sys.argv[2])
PY
sudo -u "$RUN_USER" env -i HOME="$RUN_HOME" PATH="$PATH" GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null "$GIT_BIN" --no-pager -c core.hooksPath=/dev/null -c core.fsmonitor=false -c submodule.recurse=false -c credential.helper= -c protocol.ext.allow=never -C "$MAILBOX_ROOT" sparse-checkout init --no-cone
sudo -u "$RUN_USER" env -i HOME="$RUN_HOME" PATH="$PATH" GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null "$GIT_BIN" --no-pager -c core.hooksPath=/dev/null -c core.fsmonitor=false -c submodule.recurse=false -c credential.helper= -c protocol.ext.allow=never -C "$MAILBOX_ROOT" sparse-checkout set --no-cone '/_executor_spike/tasks/' '/_executor_spike/results/' '/_executor_spike/conflicts/'
sudo -u "$RUN_USER" env -i HOME="$RUN_HOME" PATH="$PATH" GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 "$GIT_BIN" --no-pager -c core.hooksPath=/dev/null -c core.fsmonitor=false -c submodule.recurse=false -c credential.helper= -c protocol.ext.allow=never -C "$MAILBOX_ROOT" reset --hard "origin/$MAILBOX_BRANCH"
sudo -u "$RUN_USER" env -i HOME="$RUN_HOME" PATH="$PATH" PYTHONPATH="$WORKER_ROOT" python3 - "$MAILBOX_ROOT" <<'PY'
from pathlib import Path
import sys
from local_hand.mailbox_safety import validate_checkout_control_dirs
validate_checkout_control_dirs(Path(sys.argv[1]))
PY

TEMP_UNIT="$(mktemp)"; OLD_UNIT_BACKUP="$(mktemp)"
INSTALL_RECORD="$CREDENTIALS_ROOT/install-record.json"
sudo env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$WORKER_ROOT" python3 -B -m local_hand.installation --profile "$PROFILE_PATH" --output "$INSTALL_RECORD" --state-root "$RUNTIME_STATE" --mailbox-root "$MAILBOX_ROOT" --install-instance-id "$INSTALL_INSTANCE_ID" --git "$GIT_BIN" --ssh "$SSH_BIN" --mailbox-key "$MAILBOX_KEY" --known-hosts "$MAILBOX_KNOWN_HOSTS"
sudo chown root:"$RUN_GROUP" "$INSTALL_RECORD"; sudo chmod 0440 "$INSTALL_RECORD"
assert_owned_existing_unit
if sudo test -e "$UNIT_PATH"; then
  sudo cat "$UNIT_PATH" >"$OLD_UNIT_BACKUP"; OLD_UNIT_EXISTS=true
fi
if [[ "$OLD_UNIT_EXISTS" == true ]]; then
  OLD_ACTIVE_STATE="$(sudo systemctl show "${SERVICE_NAME}.service" --property=ActiveState --value 2>/dev/null)" || { echo "cannot determine old Local Hand active state" >&2; exit 1; }
  case "$OLD_ACTIVE_STATE" in active) OLD_WAS_ACTIVE=true;; inactive|failed) OLD_WAS_ACTIVE=false;; *) echo "old Local Hand active state is transitional/indeterminate: $OLD_ACTIVE_STATE" >&2; exit 1;; esac
  OLD_UNIT_FILE_STATE="$(sudo systemctl show "${SERVICE_NAME}.service" --property=UnitFileState --value 2>/dev/null)" || { echo "cannot determine old Local Hand enable state" >&2; exit 1; }
  case "$OLD_UNIT_FILE_STATE" in enabled) OLD_WAS_ENABLED=true;; disabled) OLD_WAS_ENABLED=false;; *) echo "old Local Hand enable state is unsupported/indeterminate: $OLD_UNIT_FILE_STATE" >&2; exit 1;; esac
fi
PYTHON_BIN="$(command -v python3)"
[[ "$PYTHON_BIN" != *%* ]] || { echo "v0.1 systemd unit values must not contain '%': $PYTHON_BIN" >&2; exit 2; }
[[ "$PYTHON_BIN" =~ ^/[A-Za-z0-9._/@:+-]+$ ]] || { echo "v0.1 systemd unit paths must use safe absolute ASCII syntax: $PYTHON_BIN" >&2; exit 2; }
cat >"$TEMP_UNIT" <<EOF
# X-Local-Hand-Owner=$SERVICE_OWNER_TOKEN
# X-Local-Hand-StateRoot=$STATE_ROOT
# X-Local-Hand-NodeId=$NODE_ID
[Unit]
Description=Local Hand v0.1 ($NODE_ID)
Wants=network-online.target
After=network-online.target
[Service]
Type=simple
User=$RUN_USER
Group=$RUN_GROUP
Environment=HOME=$RUN_HOME
Environment=PYTHONPATH=$WORKER_ROOT
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONNOUSERSITE=1
Environment=LOCAL_HAND_GIT_TIMEOUT_SECONDS=45
Environment=LOCAL_HAND_IMPLEMENTATION_COMMIT=$IMPLEMENTATION_COMMIT
Environment=LOCAL_HAND_INSTALL_INSTANCE_ID=$INSTALL_INSTANCE_ID
Environment=LOCAL_HAND_INSTALL_RECORD=$INSTALL_RECORD
Environment=LOCAL_HAND_GIT_EXECUTABLE=$GIT_BIN
Environment=LOCAL_HAND_SSH_EXECUTABLE=$SSH_BIN
Environment=LOCAL_HAND_MAILBOX_USES_SSH=1
Environment=LOCAL_HAND_MAILBOX_SSH_KEY=$MAILBOX_KEY
Environment=LOCAL_HAND_KNOWN_HOSTS=$MAILBOX_KNOWN_HOSTS
ExecStart=$PYTHON_BIN -m local_hand.worker --profile $PROFILE_PATH --mailbox-repo $MAILBOX_ROOT --mailbox-branch $MAILBOX_BRANCH --state-root $RUNTIME_STATE --poll-seconds 5
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RestrictRealtime=true
LockPersonality=true
CapabilityBoundingSet=
AmbientCapabilities=
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
ReadOnlyPaths=$DEPLOYMENT_ROOT $CREDENTIALS_ROOT
ReadWritePaths=$RUNTIME_STATE $PROJECTS_ROOT $MAILBOX_ROOT
[Install]
WantedBy=multi-user.target
EOF

SWITCH_STARTED=true
if [[ "$OLD_UNIT_EXISTS" == true ]]; then
  sudo systemctl stop "${SERVICE_NAME}.service"
  if ! service_is_confirmed_stopped; then
    echo "old Local Hand service did not stop before upgrade" >&2
    exit 1
  fi
fi
sudo install -m0644 "$TEMP_UNIT" "$UNIT_PATH"
sudo systemctl daemon-reload
assert_owned_existing_unit
sudo systemctl enable "${SERVICE_NAME}.service" >/dev/null
sudo systemctl restart "${SERVICE_NAME}.service"
sleep 3
sudo systemctl is-active --quiet "${SERVICE_NAME}.service"
SWITCH_COMMITTED=true

echo BOOTSTRAP=PASS
echo NODE_ID="$NODE_ID"
echo RUN_USER="$RUN_USER"
echo RUN_GROUP="$RUN_GROUP"
echo STATE_ROOT="$STATE_ROOT"
echo PROJECTS_ROOT="$PROJECTS_ROOT"
echo PROFILE="$PROFILE_PATH"
echo MAILBOX="$MAILBOX_ROOT"
echo DEPLOYMENT_ID="$DEPLOYMENT_ID"
echo INSTALL_INSTANCE_ID="$INSTALL_INSTANCE_ID"
echo IMPLEMENTATION_COMMIT="$IMPLEMENTATION_COMMIT"
echo SOURCE_HEAD_VERIFIED="$ACTUAL_SOURCE_HEAD"
echo SOURCE_TREE_CLEAN=true
echo SERVICE_ACTIVE=true
echo DEDICATED_OS_IDENTITY=true
echo DEDICATED_OS_GROUP=true
echo IMMUTABLE_DEPLOYMENT=true
echo INDEPENDENT_MAILBOX=true
echo VALIDATION_PROFILE_ADMITTED=true
echo SINGLE_WRITER="$(profile_field single_writer)"
