#!/usr/bin/env python
"""The published schemas must describe what the coordinator actually writes.

`schemas/` is the contract for workers that cannot run `roach.py` -- an agent
with repository API tools and no shell reproduces the protocol from it. That
contract is only worth anything if it stays true, and nothing about adding a
field to a task record forces anyone to update a JSON file in another
directory. These tests are that force.

No third-party dependency: this compares the schemas against the coordinator
itself rather than validating documents against them.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCHEMAS = REPO / "schemas"

SPEC = importlib.util.spec_from_file_location("roach_under_test", REPO / "scripts" / "roach.py")
assert SPEC is not None and SPEC.loader is not None
roach = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(roach)


def schema(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))


class TaskSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = schema("task")
        self.properties = self.schema["properties"]
        self.record = roach.make_task(task_id="T001", kind="implementation", title="t",
                                      acceptance=["a"])

    def test_every_field_the_coordinator_writes_is_described(self) -> None:
        missing = sorted(set(self.record) - set(self.properties))
        self.assertEqual([], missing, "task records gained fields the schema does not describe")

    def test_the_schema_describes_no_field_the_coordinator_omits(self) -> None:
        extra = sorted(set(self.properties) - set(self.record))
        self.assertEqual([], extra, "the schema describes fields no task record contains")

    def test_required_fields_are_actually_produced(self) -> None:
        for field in self.schema["required"]:
            self.assertIn(field, self.record, f"schema requires {field}, which make_task never writes")

    def test_status_and_priority_vocabularies_agree(self) -> None:
        self.assertEqual(sorted(roach.STATUSES), sorted(self.properties["status"]["enum"]))
        self.assertEqual(sorted(roach.PRIORITY), sorted(self.properties["priority"]["enum"]))

    def test_id_and_token_patterns_accept_and_reject_the_same_values(self) -> None:
        """Compare behaviour, not spelling: `\\d` and `[0-9]` are the same rule."""
        import re

        task_pattern = re.compile(self.properties["id"]["pattern"])
        for value in ("T000", "T001", "T1234"):
            self.assertTrue(roach.TASK_RE.fullmatch(value) and task_pattern.fullmatch(value), value)
        for value in ("T1", "T12", "X001", "t001", "T001a", ""):
            self.assertFalse(roach.TASK_RE.fullmatch(value) or task_pattern.fullmatch(value), value)

        kind_pattern = re.compile(self.properties["kind"]["pattern"])
        for value in ("implementation", "repo-write", "unity-editor", "a1", "x.y:z"):
            self.assertTrue(roach.TOKEN_RE.fullmatch(value) and kind_pattern.fullmatch(value), value)
        for value in ("Implementation", "-leading", "has space", ""):
            self.assertFalse(roach.TOKEN_RE.fullmatch(value) or kind_pattern.fullmatch(value), value)

    def test_claim_fields_match_what_claim_writes(self) -> None:
        described = set(self.properties["claim"]["oneOf"][1]["properties"])
        written = {"worker", "claimed_at", "lease_expires_at", "branch", "base_commit",
                   "adopted_from", "adopted_reason"}
        self.assertEqual(written, described, "claim shape drifted from claim/adopt")


class StateSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = schema("state")
        self.properties = self.schema["properties"]

    def test_protocol_version_is_pinned_to_the_coordinator(self) -> None:
        self.assertEqual(roach.PROTOCOL_VERSION, self.properties["protocol_version"]["const"])

    def test_status_and_phase_vocabularies_agree(self) -> None:
        self.assertEqual(sorted(roach.PROJECT_STATUSES),
                         sorted(self.properties["project_status"]["enum"]))
        self.assertEqual(sorted(roach.PHASES), sorted(self.properties["phase"]["enum"]))

    def test_the_shipped_template_state_matches_its_own_schema(self) -> None:
        state = json.loads((REPO / ".agent/STATE.json").read_text(encoding="utf-8"))
        self.assertEqual([], sorted(set(state) - set(self.properties)),
                         "the template's STATE.json has fields the schema does not describe")
        for field in self.schema["required"]:
            self.assertIn(field, state)


class VerifySchemaTests(unittest.TestCase):
    def test_the_shipped_template_verify_matches_its_own_schema(self) -> None:
        cfg = json.loads((REPO / ".agent/VERIFY.json").read_text(encoding="utf-8"))
        properties = schema("verify")["properties"]
        self.assertEqual([], sorted(set(cfg) - set(properties)))
        self.assertEqual(sorted(("quick", "full", "smoke")),
                         sorted(properties["commands"]["properties"]))


class ProtocolDocTests(unittest.TestCase):
    """The normative reference names every command it claims to specify."""

    def test_every_subcommand_appears_in_the_protocol_document(self) -> None:
        text = (REPO / "docs/PROTOCOL.md").read_text(encoding="utf-8")
        parser = roach.parser()
        subcommands = set()
        for action in parser._subparsers._group_actions:
            subcommands.update(action.choices)
        undocumented = sorted(name for name in subcommands if name not in text)
        self.assertEqual([], undocumented, "docs/PROTOCOL.md does not mention these commands")


if __name__ == "__main__":
    unittest.main(verbosity=2)
