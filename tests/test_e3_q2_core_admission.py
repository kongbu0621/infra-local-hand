"""Policy component tests using temporary files and real bounded child processes.

These do not contact the guest or stand in for live admission/capacity evidence.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux held-fd and wait4 policy collectors", allow_module_level=True)

PATH = Path(__file__).parent / "e3_host" / "q2_core_delivery_dispatcher.py"
spec = importlib.util.spec_from_file_location("_core_admit_test", PATH)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


@pytest.fixture(autouse=True)
def synthetic_prior_pins(monkeypatch):
    from core_prior_fixture import fixture as prior_fixture
    import test_e3_q2_core_delivery_dispatcher as shared
    prior_fixture(monkeypatch, d, shared.d)


GRANT = dict(commands=["ALL"], host="ALL", runas_groups=[], runas_users=["ALL"], tags=["NOPASSWD"])
SUDO = b'''Matching Defaults entries for q1admin on local-hand-q1:
    env_reset, mail_badpass

User q1admin may run the following commands on local-hand-q1:

Sudoers entry:
    RunAsUsers: ALL
    RunAsGroups: ALL
    Commands:
        ALL

Sudoers entry:
    RunAsUsers: ALL
    Options: !authenticate
    Commands:
        ALL
'''


def test_sudo_requires_exact_nopasswd_without_explicit_groups():
    grants = d._admit_sudo_output(SUDO, GRANT)
    assert grants[1] == GRANT
    assert grants[0]["runas_groups"] == ["ALL"]
    with pytest.raises(d.DispatchError, match="SUDO_GRANT"):
        d._admit_sudo_output(SUDO.replace(b"    Options: !authenticate", b"    RunAsGroups: ALL\n    Options: !authenticate"), GRANT)


@pytest.mark.parametrize("command_indent", [b"        ", b"\t"])
def test_sudo_long_listing_accepts_native_command_indentation(command_indent):
    raw = SUDO.replace(b"        ALL", command_indent + b"ALL")
    assert d._admit_sudo_output(raw, GRANT)[1] == GRANT


def test_sudo_long_listing_does_not_require_matching_defaults():
    raw = SUDO.split(b"User q1admin", 1)[1]
    assert d._admit_sudo_output(b"User q1admin" + raw, GRANT)[1] == GRANT


SUDO_SOURCE_PATHS = ("/etc/sudoers", "/etc/sudoers.d/90-cloud-init-users")


def sourced_sudo_listing(first=b"/etc/sudoers", second=b"/etc/sudoers.d/90-cloud-init-users"):
    header, ordinary, passwordless = SUDO.split(b"Sudoers entry:")
    def title(source):
        return b"Sudoers entry:" + (b" " + source if source is not None else b"")
    return header + title(first) + ordinary + title(second) + passwordless


@pytest.mark.parametrize("sources", [
    (None, None),
    (b"/etc/sudoers", b"/etc/sudoers.d/90-cloud-init-users"),
    (None, b"/etc/sudoers.d/90-cloud-init-users"),
    (b"/etc/sudoers", None),
])
@pytest.mark.parametrize("command_indent", [b"        ", b"\t"])
def test_sudo_old_and_sourced_entry_headers_preserve_same_grants(sources, command_indent):
    raw = sourced_sudo_listing(*sources).replace(b"        ALL", command_indent + b"ALL")
    grants = d._admit_sudo_output(raw, GRANT, source_paths=SUDO_SOURCE_PATHS)
    assert grants == [
        dict(commands=["ALL"], host="ALL", runas_groups=["ALL"],
             runas_users=["ALL"], tags=["PASSWD"]),
        GRANT,
    ]


@pytest.mark.parametrize("source,held", [
    (b"/etc/sudoers.d/90-cloud-init-users", ()),
    (b"/etc/sudoers.d/unread", SUDO_SOURCE_PATHS),
    (b"/etc/sudoers", ("/etc/sudoers.d/90-cloud-init-users",)),
    (b"/etc/sudo.conf", SUDO_SOURCE_PATHS + ("/etc/sudo.conf",)),
    (b"/tmp/sudoers", SUDO_SOURCE_PATHS),
    (b"sudoers", SUDO_SOURCE_PATHS),
    (b"/etc/sudoers.d/../sudoers", SUDO_SOURCE_PATHS),
    (b"/etc//sudoers", SUDO_SOURCE_PATHS),
    (b"/etc/sudoers:12", SUDO_SOURCE_PATHS),
    (b"/etc/sudoers # comment", SUDO_SOURCE_PATHS),
    (b"/etc/sudoers ", SUDO_SOURCE_PATHS),
])
def test_sudo_sourced_title_must_name_an_already_read_sudoers_file(source, held):
    # A valid grant in the other entry cannot hide an unbound source title.
    raw = sourced_sudo_listing(source, None)
    with pytest.raises(d.DispatchError, match="SUDO"):
        d._admit_sudo_output(raw, GRANT, source_paths=held)


@pytest.mark.parametrize("change", [
    (b"    RunAsUsers: ALL", b"    RunAsUsers: ALL\n    RunAsUsers: ALL"),
    (b"    Options: !authenticate", b"    Options: !authenticate\n    Options: !authenticate"),
    (b"    Commands:\n", b"    Unknown: ignored\n    Commands:\n"),
    (b"    RunAsUsers: ALL", b"    RunAsUsers: root"),
    (b"    RunAsGroups: ALL", b"    RunAsGroups: root"),
    (b"    Options: !authenticate", b"    Options: !authenticate, noexec"),
    (b"    Options: !authenticate", b"    Options: authenticate"),
    (b"    Commands:\n", b"    Commands: ALL\n"),
    (b"        ALL", b"\t/bin/true"),
    (b"        ALL", b"        ALL\n        /bin/true"),
    (b"        ALL", b"        ALL\n        ALL"),
    (b"        ALL", b""),
    (b"        ALL", b"    ALL"),
    (b"        ALL", b"ALL"),
])
def test_sudo_native_format_support_does_not_expand_permissions_or_fields(change):
    raw = sourced_sudo_listing().replace(*change)
    with pytest.raises(d.DispatchError, match="SUDO"):
        d._admit_sudo_output(raw, GRANT, source_paths=SUDO_SOURCE_PATHS)


@pytest.mark.parametrize("change", [
    (b"User q1admin may run", b"User other may run"),
    (b"User q1admin may run the following commands on local-hand-q1:", b""),
    (b"Sudoers entry: /etc/sudoers\n", b"Sudoers entry: /etc/sudoers\x00\n"),
    (b"Sudoers entry: /etc/sudoers\n", b"Sudoers entry: /etc/sudoers\r\n"),
    (b"Sudoers entry: /etc/sudoers\n", b"Sudoers entry: /etc/sudoers\v\n"),
    (b"Sudoers entry: /etc/sudoers\n", b"Sudoers entry: /etc/sudoers\nSudoers entry:\n"),
    (b"Sudoers entry: /etc/sudoers\n", b" Sudoers entry: /etc/sudoers\n"),
])
def test_sudo_native_format_rejects_ambiguous_boundaries_and_identity(change):
    with pytest.raises(d.DispatchError, match="SUDO|TEXT"):
        d._admit_sudo_output(sourced_sudo_listing().replace(*change), GRANT,
                             source_paths=SUDO_SOURCE_PATHS)


@pytest.mark.parametrize("raw", [
    SUDO.replace(b"    Options: !authenticate", b"    PrivateValue: DO_NOT_ECHO_THIS_VALUE"),
    sourced_sudo_listing(b"/private/DO_NOT_ECHO_THIS_PATH", None),
    SUDO.replace(b"        ALL", b"\t/bin/DO_NOT_ECHO_THIS_COMMAND"),
    SUDO.replace(b"    Options: !authenticate", b"    Options: authenticate"),
], ids=["unknown-field", "unread-source", "non-all-command", "grant-mismatch"])
def test_sudo_failure_diagnostics_survive_real_bootstrap_without_raw_output(monkeypatch, raw):
    from e3_host import q2_core_delivery_bootstrap as bootstrap
    with pytest.raises(d.DispatchError) as captured:
        d._admit_sudo_output(raw, GRANT, source_paths=SUDO_SOURCE_PATHS)
    error = captured.value
    code = str(error)
    assert re.fullmatch(r"CORE_ADMIT_SUDO_(?:OUTPUT_[A-Z_]+|GRANT_MATCH)_L[0-9]+_E[0-9]+"
                        r"_BYTES[0-9]+_LINES[0-9]+_ENTRIES[0-9]+_SOURCE[0-9]+"
                        r"_TAB[0-9]+_SPACES[0-9]+_SHA256_[A-F0-9]{64}", code)
    assert len(code.encode("ascii")) <= 384
    assert f"_BYTES{len(raw)}_" in code
    assert code.endswith("_SHA256_" + hashlib.sha256(raw).hexdigest().upper())
    assert "DO_NOT_ECHO" not in code and "/" not in code

    def fail_in_serve(**kwargs):
        raise error

    monkeypatch.setattr(bootstrap, "serve", fail_in_serve)
    stdout, stderr = io.BytesIO(), io.BytesIO()
    status = bootstrap.main(io.BytesIO(), stdout, stderr, bootstrap_sha256="a" * 64)
    assert status == 3
    assert stdout.getvalue() == b""
    assert stderr.getvalue() == code.encode("ascii") + b"\n"


def test_sudo_failure_diagnostic_stays_bounded_at_helper_output_limit():
    # The approved sudo helper allows at most 65536 combined output bytes.
    raw = b"\n" * 65536
    with pytest.raises(d.DispatchError) as captured:
        d._admit_sudo_output(raw, GRANT, source_paths=SUDO_SOURCE_PATHS)
    code = str(captured.value)
    assert len(code.encode("ascii")) <= 384
    assert "_BYTES65536_" in code
    assert code.endswith("_SHA256_" + hashlib.sha256(raw).hexdigest().upper())


@pytest.mark.parametrize("change", [
    (b"!authenticate", b"authenticate"),
    (b"    Options: !authenticate", b"    Unknown: !authenticate"),
    (b"        ALL", b"        /bin/true"),
    (b"q1admin on", b"other on"),
])
def test_sudo_unknown_or_restricted_output_stops(change):
    with pytest.raises(d.DispatchError):
        d._admit_sudo_output(SUDO.replace(*change), GRANT)


def test_sudo_source_host_relation_and_plugin_are_not_guessed():
    source = {"/etc/sudo.conf": b"# system defaults\n", "/etc/sudoers": b"Defaults env_reset\nroot ALL=(ALL:ALL) ALL\n@includedir /etc/sudoers.d\n",
              "/etc/sudoers.d/90-cloud-init-users": b"q1admin ALL=(ALL) NOPASSWD:ALL\n"}
    assert d._admit_sudo_source(source, "q1admin ALL=(ALL) NOPASSWD:ALL") == 1
    with pytest.raises(d.DispatchError, match="PLUGIN"):
        d._admit_sudo_source({**source, "/etc/sudo.conf": b"Plugin custom /tmp/plugin.so\n"}, "q1admin ALL=(ALL) NOPASSWD:ALL")
    with pytest.raises(d.DispatchError, match="INCLUDE"):
        d._admit_sudo_source({**source, "/etc/sudoers.d/90-cloud-init-users": b"@include /other\n"}, "q1admin ALL=(ALL) NOPASSWD:ALL")


def test_sshd_source_effective_both_required():
    d._admit_sshd_source({"/etc/ssh/sshd_config": b"Include /etc/ssh/sshd_config.d/*.conf\nPubkeyAuthentication yes\n"})
    required = dict(authorizedkeyscommand="none", authorizedkeysfile=[".ssh/authorized_keys", ".ssh/authorized_keys2"],
                    forcecommand="none", permituserenvironment="no", pubkeyauthentication="yes")
    raw = b"\n".join((key + " " + (" ".join(value) if type(value) is list else value)).encode() for key, value in required.items())
    assert d._admit_sshd_output(raw, required) == required
    assert d._admit_sshd_output(raw + b'\nhostkey /etc/ssh/ssh_host_rsa_key\nhostkey /etc/ssh/ssh_host_ed25519_key\n',
        required) == required
    with pytest.raises(d.DispatchError, match='PREDICATE'):
        d._admit_sshd_output(raw + b'\nforcecommand none\n', required)
    with pytest.raises(d.DispatchError, match="PREDICATE"):
        d._admit_sshd_output(raw.replace(b"forcecommand none", b"forcecommand /bin/x"), required)
    with pytest.raises(d.DispatchError, match="MATCH"):
        d._admit_sshd_source({"/etc/ssh/sshd_config": b"Match User q1admin\n"})
    with pytest.raises(d.DispatchError, match="INCLUDE"):
        d._admit_sshd_source({"/etc/ssh/sshd_config": b"Include /tmp/*.conf\n"})


SSHD_MAIN = "/etc/ssh/sshd_config"
SSHD_INCLUDE = b"Include /etc/ssh/sshd_config.d/*.conf\n"


@pytest.mark.parametrize("line,reason", [
    (b'Banner "DO_NOT_ECHO_THIS_VALUE"', "GRAMMAR_QUOTE_OR_EXPANSION"),
    (b"Banner 'DO_NOT_ECHO_THIS_VALUE'", "GRAMMAR_QUOTE_OR_EXPANSION"),
    (b"Banner /private/DO_NOT_ECHO_THIS_PATH\\suffix", "GRAMMAR_QUOTE_OR_EXPANSION"),
    (b"Banner `DO_NOT_ECHO_THIS_VALUE`", "GRAMMAR_QUOTE_OR_EXPANSION"),
    (b"Banner $DO_NOT_ECHO_THIS_VALUE", "GRAMMAR_QUOTE_OR_EXPANSION"),
    (b"PubkeyAuthentication", "GRAMMAR_ARGUMENT_COUNT"),
    (b"Match User DO_NOT_ECHO_THIS_VALUE", "MATCH_DIRECTIVE"),
    (b"Include /private/DO_NOT_ECHO_THIS_PATH", "INCLUDE_TARGET"),
    (b"Include /etc/ssh/sshd_config.d/*.conf other", "INCLUDE_TARGET"),
    (b"Bad-Keyword value", "GRAMMAR_KEYWORD"),
    (b"AcceptEnv LANG LC_* EXTRA", "GRAMMAR_GLOB"),
    (b"AcceptEnv LANG LC_?", "GRAMMAR_GLOB"),
    (b"AcceptEnv LANG LC_[ABC]", "GRAMMAR_GLOB"),
    (b"Banner /private/DO_NOT_ECHO_THIS_PATH]", "GRAMMAR_GLOB"),
])
def test_sshd_source_rejection_has_exact_stage_line_and_safe_digest(monkeypatch, line, reason):
    from e3_host import q2_core_delivery_bootstrap as bootstrap
    raw = SSHD_INCLUDE + b"# comment\n\n" + line + b"\n"
    with pytest.raises(d.DispatchError) as captured:
        d._admit_sshd_source({SSHD_MAIN: raw})
    code = str(captured.value)
    assert code.startswith(f"CORE_ADMIT_SSHD_{reason}_F1_L4_FILES1_BYTES{len(raw)}_LINES4_INCLUDES1_")
    assert "_PATHSHA256_" + hashlib.sha256(SSHD_MAIN.encode()).hexdigest().upper() in code
    assert code.endswith("_SHA256_" + hashlib.sha256(raw).hexdigest().upper())
    assert re.fullmatch(r"CORE_[A-Z0-9_]+", code) and len(code) <= 384
    assert "DO_NOT_ECHO" not in code and "/" not in code

    def fail_in_serve(**_kwargs):
        raise captured.value
    monkeypatch.setattr(bootstrap, "serve", fail_in_serve)
    stdout, stderr = io.BytesIO(), io.BytesIO()
    assert bootstrap.main(io.BytesIO(), stdout, stderr, bootstrap_sha256="a" * 64) == 3
    assert stdout.getvalue() == b"" and stderr.getvalue() == code.encode("ascii") + b"\n"


@pytest.mark.parametrize("raw", [b"# invalid\xff\n", b"Banner foo\x00\n", b"Banner foo\r\n"])
def test_sshd_source_text_failure_keeps_original_encoding_rejection(raw):
    with pytest.raises(d.DispatchError) as captured:
        d._admit_sshd_source({SSHD_MAIN: raw})
    code = str(captured.value)
    assert code.startswith("CORE_ADMIT_POLICY_ENCODING_SSHD_SOURCE_TEXT_F1_L0_FILES1_")
    assert code.endswith("_SHA256_" + hashlib.sha256(raw).hexdigest().upper())
    assert re.fullmatch(r"CORE_[A-Z0-9_]+", code) and len(code) <= 384


@pytest.mark.parametrize("leaf", ["50-private.conf", "50-\udcff-private.conf"])
def test_sshd_source_diagnostic_binds_second_file_without_disclosing_path(leaf):
    path = "/etc/ssh/sshd_config.d/" + leaf
    raw = b"# comment\nInclude /etc/ssh/sshd_config.d/*.conf\n"
    with pytest.raises(d.DispatchError) as captured:
        d._admit_sshd_source({SSHD_MAIN: SSHD_INCLUDE, path: raw})
    code = str(captured.value)
    assert code.startswith("CORE_ADMIT_SSHD_INCLUDE_LOCATION_F2_L2_FILES2_")
    assert "_PATHSHA256_" + hashlib.sha256(path.encode("utf-8", "surrogatepass")).hexdigest().upper() in code
    assert code.endswith("_SHA256_" + hashlib.sha256(raw).hexdigest().upper())
    assert re.fullmatch(r"CORE_[A-Z0-9_]+", code) and "private" not in code.lower()


@pytest.mark.parametrize("raws,includes", [
    ({}, 0), ({SSHD_MAIN: b""}, 0), ({SSHD_MAIN: b"PubkeyAuthentication yes\n"}, 0),
    ({SSHD_MAIN: SSHD_INCLUDE * 2}, 2),
])
def test_sshd_source_missing_duplicate_include_uses_closure_diagnostic(raws, includes):
    with pytest.raises(d.DispatchError) as captured:
        d._admit_sshd_source(raws)
    code = str(captured.value)
    expected = d.canonical([dict(path_sha256=hashlib.sha256(path.encode()).hexdigest(),
        bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()) for path, raw in raws.items()])
    assert code.startswith(f"CORE_ADMIT_SSHD_INCLUDE_COUNT_F0_L0_FILES{len(raws)}_")
    assert f"_INCLUDES{includes}_PATHSHA256_" + "0" * 64 in code
    assert code.endswith("_SHA256_" + hashlib.sha256(expected).hexdigest().upper())


@pytest.mark.parametrize("raw", [
    SSHD_INCLUDE,
    SSHD_INCLUDE + b"PubkeyAuthentication yes\nAcceptEnv LANG\n",
    SSHD_INCLUDE + b"# ignored quotes, glob and expansions: \"*?$\n\n",
    b"\tinclude\t/etc/ssh/sshd_config.d/*.conf\nPUBKEYAUTHENTICATION yes\n",
])
def test_sshd_source_diagnostic_preserves_existing_success(raw):
    assert d._admit_sshd_source({SSHD_MAIN: raw, "/etc/ssh/sshd_config.d/50-local.conf": b"# no change\n"}) is None


@pytest.mark.parametrize("line", [
    b"AcceptEnv LANG LC_*\n", b"AcceptEnv LANG LC_*",
    b"  AcceptEnv\tLANG  LC_* \t\n", b"\tacceptenv LANG LC_*\t",
    b"\tAcCePtEnV\tLANG\tLC_*\n",
])
@pytest.mark.parametrize("before_include", [False, True])
def test_sshd_locale_exact_main_line_is_accepted(line, before_include):
    raw = line + b"\n" + SSHD_INCLUDE if before_include else SSHD_INCLUDE + line
    raws = {SSHD_MAIN: raw, "/etc/ssh/sshd_config.d/50-local.conf": b"PubkeyAuthentication yes\n"}
    # Repeated independent parser calls do not share the one-declaration state.
    assert d._admit_sshd_source(raws) is None
    assert d._admit_sshd_source(raws) is None


@pytest.mark.parametrize("line", [
    b"AcceptEnv LC_*", b"AcceptEnv LC_* LANG", b"AcceptEnv LANG LANG LC_*",
    b"AcceptEnv LANG LC_* LC_*", b"AcceptEnv LANG LC_* EXTRA",
    b"AcceptEnv lang LC_*", b"AcceptEnv LANG lc_*", b"AcceptEnv LANG LC_**",
    b"AcceptEnv LANG LC_?", b"AcceptEnv LANG LC_[ABC]", b"AcceptEnv LANG *",
    b"AcceptEnv LANG LC_ALL*", b"AcceptEnv LANG !LC_*", b"AcceptEnv LANG LC_*,LANG",
    b"AcceptEnv LANG LC_* # comment", b"AcceptEnv LANG LC_*#comment",
    b"AcceptEnv=LANG LC_*", b"SetEnv LANG LC_*", b"Banner LANG LC_*",
])
def test_sshd_locale_does_not_accept_nearby_patterns(line):
    raw = SSHD_INCLUDE + line + b"\n"
    with pytest.raises(d.DispatchError) as captured:
        d._admit_sshd_source({SSHD_MAIN: raw})
    assert "_F1_L2_" in str(captured.value)
    assert str(captured.value).endswith("_SHA256_" + hashlib.sha256(raw).hexdigest().upper())


@pytest.mark.parametrize("control", [bytes([value]) for value in range(32) if value not in (9, 10)] + [b"\x7f"])
@pytest.mark.parametrize("position", ["prefix", "between", "suffix"])
def test_sshd_locale_rejects_control_bytes_before_strip(control, position):
    line = {"prefix": control + b"AcceptEnv LANG LC_*\n",
            "between": b"AcceptEnv LANG" + control + b"LC_*\n",
            "suffix": b"AcceptEnv LANG LC_*" + control + b"\n"}[position]
    raw = SSHD_INCLUDE + line
    with pytest.raises(d.DispatchError):
        d._admit_sshd_source({SSHD_MAIN: raw})


@pytest.mark.parametrize("separator", [b"\v", b"\f", b"\x1c", b"\x1d", b"\x1e"])
@pytest.mark.parametrize("prefix", [b"PubkeyAuthentication yes", b"# comment"])
def test_sshd_locale_cannot_follow_a_non_lf_parser_boundary(separator, prefix):
    raw = SSHD_INCLUDE + prefix + separator + b"AcceptEnv LANG LC_*\n"
    with pytest.raises(d.DispatchError, match="GRAMMAR_GLOB_F1_L3_"):
        d._admit_sshd_source({SSHD_MAIN: raw})
    # The same historical splitlines behavior still applies to non-glob input.
    assert d._admit_sshd_source({SSHD_MAIN: raw.replace(b"LC_*", b"LC_ALL")}) is None


@pytest.mark.parametrize("line", [
    b'AcceptEnv "LANG" LC_*\n', b"AcceptEnv 'LANG' LC_*\n",
    b"AcceptEnv LANG LC_*\\\n", b"AcceptEnv LANG $LC_*\n", b"AcceptEnv LANG `LC_*`\n",
    b"AcceptEnv LANG\nLC_*\n", b"AcceptEnv LANG LC_*\xff\n",
])
def test_sshd_locale_keeps_quote_expansion_encoding_and_continuation_rejections(line):
    with pytest.raises(d.DispatchError):
        d._admit_sshd_source({SSHD_MAIN: SSHD_INCLUDE + line})


@pytest.mark.parametrize("main_locale", [b"", b"AcceptEnv LANG LC_*\n"])
def test_sshd_locale_never_applies_in_a_drop_in(main_locale):
    path = "/etc/ssh/sshd_config.d/50-private.conf"
    raw = b"AcceptEnv LANG LC_*\n"
    with pytest.raises(d.DispatchError, match="GRAMMAR_GLOB_F2_L1_") as captured:
        d._admit_sshd_source({SSHD_MAIN: SSHD_INCLUDE + main_locale, path: raw})
    code = str(captured.value)
    assert code.endswith("_SHA256_" + hashlib.sha256(raw).hexdigest().upper())
    assert "private" not in code.lower() and "AcceptEnv" not in code


def test_sshd_locale_second_main_declaration_is_rejected():
    raw = SSHD_INCLUDE + b"AcceptEnv LANG LC_*\n\tacceptenv\tLANG LC_*\n"
    with pytest.raises(d.DispatchError, match="GRAMMAR_GLOB_F1_L3_"):
        d._admit_sshd_source({SSHD_MAIN: raw})


@pytest.mark.parametrize("following,reason", [
    (b"Match User example\n", "MATCH_DIRECTIVE"),
    (b"Include /outside/*.conf\n", "INCLUDE_TARGET"),
    (b"Banner *\n", "GRAMMAR_GLOB"),
    (b'Banner "value"\n', "GRAMMAR_QUOTE_OR_EXPANSION"),
])
def test_sshd_locale_does_not_skip_later_main_checks(following, reason):
    raw = SSHD_INCLUDE + b"AcceptEnv LANG LC_*\n" + following
    with pytest.raises(d.DispatchError, match=reason + "_F1_L3_"):
        d._admit_sshd_source({SSHD_MAIN: raw})


@pytest.mark.parametrize("file_index", [2, 3])
def test_sshd_locale_does_not_skip_later_files_or_leak_diagnostics(monkeypatch, file_index):
    from e3_host import q2_core_delivery_bootstrap as bootstrap
    raws = {SSHD_MAIN: SSHD_INCLUDE + b"AcceptEnv LANG LC_*\n"}
    if file_index == 3:
        raws["/etc/ssh/sshd_config.d/50-local.conf"] = b"PubkeyAuthentication yes\n"
    raw = b"# retained\nBanner /private/DO_NOT_ECHO*\n"
    raws["/etc/ssh/sshd_config.d/90-private.conf"] = raw
    with pytest.raises(d.DispatchError) as captured:
        d._admit_sshd_source(raws)
    code = str(captured.value)
    assert code.startswith(f"CORE_ADMIT_SSHD_GRAMMAR_GLOB_F{file_index}_L2_FILES{file_index}_")
    assert code.endswith("_SHA256_" + hashlib.sha256(raw).hexdigest().upper())
    assert re.fullmatch(r"CORE_[A-Z0-9_]+", code) and len(code) <= 384 and "DO_NOT_ECHO" not in code

    def fail_in_serve(**_kwargs):
        raise captured.value
    monkeypatch.setattr(bootstrap, "serve", fail_in_serve)
    stdout, stderr = io.BytesIO(), io.BytesIO()
    assert bootstrap.main(io.BytesIO(), stdout, stderr, bootstrap_sha256="a" * 64) == 3
    assert stdout.getvalue() == b"" and stderr.getvalue() == code.encode() + b"\n"


@pytest.mark.parametrize("includes", [b"", SSHD_INCLUDE * 2])
def test_sshd_locale_does_not_replace_closure_include_count(includes):
    with pytest.raises(d.DispatchError, match="INCLUDE_COUNT_F0_L0_"):
        d._admit_sshd_source({SSHD_MAIN: includes + b"AcceptEnv LANG LC_*\n"})


def test_sshd_locale_is_pure_and_keeps_the_field_release_closed(monkeypatch):
    from e3_host import q2_core_delivery_entry as entry

    def forbidden(*_args, **_kwargs):
        pytest.fail("sshd source parser attempted an external effect")

    monkeypatch.setattr(d.os, "open", forbidden)
    monkeypatch.setattr(d.subprocess, "Popen", forbidden)
    assert d._admit_sshd_source({SSHD_MAIN: SSHD_INCLUDE + b"AcceptEnv LANG LC_*\n"}) is None
    assert entry.RELEASABLE_DISPATCHER_SHA256 == frozenset()


def test_sshd_locale_accepts_a_complete_maximum_size_main_file_and_65_files():
    line = b"AcceptEnv LANG LC_*\n"
    raw = SSHD_INCLUDE + b"#" + b"a" * (262144 - len(SSHD_INCLUDE) - len(line) - 2) + b"\n" + line
    raws = {SSHD_MAIN: raw}
    for index in range(64):
        raws[f"/etc/ssh/sshd_config.d/{index:02}.conf"] = b"#" + b"a" * 8190 + b"\n"
    assert len(raw) == 262144 and len(raws) == 65 and sum(map(len, raws.values())) <= 1048576
    assert d._admit_sshd_source(raws) is None


@pytest.mark.parametrize("key", ["authorizedkeyscommand", "authorizedkeysfile", "forcecommand",
                                 "permituserenvironment", "pubkeyauthentication"])
@pytest.mark.parametrize("fault", ["missing", "duplicate", "wrong"])
def test_sshd_locale_does_not_replace_any_effective_predicate(key, fault):
    assert d._admit_sshd_source({SSHD_MAIN: SSHD_INCLUDE + b"AcceptEnv LANG LC_*\n"}) is None
    required = dict(authorizedkeyscommand="none", authorizedkeysfile=[".ssh/authorized_keys", ".ssh/authorized_keys2"],
                    forcecommand="none", permituserenvironment="no", pubkeyauthentication="yes")
    rows = {name: (name + " " + (" ".join(value) if type(value) is list else value)).encode()
            for name, value in required.items()}
    selected = rows.pop(key)
    if fault != "missing":
        rows[key] = selected + b"\n" + selected if fault == "duplicate" else key.encode() + b" unexpected"
    with pytest.raises(d.DispatchError, match="PREDICATE"):
        d._admit_sshd_output(b"\n".join(rows.values()), required)


def test_sshd_source_diagnostic_uses_existing_parser_line_numbering():
    raw = SSHD_INCLUDE + b"PubkeyAuthentication yes\vAcceptEnv LC_*\n"
    with pytest.raises(d.DispatchError) as captured:
        d._admit_sshd_source({SSHD_MAIN: raw})
    assert "_F1_L3_FILES1_" in str(captured.value) and "_LINES3_" in str(captured.value)


def test_sshd_source_diagnostic_is_bounded_at_existing_closure_limits():
    raws = {SSHD_MAIN: SSHD_INCLUDE}
    for index in range(63):
        raws[f"/etc/ssh/sshd_config.d/{index:02}.conf"] = b"#" + b"a" * 8190 + b"\n"
    path = "/etc/ssh/sshd_config.d/63.conf"
    raw = b"\n" * (262144 - len(b"AcceptEnv LC_*\n")) + b"AcceptEnv LC_*\n"
    raws[path] = raw
    assert len(raws) == 65 and sum(map(len, raws.values())) < 1048576
    with pytest.raises(d.DispatchError) as captured:
        d._admit_sshd_source(raws)
    code = str(captured.value)
    assert "_F65_" in code and "_BYTES262144_" in code
    assert len(code) <= 384 and code.endswith("_SHA256_" + hashlib.sha256(raw).hexdigest().upper())


def test_single_key_exact_bytes_and_no_options():
    key = base64.b64encode(b"\0\0\0\x0bssh-ed25519\0\0\0 " + b"x" * 32).decode()
    approved = dict(type="ssh-ed25519", key_base64=key)
    raw = ("# comment\n\nssh-ed25519 " + key + " label\n").encode()
    result = d._admit_authorized(raw, "/home/q1admin/.ssh/authorized_keys", approved)
    assert result[0]["line_number"] == 3 and result[0]["options"] == []
    for bad in (b'command="/bin/true" ' + raw.splitlines()[-1], raw + raw,
                raw.replace(b"ssh-ed25519", b"ssh-rsa")):
        with pytest.raises(d.DispatchError):
            d._admit_authorized(bad, "/home/q1admin/.ssh/authorized_keys", approved)


@pytest.mark.parametrize("prefix", [b"X=1\n", b"echo hello\n", b"trap true EXIT\n", b"source /tmp/x\n", b"\\\n"])
def test_bashrc_only_accepts_first_executable_guard(prefix):
    guard = b"# Ubuntu default\ncase $- in\n    *i*) ;;\n      *) return;;\nesac\nexport AFTER=yes\n"
    assert d._admit_bashrc(guard)
    with pytest.raises(d.DispatchError, match="BASHRC_GUARD"):
        d._admit_bashrc(prefix + guard)


@pytest.fixture
def held_reader(tmp_path, monkeypatch):
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    reader = d._admit_reader(lambda: None, "/unit", os.getuid())
    monkeypatch.setattr(reader, "parent", lambda path: (fd, Path(path).name))
    try:
        yield reader, tmp_path
    finally:
        reader.close()
        os.close(fd)


def test_held_reader_real_inode_replacement_and_appearing_absence(held_reader):
    reader, root = held_reader
    file = root / "policy"
    file.write_bytes(b"source\n"); file.chmod(0o600)
    assert reader.read("/unit/policy") == b"source\n"
    file.rename(root / "old")
    file.write_bytes(b"source\n"); file.chmod(0o600)
    with pytest.raises(d.DispatchError, match="DRIFT"):
        reader.recheck()


def test_held_reader_absence_rechecked(held_reader):
    reader, root = held_reader
    assert reader.read("/unit/missing", required=False) is None
    (root / "missing").write_bytes(b"new")
    with pytest.raises(d.DispatchError, match="DRIFT"):
        reader.recheck()


@pytest.mark.parametrize("kind", ["symlink", "fifo", "hardlink", "world-write"])
def test_held_reader_rejects_unsafe_before_open(held_reader, kind):
    reader, root = held_reader
    path = root / "policy"
    if kind == "fifo":
        os.mkfifo(path)
    else:
        path.write_bytes(b"policy"); path.chmod(0o600)
        if kind == "symlink":
            path.rename(root / "original"); path.symlink_to(root / "original")
        elif kind == "hardlink":
            os.link(path, root / "other")
        else:
            path.chmod(0o666)
    with pytest.raises(d.DispatchError, match="PROTECTION"):
        reader.read("/unit/policy")


def test_parent_walk_rejects_real_world_writable_ancestor(tmp_path):
    if os.geteuid() != 0:
        pytest.skip("field root-directory O_NOATIME requires root")
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir(); unsafe.chmod(0o777)
    reader = d._admit_reader(lambda: None, str(tmp_path), os.getuid())
    try:
        with pytest.raises(d.DispatchError, match="PROTECTION"):
            reader.read(str(unsafe / "missing"), required=False)
    finally:
        reader.close()


def helper_fixture(monkeypatch, script, *, seconds=5, output=65536):
    real_popen = subprocess.Popen
    calls = []
    def launch(argv, **kwargs):
        calls.append((argv, kwargs.copy()))
        # Substitute only the component-test executable; child I/O and wait4
        # are real, while the production fixed sudo command is never run.
        return real_popen([sys.executable, "-I", "-c", script], **kwargs)
    monkeypatch.setattr(d.subprocess, "Popen", launch)
    def binding(*_):
        # The real production binder is tested separately. This explicit
        # fixture supplies only the held test-Python executable, never sudo.
        fd = os.open(sys.executable, os.O_RDONLY | os.O_CLOEXEC)
        return SimpleNamespace(close=lambda: os.close(fd)), fd
    monkeypatch.setattr(d, '_admit_exec_binding', binding)
    end = time.clock_gettime_ns(time.CLOCK_BOOTTIME) + 10 * d.NS
    effects = SimpleNamespace(_effect_guard=lambda: None,
        context={"guest_deadlines": {}}, _admit_helper_usage=[])
    def stop_guard(*args):
        if time.clock_gettime_ns(time.CLOCK_BOOTTIME) >= end:
            raise d.DispatchError("TEST_STOP_LIMIT")
    monkeypatch.setattr(d, "_clock", stop_guard)
    policy = dict(argv=["/usr/bin/sudo", "-n", "-ll", "-U", "q1admin"],
        environment={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin"},
        limits=dict(command_seconds=seconds, command_cpu_seconds=2,
                    stdout_bytes=output, stderr_bytes=output, combined_output_bytes=output))
    return effects, policy, calls


def test_real_helper_wait4_two_eof_fixed_invocation_and_no_retry(monkeypatch):
    effects, policy, calls = helper_fixture(monkeypatch, "import os; os.write(1,b'ok'); os.write(2,b'note')")
    checks = []
    stdout, stderr, facts = d._admit_helper(effects, policy, lambda: checks.append(True))
    assert (stdout, stderr) == (b"ok", b"note")
    assert facts["stdout_eof"] and facts["stderr_eof"] and facts["exit_status"] == 0
    assert facts["combined_bytes"] == 6 and facts["finished_boottime_ns"] >= facts["started_boottime_ns"]
    usage = effects._admit_helper_usage[0]
    assert usage["wait4"]["max_rss_bytes"] > 0 and usage["eof"] == ["stderr", "stdout"]
    assert calls[0][1]["shell"] is False and calls[0][1]["cwd"] == "/" and len(checks) == 2
    with pytest.raises(d.DispatchError, match="REPLAY"):
        d._admit_helper(effects, policy, lambda: None)
    assert len(calls) == 1


@pytest.mark.parametrize('failure_slot', [None, 0, 1, 2, 3, 4, 5])
def test_prior_show_slots_allow_six_real_waits_but_never_a_retry(monkeypatch, failure_slot):
    effects, policy, calls = helper_fixture(monkeypatch, 'import os; os.write(1,b"show")', output=32768)
    slots = ((0, 1), (1, 1), (2, 1), (0, 2), (1, 2), (2, 2))
    for number, slot in enumerate(slots):
        policy['argv'] = ['/usr/bin/systemctl', '--system', '--no-pager', '--no-ask-password',
            'show', '--all', d._prior_profile(slot[0])['unit'], '--property=' + ','.join(d.PRIOR_SHOW_FIELDS)]
        def check():
            if number == failure_slot: raise d.DispatchError('TEST_PRIOR_SHOW_START')
        if number == failure_slot:
            with pytest.raises(d.DispatchError, match='TEST_PRIOR_SHOW_START'):
                d._admit_run_helper(effects, policy, check, prior_observation=slot)
            with pytest.raises(d.DispatchError, match='SHOW_SLOT'):
                d._admit_run_helper(effects, policy, lambda: None, prior_observation=slot)
            if number + 1 < len(slots):
                with pytest.raises(d.DispatchError, match='SHOW_SLOT'):
                    d._admit_run_helper(effects, policy, lambda: None, prior_observation=slots[number+1])
            break
        stdout, stderr, receipt = d._admit_run_helper(effects, policy, check, prior_observation=slot)
        assert stdout == b'show' and stderr == b'' and receipt['stdout_eof'] and receipt['stderr_eof']
    assert len(calls) == (6 if failure_slot is None else failure_slot)
    assert len(effects._admit_helper_usage) == len(calls)
    assert all(row['wait4'] is not None and row['failure'] is None for row in effects._admit_helper_usage)
    if failure_slot is None:
        with pytest.raises(d.DispatchError, match='SHOW_SLOT'):
            d._admit_run_helper(effects, policy, lambda: None, prior_observation=(1, 2))
        assert len(calls) == 6


@pytest.mark.parametrize("script,seconds,output,reason", [
    ("import os; os.write(1,b'x'*65536); os.write(2,b'y'*65536)", 5, 128, "OUTPUT_LIMIT"),
    ("import time; time.sleep(5)", 0.04, 65536, "TIMEOUT"),
    ("raise SystemExit(7)", 5, 65536, "EXIT"),
])
def test_real_helper_failure_kills_reaps_and_keeps_no_success(monkeypatch, script, seconds, output, reason):
    effects, policy, _ = helper_fixture(monkeypatch, script, seconds=seconds, output=output)
    with pytest.raises(d.DispatchError, match=reason):
        d._admit_helper(effects, policy, lambda: None)
    usage = effects._admit_helper_usage[0]
    assert usage["wait4"] is not None and usage["eof"] == ["stderr", "stdout"]
    assert usage["failure"] and usage["cleanup_failure"] is None


@pytest.mark.parametrize("key,value", [
    ("stage", "PRE_ENTRY"), ("pre_entry_containment", True), ("matched", False),
    ("policy_basis_sha256", "0" * 64), ("predicate_sha256", "0" * 64),
    ("snapshot_sha256", "0" * 64), ("facts_sha256", "not-a-digest"),
])
def test_public_admission_requires_exact_policy_binding(key, value):
    import test_e3_q2_core_delivery_dispatcher as fixture
    context = fixture.context()
    admission = fixture.FakeEffects(context).admit({})
    admission["policies"]["sudo"]["relation"][key] = value
    with pytest.raises(fixture.d.DispatchError, match="POLICY_RELATION"):
        fixture.d._validate_admission(admission, context)


def test_real_program_identity_cannot_adopt_another_digest():
    if os.geteuid() != 0:
        pytest.skip("O_NOATIME current root-owned executable requires root")
    reader = d._admit_reader(lambda: None, "/home/q1admin", 1000)
    try:
        value = d._admit_program(reader, "/usr/bin/true")
        assert value["resolved_path"] == "/usr/bin/true" and value["bytes"] > 0
    finally:
        reader.close()
    other = d._admit_reader(lambda: None, "/home/q1admin", 1000)
    try:
        with pytest.raises(d.DispatchError, match="PROGRAM_BINDING"):
            d._admit_program(other, "/usr/bin/true", {**value, "sha256": "0" * 64})
    finally:
        other.close()


def test_reader_closes_late_open_and_does_not_continue(tmp_path, monkeypatch):
    target = tmp_path / 'policy'; target.write_bytes(b'value')
    stale = False; opened = []
    real_open = os.open
    def guard():
        if stale: raise d.DispatchError('TEST_ORIGINAL_DEADLINE')
    def late(*args, **kwargs):
        nonlocal stale
        fd = real_open(*args, **kwargs); opened.append(fd); stale = True
        return fd
    reader = d._admit_reader(guard, str(tmp_path), os.getuid())
    monkeypatch.setattr(d.os, 'open', late)
    with pytest.raises(d.DispatchError, match='TEST_ORIGINAL_DEADLINE'):
        reader.open(target, os.O_RDONLY)
    assert reader.held == [] and len(opened) == 1
    with pytest.raises(OSError): os.fstat(opened[0])


@pytest.mark.parametrize('stage', [None, 'policies', 'programs', 'guest', 'prior_0a', 'prior_1a', 'prior_2a',
    'capacity', 'managers', 'prior_0b', 'prior_1b', 'prior_2b', 'finish_0', 'finish_1', 'finish_2',
    'recheck_0', 'recheck_1', 'recheck_2'])
def test_real_admit_orders_components_and_never_retries(monkeypatch, stage):
    import test_e3_q2_core_delivery_dispatcher as fixture
    context = fixture.context(); expected = fixture.FakeEffects(context).admit({})
    effect = d.FieldEffects(context); trace = []
    effect._effect_guard = lambda: None
    monkeypatch.setattr(d, '_validate_approved_components', lambda *_: None)
    def result(name, value):
        def call(*_):
            trace.append(name)
            if stage == name: raise d.DispatchError('TEST_' + name)
            return value
        return call
    manager_keys = ('user_manager_unit', 'user_manager_invocation_id', 'user_manager_cgroup')
    directory = set(d._CAP_ROLES)
    monkeypatch.setattr(d, '_admit_collect_policies', result('policies', {'policies': expected['policies']}))
    monkeypatch.setattr(d, '_admit_programs', result('programs', expected['programs']))
    monkeypatch.setattr(d, '_admit_guest', result('guest', {k: v for k, v in expected['guest'].items()
        if k not in manager_keys}))
    effect._capacity_admission = result('capacity', dict(
        parents={k: v for k, v in expected['parents'].items() if k in directory},
        filesystems=expected['filesystems'], capacity=expected['capacity'], absence=expected['absence']))
    effect._capacity_managers = result('managers', dict(
        parents={k: v for k, v in expected['parents'].items() if k not in directory}, absence=[],
        manager={k: expected['guest'][k] for k in manager_keys}))
    class Observer:
        def __init__(self, _effects, _program, index=0): self.count = 0; self.index = index
        def observe(self):
            self.count += 1
            return result('prior_' + str(self.index) + ('a' if self.count == 1 else 'b'), None)()
        def finish(self):
            return result('finish_' + str(self.index), expected['prior_core_attempts'][self.index])()
        def recheck(self): result('recheck_' + str(self.index), None)()
        def close(self): pass
    monkeypatch.setattr(d, '_PriorScopeObserver', Observer)
    argument = {key: context[key] for key in ('manifest', 'hello', 'guest_deadlines')}
    # Component-ordering fixture has synthetic parents; the actual metadata
    # observer is covered by temporary-filesystem integration tests.
    monkeypatch.setattr(d._PoolAccounting, 'observe', result('accounting', None))
    order = ['policies', 'programs', 'guest', 'prior_0a', 'prior_1a', 'prior_2a', 'capacity', 'managers',
             'prior_0b', 'prior_1b', 'prior_2b', 'finish_0', 'finish_1', 'finish_2',
             'recheck_0', 'recheck_1', 'recheck_2']
    if stage is None:
        assert effect.admit(argument) == expected
        assert trace == order + ['accounting']
    else:
        with pytest.raises(d.DispatchError, match='TEST_' + stage): effect.admit(argument)
        assert trace == order[:order.index(stage) + 1] and effect._admission is None
    prior = list(trace)
    with pytest.raises(d.DispatchError, match='ADMISSION_BINDING'): effect.admit(argument)
    assert trace == prior and effect._installation is None and not effect.held


@pytest.mark.parametrize('change', ['boot', 'account', 'groups', 'manager', 'parent', 'owner',
    'device', 'reserve', 'roles', 'missing_path', 'missing_project'])
def test_admission_consumer_rejects_cross_binding_errors(change):
    import test_e3_q2_core_delivery_dispatcher as fixture
    context = fixture.context(); value = fixture.FakeEffects(context).admit({})
    if change == 'boot': value['guest']['boot_id'] = '00000000-0000-0000-0000-000000000000'
    elif change == 'account': value['guest']['ordinary_user'] = 'other'
    elif change == 'groups': value['guest']['ordinary_groups'].append(0)
    elif change == 'manager': value['guest']['user_manager_unit'] = 'user@0.service'
    elif change == 'parent': value['parents']['state']['path'] = '/different'
    elif change == 'owner': value['parents']['state']['uid'] = 1100
    elif change == 'device': value['capacity'][0]['dev'] = 1
    elif change == 'reserve': value['capacity'][0]['new_required_bytes'] -= 1
    elif change == 'roles': value['capacity'][0]['roles'].pop()
    elif change == 'missing_path': value['absence'] = [r for r in value['absence'] if r['kind'] != 'path']
    elif change == 'missing_project': value['absence'] = [r for r in value['absence'] if r['kind'] != 'project']
    with pytest.raises(d.DispatchError): d._validate_admission(value, context)
