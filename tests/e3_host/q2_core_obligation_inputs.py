"""Pinned retained-horizon transforms for closed core amendment A 0bdb49c.

Pure D1 input processing: bytes must come from the host's held-source reader.
No file extraction, guest observation, release, current-device assignment or
field readiness is performed here. Historical rows and configured quotas are
separate liabilities; neither is a current filesystem bill.
"""
from __future__ import annotations

import copy
from decimal import Decimal
import hashlib
import io
import json
from pathlib import PurePosixPath
import zipfile

from . import q2_core_delivery_contract as c


ARCHIVES = (
    ("20260930b", "local-hand-normal-5ca9753-run-20260930b-evidence.zip", 289401,
     "eeef31dc11bb277caec267cd11590654cb2e6d036485f941607dce0dc9af0ac1"),
    ("20261001a", "local-hand-normal-5ca9753-run-20261001a-evidence.zip", 297168,
     "d9e26cdbdd393a83cd83e396e560cbd1ea6b01f84dab10e58d0e1974c00f181d"),
    ("20261001b", "local-hand-normal-5ca9753-run-20261001b-evidence.zip", 308465,
     "ae969b050c6d20761af05b0b87c0be0e8c45d059fcd851db0c24f0b605736f43"),
    ("20261001c", "local-hand-normal-b37935d-run-20261001c-evidence.zip", 349790,
     "2013877a266b87509579ea6b05e539cfb562fbbb2e11275c8a80100cb1ad0264"),
    ("20261001d", "local-hand-normal-7780364-run-20261001d-evidence.zip", 356297,
     "6707359a14565747a673db4862d435d56e4967fc50aded26e3ac1ec93e90dd5c"),
    ("20261001e", "local-hand-system-manager-1a900e4-run-20261002-evidence.zip", 129584,
     "f352d1d8bc70d3d4c419c21de493efca2c51a3453dc90d04fba3ec654e7e33b6"),
)

