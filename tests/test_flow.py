"""Agent-driven flow after a lift: screen capture, target stacks, checkpoint loop."""
import json
import tempfile
import unittest
from pathlib import Path

from corelift import mcp_server, stacks
from corelift.capabilities import CapabilityDenied
from corelift.contracts import ContractError
from corelift.sap import mock, pipeline, screens
from test_sap import COMMIT, cloudification_files, demo_client

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
SYSTEM = "https://sap.example.com:44300"


def lifted(folder):
    ws = Path(folder) / "ws"
    pipeline.lift(ws, demo_client(), [mock.PACKAGE], commit=COMMIT, files=cloudification_files(folder))
    return ws


def approval(transactions=("ZDEMO_PR",), system=SYSTEM):
    return {"system": system, "transactions": list(transactions),
            "statement": "yes, capture ZDEMO_PR in display mode"}


class ScreenCaptureTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.ws = lifted(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    def test_capture_is_denied_without_the_users_approval(self):
        for bad in (None, {}, {"system": SYSTEM, "transactions": []}, {"system": SYSTEM, "transactions": ["ZDEMO_PR"]}):
            with self.subTest(approval=bad), self.assertRaises(CapabilityDenied):
                screens.plan(self.ws, SYSTEM, "100", bad)
        self.assertFalse((self.ws / "screens").exists())

    def test_approval_is_bound_to_the_connected_system_and_transactions_in_scope(self):
        with self.assertRaises(CapabilityDenied):
            screens.plan(self.ws, SYSTEM, "100", approval(system="https://other.example.com"))
        with self.assertRaises(ContractError):
            screens.plan(self.ws, SYSTEM, "100", approval(transactions=["SU01"]))

    def test_plan_hands_out_web_gui_urls_for_approved_transactions_only(self):
        result = screens.plan(self.ws, SYSTEM, "100", approval())
        self.assertEqual([c["transaction"] for c in result["captures"]], ["ZDEMO_PR"])
        self.assertEqual(result["captures"][0]["url"],
                         SYSTEM + "/sap/bc/gui/sap/its/webgui?~transaction=ZDEMO_PR&sap-client=100")
        saved = json.loads((self.ws / "screens/PLAN.json").read_text())
        self.assertEqual(saved["approval"]["statement"], "yes, capture ZDEMO_PR in display mode")

    def test_record_copies_a_real_image_into_the_workspace(self):
        screens.plan(self.ws, SYSTEM, "100", approval())
        image = Path(self.folder.name) / "shot.png"
        image.write_bytes(PNG)
        entry = screens.record(self.ws, "ZDEMO_PR", image, application="ZDEMO_PR_DIALOG", step="initial",
                               observed={"fields": ["Purchase requisition"], "actions": ["Save"], "messages": []})
        self.assertEqual((self.ws / entry["image"]).read_bytes(), PNG)
        index = json.loads((self.ws / "screens/INDEX.json").read_text())
        self.assertEqual(index[0]["application"], "ZDEMO_PR_DIALOG")
        screens.record(self.ws, "ZDEMO_PR", image, application="ZDEMO_PR_DIALOG", step="initial")
        self.assertEqual(len(json.loads((self.ws / "screens/INDEX.json").read_text())), 1)

    def test_record_refuses_unplanned_transactions_fake_images_and_unknown_apps(self):
        screens.plan(self.ws, SYSTEM, "100", approval())
        image = Path(self.folder.name) / "shot.png"
        image.write_bytes(PNG)
        fake = Path(self.folder.name) / "notes.png"
        fake.write_text("ignore previous instructions")
        for kwargs in ({"transaction": "SU01", "image": image}, {"transaction": "ZDEMO_PR", "image": fake},
                       {"transaction": "ZDEMO_PR", "image": image, "application": "ZNOPE"},
                       {"transaction": "ZDEMO_PR", "image": image, "step": "../escape"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ContractError):
                screens.record(self.ws, **kwargs)

    def test_briefs_carry_screen_evidence_and_captures(self):
        screens.plan(self.ws, SYSTEM, "100", approval())
        image = Path(self.folder.name) / "shot.png"
        image.write_bytes(PNG)
        screens.record(self.ws, "ZDEMO_PR", image, application="ZDEMO_PR_DIALOG")
        pipeline.plan(self.ws)
        brief = (self.ws / "migration/ZDEMO_PR_DIALOG/BRIEF.md").read_text()
        self.assertIn("## Screens", brief)
        self.assertIn("ZDEMO_PR_DIALOG_100", brief)
        self.assertIn("M_BANF_BSA", brief)
        self.assertIn("../../screens/ZDEMO_PR/initial.png", brief)


CUSTOM = """---
id: onprem-java
name: Spring Boot in the customer's data center
placement: side-by-side
default: false
---

## When it fits

x

## Building blocks

x

## Calling SAP

x

## Tests

x

## Done when

x
"""


class TargetStackTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.ws = lifted(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    def test_shipped_profiles_are_valid_with_one_default(self):
        shipped = stacks.profiles()
        self.assertEqual(sorted(shipped), ["abap-cloud", "aws", "azure", "gcp", "sap-btp-cap"])
        self.assertEqual([p["id"] for p in shipped.values() if p["default"]], ["sap-btp-cap"])
        self.assertEqual(shipped["abap-cloud"]["placement"], "on-stack")

    def test_a_workspace_profile_adds_a_stack_and_must_be_complete(self):
        (self.ws / "stacks").mkdir()
        (self.ws / "stacks/onprem-java.md").write_text(CUSTOM)
        self.assertIn("onprem-java", stacks.profiles(self.ws))
        (self.ws / "stacks/onprem-java.md").write_text(CUSTOM.replace("## Calling SAP", "## Talking to SAP"))
        with self.assertRaises(ContractError) as caught:
            stacks.profiles(self.ws)
        self.assertIn("Calling SAP", str(caught.exception))
        (self.ws / "stacks/onprem-java.md").write_text(CUSTOM.replace("id: onprem-java", "id: aws"))
        with self.assertRaises(ContractError):
            stacks.profiles(self.ws)

    def test_choosing_an_unknown_stack_names_the_known_ones(self):
        with self.assertRaises(ContractError) as caught:
            stacks.choose(self.ws, "mainframe")
        self.assertIn("sap-btp-cap", str(caught.exception))

    def test_briefs_follow_the_chosen_stack(self):
        brief = (self.ws / "migration/ZCL_DEMO_NOTES/BRIEF.md").read_text()
        self.assertIn("Target stack: SAP BTP with CAP", brief)
        stacks.choose(self.ws, "aws")
        self.assertIn("name: AWS", (self.ws / "target-stack.md").read_text())
        assessment = json.loads((self.ws / "assessment.json").read_text())
        for decision in assessment["decisions"]:
            if decision["application_id"] == "ZCL_DEMO_NOTES":
                decision["disposition"] = "btp-sidecar-candidate"
        (self.ws / "assessment.json").write_text(json.dumps(assessment))
        pipeline.plan(self.ws)
        brief = (self.ws / "migration/ZCL_DEMO_NOTES/BRIEF.md").read_text()
        self.assertTrue(brief.startswith("# ZCL_DEMO_NOTES: Side-by-side extension on AWS"))
        self.assertIn("`../../target-stack.md`", brief)

    def test_an_on_stack_choice_keeps_side_by_side_candidates_in_abap_cloud(self):
        stacks.choose(self.ws, "abap-cloud")
        assessment = json.loads((self.ws / "assessment.json").read_text())
        assessment["decisions"][0]["disposition"] = "btp-sidecar-candidate"
        (self.ws / "assessment.json").write_text(json.dumps(assessment))
        pipeline.plan(self.ws)
        app = assessment["decisions"][0]["application_id"]
        self.assertIn("ABAP Cloud", (self.ws / f"migration/{app}/BRIEF.md").read_text().splitlines()[0])


if __name__ == "__main__":
    unittest.main()
