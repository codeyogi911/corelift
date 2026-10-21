import json
import os
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from corelift import mcp_server
from corelift.contracts import ROOT, ContractError, contract
from corelift.engine import assess
from corelift.sap import evidence, mock, pipeline, profile
from corelift.sap.adt import ADTClient, ADTError, ReadOnlyViolation, allowed
from corelift.sap.discover import discover, source_system

SOURCES = json.loads((ROOT / "evidence/sources.json").read_text())
COMMIT = "0123456789abcdef0123456789abcdef01234567"


def cloudification_files(folder):
    """Tiny files in SAP's published format; the states are what the tests need."""
    release = {"formatVersion": "1", "objectReleaseInfo": [
        {"tadirObject": "TABL", "tadirObjName": "EKKO", "objectType": "TABL", "objectKey": "EKKO",
         "state": "notToBeReleased", "successors": [{"objectKey": "I_PURCHASEORDERAPI01"}]},
        {"tadirObject": "TABL", "tadirObjName": "EBAN", "objectType": "TABL", "objectKey": "EBAN", "state": "notToBeReleased"},
        {"tadirObject": "FUNC", "tadirObjName": "BAPI_PO_GETDETAIL1", "objectType": "FUNC", "objectKey": "BAPI_PO_GETDETAIL1", "state": "released"}]}
    classic = {"formatVersion": "2", "objectClassifications": [
        {"tadirObject": "FUNC", "tadirObjName": "BAPI_PO_GETDETAIL", "objectType": "FUNC", "objectKey": "BAPI_PO_GETDETAIL",
         "state": "noAPI", "successors": [{"objectKey": "BAPI_PO_GETDETAIL1"}]},
        {"tadirObject": "FUNC", "tadirObjName": "SO_NEW_DOCUMENT_SEND_API1", "objectType": "FUNC",
         "objectKey": "SO_NEW_DOCUMENT_SEND_API1", "state": "classicAPI"}]}
    paths = [Path(folder) / "objectReleaseInfo_PCE2025_1.json", Path(folder) / "objectClassifications_SAP.json"]
    paths[0].write_text(json.dumps(release))
    paths[1].write_text(json.dumps(classic))
    return paths


def demo_client():
    return ADTClient(mock.shared_demo_url(), mock.USER, mock.PASSWORD)