# Exact members, in A's order. Basename searching and alternate copies are not
# admissible even when a different member has identical content.
NORMAL_PINS = (
    ("20260930b", "plan", 13383, "6836678f2c2a5bc320bb18f40344cd83e162e53801f08140e78d87c75f3e1363"),
    ("20260930b", "observed", 59349, "1458436d63130589b42cea02d438c92c5d151f041e49d76be074fe1d5daa159e"),
    ("20261001a", "plan", 15072, "50f1c8c157d0515f4dd27337c474d2345e010f63271e3866b1d32d96bca0c8f5"),
    ("20261001a", "observed", 62307, "afaf940b1a0671c152d951e0a8ba2ee670333aef8561e76337b558ca1b8dab18"),
    ("20261001b", "plan", 16838, "998dc901303967660c5bcc19768d03002a00eb594f260cdbbf598fc3acefdd89"),
    ("20261001b", "observed", 65268, "c2dd6ab190a8e96fd98ea93a0b1f5fb88120f6d482137500e8491db07383df6c"),
    ("20261001c", "plan", 18595, "7144977af9f3ff874f4e41317420a01b40fa601c9c420e288c9c1fab2f55b9a5"),
    ("20261001c", "observed", 68505, "7f62ccabf4063d292b443c034bfb3c4fbd4d0fdb14b633e6003986ae6a0ae14b"),
    ("20261001c", "code-intent", 519, "2ae23f8d219b265fdb98c8e54d678ca540499b9e1390897b9f8a26ae08b11fd1"),
    ("20261001c", "installation", 45338, "56cd30fe64c26923a0bf4aab10f4dab6f8c7793883fa83f056c50d23246a4893"),
    ("20261001d", "plan", 20429, "35aa2fb4fc0f5fc5ea00f1e895fbee330d1fe2825f46cb7f3ca0ddfbda0f85e8"),
    ("20261001d", "observed", 72163, "b15625827d845ab7d54e8fef42c63a8bc85ce18d5c3ee3289a178d536cd80e88"),
    ("20261001d", "code-intent", 519, "30e68dd477eaafac70c1142dc567a70c028eaaf05b1696008745e4e731b3bfbd"),
    ("20261001d", "installation", 45338, "df92885a74f4df2b14e06aa4420c2fb876fe987e3d35a722574a37718549f853"),
)
DELTA_BASE = "guest/opt/local-hand-resume-5ca9753-20261001e/"
DELTA_PINS = (
    ("installation", "guest/opt/local-hand-code-20261001e/installation.json", 47699,
     "1bc8d61538d0c48f604e3bf2fb7002b481bb62e7f0c3c7ffc433c0818ef5b1f5"),
    ("client-intent", DELTA_BASE + "client-log/intent.json", 1402,
     "ab57768eb5efe19015c4dcc4e2d4f79db7901684b932c91f65444d2cbd2e1377"),
    ("client-result", DELTA_BASE + "client-log/result.json", 305,
     "ef898352c22ffc601f2617327918a0f0baa45d45def99e487bde45e41e1878cd"),
    ("consumed", DELTA_BASE + "consumed.json", 331,
     "ba29f6c3dcfab18708f1d67de58a5bb8bff1918b4d01c3fd49b67ee1c70156ee"),
    ("staged", DELTA_BASE + "staged.json", 523,
     "63fd8aa4b3f8cc406b47b94109d547d4ecdc85d147034e45b068e65e222a08ae"),
    ("code-intent", DELTA_BASE + "prepare-log/0006-code-update-intent.json", 895,
     "c4e45fc7fa217722fe57f7576d85c72181ad93a9cdf422e0a3919b77a1493a48"),
    ("code-complete", DELTA_BASE + "prepare-log/0019-code-update-complete.json", 326,
     "896066511a5a5656073aa858a6e4c0c23e2b1550faef38597ee7e0603854c97e"),
    ("plan", DELTA_BASE + "prepare-log/0023-plan.json", 30813,
     "85633b837718282ba6590b7a6679d51aa60addfb0f5be39ea929af83de4a45c1"),
    ("original-budget", DELTA_BASE + "prepare-log/0046-original-budget-bounds.json", 619,
     "6e19304516853a0b3c4d89deb4a4011e9a3ea72d287904ef7dfd5b484ff97621"),
    ("historical-snapshot", DELTA_BASE + "prepare-log/0047-historical-issued-obligations.json", 21086,
     "9e0bfb17a58c8fec064601ef675e391a8ef358269b775daca60f7ea47150cb8e"),
    ("preflight", DELTA_BASE + "prepare-log/0048-resource-preflight.json", 94533,
     "eabe18b207e68967e65b9dc9d114466aad7284063cff6e90814938a0ae9fb086"),
    ("failure", DELTA_BASE + "prepare-log/0053-failure.json", 943,
     "79ccccf1745bcad29089c381e692ca777c7fc2165cd31cc1f54ed825db545b85"),
)
VECTOR_PINS = {
    "snapshot": (11433, "82bdb7a94c85a7450a45d9ee7dff2baa4e5fef7b8a7a7d8f7787a0cb7bea358e"),
    "delta": (6678, "b8af1d3264b77b9142a48288482c26d2eafa894523f85baa0fc71d595da90352"),
    "effective": (18110, "7c2786f240144e7a2de90bc9a70561089a7334559bd8e962371132cf1db806e9"),
    "quota": (2997, "95b59d878d643bfbce2eef6ce88145bf1086058694dee127b3de49d13319bde0"),
    "placement_source": (4327, "edcb0bb95508c15e5b3fb60d679c46c93961e95d8e802a338fc1f4397c18ee0d"),
    "placement_normalized": (4549, "b6153d8c45e5b009bcc1f878406565e08bcf7c7d07c17f18361b562bf1096703"),
    "row_relation": (462, "89dea12770f6c6ab19b901adcf4c4d42e6b8b42300c1ca470b1ec7ac03ec47e6"),
}
PREFIX_SHA256 = "09f107f265986afd0dcc0535de84d2df37ac47ddeff78d20569c2bb8a5513e88"
TAIL_SHA256 = "60885e762f1dfe007f43b6ae1e056dabdce9b1e142688741d333f806f6952a68"
TOTALS = dict(snapshot_bytes=626790400, snapshot_inodes=32113,
              delta_bytes=138412032, delta_inodes=8064,
              effective_bytes=765202432, effective_inodes=40177,
              configured_quota_bytes=249561088, configured_quota_inodes=17792)


def _require(condition, code):
    c.require(condition, "CORE_OBLIGATION_" + code)


def _pin(raw, size, digest, code):
    _require(type(raw) is bytes and len(raw) == size
             and hashlib.sha256(raw).hexdigest() == digest, code)
    return raw


def _vector(value, name):
    return _pin(c.canonical(value), *VECTOR_PINS[name], "VECTOR_" + name.upper())


def _json(raw, *, historical_client_intent=False):
    # Retained evidence is not required to have used the new canonical encoding.
    # Its exact bytes are pinned before parsing. New output is canonical.
    def integer(text):
        value = int(text)
        _require(-(2**63) <= value <= 2**63 - 1, "INTEGER_RANGE")
        return value
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=c._pairs,
                           parse_int=integer,
                           parse_float=Decimal if historical_client_intent else c._constant,
                           parse_constant=c._constant)
    except (ValueError, UnicodeError) as error:
        raise c.ContractError("CORE_OBLIGATION_SOURCE_JSON") from error
    if not historical_client_intent:
        c._shape(value)
    # The exactly pinned old client intent contains a decimal timing value.
    # It is not an amendment JSON artifact. Retain its numeric spelling as
    # Decimal, never round it to int or permit it in new canonical output.
    _require(type(value) is dict, "SOURCE_OBJECT")
    return value


