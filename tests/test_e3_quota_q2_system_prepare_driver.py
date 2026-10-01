"""System preparation is explicit, measured and charged within the old pools."""
import copy
import unittest

from test_e3_quota_q2_prepare_driver import d, fixture, ModelFiles


def system_fixture():
    plan, receipt = fixture()
    observed = receipt["facts"]
    plan["schema"] = d.SYSTEM_PLAN_SCHEMA
    plan["settings"]["schema"] = d.SYSTEM_SETTINGS_SCHEMA
    plan["settings"]["controllers"]["target"]["memory_bytes"] = 256 * 1024**2
    plan["settings"]["capacity_management"]["memory_bytes"] = 1536 * 1024**2
    plan["retained_ordinary_parent"] = d.pin(observed["parents"]["ordinary"])
    outer = d.pin(observed["parents"]["controller"])
    ordinary = dict(path=outer["path"] + "/lhqcontroller-ordinary.slice", device=70, inode=600)
    observed["parents"]["ordinary"].update(ordinary)
    observed["system_geometry"] = dict(schema="local-hand-q2-system-geometry/v1", **{
        key: dict(parent=parent, memory_bytes=memory, tasks_max=tasks,
            cpu_quota_per_sec_usec=1_000_000, memory_swap_max=0)
        for key, parent, memory, tasks in (
            ("controller_parent", outer, 512 * 1024**2, 64),
            ("ordinary_parent", ordinary, 256 * 1024**2, 32),
            ("retained_ordinary_parent", plan["retained_ordinary_parent"], 256 * 1024**2, 64))})
    return plan, receipt


def translate(plan, receipt):
    files = ModelFiles()
    observed = receipt["facts"]
    children = {name: files.directory(observed["directories"]["capture"], name) for name in
        ("preflight", "postflight", "reconcile", "management_evidence", "launcher_output", "launcher_declarations",
         "supervisor_output", "supervisor_declarations")}
    # Reuse the actual phase set, which is part of the assembly contract.
    for name in d.helper("q2_prepare_assembly").PHASES:
        if name not in children:
            children[name] = files.directory(observed["directories"]["capture"], name)
    return d.facts_from_observed(plan, observed, children, dict(schema="synthetic-authority/v1"))


class SystemPreparationTests(unittest.TestCase):
    def test_explicit_versions_are_paired_and_legacy_keeps_shape(self):
        plan, receipt = fixture()
        facts, _, manifest = translate(plan, receipt)
        self.assertEqual("local-hand-q2-assembly-facts/v1", facts["schema"])
        self.assertNotIn("manager_binding", facts["ordinary"])
        self.assertNotIn("system_geometry", manifest)
        for side in ("plan", "settings", "unknown"):
            plan, _ = system_fixture()
            if side == "plan":
                plan.pop("schema")
            elif side == "settings":
                plan["settings"].pop("schema")
            else:
                plan["settings"]["schema"] += "-unknown"
            with self.subTest(side=side), self.assertRaises(ValueError):
                d.validate_plan(plan)

    def test_new_facts_bind_measured_geometry_and_manifest(self):
        plan, receipt = system_fixture()
        facts, _, manifest = translate(plan, receipt)
        self.assertEqual("local-hand-q2-system-assembly-facts/v1", facts["schema"])
        binding = facts["ordinary"]["manager_binding"]
        self.assertEqual("system", binding["manager_kind"])
        self.assertEqual(facts["identity"]["authority_id"], binding["authority_id"])
        self.assertEqual(receipt["facts"]["host"]["boot_id"], binding["boot_id"])
        self.assertEqual(d.pin(receipt["facts"]["parents"]["ordinary"]), binding["parent"])
        self.assertEqual(facts["system_geometry"], manifest["system_geometry"])
        self.assertEqual(d.sha(d.encoded(manifest)), facts["identity"]["manifest_digest"])
        facts["system_geometry"]["ordinary_parent"]["parent"]["inode"] += 1
        self.assertNotEqual(facts["system_geometry"], receipt["facts"]["system_geometry"])

    def test_changed_retained_pin_geometry_or_limits_reject(self):
        for fault in ("old_pin", "new_pin", "nested_old", "memory", "tasks", "target"):
            plan, receipt = system_fixture()
            geometry = receipt["facts"]["system_geometry"]
            # Break aliases deliberately to model a changed observation.
            receipt["facts"]["system_geometry"] = geometry = copy.deepcopy(geometry)
            if fault == "old_pin": geometry["retained_ordinary_parent"]["parent"]["inode"] += 1
            elif fault == "new_pin": geometry["ordinary_parent"]["parent"]["inode"] += 1
            elif fault == "nested_old": geometry["retained_ordinary_parent"]["parent"]["path"] = "/lhqcontroller.slice/old.slice"
            elif fault == "memory": geometry["ordinary_parent"]["memory_bytes"] += 1
            elif fault == "tasks": geometry["ordinary_parent"]["tasks_max"] += 1
            else: plan["settings"]["controllers"]["target"]["memory_bytes"] -= 1
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                translate(plan, receipt)

    def test_gateway_output_is_charged_once_without_storage_pool(self):
        plan, _ = system_fixture()
        settings = plan["settings"]
        legacy = copy.deepcopy(settings); legacy.pop("schema")
        # Find the pre-existing exact output boundary without duplicating the
        # production accounting formula in the test.
        low, high = 1, settings["capacity_management"]["output_bytes"]
        while low < high:
            middle = (low + high) // 2
            legacy["capacity_management"]["output_bytes"] = middle
            try:
                d.validate_settings(legacy)
                high = middle
            except ValueError:
                low = middle + 1
        settings["capacity_management"]["output_bytes"] = low + d.SYSTEM_GATEWAY_OUTPUT_BYTES
        self.assertEqual(settings, d.validate_settings(settings))
        self.assertEqual(legacy["capacity_management"]["storage_bytes"], settings["capacity_management"]["storage_bytes"])
        settings["capacity_management"]["output_bytes"] -= 1
        with self.assertRaisesRegex(ValueError, "DRIVER_COMBINED_CAPACITY"):
            d.validate_settings(settings)

    def test_system_observation_cannot_be_relabelled_legacy(self):
        plan, receipt = system_fixture()
        plan.pop("schema"); plan["settings"].pop("schema")
        with self.assertRaisesRegex(ValueError, "DRIVER_SCHEMA_FAMILY"):
            translate(plan, receipt)


if __name__ == "__main__":
    unittest.main()