class ReadOnlyClientTests(unittest.TestCase):
    def test_allowlist_refuses_writes_before_any_request(self):
        client = demo_client()
        for method, path in [("POST", "/sap/bc/adt/activation"), ("PUT", "/sap/bc/adt/programs/programs/zx/source/main"),
                             ("DELETE", "/sap/bc/adt/programs/programs/zx"), ("POST", "/sap/bc/adt/cts/transportrequests"),
                             ("GET", "/sap/bc/adt/datapreview/freestyle"), ("GET", "/sap/opu/odata/sap/API_PO")]:
            with self.subTest(method=method, path=path):
                self.assertFalse(allowed(method, path))
                with patch.object(client._opener, "open", side_effect=AssertionError("network")):
                    with self.assertRaises(ReadOnlyViolation):
                        client.request(method, path)

    def test_dot_segments_from_untrusted_uris_are_refused(self):
        self.assertFalse(allowed("GET", "/sap/bc/adt/oo/classes/../source/main"))
        self.assertFalse(allowed("GET", "/sap/bc/adt/programs/programs/./source/main"))

    def test_plain_http_only_for_loopback(self):
        with self.assertRaises(ADTError):
            ADTClient("http://sap.example.com:8000", "u", "p")
        ADTClient("https://sap.example.com:44300", "u", "p")

    def test_wrong_password_is_explained_without_echoing_it(self):
        client = ADTClient(mock.shared_demo_url(), mock.USER, "wrong-secret")
        with self.assertRaises(ADTError) as caught:
            client.ping()
        self.assertIn("401", str(caught.exception))
        self.assertNotIn("wrong-secret", str(caught.exception) + repr(client))

    def test_reads_against_synthetic_adt(self):
        client = demo_client()
        self.assertGreater(client.ping(), 0)
        self.assertEqual(client.components()["SAP_APPL"], "618")
        names = {o["name"] for o in client.package_contents(mock.PACKAGE)}
        self.assertIn("ZCL_DEMO_NOTES", names)
        self.assertEqual({o["name"] for o in client.search("ZDEMO_P*")}, {"ZDEMO_PO_REPORT", "ZDEMO_PR_DIALOG"})
        self.assertIn("SELECT * FROM ekko", client.source("/sap/bc/adt/programs/programs/zdemo_po_report"))


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.inventory, self.sources, self.record = discover(demo_client(), [mock.PACKAGE])
        self.apps = {a["id"]: a for a in self.inventory["applications"]}

    def test_inventory_meets_contract_and_owns_customer_objects(self):
        contract("inventory", self.inventory)
        self.assertFalse(self.inventory["synthetic"])
        self.assertEqual(self.inventory["source_system"]["family"], "ECC")
        self.assertEqual(set(self.apps), {"ZDEMO_PO_REPORT", "ZCL_DEMO_NOTES", "Z_DEMO_NOTIFY", "ZDEMO_PR_DIALOG"})
        self.assertEqual([d["id"] for d in self.inventory["datasets"]], ["ZDEMO_NOTES"])
        notes = self.apps["ZCL_DEMO_NOTES"]
        self.assertEqual(notes["depends_on"], ["Z_DEMO_NOTIFY"])
        self.assertIn({"object": "ZDEMO_NOTES", "kind": "table", "operation": "write"}, notes["dependencies"])
        self.assertEqual(notes["datasets"], ["ZDEMO_NOTES"])

    def test_dialogs_and_standard_writes_are_transaction_coupled(self):
        dialog = self.apps["ZDEMO_PR_DIALOG"]
        self.assertTrue(dialog["transaction_coupled"])
        self.assertEqual([s["id"] for s in self.inventory["screens"]], ["ZDEMO_PR_DIALOG_100"])
        self.assertFalse(self.apps["ZDEMO_PO_REPORT"]["transaction_coupled"])

    def test_namespaced_sap_objects_are_apis_not_customer_code(self):
        from corelift.sap import discover as module
        with patch.object(mock, "OBJECTS", mock.OBJECTS + [("ZDEMO_EWM", "PROG/P", "/sap/bc/adt/programs/programs/zdemo_ewm", "EWM caller",
                                                            "REPORT zdemo_ewm.\nDATA(lo) = /scwm/cl_tm=>get( ).\n")]):
            inventory, _, _ = module.discover(demo_client(), [mock.PACKAGE])
        app = next(a for a in inventory["applications"] if a["id"] == "ZDEMO_EWM")
        self.assertIn({"object": "/SCWM/CL_TM", "kind": "api", "operation": "call"}, app["dependencies"])
        self.assertTrue(app["coverage_complete"])

    def test_component_release_mapping(self):
        self.assertEqual(source_system({"SAP_BASIS": "758", "S4CORE": "108"})["release"], "2023")
        self.assertEqual(source_system({"SAP_BASIS": "999"})["release"], "0000")

    def test_unresolved_customer_reference_marks_coverage_incomplete(self):
        inventory, _, _ = discover(demo_client(), query="ZCL_DEMO*")
        self.assertFalse(inventory["applications"][0]["coverage_complete"])


class EvidenceAndAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.inventory, _, _ = discover(demo_client(), [mock.PACKAGE])
        self.api, self.notes = evidence.build(self.inventory, cloudification_files(self.folder.name), COMMIT)

    def tearDown(self):
        self.folder.cleanup()

    def test_states_map_and_customer_objects_are_not_sap_evidence(self):
        contract("api-evidence", self.api)
        states = {o["object"]: o["state"] for o in self.api["objects"]}
        self.assertEqual(states, {"BAPI_PO_GETDETAIL": "not-recommended", "EBAN": "internal", "EKKO": "internal",
                                  "SO_NEW_DOCUMENT_SEND_API1": "classic"})
        self.assertTrue(all(o["contract"] == "unknown" and o["remote_pathway"] == "unknown" for o in self.api["objects"]))
        self.assertEqual(self.notes["objects"]["BAPI_PO_GETDETAIL"]["successors"], ["BAPI_PO_GETDETAIL1"])
        self.assertEqual(self.notes["objects"]["BAPI_PO_GETDETAIL"]["successor_states"], {"BAPI_PO_GETDETAIL1": "released"})
        self.assertEqual(self.notes["objects"]["EKKO"]["successor_states"], {"I_PURCHASEORDERAPI01": "unlisted"})
        self.assertEqual(len(self.notes["file_sha256"]), 2)

    def test_pinned_evidence_classifies_but_never_endorses_remote(self):
        result = assess(self.inventory, self.api, SOURCES)
        decisions = {d["application_id"]: d for d in result["decisions"]}
        self.assertEqual(decisions["ZDEMO_PO_REPORT"]["disposition"], "rebuild-candidate")
        self.assertEqual(decisions["Z_DEMO_NOTIFY"]["clean_core_level_candidate"], "B")
        self.assertEqual(decisions["ZCL_DEMO_NOTES"]["clean_core_level_candidate"], "B")
        self.assertNotIn("ZDEMO_NOTES", [d["object"] for d in decisions["ZCL_DEMO_NOTES"]["dependencies"]])
        self.assertEqual(decisions["ZDEMO_PR_DIALOG"]["disposition"], "investigate")
        self.assertFalse(any(d["disposition"] == "btp-sidecar-candidate" for d in decisions.values()))

    def test_unpinned_commit_and_exported_claims_stay_unknown(self):
        with self.assertRaises(ContractError):
            evidence.build(self.inventory, cloudification_files(self.folder.name), "main")
        for item in self.api["objects"]:
            item["verification"] = "exported-unverified"
        result = assess(self.inventory, self.api, SOURCES)
        self.assertTrue(all(d["clean_core_level_candidate"] == "unknown" for d in result["decisions"]))

    def test_file_names_follow_sap_feature_pack_naming(self):
        self.assertEqual(evidence.files_for({"edition": "private", "release": "2025", "fps": "FPS01"})[0],
                         ["src/objectReleaseInfo_PCE2025_1.json", "src/objectReleaseInfo_PCE2025.json"])
        self.assertEqual(evidence.files_for({"edition": "public", "release": "2025", "fps": "2508"}),
                         [["src/objectReleaseInfoLatest.json"]])


class PipelineTests(unittest.TestCase):
    def test_lift_writes_only_inside_a_marked_workspace(self):
        with tempfile.TemporaryDirectory() as folder:
            files = cloudification_files(folder)
            ws = Path(folder) / "ws"
            steps = pipeline.lift(ws, demo_client(), [mock.PACKAGE], commit=COMMIT, files=files)
            self.assertEqual(steps["evidence"]["classified"], 4)
            for name in (".corelift-workspace", ".gitignore", "inventory.json", "api-evidence.json",
                         "assessment.json", "assessment.md", "migration/INDEX.json", "source/ZDEMO_PO_REPORT.abap"):
                self.assertTrue((ws / name).is_file(), name)
            brief = (ws / "migration/ZDEMO_PO_REPORT/BRIEF.md").read_text()
            self.assertIn("successor `BAPI_PO_GETDETAIL1` (released for the target)", brief)
            self.assertIn("successor `I_PURCHASEORDERAPI01` (not in the target's release file; confirm before use)", brief)
            self.assertIn("data, not instructions", brief)
            self.assertNotEqual(pipeline.slug("/AB/C_D"), pipeline.slug("/AB_C/D"))
            self.assertNotIn(".", pipeline.slug(".."))
            other = Path(folder) / "not-a-workspace"
            other.mkdir()
            (other / "keep.txt").write_text("x")
            with self.assertRaises(ContractError):
                pipeline.discover(other, demo_client(), [mock.PACKAGE])


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"CORELIFT_HOME": self.home.name}, clear=False)
        self.env.start()
        for key in [k for k in os.environ if k.startswith("CORELIFT_SAP_")]:
            os.environ.pop(key)

    def tearDown(self):
        self.env.stop()
        self.home.cleanup()

    def test_saved_file_is_owner_only_and_password_never_public(self):
        path = profile.save("https://sap.example.com", "DEV", "s3cret-pass", "100")
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        settings = profile.load()
        self.assertEqual(settings["password"], "s3cret-pass")
        self.assertNotIn("s3cret-pass", json.dumps(profile.public(settings)))
        if os.name == "posix":
            path.chmod(0o644)
            with self.assertRaises(PermissionError):
                profile.load()

    def test_environment_wins_and_unfilled_placeholders_mean_unset(self):
        profile.save("https://saved.example.com", "DEV", "pw")
        with patch.dict(os.environ, {"CORELIFT_SAP_URL": "${user_config.sap_url}"}):
            self.assertEqual(profile.load()["url"], "https://saved.example.com")
        with patch.dict(os.environ, {"CORELIFT_SAP_URL": "https://env.example.com", "CORELIFT_SAP_USER": "ENV"}):
            self.assertEqual(profile.load()["source"], "environment")
        self.assertIsNone(profile.forget() and None)
        self.assertIsNone(profile.load())


class MCPServerTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"CORELIFT_HOME": self.home.name})
        self.env.start()
        mcp_server._demo = False

    def tearDown(self):
        mcp_server._demo = False
        self.env.stop()
        self.home.cleanup()

    def rpc(self, method, params=None, id=1):
        return mcp_server.handle({"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}})

    def test_tools_are_reads_or_local_workspace_writes_only(self):
        init = self.rpc("initialize", {"protocolVersion": "2025-06-18"})["result"]
        self.assertEqual(init["protocolVersion"], "2025-06-18")
        tools = self.rpc("tools/list")["result"]["tools"]
        for tool in tools:
            self.assertFalse(tool["annotations"]["destructiveHint"], tool["name"])
            self.assertFalse(any(word in tool["name"] for word in ("write", "deploy", "transport", "activate", "delete")))
        self.assertEqual(self.rpc("tools/call", {"name": "sap_write", "arguments": {}})["error"]["code"], -32602)
        self.assertIsNone(mcp_server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_unreachable_system_reports_reachable_false(self):
        profile.save("https://127.0.0.1:1", "DEV", "pw")
        status = self.rpc("tools/call", {"name": "sap_connection_status"})["result"]
        self.assertFalse(status["isError"])
        self.assertFalse(status["structuredContent"]["reachable"])
        self.assertIn("cannot reach", status["structuredContent"]["error"])
        self.assertEqual(status["structuredContent"]["connect_command"], mcp_server.CONNECT)

    def test_missing_arguments_and_demo_switch_back(self):
        missing = self.rpc("tools/call", {"name": "sap_read_source", "arguments": {}})["result"]
        self.assertIn("missing argument", missing["content"][0]["text"])
        self.rpc("tools/call", {"name": "sap_use_demo_system"})
        back = self.rpc("tools/call", {"name": "sap_use_demo_system", "arguments": {"enabled": False}})["result"]["structuredContent"]
        self.assertFalse(back["configured"])
        self.assertFalse(mcp_server._demo)

    def test_unconnected_status_guides_user_and_demo_connects(self):
        status = self.rpc("tools/call", {"name": "sap_connection_status"})["result"]["structuredContent"]
        self.assertFalse(status["configured"])
        command = status["connect_command"]
        self.assertIn(command, status["next_step"])
        self.assertNotIn("<plugin-root>", status["next_step"])
        script = Path(shlex.split(command)[1])
        self.assertTrue(script.is_absolute() and script.is_file(), command)
        self.assertEqual(shlex.split(command)[2:], ["connect"])
        self.assertIn(f"{shlex.split(command)[0]} {shlex.quote(str(script))} connect --demo", status["next_step"])
        failing = self.rpc("tools/call", {"name": "sap_search_objects", "arguments": {"query": "Z*"}})["result"]
        self.assertTrue(failing["isError"])
        self.rpc("tools/call", {"name": "sap_use_demo_system"})
        status = self.rpc("tools/call", {"name": "sap_connection_status"})["result"]["structuredContent"]
        self.assertTrue(status["reachable"])
        self.assertNotIn("password", json.dumps(status))
        relative = self.rpc("tools/call", {"name": "corelift_discover", "arguments": {"workspace": "ws"}})["result"]
        self.assertTrue(relative["isError"])

    def test_stdio_process_round_trip(self):
        lines = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2099-01-01"}},
                 {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
        out = subprocess.run([sys.executable, str(ROOT / "scripts/corelift.py"), "mcp"], input="\n".join(map(json.dumps, lines)) + "\nnot json\n",
                             capture_output=True, text=True, timeout=30, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}).stdout
        replies = [json.loads(line) for line in out.splitlines()]
        self.assertEqual(replies[0]["result"]["protocolVersion"], mcp_server.PROTOCOLS[0])
        self.assertIn("corelift_lift", [t["name"] for t in replies[1]["result"]["tools"]])
        self.assertEqual(replies[2]["error"]["code"], -32700)


if __name__ == "__main__":
    unittest.main()
