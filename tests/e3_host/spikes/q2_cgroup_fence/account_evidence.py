#!/usr/bin/env python3
"""Fixed H07 account observation and ownership evidence; not a general runner.

Import and receipt validation are platform independent. Only the explicit internal
observer imports Linux NSS modules. A caller supplies bounded command supervision.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

SOURCE_LIMITS = {"/etc/nsswitch.conf": 16384, "/etc/passwd": 262144, "/etc/group": 262144}
OUTPUT_LIMIT = 8192
TOOLS = ("/usr/sbin/useradd", "/usr/sbin/userdel", "/usr/sbin/groupdel")
PHASES = ("pre_create", "post_create", "pre_cleanup", "post_userdel", "post_groupdel")
ROLES = (*PHASES, "useradd", "userdel", "groupdel")
ASSUMPTIONS = {"trusted_host_os": True, "no_concurrent_account_management": True,
               "systemd_service_internal_work_bounded": False}
EMPTY_SHA = hashlib.sha256(b"").hexdigest()


class AccountEvidenceError(RuntimeError):
    pass


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _integer(value, maximum=2**63 - 1):
    return type(value) is int and 0 <= value <= maximum


def _identifier(value):
    return _integer(value, 2**32 - 2)


def _name(value):
    return isinstance(value, str) and re.fullmatch(r"q2hf[0-9]{1,15}r[23]", value) is not None


def _keys(value, names):
    return type(value) is dict and set(value) == set(names.split())


def _json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise AccountEvidenceError("duplicate_json_key")
            result[key] = value
        return result
    try:
        return json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(AccountEvidenceError("nonfinite_json")))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise AccountEvidenceError("invalid_json") from exc


def _fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _protected(info):
    return stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022


def _open_sources():
    opened = {}
    try:
        for path, limit in SOURCE_LIMITS.items():
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            opened[path] = (fd, os.fstat(fd))
            info = opened[path][1]
            if not _protected(info) or info.st_size > limit:
                raise AccountEvidenceError("source_protection_or_size")
            if _fingerprint(os.stat(path, follow_symlinks=False)) != _fingerprint(info):
                raise AccountEvidenceError("source_path_changed")
        return opened
    except BaseException:
        for fd, _ in opened.values():
            os.close(fd)
        raise


def _read_sources(opened):
    raw, summaries = {}, []
    for path, (fd, info) in opened.items():
        data = bytearray()
        limit = SOURCE_LIMITS[path]
        while len(data) <= limit:
            part = os.read(fd, min(65536, limit + 1 - len(data)))
            if not part:
                break
            data.extend(part)
        if len(data) > limit or len(data) != info.st_size:
            raise AccountEvidenceError("source_size_changed")
        raw[path] = bytes(data)
        summaries.append(dict(zip(("dev", "ino", "size", "mtime_ns", "ctime_ns"), _fingerprint(info)),
                              path=path, sha256=_sha(data)))
    return raw, summaries


def _stable(opened):
    for path, (fd, before) in opened.items():
        after = os.fstat(fd)
        current = os.stat(path, follow_symlinks=False)
        if (not _protected(after) or not _protected(current)
                or _fingerprint(before) != _fingerprint(after)
                or _fingerprint(before) != _fingerprint(current)):
            return False
    return True


def parse_sources(raw):
    """Parse bounded bytes only. No NSS, file access or disclosure of other rows."""
    if set(raw) != set(SOURCE_LIMITS) or any(not isinstance(value, bytes) or len(value) > SOURCE_LIMITS[key]
                                           for key, value in raw.items()):
        raise AccountEvidenceError("source_input_shape")
    try:
        texts = {key: value.decode("utf-8", "strict") for key, value in raw.items()}
    except UnicodeError as exc:
        raise AccountEvidenceError("source_encoding") from exc
    if any("\0" in text for text in texts.values()):
        raise AccountEvidenceError("source_nul")
    providers = {}
    for line in texts["/etc/nsswitch.conf"].splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            raise AccountEvidenceError("nss_syntax")
        database, names = line.split(":", 1)
        database = database.strip()
        if database not in ("passwd", "group", "initgroups"):
            continue
        names = names.split()
        if database in providers or names not in (["files"], ["files", "systemd"]):
            raise AccountEvidenceError("nss_provider_rejected")
        providers[database] = names
    if "passwd" not in providers or "group" not in providers:
        raise AccountEvidenceError("nss_database_missing")
    if "initgroups" in providers and providers["initgroups"] != providers["group"]:
        raise AccountEvidenceError("nss_initgroups_mismatch")
    providers.setdefault("initgroups", providers["group"][:])
    users, groups = [], []
    seen_users, seen_groups = set(), set()
    for path, width, rows, seen in (("/etc/passwd", 7, users, seen_users), ("/etc/group", 4, groups, seen_groups)):
        for line in texts[path].splitlines():
            if not line:
                continue
            cells = line.split(":")
            if len(cells) != width or not cells[0] or cells[0] in seen or any(ord(c) < 32 for c in line):
                raise AccountEvidenceError("database_record_invalid")
            seen.add(cells[0])
            if not re.fullmatch(r"[0-9]+", cells[2]) or not _identifier(int(cells[2])):
                raise AccountEvidenceError("database_id_invalid")
            if width == 7:
                if not re.fullmatch(r"[0-9]+", cells[3]) or not _identifier(int(cells[3])):
                    raise AccountEvidenceError("database_id_invalid")
                rows.append({"name": cells[0], "uid": int(cells[2]), "gid": int(cells[3]),
                             "home": cells[5], "shell": cells[6]})
            else:
                members = cells[3].split(",") if cells[3] else []
                if any(not member for member in members) or len(members) != len(set(members)):
                    raise AccountEvidenceError("group_members_invalid")
                rows.append({"name": cells[0], "gid": int(cells[2]), "members": members})
    return providers, users, groups


class _Resolver:
    def __init__(self):
        import pwd
        import grp
        self.pwd, self.grp = pwd, grp

    def user_name(self, name):
        try:
            row = self.pwd.getpwnam(name)
        except KeyError:
            return None
        return {"name": row.pw_name, "uid": row.pw_uid, "gid": row.pw_gid,
                "home": row.pw_dir, "shell": row.pw_shell}

    def group_name(self, name):
        try:
            row = self.grp.getgrnam(name)
        except KeyError:
            return None
        return {"name": row.gr_name, "gid": row.gr_gid, "members": list(row.gr_mem)}

    def user_id(self, uid):
        try:
            row = self.pwd.getpwuid(uid)
        except KeyError:
            return None
        return {"name": row.pw_name, "uid": row.pw_uid, "gid": row.pw_gid,
                "home": row.pw_dir, "shell": row.pw_shell}

    def group_id(self, gid):
        try:
            row = self.grp.getgrgid(gid)
        except KeyError:
            return None
        return {"name": row.gr_name, "gid": row.gr_gid, "members": list(row.gr_mem)}

    def memberships(self, name, gid):
        return os.getgrouplist(name, gid)


def _target_facts(name, expected_uid, expected_gid, providers, users, groups, resolver):
    user = next((row for row in users if row["name"] == name), None)
    group = next((row for row in groups if row["name"] == name), None)
    # Source admission and complete bounded files parsing happen before ANY NSS call.
    if resolver.user_name(name) != user or resolver.group_name(name) != group:
        raise AccountEvidenceError("nss_target_mismatch")
    memberships = []
    if user is not None:
        if resolver.user_id(user["uid"]) != user or resolver.group_id(user["gid"]) != group:
            raise AccountEvidenceError("nss_id_mismatch")
        memberships = resolver.memberships(name, user["gid"])
        if (not isinstance(memberships, list) or len(memberships) > 64
                or any(not _identifier(value) for value in memberships)
                or len(memberships) != len(set(memberships))):
            raise AccountEvidenceError("nss_memberships_invalid")
        local_memberships = {user["gid"]} | {row["gid"] for row in groups if name in row["members"]}
        if set(memberships) != local_memberships:
            raise AccountEvidenceError("nss_memberships_mismatch")
    uid = expected_uid if expected_uid is not None else (user["uid"] if user else None)
    gid = expected_gid if expected_gid is not None else (user["gid"] if user else group["gid"] if group else None)
    conflicts = {"uid_aliases": sum(row["uid"] == uid and row["name"] != name for row in users),
                 "gid_aliases": sum(row["gid"] == gid and row["name"] != name for row in groups),
                 "other_primary_refs": sum(row["gid"] == gid and row["name"] != name for row in users),
                 "group_members": len(group["members"]) if group else 0}
    identity = None if user is None else dict(user, supplementary_gids=sorted(memberships),
                                            group_member_count=len(group["members"]) if group else None)
    safe_group = None if group is None else {"name": name, "gid": group["gid"], "member_count": len(group["members"])}
    classification = "ABSENT_BOTH" if user is None and group is None else "PARTIAL"
    if user is not None and group is not None and user["gid"] == group["gid"]:
        classification = "EXACT_PAIR"
    return {"providers": providers, "identity": identity, "group": safe_group,
            "conflicts": conflicts, "classification": classification, "nss_match": True}


def observe(name, expected_uid=None, expected_gid=None):
    """Internal fixed observer. Parent owns the <=2s dual-clock process deadline."""
    if not _name(name) or ((expected_uid is None) != (expected_gid is None)) or (
            expected_uid is not None and (not _identifier(expected_uid) or not _identifier(expected_gid))):
        raise AccountEvidenceError("observer_argument_rejected")
    start_mono = time.monotonic_ns()
    start_boot = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    result = {"schema_version": 1, "target": name, "expected_uid": expected_uid,
              "expected_gid": expected_gid, "classification": "UNOBSERVABLE", "complete": False,
              "reason": None, "sources": [], "providers": None, "identity": None, "group": None,
              "conflicts": None, "nss_match": False, "stable": False, "clocks": None}
    opened = {}
    try:
        opened = _open_sources()
        raw, result["sources"] = _read_sources(opened)
        providers, users, groups = parse_sources(raw)
        result.update(_target_facts(name, expected_uid, expected_gid, providers, users, groups, _Resolver()))
        if not _stable(opened):
            raise AccountEvidenceError("source_changed")
        result.update(complete=True, stable=True)
    except (AccountEvidenceError, OSError, ValueError, OverflowError) as exc:
        result["classification"] = "AMBIGUOUS" if isinstance(exc, AccountEvidenceError) else "UNOBSERVABLE"
        result["reason"] = str(exc) if isinstance(exc, AccountEvidenceError) else "source_or_nss_os_error"
    finally:
        for fd, _ in opened.values():
            os.close(fd)
        result["clocks"] = {"start_mono_ns": start_mono, "start_boot_ns": start_boot,
                            "end_mono_ns": time.monotonic_ns(),
                            "end_boot_ns": time.clock_gettime_ns(time.CLOCK_BOOTTIME)}
    return result


def _identity_ok(value):
    return (_keys(value, "name uid gid home shell supplementary_gids group_member_count")
            and _name(value["name"]) and _identifier(value["uid"]) and value["uid"] > 0
            and _identifier(value["gid"]) and value["gid"] > 0
            and value["home"] == "/nonexistent" and value["shell"] == "/usr/sbin/nologin"
            and value["supplementary_gids"] == [value["gid"]] and value["group_member_count"] == 0)


def validate_audit(value):
    errors = []
    names = ("command_id role attempted started exit_observed rc timeout termination_requested stdout stderr "
             "deadline_met pending start_mono_ns start_boot_ns deadline_mono_ns deadline_boot_ns end_mono_ns end_boot_ns")
    if not _keys(value, names):
        return ["command audit fields"]
    if not isinstance(value["command_id"], str) or not re.fullmatch(r"[1-9][0-9]{0,18}-[23]-[1-9][0-9]{0,5}", value["command_id"]):
        errors.append("command audit identity")
    if value["role"] not in ROLES:
        errors.append("command audit role")
    for key in ("attempted", "started", "exit_observed", "timeout", "termination_requested", "deadline_met", "pending"):
        if type(value[key]) is not bool:
            errors.append("command audit boolean " + key)
    for key in ("start_mono_ns", "start_boot_ns", "deadline_mono_ns", "deadline_boot_ns", "end_mono_ns", "end_boot_ns"):
        if not _integer(value[key]):
            errors.append("command audit clock " + key)
    if value["rc"] is not None and type(value["rc"]) is not int:
        errors.append("command audit rc")
    if (value["exit_observed"] != (value["rc"] is not None) or (value["started"] and not value["attempted"])
            or (value["exit_observed"] and not value["started"])):
        errors.append("command audit exit/start relation")
    for stream in ("stdout", "stderr"):
        row = value[stream]
        if (not _keys(row, "eof complete bytes sha256") or type(row.get("eof")) is not bool
                or type(row.get("complete")) is not bool or not _integer(row.get("bytes"), 262144)
                or not isinstance(row.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
            errors.append("command audit stream " + stream)
        elif row["bytes"] == 0 and row["sha256"] != EMPTY_SHA:
            errors.append("command audit empty stream digest")
    if not errors:
        met = all(value["start_" + clock + "_ns"] <= value["end_" + clock + "_ns"] <= value["deadline_" + clock + "_ns"]
                  for clock in ("mono", "boot"))
        if value["deadline_met"] != met:
            errors.append("command audit deadline relation")
        if value["pending"] is False and value["started"] and not (
                value["exit_observed"] and value["stdout"]["eof"] and value["stderr"]["eof"]):
            errors.append("command audit unresolved process/streams")
        if value["role"] in PHASES and any(value["deadline_" + c + "_ns"] - value["start_" + c + "_ns"] > 2_000_000_000
                                            for c in ("mono", "boot")):
            errors.append("observer window exceeds two seconds")
    return errors


def _settled(audit):
    return (not validate_audit(audit) and audit["started"] and audit["exit_observed"] and not audit["pending"]
            and audit["stdout"]["eof"] and audit["stderr"]["eof"])


def _complete(audit):
    return (_settled(audit) and not audit["timeout"] and audit["deadline_met"]
            and audit["stdout"]["complete"] and audit["stderr"]["complete"])


def _validate_observation(value):
    if not _keys(value, "schema_version target expected_uid expected_gid classification complete reason sources providers identity group conflicts nss_match stable clocks"):
        return ["observation fields"]
    errors = []
    if type(value["schema_version"]) is not int or value["schema_version"] != 1 or not _name(value["target"]):
        errors.append("observation identity/version")
    if ((value["expected_uid"] is None) != (value["expected_gid"] is None)) or any(
            value[key] is not None and not _identifier(value[key]) for key in ("expected_uid", "expected_gid")):
        errors.append("observation expected identity")
    if value["classification"] not in ("ABSENT_BOTH", "EXACT_PAIR", "PARTIAL", "AMBIGUOUS", "UNOBSERVABLE"):
        errors.append("observation classification")
    for key in ("complete", "nss_match", "stable"):
        if type(value[key]) is not bool:
            errors.append("observation boolean")
    clocks = value["clocks"]
    if (not _keys(clocks, "start_mono_ns start_boot_ns end_mono_ns end_boot_ns")
            or any(not _integer(v) for v in clocks.values())
            or clocks["end_mono_ns"] < clocks["start_mono_ns"] or clocks["end_boot_ns"] < clocks["start_boot_ns"]):
        errors.append("observation clocks")
    sources = value["sources"]
    if not isinstance(sources, list) or len(sources) > 3:
        errors.append("observation sources")
    else:
        paths = []
        for row in sources:
            if (not _keys(row, "path dev ino size mtime_ns ctime_ns sha256") or row["path"] not in SOURCE_LIMITS
                    or any(not _integer(row[key]) for key in ("dev", "ino", "size", "mtime_ns", "ctime_ns"))
                    or row["size"] > SOURCE_LIMITS.get(row["path"], 0)
                    or not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
                errors.append("observation source fields")
            else:
                paths.append(row["path"])
        if len(paths) != len(set(paths)):
            errors.append("observation duplicate source")
    if value["complete"]:
        if value["reason"] is not None or not value["stable"] or not value["nss_match"] or len(sources) != 3:
            errors.append("complete observation lacks evidence")
        providers = value["providers"]
        if (not _keys(providers, "passwd group initgroups")
                or any(row not in (["files"], ["files", "systemd"]) for row in providers.values())
                or providers["initgroups"] != providers["group"]):
            errors.append("observation providers")
        conflicts = value["conflicts"]
        if not _keys(conflicts, "uid_aliases gid_aliases other_primary_refs group_members") or any(not _integer(v) for v in conflicts.values()):
            errors.append("observation conflicts")
        identity, group = value["identity"], value["group"]
        if identity is not None and (not _keys(identity, "name uid gid home shell supplementary_gids group_member_count")
                or identity["name"] != value["target"] or not _identifier(identity["uid"]) or not _identifier(identity["gid"])
                or not isinstance(identity["home"], str) or not isinstance(identity["shell"], str)
                or len(identity["home"]) > 1024 or len(identity["shell"]) > 1024
                or not isinstance(identity["supplementary_gids"], list) or len(identity["supplementary_gids"]) > 64
                or any(not _identifier(v) for v in identity["supplementary_gids"])
                or (identity["group_member_count"] is not None and not _integer(identity["group_member_count"]))):
            errors.append("observation candidate identity")
        if group is not None and (not _keys(group, "name gid member_count") or group["name"] != value["target"]
                                  or not _identifier(group["gid"]) or not _integer(group["member_count"])):
            errors.append("observation group")
        if not errors:
            actual = "ABSENT_BOTH" if identity is None and group is None else "PARTIAL"
            if identity is not None and group is not None and identity["gid"] == group["gid"]:
                actual = "EXACT_PAIR"
            if value["classification"] != actual:
                errors.append("observation classification relation")
            if group is not None and (conflicts["group_members"] != group["member_count"] or
                                     (identity is not None and identity["group_member_count"] != group["member_count"])):
                errors.append("observation group count relation")
    else:
        if (not isinstance(value["reason"], str) or not 1 <= len(value["reason"]) <= 128
                or value["classification"] not in ("AMBIGUOUS", "UNOBSERVABLE") or value["stable"]):
            errors.append("incomplete observation reason/classification")
        providers, identity, group, conflicts = (value[key] for key in ("providers", "identity", "group", "conflicts"))
        if providers is not None and (not _keys(providers, "passwd group initgroups")
                or any(row not in (["files"], ["files", "systemd"]) for row in providers.values())
                or providers["initgroups"] != providers["group"]):
            errors.append("incomplete observation providers")
        if identity is not None and (not _keys(identity, "name uid gid home shell supplementary_gids group_member_count")
                or identity["name"] != value["target"] or not _identifier(identity["uid"]) or not _identifier(identity["gid"])
                or not isinstance(identity["home"], str) or not isinstance(identity["shell"], str)
                or len(identity["home"]) > 1024 or len(identity["shell"]) > 1024
                or not isinstance(identity["supplementary_gids"], list) or len(identity["supplementary_gids"]) > 64
                or any(not _identifier(v) for v in identity["supplementary_gids"])
                or (identity["group_member_count"] is not None and not _integer(identity["group_member_count"]))):
            errors.append("incomplete observation candidate")
        if group is not None and (not _keys(group, "name gid member_count") or group["name"] != value["target"]
                                  or not _identifier(group["gid"]) or not _integer(group["member_count"])):
            errors.append("incomplete observation group")
        if conflicts is not None and (not _keys(conflicts, "uid_aliases gid_aliases other_primary_refs group_members")
                                     or any(not _integer(v) for v in conflicts.values())):
            errors.append("incomplete observation conflicts")
    return errors


def validate_observation(value):
    try:
        return _validate_observation(value)
    except (TypeError, ValueError, KeyError, IndexError, AttributeError, RecursionError):
        return ["malformed observation"]


def _good(row):
    return (row is not None and not validate_observation(row) and row["complete"]
            and not any(row["conflicts"].values()))


def _admissible(row):
    return _good(row) and row["classification"] == "EXACT_PAIR" and _identity_ok(row["identity"])


def _absent(row):
    return _good(row) and row["classification"] == "ABSENT_BOTH"


def pin_tools():
    result = []
    for path in TOOLS:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if not _protected(before) or not before.st_mode & 0o111 or before.st_size > 2 * 1024**2:
                raise AccountEvidenceError("account_tool_protection")
            raw = bytearray()
            while len(raw) <= before.st_size:
                chunk = os.read(fd, min(65536, before.st_size + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
            if (len(raw) != before.st_size or _fingerprint(before) != _fingerprint(os.fstat(fd))
                    or _fingerprint(before) != _fingerprint(os.stat(path, follow_symlinks=False))):
                raise AccountEvidenceError("account_tool_changed")
            result.append({"path": path, "sha256": _sha(raw), "size": len(raw), "version": None,
                           "version_basis": "not_invoked", "dev": before.st_dev, "ino": before.st_ino,
                           "mtime_ns": before.st_mtime_ns, "ctime_ns": before.st_ctime_ns})
        finally:
            os.close(fd)
    return result


class AccountLifecycle:
    def __init__(self, fixture, module_path=None):
        self.fixture = fixture
        self.module_path = Path(module_path) if module_path else Path(__file__).resolve()
        self.record = {"schema_version": 1, "target": fixture.account, "run_id": fixture.run_id,
                       "round": fixture.round, "assumptions": dict(ASSUMPTIONS), "tools": [],
                       "observations": [], "create_command": None, "observed_identity": None,
                       "admitted_identity": None, "delete_commands": [], "cleanup_verified": False,
                       "failure": None}
        self.blocked = False

    def _fail(self, reason):
        if self.record["failure"] is None:
            self.record["failure"] = reason
        raise AccountEvidenceError(reason)

    def _command(self, argv, deadline, role, cleanup=False):
        try:
            rc, raw, audit = self.fixture.audit_command(argv, deadline, role=role,
                                                       stdout_limit=OUTPUT_LIMIT, cleanup=cleanup)
        except Exception:
            audit = getattr(self.fixture, "last_command_audit", None)
            if not isinstance(audit, dict) or audit.get("role") != role:
                self.blocked = True
                raise
            rc, raw = audit.get("rc"), b""
        if validate_audit(audit):
            self.blocked = True
            self._fail("command_audit_invalid")
        if not _complete(audit):
            self.blocked = True
        return rc, raw, audit

    def _observe(self, phase, deadline, *, cleanup=False):
        if (self.blocked or getattr(self.fixture, "account_commands_blocked", False)
                or getattr(self.fixture, "pending_commands", [])):
            self._fail("original_command_unresolved")
        if len(self.record["observations"]) >= 5 or phase in [row["phase"] for row in self.record["observations"]]:
            self._fail("observation_limit")
        admitted = self.record["admitted_identity"]
        argv = [sys.executable, "-I", "-B", str(self.module_path), "--observe", self.fixture.account]
        if admitted is not None:
            argv += ["--uid", str(admitted["uid"]), "--gid", str(admitted["gid"])]
        rc, raw, audit = self._command(argv, self.fixture.observer_deadline(deadline), phase, cleanup)
        entry = {"phase": phase, "audit": audit, "observation": None}
        self.record["observations"].append(entry)
        if not _complete(audit) or rc != 0 or len(raw) > OUTPUT_LIMIT or audit["stdout"]["bytes"] != len(raw) or audit["stdout"]["sha256"] != _sha(raw):
            self._fail("observer_capture_incomplete")
        try:
            value = _json(raw)
        except AccountEvidenceError:
            self._fail("observer_json_invalid")
        entry["observation"] = value
        if validate_observation(value) or value["target"] != self.fixture.account or (
                value["expected_uid"], value["expected_gid"]) != ((admitted["uid"], admitted["gid"]) if admitted else (None, None)):
            self._fail("observer_record_invalid")
        if phase == "post_create":
            self.record["observed_identity"] = value["identity"]
        if not value["complete"]:
            self._fail("observer_incomplete")
        return value

    def create(self, deadline):
        if self.record["create_command"] is not None or self.record["observations"]:
            self._fail("account_setup_replay")
        deadline.check()
        self.record["tools"] = pin_tools()
        deadline.check()
        before = self._observe("pre_create", deadline)
        if not _absent(before):
            self._fail("dedicated_name_not_absent")
        self.fixture.account_attempted = True
        # --system, without -F, suppresses mail and subids; no login.defs mail key.
        rc, _, audit = self._command([TOOLS[0], "--system", "--user-group", "--no-create-home",
                                      "--no-log-init", "--home-dir", "/nonexistent", "--shell",
                                      "/usr/sbin/nologin", self.fixture.account], deadline, "useradd")
        self.record["create_command"] = audit
        after = None
        if not self.blocked:
            after = self._observe("post_create", deadline)
            self.record["observed_identity"] = after["identity"]
        if not _complete(audit) or rc != 0:
            self._fail("account_creation_not_confirmed")
        if not _admissible(after):
            self._fail("account_postconditions_failed")
        identity = dict(after["identity"])
        self.record["admitted_identity"] = identity
        self.fixture.account_id = (identity["uid"], identity["gid"])
        self.fixture.facts["account"] = {"uid": identity["uid"], "gid": identity["gid"],
                                          "supplementary_groups": [], "home_created": False}
        return identity

    def cleanup(self, deadline):
        admitted = self.record["admitted_identity"]
        if (self.blocked or getattr(self.fixture, "account_commands_blocked", False)
                or getattr(self.fixture, "pending_commands", [])):
            return False, ["account command or observer completion remains unverified"]
        if admitted is None:
            if self.record["create_command"] is not None or self.fixture.account_attempted:
                return False, ["account creation was attempted but its exact identity is not established"]
            # No account mutation was attempted; this does not certify host rollback.
            return True, []
        try:
            if self.record["delete_commands"]:
                self._fail("account_cleanup_replay")
            before = self._observe("pre_cleanup", deadline, cleanup=True)
            if not _admissible(before) or before["identity"] != admitted:
                self._fail("account_cleanup_identity_mismatch")
            rc, _, audit = self._command([TOOLS[1], self.fixture.account], deadline, "userdel", True)
            self.record["delete_commands"].append(audit)
            if not _complete(audit) or rc != 0:
                self._fail("userdel_not_confirmed")
            after = self._observe("post_userdel", deadline, cleanup=True)
            if not _good(after) or after["identity"] is not None:
                self._fail("account_deletion_unverified")
            if after["group"] is not None:
                if after["group"] != {"name": admitted["name"], "gid": admitted["gid"], "member_count": 0}:
                    self._fail("remaining_group_identity_mismatch")
                rc, _, audit = self._command([TOOLS[2], self.fixture.account], deadline, "groupdel", True)
                self.record["delete_commands"].append(audit)
                if not _complete(audit) or rc != 0:
                    self._fail("groupdel_not_confirmed")
                after = self._observe("post_groupdel", deadline, cleanup=True)
            if not _absent(after):
                self._fail("account_or_group_residual")
            self.record["cleanup_verified"] = True
            return True, []
        except (AccountEvidenceError, OSError, RuntimeError) as exc:
            return False, ["account cleanup: " + str(exc)]


def _checked_observations(value, errors):
    rows = value["observations"]
    phases, result, command_ids = [], {}, []
    if not isinstance(rows, list) or len(rows) > 5:
        errors.append("account observations limit")
        return {}, []
    for row in rows:
        if not _keys(row, "phase audit observation") or row["phase"] not in PHASES:
            errors.append("account observation entry")
            continue
        phase, audit, observation = row["phase"], row["audit"], row["observation"]
        phases.append(phase)
        audit_errors = validate_audit(audit)
        errors.extend(audit_errors)
        if not audit_errors:
            command_ids.append(audit["command_id"])
            if audit["role"] != phase:
                errors.append("account observation role")
        if observation is not None:
            errs = validate_observation(observation)
            errors.extend(errs)
            if not errs and observation["target"] != value["target"]:
                errors.append("account observation target")
            if not errs and not audit_errors:
                clocks = observation["clocks"]
                if any(not audit["start_" + c + "_ns"] <= clocks["start_" + c + "_ns"] <= clocks["end_" + c + "_ns"] <= audit["end_" + c + "_ns"]
                       for c in ("mono", "boot")):
                    errors.append("observation not inside original command window")
                raw = json.dumps(observation, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"
                if len(raw) > OUTPUT_LIMIT or audit["stdout"]["bytes"] != len(raw) or audit["stdout"]["sha256"] != _sha(raw):
                    errors.append("observation capture binding")
            if not errs and not audit_errors and _complete(audit) and audit["rc"] == 0:
                result[phase] = observation
    if phases != sorted(set(phases), key=PHASES.index):
        errors.append("account observation order/repetition")
    return result, command_ids


def _validate_account_setup(value, *, run=None, fixture_account=None, cleanup=None):
    """Strict receipt consistency, never host attestation or deletion authority."""
    names = ("schema_version target run_id round assumptions tools observations create_command observed_identity "
             "admitted_identity delete_commands cleanup_verified failure")
    if not _keys(value, names):
        return ["account setup fields"]
    errors = []
    if (type(value["schema_version"]) is not int or value["schema_version"] != 1
            or not isinstance(value["run_id"], str) or not re.fullmatch(r"[1-9][0-9]{0,18}", value["run_id"])
            or type(value["round"]) is not int or value["round"] not in (2, 3)
            or value["target"] != "q2hf" + value["run_id"][-15:] + "r" + str(value["round"])):
        errors.append("account setup run/target")
    if value["assumptions"] != ASSUMPTIONS or any(type(v) is not bool for v in value["assumptions"].values()):
        errors.append("account setup assumptions")
    if type(value["cleanup_verified"]) is not bool or (value["failure"] is not None and (
            not isinstance(value["failure"], str) or not 1 <= len(value["failure"]) <= 128)):
        errors.append("account setup status")
    tools = value["tools"]
    if not isinstance(tools, list) or len(tools) not in (0, 3):
        errors.append("account tools")
    else:
        for i, row in enumerate(tools):
            if (not _keys(row, "path sha256 size version version_basis dev ino mtime_ns ctime_ns")
                    or row["path"] != TOOLS[i] or row["version"] is not None or row["version_basis"] != "not_invoked"
                    or any(not _integer(row[k]) for k in ("size", "dev", "ino", "mtime_ns", "ctime_ns"))
                    or row["size"] > 2 * 1024**2 or not isinstance(row["sha256"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
                errors.append("account tool pin")
    observations, ids = _checked_observations(value, errors)
    create = value["create_command"]
    deletes = value["delete_commands"]
    if not isinstance(deletes, list) or len(deletes) > 2:
        errors.append("account delete commands")
        deletes = []
    for audit, role in [(create, "useradd")] + list(zip(deletes, ("userdel", "groupdel"))):
        if audit is None:
            continue
        errs = validate_audit(audit)
        errors.extend(errs)
        if not errs:
            ids.append(audit["command_id"])
            if audit["role"] != role:
                errors.append("account command role")
    if len(ids) != len(set(ids)) or any(not item.startswith(str(value["run_id"]) + "-" + str(value["round"]) + "-") for item in ids):
        errors.append("account command identity reuse/mismatch")
    # The accepted transcript is one irreversible sequence. A previous command's
    # timeout/EOF uncertainty cannot be erased by a later successful observation.
    by_phase = {row["phase"]: row["audit"] for row in value["observations"]
                if _keys(row, "phase audit observation") and row["phase"] in PHASES}
    sequence = [by_phase.get("pre_create"), create, by_phase.get("post_create"),
                by_phase.get("pre_cleanup"), deletes[0] if deletes else None,
                by_phase.get("post_userdel"), deletes[1] if len(deletes) == 2 else None,
                by_phase.get("post_groupdel")]
    sequence = [audit for audit in sequence if audit is not None]
    for previous, following in zip(sequence, sequence[1:]):
        if validate_audit(previous) or validate_audit(following):
            continue
        if (not _complete(previous)
                or int(previous["command_id"].rsplit("-", 1)[1]) >= int(following["command_id"].rsplit("-", 1)[1])
                or any(previous["end_" + c + "_ns"] > following["start_" + c + "_ns"] for c in ("mono", "boot"))):
            errors.append("account command order or unresolved predecessor")
    before, after = observations.get("pre_create"), observations.get("post_create")
    observed, admitted = value["observed_identity"], value["admitted_identity"]
    if create is not None and (len(tools) != 3 or not _absent(before)):
        errors.append("creation lacks admitted precheck/tools")
    if after is not None and create is None:
        errors.append("postcreate without command")
    if observed != (after["identity"] if after else None):
        errors.append("observed identity not derived from postcheck")
    derived_admitted = (create is not None and not validate_audit(create) and _complete(create)
                        and create["rc"] == 0 and _absent(before) and _admissible(after))
    if admitted is not None and (not derived_admitted or admitted != after["identity"]):
        errors.append("admitted identity lacks successful creation proof")
    if admitted is None and derived_admitted:
        errors.append("successful identity admission missing")
    if admitted is None and any(phase in by_phase for phase in PHASES[2:]):
        errors.append("cleanup observation lacks admitted identity")
    for phase, row in observations.items():
        expected = (admitted["uid"], admitted["gid"]) if admitted and phase in PHASES[2:] else (None, None)
        if (row["expected_uid"], row["expected_gid"]) != expected:
            errors.append("observation expected identity mismatch")
    preclean, postdel, postgroup = (observations.get(phase) for phase in PHASES[2:])
    if deletes and (admitted is None or not _admissible(preclean) or preclean["identity"] != admitted):
        errors.append("deletion lacks admitted exact identity")
    if postdel is not None and not deletes:
        errors.append("post-userdel without command")
    if len(deletes) == 2 and (not _good(postdel) or postdel["identity"] is not None
                            or admitted is None or postdel["group"] != {"name": value["target"], "gid": admitted["gid"], "member_count": 0}):
        errors.append("group deletion lacks exact unshared group")
    if postgroup is not None and len(deletes) != 2:
        errors.append("post-groupdel without command")
    clean = (admitted is not None and bool(deletes) and all(not validate_audit(a) and _complete(a) and a["rc"] == 0 for a in deletes)
             and _absent(postgroup if len(deletes) == 2 else postdel))
    if value["cleanup_verified"] != clean:
        errors.append("account cleanup aggregate not derived")
    if clean and value["failure"] is not None:
        errors.append("account cleanup success contradicts retained failure")
    if run is not None and (run.get("id") != value["run_id"] or run.get("round") != value["round"]
                            or type(run.get("attempt")) is not int or run["attempt"] != 1):
        errors.append("account setup differs from run")
    if fixture_account is not None and fixture_account != ({} if admitted is None else {
            "uid": admitted["uid"], "gid": admitted["gid"], "supplementary_groups": [], "home_created": False}):
        errors.append("fixture account differs from admitted identity")
    if cleanup is not None and cleanup.get("verified") is True and create is not None and not clean:
        errors.append("outer cleanup hides account unknown")
    if cleanup is not None and cleanup.get("verified") is True and any(not _complete(audit) for audit in sequence):
        errors.append("outer cleanup hides original account command uncertainty")
    return errors


def validate_account_setup(value, *, run=None, fixture_account=None, cleanup=None):
    try:
        return _validate_account_setup(value, run=run, fixture_account=fixture_account, cleanup=cleanup)
    except (TypeError, ValueError, KeyError, IndexError, AttributeError, RecursionError):
        return ["malformed account setup"]


def account_setup_facts(value):
    errors = validate_account_setup(value)
    diagnostic_bytes = 0
    if not errors:
        audits = [row["audit"] for row in value["observations"]] + value["delete_commands"]
        if value["create_command"] is not None:
            audits.append(value["create_command"])
        diagnostic_bytes = sum(audit[stream]["bytes"] for audit in audits for stream in ("stdout", "stderr"))
    return {"errors": errors, "admitted": not errors and value["admitted_identity"] is not None,
            "cleanup_verified": not errors and value["cleanup_verified"] is True,
            "diagnostic_bytes": diagnostic_bytes}


def main(argv=None):
    # No argparse paths, provider choices, command arguments or retry mode exist.
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) not in (2, 6) or args[0] != "--observe" or not _name(args[1]):
        return 2
    uid = gid = None
    if len(args) == 6:
        if args[2] != "--uid" or args[4] != "--gid" or any(not re.fullmatch(r"[0-9]{1,10}", v) for v in (args[3], args[5])):
            return 2
        uid, gid = int(args[3]), int(args[5])
        if not _identifier(uid) or not _identifier(gid):
            return 2
    if sys.platform != "linux":
        return 2
    result = observe(args[1], uid, gid)
    raw = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"
    if len(raw) > OUTPUT_LIMIT:
        return 3
    sys.stdout.buffer.write(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
