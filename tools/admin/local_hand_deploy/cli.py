"""One private administrator entry for plan/apply/resume/rollback/status."""
from __future__ import annotations

import argparse
import json
import os
import sys

from local_hand_jobs.maintenance import MaintenanceGate
from local_hand_jobs.contract import JobError
from local_hand_jobs.startup import protected_read

from .checks import check_public
from .bootstrap import adopt_bootstrap, build_bootstrap_plan, is_bootstrap, rollback_bootstrap
from .coordinator import Coordinator
from .identity import implementation_identity
from .model import DeployError, decode, validate_plan
from .planner import build_plan
from .report import admission_view, report
from .runtime import ConcreteEnvironment
from .store import Store
from .binding import release_plan, repair_plan, validate_binding


def read_document(path):
    return decode(protected_read(path, owner_uid=os.geteuid(), maximum=2 * 1024 * 1024))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Resume fixed local deployment effects; never replay business tasks")
    parser.add_argument("--state", help="Existing protected deployment state directory")
    parser.add_argument("--node", help="Exact configured node identity")
    parser.add_argument("--binding", help="Protected data-only node binding; cannot override it with --state/--node")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-state", help="Explicit create-only initialization; does not open admission")
    commands.add_parser("plan").add_argument("manifest")
    commands.add_parser("release-plan", help="Read-only plan from fixed node binding and release").add_argument("release")
    repair = commands.add_parser("repair-plan", help="Read-only corrective plan bound to an original deployment")
    repair.add_argument("operation"); repair.add_argument("release")
    commands.add_parser("bootstrap-plan", help="Read-only offline compatibility import plan").add_argument("manifest")
    commands.add_parser("bootstrap-adopt", help="Resume verified stopped compatibility import").add_argument("plan")
    commands.add_parser("apply").add_argument("plan")
    commands.add_parser("status").add_argument("operation", nargs="?")
    for name in ("resume", "rollback"):
        commands.add_parser(name).add_argument("operation")
    supersede = commands.add_parser("supersede")
    supersede.add_argument("operation"); supersede.add_argument("plan")
    commands.add_parser("check-public").add_argument("specification")
    args = parser.parse_args(argv)
    try:
        binding = validate_binding(read_document(args.binding)) if args.binding else None
        if binding:
            if args.state is not None or args.node is not None:
                raise DeployError("INVALID_BINDING", "Cannot override the selected private node binding")
            args.state, args.node = binding["state"], binding["node_id"]
        implementation = (implementation_identity() if args.command in
                          {"apply", "resume", "rollback", "supersede", "init-state", "bootstrap-adopt"} else None)
        if args.command in {"release-plan", "repair-plan"}:
            if binding is None:
                raise DeployError("INVALID_BINDING", "release-plan requires --binding")
            result = (release_plan(binding, read_document(args.release)) if args.command == "release-plan" else
                      repair_plan(binding, read_document(args.release), args.operation))
        elif args.command == "plan":
            result = build_plan(read_document(args.manifest))
        elif args.command == "bootstrap-plan":
            result = build_bootstrap_plan(read_document(args.manifest))
        elif args.command == "check-public":
            result = check_public(read_document(args.specification))
        else:
            if not args.state or not args.node:
                raise DeployError("INVALID_REQUEST", "This command requires --state and --node")
            store = Store(args.state, args.node)
            if args.command == "init-state":
                store.initialize()
                result = {"initialized": True, "admission": "UNCHANGED"}
            elif args.command == "status":
                operations = [store.get(args.operation)] if args.operation else store.list(unfinished=True)
                result = []
                for operation in operations:
                    profile = operation["plan"]["profile"]
                    gate = MaintenanceGate(profile["maintenance_directory"], args.node,
                                           owner_uid=profile.get("owner_uid", 0))
                    result.append(report(operation, admission=admission_view(gate)))
            else:
                if args.command in {"apply", "bootstrap-adopt"}:
                    plan = validate_plan(read_document(args.plan))
                else:
                    plan = store.get(args.operation)["plan"]
                if plan["node_id"] != args.node:
                    raise DeployError("NODE_CONFLICT", "Plan belongs to a different node")
                profile = plan["profile"]
                gate = MaintenanceGate(profile["maintenance_directory"], args.node,
                                       owner_uid=profile.get("owner_uid", 0))
                if is_bootstrap(plan):
                    if args.command in {"bootstrap-adopt", "resume"}:
                        operation = adopt_bootstrap(store, plan, implementation=implementation)
                    elif args.command == "rollback":
                        operation = rollback_bootstrap(store, args.operation)
                    else:
                        raise DeployError("BOOTSTRAP_SCOPE", "Use bootstrap-adopt/resume or isolated rollback for this import")
                    result = report(operation, admission=admission_view(gate))
                    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
                    return 3 if operation["waiting"] else 0
                if args.command == "bootstrap-adopt":
                    raise DeployError("BOOTSTRAP_SCOPE", "Expected an offline import plan")
                coordinator = Coordinator(store, gate, ConcreteEnvironment(plan, store, gate), implementation=implementation)
                if args.command == "apply":
                    operation = coordinator.apply(plan)
                elif args.command == "supersede":
                    operation = coordinator.supersede(args.operation, validate_plan(read_document(args.plan)))
                else:
                    operation = getattr(coordinator, args.command)(args.operation)
                result = report(operation, admission=admission_view(gate))
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
        if args.command == "check-public":
            return 0 if result["status"] == "PASSED" else 4
        return 0 if not isinstance(result, dict) or not result.get("recovery", {}).get("waiting") else 3
    except (OSError, RuntimeError, ValueError, JobError) as error:
        # Private tools may record detailed raw errors separately. Never put
        # source paths, URLs, credentials or command output in this public form.
        print(json.dumps({"status": "NOT_COMPLETED", "error": getattr(error, "code", type(error).__name__)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