def source_members():
    rows = []
    for batch, role, size, digest in NORMAL_PINS:
        if role in ("plan", "observed"):
            name = "resume-plan.json" if role == "plan" else "observed.json"
            path = "root/q2-normal-setup-" + batch + "/" + name
        elif role == "code-intent":
            path = "opt/local-hand-resume-5ca9753-" + batch + "/prepare-log/0006-code-update-intent.json"
        else:
            path = "opt/local-hand-code-" + batch + "/installation.json"
        rows.append(dict(batch=batch, role=role, path=path, bytes=size, sha256=digest))
    rows.extend(dict(batch="20261001e", role=role, path=path, bytes=size, sha256=digest)
                for role, path, size, digest in DELTA_PINS)
    return rows


def read_horizon(archive_bytes):
    """Verify all six carriers and all 26 exact members; never extract files."""
    _require(type(archive_bytes) is dict
             and set(archive_bytes) == {row[0] for row in ARCHIVES}, "CARRIER_SET")
    members = source_members()
    documents = {}
    for batch, _basename, size, digest in ARCHIVES:
        raw = _pin(archive_bytes[batch], size, digest, "CARRIER_PIN")
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries = archive.infolist()
                names = [item.filename for item in entries]
                _require(0 < len(entries) <= 4096 and len(names) == len(set(names)), "ZIP_MEMBERS")
                for item in entries:
                    name = item.filename
                    _require(name.isascii() and not name.startswith("/")
                             and "\\" not in name and "\0" not in name
                             and ".." not in PurePosixPath(name).parts
                             and str(PurePosixPath(name)) == name.rstrip("/"), "ZIP_PATH")
                for row in (row for row in members if row["batch"] == batch):
                    info = archive.getinfo(row["path"])
                    _require(not info.is_dir() and info.file_size == row["bytes"]
                             and not info.flag_bits & 1, "MEMBER_SIZE")
                    with archive.open(info) as stream:
                        content = stream.read(row["bytes"] + 1)
                    _pin(content, row["bytes"], row["sha256"], "MEMBER_PIN")
                    documents[batch, row["role"]] = _json(content,
                        historical_client_intent=(batch, row["role"]) == ("20261001e", "client-intent"))
        except (KeyError, OSError, RuntimeError, zipfile.BadZipFile) as error:
            raise c.ContractError("CORE_OBLIGATION_ARCHIVE") from error
    return documents


def delta_rows():
    """A's new transform, not claimed as output of the historical producer."""
    base = "/opt/local-hand-resume-5ca9753-20261001e"
    code = "/opt/local-hand-code-20261001e"
    common = [base + "/consumed.json", base + "/prepare-log/0023-plan.json",
              base + "/prepare-log/0053-failure.json"]
    code_evidence = [code + "/installation.json", common[0],
                     base + "/prepare-log/0006-code-update-intent.json", common[2]]
    management_evidence = [base + "/client-log/intent.json", *common]
    specifications = [
        ("code_pool", [code], code_evidence, 67108864, 4096, "install_parent"),
        ("management", [base, "/root/q2-normal-setup-20261001e",
                        "/var/lib/local-hand-q2-normal-declarations-20261001e"],
         management_evidence, 33554432, 1024, "state_parent"),
        ("state", ["/var/lib/local-hand-q2-normal-" + role + "-20261001e"
                   for role in ("state", "authority", "session", "control")],
         common, 8388608, 1536, "state_parent"),
        ("journal", ["/srv/local-hand-q1/journal/q2-normal-20261001e"],
         common, 1048576, 128, "journal_parent"),
        ("capture", ["/srv/local-hand-q1/evidence/q2-normal-capture-20261001e"],
         common, 20971520, 384, "evidence_parent"),
    ]
    for slot in ("a", "b"):
        for kind in ("work", "evidence", "temporary"):
            specifications.append(("quota." + kind + "-" + slot,
                ["/srv/local-hand-q1/quota/q2-" + kind + "-20261001e/slot-" + slot],
                common, 1048576, 128, "quota_parent"))
    specifications.append(("quota.retained_store",
        ["/srv/local-hand-q1/quota/q2-store-parent-20261001e/store"],
        common, 1048576, 128, "quota_parent"))
    result = [dict(reservation_id="20261001e:" + category, batch="20261001e",
                   category=category, covered_paths=paths, evidence=list(evidence),
                   commitment=dict(bytes=size, inodes=count), device_selector=selector,
                   status="UNRELEASED", actual_allocation_already_excluded_from_free=True)
              for category, paths, evidence, size, count, selector in specifications]
    _vector(result, "delta")
    return result


