import json
import subprocess
import sys
import tempfile
import unittest
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_mofu(*args, cwd=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, "-m", "mofu", *args],
        cwd=str(cwd or ROOT),
        env=env,
        text=True,
        capture_output=True,
    )


class MofuCliTests(unittest.TestCase):
    def test_version_and_init_status(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            self.assertEqual(run_mofu("--version", cwd=cwd).stdout.strip(), "0.1.0")
            init = run_mofu("init", "--json", cwd=cwd)
            self.assertEqual(init.returncode, 0, init.stderr)
            self.assertTrue((cwd / ".mofumofu/config.toml").exists())
            status = run_mofu("status", "--json", cwd=cwd)
            data = json.loads(status.stdout)
            self.assertEqual(data["activeSpec"], "none")
            self.assertEqual(data["provider"], "local")

    def test_config_project_precedence_and_secret_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            self.assertEqual(run_mofu("init", cwd=cwd).returncode, 0)
            self.assertEqual(run_mofu("config", "set", "model.default_model", "abc", cwd=cwd).returncode, 0)
            got = run_mofu("config", "get", "model.default_model", cwd=cwd)
            self.assertEqual(got.stdout.strip(), "abc")
            fake_secret = "sk-" + "a" * 20
            bad = run_mofu("config", "set", "model.default_model", fake_secret, cwd=cwd)
            self.assertNotEqual(bad.returncode, 0)

    def test_machine_config_shared_across_projects(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as p1, tempfile.TemporaryDirectory() as p2:
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT)
            env["XDG_CONFIG_HOME"] = str(Path(home) / "config")

            def run_with_home(*args, cwd):
                return subprocess.run(
                    [sys.executable, "-m", "mofu", *args],
                    cwd=str(cwd),
                    env=env,
                    text=True,
                    capture_output=True,
                )

            self.assertEqual(run_with_home("config", "set", "model.default_provider", "hosted-strong", "--global", cwd=Path(p1)).returncode, 0)
            self.assertEqual(run_with_home("config", "set", "model.default_model", "shared-model", "--global", cwd=Path(p1)).returncode, 0)

            first = json.loads(run_with_home("config", "explain", "--json", cwd=Path(p1)).stdout)
            second = json.loads(run_with_home("config", "explain", "--json", cwd=Path(p2)).stdout)

            self.assertEqual(first["effective"]["model"]["default_provider"], "hosted-strong")
            self.assertEqual(second["effective"]["model"]["default_provider"], "hosted-strong")
            self.assertEqual(second["effective"]["model"]["default_model"], "shared-model")
            self.assertIn("machine", {source["kind"] for source in second["sources"]})

    def test_spec_trace_context_and_gate(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            run_mofu("init", cwd=cwd)
            self.assertEqual(run_mofu("spec", "new", "demo", "--title", "Demo", cwd=cwd).returncode, 0)
            self.assertEqual(run_mofu("spec", "active", "demo", cwd=cwd).returncode, 0)
            for stage in ("requirements", "design", "tasks"):
                self.assertEqual(run_mofu("spec", "approve", "demo", "--stage", stage, cwd=cwd).returncode, 0)
            (cwd / "implemented.py").write_text("def demo():\n    return 1\n")
            self.assertEqual(run_mofu("trace", "update", "--from", "requirement:REQ-1", "--to", "implemented.py", "--relation", "implemented_by", "--status", "PASS", cwd=cwd).returncode, 0)
            trace_path = cwd / ".mofumofu/specs/demo/trace-map.json"
            trace = json.loads(trace_path.read_text())
            trace["links"][0]["evidence"] = ["ev_test"]
            trace_path.write_text(json.dumps(trace))
            self.assertEqual(run_mofu("audit", "properties", "--spec", "demo", cwd=cwd).returncode, 0)
            self.assertEqual(run_mofu("context", "pack", "--spec", "demo", "--goal", "test", cwd=cwd).returncode, 0)
            gate = run_mofu("gate", "status", "--spec", "demo", "--json", cwd=cwd)
            self.assertEqual(gate.returncode, 0, gate.stderr)
            self.assertEqual(json.loads(gate.stdout)["status"], "PASS")

    def test_gate_blocks_high_validation_findings(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            run_mofu("init", cwd=cwd)
            run_mofu("spec", "new", "demo", cwd=cwd)
            run_mofu("spec", "active", "demo", cwd=cwd)
            for stage in ("requirements", "design", "tasks"):
                run_mofu("spec", "approve", "demo", "--stage", stage, cwd=cwd)
            (cwd / "x.py").write_text("def x():\n    return 1\n")
            run_mofu("trace", "update", "--from", "requirement:REQ-1", "--to", "x.py", "--relation", "implemented_by", "--status", "PASS", cwd=cwd)
            trace_path = cwd / ".mofumofu/specs/demo/trace-map.json"
            trace = json.loads(trace_path.read_text())
            trace["links"][0]["evidence"] = ["ev_test"]
            trace_path.write_text(json.dumps(trace))
            run_mofu("audit", "properties", "--spec", "demo", cwd=cwd)
            (cwd / "fail.txt").write_text("FAILED\n")
            run_mofu("validation", "normalize", "unit-test", "--raw-path", "fail.txt", "--spec", "demo", cwd=cwd)
            gate = json.loads(run_mofu("gate", "status", "--spec", "demo", "--json", cwd=cwd).stdout)
            self.assertEqual(gate["status"], "PARTIAL")
            self.assertTrue(any("high/critical findings" in b for b in gate["blockers"]))

    def test_provider_probe_and_analysis(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            run_mofu("init", cwd=cwd)
            probe = run_mofu("provider", "probe", "local", "--json", cwd=cwd)
            self.assertFalse(json.loads(probe.stdout)["capabilities"]["toolCalling"])
            (cwd / "x.py").write_text("class Thing:\n    pass\n")
            syms = run_mofu("analyze", "symbols", "--json", cwd=cwd)
            self.assertEqual(json.loads(syms.stdout)[0]["name"], "Thing")

    def test_provider_probe_openai_compatible_local_and_hosted_fixtures(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/v1/models":
                    body = b'{"object":"list","data":[{"id":"fixture-model"}]}'
                    self.send_response(200)
                    self.send_header("content-type", "application/json")
                    self.send_header("content-length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *_):
                return

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_address[1]}/v1"
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT)
            env["MOFUMOFU_LOCAL_BASE_URL"] = base_url
            env["MOFUMOFU_HOSTED_BASE_URL"] = base_url

            def probe(provider):
                return subprocess.run(
                    [sys.executable, "-m", "mofu", "provider", "probe", provider, "--json"],
                    cwd=td,
                    env=env,
                    text=True,
                    capture_output=True,
                )

            local = json.loads(probe("local").stdout)
            hosted = json.loads(probe("hosted-strong").stdout)
            self.assertTrue(local["probe"]["reachable"])
            self.assertTrue(hosted["probe"]["reachable"])
            self.assertEqual(local["model"], "fixture-model")
            self.assertEqual(hosted["model"], "fixture-model")
            self.assertFalse(local["capabilities"]["toolCalling"])
            self.assertTrue(hosted["capabilities"]["toolCalling"])
        server.shutdown()
        server.server_close()

    def test_pi_wrapper_inventory_is_real_and_renamed(self):
        wrapped = run_mofu("wrapper", "status", "--json", cwd=ROOT)
        self.assertEqual(wrapped.returncode, 0, wrapped.stderr)
        data = json.loads(wrapped.stdout)
        self.assertTrue(data["wrapped"])
        self.assertTrue(data["sourceAvailable"])
        self.assertEqual(data["packageName"], "@mofumofu/coding-agent")
        self.assertEqual(data["appName"], "mofu")
        self.assertEqual(data["configDir"], ".mofumofu")
        self.assertIn("mofu-agent", data["bin"])
        self.assertTrue((ROOT / "vendor/pi/packages/coding-agent/dist/modes/interactive/theme/mofumofu.json").exists())
        interactive_source = (ROOT / "vendor/pi/packages/coding-agent/src/modes/interactive/interactive-mode.ts").read_text()
        self.assertIn("MofumofuStartupDashboard", interactive_source)
        self.assertIn("/\\\\_/\\\\", interactive_source)

        help_text = run_mofu("agent", "--help", cwd=ROOT)
        self.assertEqual(help_text.returncode, 0, help_text.stderr)
        rendered_help = help_text.stdout + help_text.stderr
        self.assertIn("spec-led coding agent for traceable implementation", rendered_help)
        self.assertIn("built-ins include mofumofu", rendered_help)
        self.assertNotIn("AI coding assistant with read, bash, edit, write tools", rendered_help)

    def test_agent_run_session_and_mcp_tool_call(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            run_mofu("init", cwd=cwd)
            run_mofu("spec", "new", "demo", cwd=cwd)
            run_mofu("spec", "active", "demo", cwd=cwd)
            for stage in ("requirements", "design", "tasks"):
                run_mofu("spec", "approve", "demo", "--stage", stage, cwd=cwd)
            (cwd / "x.py").write_text("def ok():\n    return True\n")
            run_mofu("trace", "update", "--from", "requirement:REQ-1", "--to", "x.py", "--relation", "implemented_by", "--status", "PASS", cwd=cwd)
            trace_path = cwd / ".mofumofu/specs/demo/trace-map.json"
            trace = json.loads(trace_path.read_text())
            trace["links"][0]["evidence"] = ["ev_test"]
            trace_path.write_text(json.dumps(trace))
            run = run_mofu("run", "--spec", "demo", "--goal", "prove baseline", "--json", cwd=cwd)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["stopReason"], "done")

            proc = subprocess.run(
                [sys.executable, "-m", "mofu", "mcp", "serve", "--stdio"],
                input='{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"mofumofu.spec.discover","arguments":{}}}\n',
                cwd=str(cwd),
                env={**os.environ, "PYTHONPATH": str(ROOT)},
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("mofumofu.spec.discover", proc.stdout)
            self.assertIn("mofumofu.validation.normalize", proc.stdout)

    def test_tool_runtime_validates_policy_and_logs(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            run_mofu("init", cwd=cwd)

            missing = subprocess.run(
                [sys.executable, "-m", "mofu", "mcp", "serve", "--stdio"],
                input='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"mofumofu.trace.get","arguments":{}}}\n',
                cwd=str(cwd),
                env={**os.environ, "PYTHONPATH": str(ROOT)},
                text=True,
                capture_output=True,
            )
            self.assertIn("INVALID_INPUT", missing.stdout)

            denied = subprocess.run(
                [sys.executable, "-m", "mofu", "mcp", "serve", "--stdio"],
                input='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"mofumofu.spec.create","arguments":{"specId":"danger","destructive":true}}}\n',
                cwd=str(cwd),
                env={**os.environ, "PYTHONPATH": str(ROOT)},
                text=True,
                capture_output=True,
            )
            self.assertIn("TOOL_DENIED", denied.stdout)

    def test_validation_normalize_cli_records_pass_and_fail(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            run_mofu("init", cwd=cwd)
            run_mofu("spec", "new", "demo", cwd=cwd)
            run_mofu("spec", "active", "demo", cwd=cwd)
            (cwd / "pass.txt").write_text("OK\n")
            passed = run_mofu("validation", "normalize", "npm-test", "--raw-path", "pass.txt", "--spec", "demo", "--json", cwd=cwd)
            self.assertEqual(json.loads(passed.stdout)["status"], "PASS")
            (cwd / "fail.txt").write_text("FAILED one test\n")
            failed = run_mofu("validation", "normalize", "npm-test", "--raw-path", "fail.txt", "--spec", "demo", "--json", cwd=cwd)
            self.assertEqual(json.loads(failed.stdout)["status"], "FAIL")
            findings = (cwd / ".mofumofu/specs/demo/findings.jsonl").read_text()
            self.assertIn("npm-test failed", findings)

    def test_generated_security_e2e_and_path_containment(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            cwd = Path(td)
            run_mofu("init", cwd=cwd)
            run_mofu("spec", "new", "demo", cwd=cwd)
            run_mofu("spec", "active", "demo", cwd=cwd)
            outside_file = Path(outside) / "fail.txt"
            outside_file.write_text("FAILED outside\n")

            escaped = run_mofu("validation", "normalize", "escape", "--raw-path", str(outside_file), "--spec", "demo", cwd=cwd)
            self.assertNotEqual(escaped.returncode, 0)
            self.assertIn("rawPath must stay inside cwd", escaped.stderr)

            result = json.loads(run_mofu("security", "generated-e2e", "--spec", "demo", "--json", cwd=cwd).stdout)
            self.assertEqual(result["status"], "PASS")
            self.assertTrue((cwd / ".mofumofu/security/generated-e2e.json").exists())
            self.assertIn("GEN-SR-002", {check["id"] for check in result["checks"]})

    def test_session_resume_stop_reasons_ledgers_and_context_trace(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            run_mofu("init", cwd=cwd)
            run_mofu("spec", "new", "demo", cwd=cwd)
            run_mofu("spec", "active", "demo", cwd=cwd)
            for stage in ("requirements", "design", "tasks"):
                run_mofu("spec", "approve", "demo", "--stage", stage, cwd=cwd)
            (cwd / "requirements_marker.py").write_text("def marker():\n    return True\n")
            run_mofu("trace", "update", "--from", "requirement:REQ-DEMO --bad", "--to", "requirements_marker.py", "--relation", "implemented_by", cwd=cwd)
            # Repair malformed trace created by CLI split test constraints with a direct valid entry.
            trace_path = cwd / ".mofumofu/specs/demo/trace-map.json"
            trace = json.loads(trace_path.read_text())
            trace["links"] = [{
                "id": "trace_demo",
                "from": {"kind": "requirement", "id": "REQ-DEMO"},
                "to": {"kind": "file", "path": "requirements_marker.py"},
                "relation": "implemented_by",
                "status": "PASS",
                "rationale": "fixture",
                "evidence": ["ev_test"]
            }]
            trace_path.write_text(json.dumps(trace))
            (cwd / ".mofumofu/specs/demo/requirements.md").write_text("# Demo\n\nREQ-DEMO\n")
            run_mofu("audit", "properties", "--spec", "demo", cwd=cwd)
            run = json.loads(run_mofu("run", "--spec", "demo", "--goal", "resume me", "--json", cwd=cwd).stdout)
            resumed = json.loads(run_mofu("session", "resume", run["sessionId"], "--json", cwd=cwd).stdout)
            self.assertEqual(resumed["status"], "PASS")
            for reason in ("done", "needs_approval", "blocked", "budget_exceeded", "context_limit", "tool_denied", "validation_failed", "error"):
                got = json.loads(run_mofu("session", "stop-reason", reason, "--json", cwd=cwd).stdout)
                self.assertEqual(got["stopReason"], reason)
            pack = json.loads(run_mofu("context", "pack", "--spec", "demo", "--goal", "ctx", "--json", cwd=cwd).stdout)
            self.assertIn("requirements_marker.py", {item["path"] for item in pack["included"]})
            self.assertEqual(json.loads(run_mofu("compact", "validate", "--json", cwd=cwd).stdout)["status"], "PASS")
            self.assertEqual(json.loads(run_mofu("fact", "record", "models change", "--source", "fixture", "--json", cwd=cwd).stdout)["status"], "current")
            self.assertEqual(json.loads(run_mofu("fact", "status", "--json", cwd=cwd).stdout)["status"], "PASS")
            self.assertEqual(json.loads(run_mofu("memory", "decide", "use pi runtime", "--rationale", "docs require it", "--json", cwd=cwd).stdout)["scope"], "project")
            self.assertTrue(json.loads(run_mofu("worktree", "status", "--json", cwd=cwd).stdout)["agent"] is not None)

    def test_audit_ingest_review_and_challenge_distinguish_verdicts(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            run_mofu("init", cwd=cwd)
            run_mofu("spec", "new", "demo", cwd=cwd)
            payload = json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "mofumofu.audit.ingest",
                    "arguments": {
                        "specId": "demo",
                        "findings": [
                            {"source": "fixture", "kind": "audit", "severity": "high", "title": "real bug", "status": "open"},
                            {"source": "fixture", "kind": "audit", "severity": "low", "title": "false positive", "status": "false_positive"},
                            {"source": "fixture", "kind": "audit", "severity": "medium", "title": "unresolved", "status": "unresolved"}
                        ]
                    }
                }
            })
            proc = subprocess.run(
                [sys.executable, "-m", "mofu", "mcp", "serve", "--stdio"],
                input=payload + "\n",
                cwd=str(cwd),
                env={**os.environ, "PYTHONPATH": str(ROOT)},
                text=True,
                capture_output=True,
            )
            self.assertIn('\\"ingested\\": 3', proc.stdout)
            findings = (cwd / ".mofumofu/specs/demo/findings.jsonl").read_text()
            self.assertIn("real bug", findings)
            self.assertIn("false_positive", findings)
            self.assertIn("unresolved", findings)

    def test_artifact_fetch_diff_trace_and_analysis_graph(self):
        class Handler(BaseHTTPRequestHandler):
            counter = 0
            def do_GET(self):
                Handler.counter += 1
                version = Handler.counter
                body = json.dumps({"openapi": "3.1.0", "info": {"title": "Fixture", "version": str(version)}, "paths": {}}).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *_):
                return

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}/openapi.json"
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            run_mofu("init", cwd=cwd)
            run_mofu("spec", "new", "demo", cwd=cwd)
            first = json.loads(run_mofu("artifact", "fetch", url, "--kind", "openapi", "--spec", "demo", "--json", cwd=cwd).stdout)
            second = json.loads(run_mofu("artifact", "fetch", url, "--kind", "openapi", "--spec", "demo", "--json", cwd=cwd).stdout)
            diff = json.loads(run_mofu("artifact", "diff", second["artifactId"], "--against", first["artifactId"], "--json", cwd=cwd).stdout)
            self.assertTrue(diff["changed"])
            (cwd / "a.py").write_text("import os\ndef alpha():\n    return os.getcwd()\n")
            graph = json.loads(run_mofu("analyze", "graph", "--json", cwd=cwd).stdout)
            self.assertEqual(graph["status"], "PASS")
            self.assertTrue(graph["nodes"])
            self.assertTrue(graph["edges"])
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    unittest.main()