def _total(rows, field):
    total = 0
    for row in rows:
        value = row["commitment"][field]
        c.integer(value)
        total += value
        c.integer(total)
    return total


def _snapshot(document):
    _require(document.get("historical_plan_executed") is False
             and document.get("released_or_refunded") is False, "SNAPSHOT_PERMISSION")
    rows = document.get("obligations")
    _require(type(rows) is list and len(rows) == 24, "SNAPSHOT_COUNT")
    _vector(rows, "snapshot")
    _require(c.sha256(c.canonical(rows[:7])) == PREFIX_SHA256
             and c.sha256(c.canonical(rows[7:])) == TAIL_SHA256, "SNAPSHOT_PREFIX")
    _require(len({row["id"] for row in rows}) == 24, "SNAPSHOT_DUPLICATE")
    _require((_total(rows, "bytes"), _total(rows, "inodes")) == (626790400, 32113), "SNAPSHOT_TOTAL")
    return copy.deepcopy(rows)


def _quota(preflight):
    source = preflight["capacity_observed"]["quota_inventory"]
    _require(type(source) is list, "QUOTA_SOURCE")
    rows, seen = [], set()
    for item in source:
        for key in ("project", "hard", "ihard"):
            c.integer(item[key])
        if item["hard"] == 0:
            continue
        project = item["project"]
        _require(project not in seen, "QUOTA_DUPLICATE")
        seen.add(project)
        amount = item["hard"] * 1024
        c.integer(amount)
        rows.append(dict(project_id=project, hard_bytes=amount, inode_hard_limit=item["ihard"]))
    _vector(rows, "quota")
    _require(len(rows) == 46 and sum(r["hard_bytes"] for r in rows) == 249561088
             and sum(r["inode_hard_limit"] for r in rows) == 17792, "QUOTA_TOTAL")
    return rows


def _placement(preflight, plan, snapshot):
    source = preflight["capacity_observed"]["historical_physical_charges"]
    _vector(source, "placement_source")
    mounts = plan["mounts"]
    roles = ("system", "quota", "journal", "evidence")
    _require(type(mounts) is dict and set(mounts) == set(roles), "MOUNT_ROLES")
    devices = {}
    for role in roles:
        device = c.integer(mounts[role]["device"], 1)
        _require(device not in devices, "HISTORICAL_DEVICE_ALIAS")
        devices[device] = role
    normalized = []
    _require(len(source) == len(snapshot), "PLACEMENT_COUNT")
    for row, obligation in zip(source, snapshot, strict=True):
        c.exact(row, {"id", "category", "devices", "full_commitment", "no_refund"})
        _require(row["id"] == obligation["id"] and row["category"] == obligation["category"]
                 and row["full_commitment"] == obligation["commitment"]
                 and row["no_refund"] is True, "PLACEMENT_RELATION")
        _require(type(row["devices"]) is list and len(row["devices"]) > 0
                 and all(type(d) is int and d in devices for d in row["devices"])
                 and len(set(row["devices"])) == len(row["devices"]), "PLACEMENT_DEVICE")
        normalized.append(dict(id=row["id"], category=row["category"],
            pool_roles=[devices[d] for d in row["devices"]],
            full_commitment=copy.deepcopy(row["full_commitment"]), no_refund=True))
    _vector(normalized, "placement_normalized")
    return normalized


def build_horizon(archive_bytes):
    """Derive pinned vectors. This is not a complete approved-input artifact.

    Legacy-source reconciliation, policy/local binding and live pool admission
    must still be supplied by their own verified consumers before field release.
    In particular the matching seven-row digest is not a rerun of legacy verify.
    """
    documents = read_horizon(archive_bytes)
    snapshot = _snapshot(documents["20261001e", "historical-snapshot"])
    preflight = documents["20261001e", "preflight"]
    delta = delta_rows()
    effective = snapshot + delta
    _vector(effective, "effective")
    _require((_total(effective, "bytes"), _total(effective, "inodes"))
             == (765202432, 40177), "EFFECTIVE_TOTAL")
    normalized = _placement(preflight, documents["20261001e", "plan"], snapshot)
    quota = _quota(preflight)
    relation = dict(reconciliation_prefix_count=7, reconciliation_prefix_sha256=PREFIX_SHA256,
        snapshot_count=24, snapshot_sha256=VECTOR_PINS["snapshot"][1], snapshot_tail_count=17,
        snapshot_tail_sha256=TAIL_SHA256, delta_count=12, effective_count=36,
        effective_construction="SNAPSHOT_24_PLUS_DELTA_12", prefix_equal=True)
    _vector(relation, "row_relation")
    return dict(snapshot_rows=snapshot, delta_rows=delta, effective_rows=effective,
                normalized_placement_rows=normalized, configured_quota_rows=quota,
                row_relation=relation, totals=copy.deepcopy(TOTALS))
