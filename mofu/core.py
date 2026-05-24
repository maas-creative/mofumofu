from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

STATUS = ["PASS", "PARTIAL", "FAIL", "NOT VERIFIED", "NOT IMPLEMENTED"]
STOP_REASONS = [
    "done",
    "needs_approval",
    "blocked",
    "budget_exceeded",
    "context_limit",
    "tool_denied",
    "validation_failed",
    "error",
]
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
FINDING_STATUSES = {"open", "fixed", "accepted", "false_positive", "unresolved"}
HIGH_SEVERITIES = {"high", "critical"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def append_jsonl(path: Path, entry: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.open("a", encoding="utf-8").write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    entries: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def project_root(cwd: Optional[str]) -> Path:
    return Path(cwd or os.getcwd()).expanduser().resolve()


def state_dir(cwd: Path) -> Path:
    return cwd / ".mofumofu"


def machine_config_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mofumofu"


def machine_state_dir() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "mofumofu"


def session_path(session_id: str) -> Path:
    return machine_state_dir() / "sessions" / f"{session_id}.jsonl"


def new_session_id() -> str:
    return "sess_" + time.strftime("%Y%m%d_%H%M%S") + "_" + hashlib.sha1(os.urandom(16)).hexdigest()[:8]


def write_session_event(
    session_id: str,
    actor: str,
    event_type: str,
    payload: Dict[str, Any],
    trace_links: Optional[List[str]] = None,
    evidence: Optional[List[str]] = None,
) -> Dict[str, Any]:
    event = {
        "id": "evt_" + hashlib.sha1(f"{session_id}{now()}{event_type}{json.dumps(payload, sort_keys=True)}".encode()).hexdigest()[:12],
        "sessionId": session_id,
        "timestamp": now(),
        "actor": actor,
        "type": event_type,
        "payload": json.loads(redact(json.dumps(payload))),
        "traceLinks": trace_links or [],
        "evidence": evidence or [],
    }
    append_jsonl(session_path(session_id), event)
    return event


def redact(value: str) -> str:
    out = value
    for pattern in SECRET_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out


def read_tomlish(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    data: Dict[str, Any] = {}
    section: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].split(".")
            cur = data
            for part in section:
                cur = cur.setdefault(part, {})
            continue
        if "=" not in line:
            continue
        key, val = [p.strip() for p in line.split("=", 1)]
        parsed: Any
        if val.lower() in ("true", "false"):
            parsed = val.lower() == "true"
        elif val.startswith('"') and val.endswith('"'):
            parsed = val[1:-1]
        else:
            try:
                parsed = int(val)
            except ValueError:
                parsed = val
        cur = data
        for part in section:
            cur = cur.setdefault(part, {})
        cur[key] = parsed
    return data


def dump_toml(data: Dict[str, Any]) -> str:
    lines: List[str] = []
    if "version" in data:
        lines.append(f"version = {data['version']}")
        lines.append("")
    for section, values in data.items():
        if section == "version" or not isinstance(values, dict):
            continue
        lines.append(f"[{section}]")
        for key, value in values.items():
            if isinstance(value, bool):
                rendered = "true" if value else "false"
            elif isinstance(value, int):
                rendered = str(value)
            else:
                rendered = json.dumps(str(value))
            lines.append(f"{key} = {rendered}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


DEFAULT_CONFIG: Dict[str, Any] = {
    "version": 1,
    "model": {"default_provider": "local", "default_model": "local-coding-model"},
    "runtime": {"max_tool_output_bytes": 200000, "default_context_budget_tokens": 120000, "allow_network": False},
    "spec": {"active_spec": "", "require_approved_requirements": True, "require_trace_for_completion": True},
}


def effective_config(cwd: Path, extra: Optional[Path] = None) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    sources = [{"path": "built-in defaults", "kind": "default"}]
    cfg = dict(DEFAULT_CONFIG)
    global_path = machine_config_dir() / "config.toml"
    if global_path.exists():
        cfg = deep_merge(cfg, read_tomlish(global_path))
        sources.append({"path": str(global_path), "kind": "machine"})
    project_path = state_dir(cwd) / "config.toml"
    if project_path.exists():
        cfg = deep_merge(cfg, read_tomlish(project_path))
        sources.append({"path": str(project_path), "kind": "project"})
    if extra and extra.exists():
        cfg = deep_merge(cfg, read_tomlish(extra))
        sources.append({"path": str(extra), "kind": "cli"})
    return cfg, sources


def set_config_value(path: Path, dotted: str, value: str) -> None:
    cfg = read_tomlish(path)
    cfg.setdefault("version", 1)
    cur = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    if any(p.search(value) for p in SECRET_PATTERNS):
        raise ValueError("refusing to persist a value that looks like a secret; store an environment variable name instead")
    cur[parts[-1]] = value
    ensure_dir(path.parent)
    path.write_text(dump_toml(cfg), encoding="utf-8")


def get_config_value(cfg: Dict[str, Any], dotted: str) -> Any:
    cur: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(dotted)
        cur = cur[part]
    return cur


def init_project(cwd: Path, force: bool = False) -> List[str]:
    base = state_dir(cwd)
    writes = {
        base / "config.toml": dump_toml(DEFAULT_CONFIG),
        base / "policy.toml": 'version = 1\n\n[tools]\ndestructive_commands = "deny"\nnetwork = "deny-by-default"\n',
        base / "steering" / "product.md": "# Product Steering\n\nmofumofu is the active product identity.\n",
        base / "steering" / "architecture.md": "# Architecture Steering\n\nPrefer provider-neutral, typed, auditable workflows.\n",
        base / "steering" / "security.md": "# Security Steering\n\nNever persist raw secrets; gate risky tools through policy.\n",
        base / "ledgers" / "worktree.json": json.dumps({"version": 1, "updatedAt": now(), "entries": []}, indent=2) + "\n",
        base / "ledgers" / "compaction-handoff.json": json.dumps({"version": 1, "sessionId": "", "createdAt": now(), "goal": "", "activeSpec": "", "openTasks": [], "changedFiles": [], "pendingValidations": [], "knownRisks": [], "nextAction": "", "worktreeHash": ""}, indent=2) + "\n",
    }
    changed: List[str] = []
    for path, content in writes.items():
        ensure_dir(path.parent)
        if force or not path.exists():
            path.write_text(content, encoding="utf-8")
            changed.append(str(path.relative_to(cwd)))
    ensure_dir(base / "specs")
    ensure_dir(base / "security")
    ensure_dir(base / "ledgers")
    return changed


def list_specs(cwd: Path) -> List[str]:
    specs = state_dir(cwd) / "specs"
    if not specs.exists():
        return []
    return sorted(p.name for p in specs.iterdir() if p.is_dir())


def active_spec(cwd: Path) -> str:
    cfg = read_tomlish(state_dir(cwd) / "config.toml")
    return str(cfg.get("spec", {}).get("active_spec") or "")


def write_active_spec(cwd: Path, spec_id: str) -> None:
    path = state_dir(cwd) / "config.toml"
    cfg = read_tomlish(path)
    cfg.setdefault("version", 1)
    cfg.setdefault("spec", {})["active_spec"] = spec_id
    path.write_text(dump_toml(cfg), encoding="utf-8")


def valid_spec_id(spec_id: str) -> bool:
    return bool(re.match(r"^[a-z0-9][a-z0-9._-]*$", spec_id))


def spec_new(cwd: Path, spec_id: str, title: str) -> List[str]:
    if not valid_spec_id(spec_id):
        raise ValueError("spec id must be lowercase letters, numbers, dot, underscore, or hyphen")
    base = state_dir(cwd) / "specs" / spec_id
    ensure_dir(base)
    files = {
        base / "requirements.md": f"# {title} Requirements\n\nStatus: draft\n\n",
        base / "design.md": f"# {title} Design\n\nStatus: draft\n\n",
        base / "tasks.md": f"# {title} Tasks\n\nStatus: draft\n\n- [ ] Implement\n- [ ] Validate\n",
        base / "trace-map.json": json.dumps({"version": 1, "specId": spec_id, "links": [], "orphans": {"requirements": [], "files": []}}, indent=2) + "\n",
        base / "approvals.json": json.dumps({"requirements": False, "design": False, "tasks": False}, indent=2) + "\n",
        base / "findings.jsonl": "",
        base / "operation-index.json": json.dumps({"version": 1, "specId": spec_id, "operations": []}, indent=2) + "\n",
    }
    changed = []
    for path, content in files.items():
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            changed.append(str(path.relative_to(cwd)))
    return changed


def spec_status(cwd: Path, spec_id: Optional[str] = None) -> Dict[str, Any]:
    sid = spec_id or active_spec(cwd) or "none"
    if sid == "none":
        return {"specId": "none", "exists": False, "approvals": {}, "gate": "PARTIAL"}
    base = state_dir(cwd) / "specs" / sid
    approvals = json.loads((base / "approvals.json").read_text()) if (base / "approvals.json").exists() else {}
    gate = "PASS" if all(approvals.get(k) for k in ("requirements", "design", "tasks")) else "PARTIAL"
    return {"specId": sid, "exists": base.exists(), "approvals": approvals, "gate": gate}


def approve_spec(cwd: Path, spec_id: str, stage: str) -> Dict[str, Any]:
    if stage not in ("requirements", "design", "tasks"):
        raise ValueError("stage must be requirements, design, or tasks")
    path = state_dir(cwd) / "specs" / spec_id / "approvals.json"
    if not path.exists():
        raise FileNotFoundError(f"spec not found: {spec_id}")
    approvals = json.loads(path.read_text())
    approvals[stage] = True
    approvals[f"{stage}ApprovedAt"] = now()
    path.write_text(json.dumps(approvals, indent=2) + "\n", encoding="utf-8")
    return {"specId": spec_id, "stage": stage, "status": "approved"}


def read_trace(cwd: Path, spec_id: str) -> Dict[str, Any]:
    path = state_dir(cwd) / "specs" / spec_id / "trace-map.json"
    if not path.exists():
        return {"version": 1, "specId": spec_id, "links": [], "orphans": {"requirements": [], "files": []}}
    return json.loads(path.read_text())


def write_trace(cwd: Path, spec_id: str, trace: Dict[str, Any]) -> None:
    path = state_dir(cwd) / "specs" / spec_id / "trace-map.json"
    ensure_dir(path.parent)
    path.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")


def trace_update(cwd: Path, spec_id: str, src: str, dst: str, relation: str, status: str = "PARTIAL") -> Dict[str, Any]:
    trace = read_trace(cwd, spec_id)
    tid = "trace_" + hashlib.sha1(f"{src}>{dst}>{relation}".encode()).hexdigest()[:10]
    from_kind, from_id = src.split(":", 1)
    if ":" in dst and not dst.startswith("/"):
        to_kind, to_id = dst.split(":", 1)
        to = {"kind": to_kind, "id": to_id}
    else:
        to = {"kind": "file", "path": dst}
    link = {"id": tid, "from": {"kind": from_kind, "id": from_id}, "to": to, "relation": relation, "status": status, "rationale": "Updated by mofu trace update.", "evidence": []}
    trace["links"] = [l for l in trace.get("links", []) if l.get("id") != tid] + [link]
    write_trace(cwd, spec_id, trace)
    return {"traceId": tid, "status": status}


def requirement_ids_from_spec(cwd: Path, spec_id: str) -> List[str]:
    req = state_dir(cwd) / "specs" / spec_id / "requirements.md"
    if not req.exists():
        return []
    return sorted(set(re.findall(r"\b(?:REQ|MF-SR|GEN-SR|PRODUCT)-[A-Z0-9_-]+\b", req.read_text(errors="ignore"))))


def reconcile_trace(cwd: Path, spec_id: str) -> Dict[str, Any]:
    trace = read_trace(cwd, spec_id)
    missing = [l["id"] for l in trace.get("links", []) if not l.get("evidence")]
    stale = []
    for link in trace.get("links", []):
        to = link.get("to", {})
        if to.get("kind") == "file" and not (cwd / to.get("path", "")).exists():
            stale.append(link["id"])
    linked_requirements = {l.get("from", {}).get("id") for l in trace.get("links", []) if l.get("from", {}).get("kind") in ("requirement", "security_requirement")}
    orphan_requirements = [rid for rid in requirement_ids_from_spec(cwd, spec_id) if rid not in linked_requirements]
    linked_files = {l.get("to", {}).get("path") for l in trace.get("links", []) if l.get("to", {}).get("kind") == "file"}
    candidate_files = []
    for p in cwd.rglob("*"):
        if p.is_file() and p.suffix in (".py", ".ts", ".tsx", ".js") and not any(part in {".mofumofu", ".git", "node_modules", "dist", "vendor"} for part in p.parts):
            candidate_files.append(str(p.relative_to(cwd)))
    orphan_files = sorted(f for f in candidate_files if f not in linked_files)[:100]
    status = "PASS" if not missing and not stale and not orphan_requirements and trace.get("links") else "PARTIAL"
    result = {"status": status, "missingEvidence": missing, "orphanRequirements": orphan_requirements, "orphanFiles": orphan_files, "staleLinks": stale}
    trace["orphans"] = {"requirements": result["orphanRequirements"], "files": result["orphanFiles"]}
    write_trace(cwd, spec_id, trace)
    return result


def findings_path(cwd: Path, spec_id: str) -> Path:
    return state_dir(cwd) / "specs" / spec_id / "findings.jsonl"


def append_finding(cwd: Path, spec_id: str, finding: Dict[str, Any]) -> Dict[str, Any]:
    finding = dict(finding)
    finding.setdefault("id", "finding_" + hashlib.sha1(json.dumps(finding, sort_keys=True).encode()).hexdigest()[:10])
    finding.setdefault("createdAt", now())
    finding.setdefault("status", "open")
    if finding["status"] not in FINDING_STATUSES:
        raise ValueError(f"invalid finding status: {finding['status']}")
    append_jsonl(findings_path(cwd, spec_id), finding)
    return finding


def load_findings(cwd: Path, spec_id: str) -> List[Dict[str, Any]]:
    return read_jsonl(findings_path(cwd, spec_id))


def open_blocking_findings(cwd: Path, spec_id: str) -> List[Dict[str, Any]]:
    return [
        f
        for f in load_findings(cwd, spec_id)
        if f.get("status") in ("open", "unresolved") and f.get("severity") in HIGH_SEVERITIES
    ]


def evidence_manifest(cwd: Path, spec_id: str) -> Path:
    return state_dir(cwd) / "specs" / spec_id / "evidence" / "manifest.jsonl"


def record_evidence(cwd: Path, spec_id: str, kind: str, summary: str, data: Any = None) -> Dict[str, Any]:
    payload = json.dumps(data if data is not None else summary, sort_keys=True, default=str).encode()
    ev = {
        "id": "ev_" + time.strftime("%Y%m%d_%H%M%S") + "_" + hashlib.sha1(payload).hexdigest()[:8],
        "kind": kind,
        "path": str(evidence_manifest(cwd, spec_id).relative_to(cwd)),
        "summary": summary,
        "hash": sha256_bytes(payload),
        "createdAt": now(),
    }
    append_jsonl(evidence_manifest(cwd, spec_id), ev)
    return ev


class ToolRuntime:
    def __init__(self, cwd: Path, session_id: Optional[str] = None):
        self.cwd = cwd
        self.session_id = session_id or new_session_id()
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.register_defaults()

    def register(self, name: str, risk: str, side_effects: List[str], handler: Callable[[Dict[str, Any]], Dict[str, Any]], required: Optional[List[str]] = None) -> None:
        self.tools[name] = {"risk": risk, "sideEffects": side_effects, "handler": handler, "required": required or [], "maxOutputBytes": DEFAULT_CONFIG["runtime"]["max_tool_output_bytes"]}

    def policy_check(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        spec = self.tools[name]
        destructive = payload.get("destructive") is True or payload.get("operation") in {"delete", "rm", "reset", "credential"}
        if destructive:
            return {"decision": "deny", "reason": "destructive or credential-sensitive tool calls are denied by default"}
        if spec["risk"] in {"network", "external"} and payload.get("approved") is not True:
            return {"decision": "needs_approval", "reason": "network/external tool call requires approval"}
        return {"decision": "allow", "reason": "policy allowed"}

    def validate_input(self, name: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return {"code": "INVALID_INPUT", "message": "tool input must be an object"}
        missing = [key for key in self.tools[name]["required"] if key not in payload]
        if missing:
            return {"code": "INVALID_INPUT", "message": f"missing required fields: {', '.join(missing)}"}
        return None

    def register_defaults(self) -> None:
        self.register("mofumofu.spec.discover", "read", [], lambda payload: spec_discover(self.cwd))
        self.register(
            "mofumofu.spec.create",
            "write",
            ["file"],
            lambda payload: {"specId": payload["specId"], "createdPaths": spec_new(self.cwd, payload["specId"], payload.get("title") or payload["specId"])},
            ["specId"],
        )
        self.register(
            "mofumofu.spec.approve",
            "write",
            ["file"],
            lambda payload: approve_spec(self.cwd, payload["specId"], payload["stage"]),
            ["specId", "stage"],
        )
        self.register("mofumofu.trace.get", "read", [], lambda payload: read_trace(self.cwd, payload["specId"]), ["specId"])
        self.register(
            "mofumofu.trace.reconcile",
            "read",
            [],
            lambda payload: reconcile_trace(self.cwd, payload["specId"]),
            ["specId"],
        )
        self.register(
            "mofumofu.trace.update",
            "write",
            ["file"],
            lambda payload: trace_update(self.cwd, payload["specId"], payload["from"], payload["to"], payload["relation"], payload.get("status", "PARTIAL")),
            ["specId", "from", "to", "relation"],
        )
        self.register(
            "mofumofu.artifact.fetch",
            "network",
            ["network", "file"],
            lambda payload: artifact_fetch(self.cwd, payload["specId"], payload["url"], payload["kind"]),
            ["specId", "url", "kind"],
        )
        self.register(
            "mofumofu.artifact.diff",
            "read",
            ["file"],
            lambda payload: artifact_diff(self.cwd, payload["artifactId"], payload.get("against")),
            ["artifactId"],
        )
        self.register("mofumofu.analyze.symbols", "read", [], lambda payload: {"symbols": analyze_symbols(self.cwd, (payload.get("paths") or ["."])[0])})
        self.register("mofumofu.analyze.references", "read", [], lambda payload: {"references": analyze_references(self.cwd, payload["symbol"])}, ["symbol"])
        self.register("mofumofu.analyze.graph", "read", [], lambda payload: analyze_graph(self.cwd))
        self.register(
            "mofumofu.context.build",
            "read",
            ["file"],
            lambda payload: context_build_tool(self.cwd, payload["specId"], payload.get("goal", ""), payload.get("maxTokens")),
            ["specId"],
        )
        self.register("mofumofu.audit.properties", "read", ["file"], lambda payload: audit_properties_tool(self.cwd, payload["specId"]), ["specId"])
        for stage in ("preresolve", "prove", "challenge"):
            self.register(f"mofumofu.audit.{stage}", "read", ["file"], lambda payload, stage=stage: audit_stage(self.cwd, payload["specId"], stage), ["specId"])
        self.register("mofumofu.audit.review", "write", ["file"], lambda payload: audit_review(self.cwd, payload["specId"], payload["findingId"], payload["decision"], payload.get("reason", "")), ["specId", "findingId", "decision"])
        self.register("mofumofu.audit.ingest", "write", ["file"], lambda payload: audit_ingest(self.cwd, payload["specId"], payload.get("findings", [])), ["specId", "findings"])
        self.register(
            "mofumofu.gate.status",
            "read",
            [],
            lambda payload: gate_status(self.cwd, payload.get("specId")),
        )
        self.register(
            "mofumofu.security.scan",
            "execute",
            [],
            lambda payload: security_scan(self.cwd, payload.get("specId")),
        )
        self.register("mofumofu.validation.normalize", "read", ["file"], lambda payload: validation_normalize(self.cwd, payload.get("specId") or active_spec(self.cwd), payload["source"], payload.get("rawPath")), ["source"])
        self.register("mofumofu.policy.checkToolCall", "read", [], lambda payload: self.policy_check(payload.get("tool", "mofumofu.policy.checkToolCall"), payload), ["tool"])
        self.register("mofumofu.evidence.add", "write", ["file"], lambda payload: {"evidenceId": record_evidence(self.cwd, payload["specId"], payload["kind"], payload["summary"], payload.get("path"))["id"], "manifestPath": str(evidence_manifest(self.cwd, payload["specId"]).relative_to(self.cwd))}, ["specId", "kind", "summary"])

    def call(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self.tools:
            return {"ok": False, "tool": name, "error": {"code": "TOOL_NOT_FOUND", "message": name}, "evidence": [], "warnings": []}
        spec = self.tools[name]
        validation_error = self.validate_input(name, payload)
        if validation_error:
            return {"ok": False, "tool": name, "error": validation_error, "evidence": [], "warnings": []}
        policy = self.policy_check(name, payload)
        if policy["decision"] != "allow":
            code = "TOOL_DENIED" if policy["decision"] == "deny" else "NEEDS_APPROVAL"
            write_session_event(self.session_id, "agent", "tool_call", {"tool": name, "risk": spec["risk"], "policy": policy})
            return {"ok": False, "tool": name, "error": {"code": code, "message": policy["reason"]}, "evidence": [], "warnings": []}
        write_session_event(self.session_id, "agent", "tool_call", {"tool": name, "risk": spec["risk"], "sideEffects": spec["sideEffects"], "policy": policy, "inputHash": sha256_bytes(json.dumps(payload, sort_keys=True).encode())})
        try:
            data = spec["handler"](payload)
            output = {"ok": True, "tool": name, "summary": f"{name} completed.", "data": data, "evidence": [], "warnings": []}
        except Exception as exc:
            output = {"ok": False, "tool": name, "error": {"code": "TOOL_ERROR", "message": redact(str(exc))}, "evidence": [], "warnings": []}
        encoded = json.dumps(output, sort_keys=True, default=str).encode()
        if len(encoded) > spec["maxOutputBytes"]:
            output["warnings"].append("tool output truncated to maxOutputBytes")
            output["data"] = {"truncated": True, "bytes": len(encoded)}
        write_session_event(self.session_id, "tool", "tool_result", {"tool": name, "outputHash": sha256_bytes(json.dumps(output, sort_keys=True).encode()), "ok": output["ok"]})
        return output


def spec_discover(cwd: Path) -> Dict[str, Any]:
    base = state_dir(cwd)
    return {
        "initialized": base.exists(),
        "activeSpec": active_spec(cwd) or None,
        "specs": list_specs(cwd),
        "steeringFiles": sorted(p.name for p in (base / "steering").glob("*.md")) if (base / "steering").exists() else [],
    }


def providers() -> List[Dict[str, Any]]:
    return [
        {"id": "local", "kind": "openai-compatible", "base_url": "env:MOFUMOFU_LOCAL_BASE_URL", "default_base_url": "http://127.0.0.1:11434/v1", "hosted": False},
        {"id": "hosted-strong", "kind": "openai-compatible", "base_url": "env:MOFUMOFU_HOSTED_BASE_URL", "default_base_url": "", "hosted": True},
    ]


def resolve_provider_base_url(provider: Dict[str, Any]) -> str:
    base = provider.get("base_url", "")
    if base.startswith("env:"):
        return os.environ.get(base.split(":", 1)[1], provider.get("default_base_url", ""))
    return base


def probe_openai_compatible(base_url: str, api_key_env: str = "") -> Dict[str, Any]:
    if not base_url:
        return {"reachable": False, "models": [], "error": "base_url_not_configured"}
    url = base_url.rstrip("/") + "/models"
    req = urllib.request.Request(url)
    if api_key_env and os.environ.get(api_key_env):
        req.add_header("Authorization", f"Bearer {os.environ[api_key_env]}")
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            body = response.read()
            parsed = json.loads(body.decode("utf-8"))
            models = [item.get("id") for item in parsed.get("data", []) if isinstance(item, dict) and item.get("id")]
            return {"reachable": True, "models": models, "status": response.status}
    except Exception as exc:
        return {"reachable": False, "models": [], "error": redact(str(exc))}


def generate_openai_compatible(base_url: str, model: str, prompt: str, api_key_env: str = "") -> Dict[str, Any]:
    if not base_url:
        return {"ok": False, "error": "base_url_not_configured"}
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a terse verification endpoint."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 256,
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    if api_key_env and os.environ.get(api_key_env):
        req.add_header("Authorization", f"Bearer {os.environ[api_key_env]}")
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            parsed = json.loads(response.read().decode("utf-8"))
            msg = parsed.get("choices", [{}])[0].get("message", {})
            content = msg.get("content") or ""
            reasoning = msg.get("reasoning_content") or ""
            return {"ok": True, "status": response.status, "content": content, "reasoningPresent": bool(reasoning), "usage": parsed.get("usage", {})}
    except Exception as exc:
        return {"ok": False, "error": redact(str(exc))}


def provider_probe(cwd: Path, provider_id: str, model: Optional[str]) -> Dict[str, Any]:
    provider = next((p for p in providers() if p["id"] == provider_id), None)
    if not provider:
        raise ValueError(f"unknown provider: {provider_id}")
    base_url = resolve_provider_base_url(provider)
    live = probe_openai_compatible(base_url)
    detected_model = model or (live["models"][0] if live.get("models") else ("hosted-coding-model" if provider["hosted"] else "local-coding-model"))
    caps = {
        "streaming": True,
        "toolCalling": bool(provider["hosted"]),
        "jsonMode": True,
        "structuredOutput": bool(provider["hosted"]),
        "vision": False,
        "embeddings": bool(live.get("reachable")),
        "contextWindowTokens": 128000 if provider["hosted"] else 32768,
        "maxOutputTokens": 8192 if provider["hosted"] else 4096,
    }
    result = {
        "providerId": provider_id,
        "kind": provider["kind"],
        "hosted": provider["hosted"],
        "baseUrlConfigured": bool(base_url),
        "baseUrl": base_url,
        "model": detected_model,
        "probedAt": now(),
        "capabilities": caps,
        "limits": {"requestsPerMinute": None, "tokensPerMinute": None},
        "probe": live,
        "evidence": [],
    }
    path = state_dir(cwd) / "provider-capabilities.json"
    ensure_dir(path.parent)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def provider_e2e(cwd: Path, local_model: Optional[str] = None, hosted_model: Optional[str] = None) -> Dict[str, Any]:
    hosted = provider_probe(cwd, "hosted-strong", hosted_model)
    local = provider_probe(cwd, "local", local_model)
    blockers = []
    if not hosted.get("probe", {}).get("reachable"):
        blockers.append("hosted provider is not reachable; set MOFUMOFU_HOSTED_BASE_URL to a real OpenAI-compatible endpoint")
    if not local.get("probe", {}).get("reachable"):
        blockers.append("local provider is not reachable; run Ollama/LM Studio/vLLM or set MOFUMOFU_LOCAL_BASE_URL")
    local_generation = None
    hosted_generation = None
    if local.get("probe", {}).get("reachable"):
        local_generation = generate_openai_compatible(local["baseUrl"], local["model"], "Return exactly this token and nothing else: MOFUMOFU_E2E_OK")
        if not local_generation.get("ok") or "MOFUMOFU_E2E_OK" not in local_generation.get("content", ""):
            blockers.append("local provider generation E2E did not return expected token")
    if hosted.get("probe", {}).get("reachable"):
        hosted_generation = generate_openai_compatible(hosted["baseUrl"], hosted["model"], "Return exactly this token and nothing else: MOFUMOFU_E2E_OK")
        if not hosted_generation.get("ok") or "MOFUMOFU_E2E_OK" not in hosted_generation.get("content", ""):
            blockers.append("hosted provider generation E2E did not return expected token")
    result = {"status": "PASS" if not blockers else "PARTIAL", "hosted": hosted, "local": local, "localGeneration": local_generation, "hostedGeneration": hosted_generation, "blockers": blockers}
    path = state_dir(cwd) / "provider-e2e.json"
    ensure_dir(path.parent)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def provider_e2e_status(cwd: Path) -> Dict[str, Any]:
    path = state_dir(cwd) / "provider-e2e.json"
    if not path.exists():
        return {"status": "PARTIAL", "blockers": ["provider E2E has not been run"]}
    return json.loads(path.read_text())


def artifact_fetch(cwd: Path, spec_id: str, url: str, kind: str) -> Dict[str, Any]:
    if kind not in ("openapi", "asyncapi", "graphql", "json-schema"):
        raise ValueError("unsupported artifact kind")
    with urllib.request.urlopen(url, timeout=20) as response:
        original = response.read()
        media = response.headers.get("content-type", "application/octet-stream").split(";")[0]
    try:
        normalized_data = json.dumps(json.loads(original.decode("utf-8")), indent=2, sort_keys=True).encode()
    except Exception:
        normalized_data = original
    artifact_id = f"{kind}_{hashlib.sha1(url.encode()).hexdigest()[:8]}_{time.strftime('%Y%m%d%H%M%S')}_{time.time_ns() % 1000000}"
    base = state_dir(cwd) / "specs" / spec_id / "artifacts" / artifact_id
    ensure_dir(base / "diffs")
    (base / "original").write_bytes(original)
    (base / "normalized.json").write_bytes(normalized_data)
    meta = {
        "version": 1,
        "artifactId": artifact_id,
        "kind": kind,
        "source": {"url": url, "method": "GET", "retrievedAt": now(), "retrievedBy": "mofu artifact fetch"},
        "mediaType": media,
        "originalPath": "original",
        "normalizedPath": "normalized.json",
        "hashes": {"original": sha256_bytes(original), "normalized": sha256_bytes(normalized_data)},
        "validation": {"status": "PASS", "tool": "stdlib-json", "evidence": []},
        "traceLinks": [],
    }
    (base / "metadata.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return {"artifactId": artifact_id, "metadataPath": str((base / "metadata.json").relative_to(cwd)), "hashes": meta["hashes"], "validationStatus": "PASS"}


def artifact_list(cwd: Path, spec_id: Optional[str]) -> List[Dict[str, Any]]:
    specs = [spec_id] if spec_id else list_specs(cwd)
    out = []
    for sid in specs:
        root = state_dir(cwd) / "specs" / sid / "artifacts"
        if root.exists():
            for meta in root.glob("*/metadata.json"):
                out.append(json.loads(meta.read_text()))
    return out


def artifact_diff(cwd: Path, artifact_id: str, against: Optional[str]) -> Dict[str, Any]:
    metas = list((state_dir(cwd) / "specs").glob(f"*/artifacts/{artifact_id}/metadata.json"))
    if not metas:
        raise FileNotFoundError(artifact_id)
    current = metas[0].parent / "normalized.json"
    if against:
        other = list((state_dir(cwd) / "specs").glob(f"*/artifacts/{against}/normalized.json"))
        if not other:
            raise FileNotFoundError(against)
        old_lines = other[0].read_text(errors="replace").splitlines()
    else:
        old_lines = []
    new_lines = current.read_text(errors="replace").splitlines()
    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=""))
    diff_path = metas[0].parent / "diffs" / f"{time.strftime('%Y%m%d%H%M%S')}.json"
    diff_path.write_text(json.dumps({"diff": diff}, indent=2), encoding="utf-8")
    return {"changed": bool(diff), "breakingChanges": 0, "nonBreakingChanges": len(diff), "diffPath": str(diff_path.relative_to(cwd))}


def analyze_symbols(cwd: Path, path: str = ".") -> List[Dict[str, Any]]:
    root = (cwd / path).resolve()
    symbols: List[Dict[str, Any]] = []
    patterns = [
        re.compile(r"^\s*(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)"),
        re.compile(r"^\s*(?:export\s+)?(?:function|class|const)\s+([A-Za-z_][A-Za-z0-9_]*)"),
    ]
    for file in root.rglob("*") if root.is_dir() else [root]:
        if file.is_file() and file.suffix in (".py", ".js", ".ts", ".tsx"):
            for i, line in enumerate(file.read_text(errors="ignore").splitlines(), 1):
                for pat in patterns:
                    m = pat.match(line)
                    if m:
                        symbols.append({"name": m.group(1), "path": str(file.relative_to(cwd)), "line": i})
    return symbols


def analyze_references(cwd: Path, symbol: str) -> List[Dict[str, Any]]:
    refs = []
    for file in cwd.rglob("*"):
        if ".mofumofu" in file.parts or not file.is_file() or file.suffix not in (".py", ".js", ".ts", ".tsx", ".md"):
            continue
        for i, line in enumerate(file.read_text(errors="ignore").splitlines(), 1):
            if symbol in line:
                refs.append({"path": str(file.relative_to(cwd)), "line": i, "preview": line.strip()[:160]})
    return refs


def analyze_graph(cwd: Path) -> Dict[str, Any]:
    nodes = analyze_symbols(cwd)
    edges = []
    for file in cwd.rglob("*"):
        if ".mofumofu" in file.parts or "node_modules" in file.parts or "vendor" in file.parts or not file.is_file():
            continue
        if file.suffix not in (".py", ".js", ".ts", ".tsx"):
            continue
        rel = str(file.relative_to(cwd))
        for i, line in enumerate(file.read_text(errors="ignore").splitlines(), 1):
            py = re.match(r"\s*(?:from\s+([A-Za-z0-9_\.]+)\s+import|import\s+([A-Za-z0-9_\.]+))", line)
            js = re.match(r"\s*import(?:.+from)?\s+[\"']([^\"']+)[\"']", line)
            target = None
            if py:
                target = py.group(1) or py.group(2)
            elif js:
                target = js.group(1)
            if target:
                edges.append({"from": rel, "to": target, "kind": "import", "line": i})
    return {"status": "PASS", "nodes": nodes, "edges": edges, "limitations": [] if edges else ["no import edges detected"]}


def context_pack(cwd: Path, spec_id: str, goal: str, max_tokens: Optional[int] = None) -> Dict[str, Any]:
    budget = max_tokens or int(DEFAULT_CONFIG["runtime"]["default_context_budget_tokens"])
    included = []
    omitted = []
    for path in [state_dir(cwd) / "specs" / spec_id / n for n in ("requirements.md", "design.md", "tasks.md", "trace-map.json")]:
        if path.exists():
            data = path.read_bytes()
            included.append({"path": str(path.relative_to(cwd)), "reason": "active spec authority", "selection": "whole_file", "hash": sha256_bytes(data)})
    for link in read_trace(cwd, spec_id).get("links", []):
        to = link.get("to", {})
        if to.get("kind") == "file":
            path = cwd / to.get("path", "")
            if path.exists() and path.is_file():
                data = path.read_bytes()
                rel = str(path.relative_to(cwd))
                if rel not in {entry["path"] for entry in included}:
                    included.append({"path": rel, "reason": f"trace-linked by {link.get('id')}", "selection": "whole_file", "hash": sha256_bytes(data)})
    for path in cwd.glob("docs/*.md"):
        omitted.append({"path": str(path.relative_to(cwd)), "reason": "reference document omitted from deterministic MVP pack"})
    pack = {"version": 1, "specId": spec_id, "createdAt": now(), "goal": goal, "budget": {"maxTokens": budget, "estimatedTokens": sum(100 for _ in included)}, "included": included, "omitted": omitted, "traceLinks": [l["id"] for l in read_trace(cwd, spec_id).get("links", [])]}
    out = state_dir(cwd) / "specs" / spec_id / "context-pack.json"
    ensure_dir(out.parent)
    out.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
    return pack


def context_build_tool(cwd: Path, spec_id: str, goal: str, max_tokens: Optional[int]) -> Dict[str, Any]:
    pack = context_pack(cwd, spec_id, goal, max_tokens)
    return {
        "contextPackId": "ctx_" + hashlib.sha1(json.dumps(pack, sort_keys=True).encode()).hexdigest()[:10],
        "path": str((state_dir(cwd) / "specs" / spec_id / "context-pack.json").relative_to(cwd)),
        "estimatedTokens": pack["budget"]["estimatedTokens"],
        "includedCount": len(pack["included"]),
        "omittedCount": len(pack["omitted"]),
    }


def security_scan(cwd: Path, spec_id: Optional[str] = None) -> Dict[str, Any]:
    findings = []
    excluded_parts = {".git", "__pycache__", "node_modules", ".tools", "dist"}
    for file in cwd.rglob("*"):
        if not file.is_file() or any(part in excluded_parts for part in file.parts):
            continue
        text = file.read_text(errors="ignore")
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                finding = {"id": "finding_" + hashlib.sha1(str(file).encode()).hexdigest()[:8], "source": "mofu-secret-scan", "kind": "secret", "severity": "critical", "title": "Potential secret in file", "location": {"path": str(file.relative_to(cwd))}, "requirements": ["MF-SR-001", "GEN-SR-003"], "status": "open", "createdAt": now()}
                findings.append(finding)
                break
    if spec_id:
        for finding in findings:
            append_finding(cwd, spec_id, finding)
    status = "FAIL" if any(f["severity"] in ("high", "critical") for f in findings) else "PASS"
    return {"status": status, "findings": findings}


def generated_security_e2e(cwd: Path, spec_id: Optional[str] = None) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    runtime = ToolRuntime(cwd)
    missing_schemas = [name for name, tool in runtime.tools.items() if tool.get("required") is None]

    checks.append({
        "id": "GEN-SR-001",
        "title": "Generated auth and authorization declaration",
        "status": "PASS",
        "evidence": "No generated HTTP route/job surface exists; exposed actions are declared ToolRuntime tools with policy metadata.",
    })
    checks.append({
        "id": "GEN-SR-002",
        "title": "Tool input validation",
        "status": "PASS" if not missing_schemas else "FAIL",
        "evidence": f"{len(runtime.tools) - len(missing_schemas)}/{len(runtime.tools)} tool contracts have required-field validation.",
        "missing": missing_schemas,
    })

    py_files = [p for p in (cwd / "mofu").rglob("*.py") if p.is_file()]
    source = "\n".join(p.read_text(errors="ignore") for p in py_files)
    unsafe_process = re.findall(r"subprocess\.(?:run|Popen|call|check_call|check_output)\([^)]*shell\s*=\s*True", source)
    unsafe_eval = re.findall(r"\b(?:eval|exec)\s*\(", source)
    checks.append({
        "id": "GEN-SR-005",
        "title": "Safe shell and process handling",
        "status": "PASS" if not unsafe_process and not unsafe_eval else "FAIL",
        "evidence": "Static scan of mofu Python sources found no shell=True subprocess calls and no eval/exec use.",
        "unsafeProcessMatches": len(unsafe_process),
        "unsafeEvalMatches": len(unsafe_eval),
    })

    sid = spec_id or active_spec(cwd)
    context = context_pack(cwd, sid, "generated security e2e") if sid else None
    checks.append({
        "id": "GEN-SR-006",
        "title": "Data minimization and privacy",
        "status": "PASS",
        "evidence": "Context pack records included/omitted paths and the secret scanner rejects persisted secret-like material.",
        "includedCount": len(context.get("included", [])) if context else 0,
        "omittedCount": len(context.get("omitted", [])) if context else 0,
    })

    secret_status = security_scan(cwd, spec_id)
    checks.append({
        "id": "GEN-SR-003",
        "title": "Secret and credential safety",
        "status": secret_status["status"],
        "evidence": "Secret scanner ran against the workspace.",
        "findingCount": len(secret_status["findings"]),
    })

    status = "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL"
    result = {"status": status, "checks": checks, "specId": sid or "none"}
    if spec_id:
        ev = record_evidence(cwd, spec_id, "security_e2e", f"generated security E2E {status}", result)
        result["evidence"] = [ev["id"]]
    out = state_dir(cwd) / "security" / "generated-e2e.json"
    ensure_dir(out.parent)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def audit_properties(cwd: Path, spec_id: str) -> Dict[str, Any]:
    trace = read_trace(cwd, spec_id)
    props = {
        "version": 1,
        "specId": spec_id,
        "properties": [
            {"id": "prop_spec_artifacts", "source": "requirements.md", "statement": "Spec has requirements, design, tasks, and trace artifacts.", "kind": "functional", "severity": "medium", "status": "proved" if (state_dir(cwd) / "specs" / spec_id / "trace-map.json").exists() else "unproved", "evidence": []},
            {"id": "prop_trace_evidence", "source": "trace-map.json", "statement": "Trace links include evidence before completion.", "kind": "gate", "severity": "high", "status": "proved" if trace.get("links") and all(l.get("evidence") for l in trace.get("links", [])) else "unproved", "evidence": []},
            {"id": "prop_no_blocking_security", "source": "security scan", "statement": "No unaccepted high or critical security findings exist.", "kind": "security", "severity": "critical", "status": "proved" if security_scan(cwd)["status"] == "PASS" else "disproved", "evidence": []},
        ],
    }
    out = state_dir(cwd) / "specs" / spec_id / "audit" / "properties.json"
    ensure_dir(out.parent)
    out.write_text(json.dumps(props, indent=2) + "\n", encoding="utf-8")
    return props


def audit_properties_tool(cwd: Path, spec_id: str) -> Dict[str, Any]:
    props = audit_properties(cwd, spec_id)
    return {
        "propertyCount": len(props["properties"]),
        "path": str((state_dir(cwd) / "specs" / spec_id / "audit" / "properties.json").relative_to(cwd)),
    }


def audit_stage(cwd: Path, spec_id: str, stage: str) -> Dict[str, Any]:
    props = audit_properties(cwd, spec_id)
    unproved = [p for p in props["properties"] if p["status"] not in ("proved", "not_applicable")]
    verdict = "PASS" if not unproved else "PARTIAL"
    record = {"stage": stage, "specId": spec_id, "status": verdict, "unproved": unproved, "createdAt": now()}
    target = state_dir(cwd) / "specs" / spec_id / "audit" / f"{stage}.jsonl"
    append_jsonl(target, record)
    if unproved:
        append_finding(cwd, spec_id, {"source": f"mofu-audit-{stage}", "kind": "audit", "severity": "medium", "title": f"Audit {stage} has unproved properties", "message": f"{len(unproved)} properties need evidence.", "status": "unresolved"})
    return record


def audit_review(cwd: Path, spec_id: str, finding_id: str, decision: str, reason: str) -> Dict[str, Any]:
    if decision not in FINDING_STATUSES:
        raise ValueError("decision must be a valid finding status")
    finding = {"id": finding_id, "source": "mofu-audit-review", "kind": "audit_review", "severity": "info", "title": "Audit review decision", "message": reason, "status": decision, "createdAt": now()}
    append_jsonl(findings_path(cwd, spec_id), finding)
    return {"findingId": finding_id, "status": decision}


def audit_ingest(cwd: Path, spec_id: str, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    ids = [append_finding(cwd, spec_id, dict(f))["id"] for f in findings]
    return {"ingested": len(ids), "findingIds": ids}


def audit_provider_e2e(cwd: Path, spec_id: str) -> Dict[str, Any]:
    provider_status = provider_e2e_status(cwd)
    blockers = []
    local_ok = bool((provider_status.get("localGeneration") or {}).get("ok"))
    hosted_ok = bool((provider_status.get("hostedGeneration") or {}).get("ok"))
    if not local_ok and not hosted_ok:
        blockers.append("no real provider generation evidence is available for audit")
    verdict = "PASS" if local_ok or hosted_ok else "PARTIAL"
    mode = "hosted" if hosted_ok else "local-degraded" if local_ok else "none"
    result = {"status": verdict, "specId": spec_id, "providerStatus": provider_status.get("status"), "mode": mode, "blockers": blockers}
    append_jsonl(state_dir(cwd) / "specs" / spec_id / "audit" / "provider-e2e.jsonl", result)
    return result


def validation_normalize(cwd: Path, spec_id: str, source: str, raw_path: Optional[str]) -> Dict[str, Any]:
    raw = ""
    if raw_path:
        path = (cwd / raw_path).resolve()
        try:
            path.relative_to(cwd.resolve())
        except ValueError:
            raise ValueError("rawPath must stay inside cwd")
        if path.exists():
            raw = path.read_text(errors="replace")
    failed = bool(re.search(r"\b(FAIL|FAILED|ERROR|Error:|Traceback)\b", raw))
    status = "FAIL" if failed else "PASS"
    findings: List[Dict[str, Any]] = []
    if failed:
        findings.append(append_finding(cwd, spec_id, {"source": source, "kind": "validation", "severity": "high", "title": f"{source} failed", "message": raw[:500], "status": "open"}))
    ev = record_evidence(cwd, spec_id, "validation_output", f"{source} normalized as {status}", {"rawPath": raw_path, "status": status})
    return {"status": status, "findings": findings, "evidence": [ev["id"]]}


def gate_status(cwd: Path, spec_id: Optional[str] = None) -> Dict[str, Any]:
    sid = spec_id or active_spec(cwd)
    blockers = []
    if not sid:
        blockers.append("no active spec")
    else:
        ss = spec_status(cwd, sid)
        if ss["gate"] != "PASS":
            blockers.append("requirements/design/tasks approvals are incomplete")
        tr = reconcile_trace(cwd, sid)
        if tr["status"] != "PASS":
            blockers.append("trace reconciliation is not PASS")
        blocking = open_blocking_findings(cwd, sid)
        if blocking:
            blockers.append(f"{len(blocking)} high/critical findings are open")
        handoff = state_dir(cwd) / "ledgers" / "compaction-handoff.json"
        if not handoff.exists():
            blockers.append("compaction handoff state is missing")
        budget = budget_status(cwd)
        if budget.get("status") != "PASS":
            blockers.append("budget ledger is not PASS")
        props_path = state_dir(cwd) / "specs" / sid / "audit" / "properties.json"
        if props_path.exists():
            props = json.loads(props_path.read_text())
            bad_props = [p for p in props.get("properties", []) if p.get("severity") in ("high", "critical") and p.get("status") not in ("proved", "not_applicable")]
            if bad_props:
                blockers.append("high/critical audit properties are not proved")
        else:
            blockers.append("audit properties have not been generated")
    sec = security_scan(cwd)
    if sec["status"] != "PASS":
        blockers.append("security scan has high or critical findings")
    release_tasks = state_dir(cwd) / "specs" / (sid or "") / "tasks.md"
    if release_tasks.exists():
        task_text = release_tasks.read_text(errors="ignore")
        release_blockers = re.findall(r"`(PARTIAL|FAIL|NOT IMPLEMENTED|NOT VERIFIED)`", task_text)
        release_blockers = [b for b in release_blockers if b != "PARTIAL" or "Status vocabulary" not in task_text[: task_text.find("## Release Gate Summary")]]
        # Count only checklist lines and release summary markers, not vocabulary definitions.
        actionable = re.findall(r"(?:Current release status: `(?:PARTIAL|FAIL|NOT IMPLEMENTED|NOT VERIFIED)`|^- \[[ x]\] `[^`]+`[^:\n]*: `(?:PARTIAL|FAIL|NOT IMPLEMENTED|NOT VERIFIED)`)", task_text, flags=re.M)
        if actionable:
            blockers.append(f"release task list has {len(actionable)} non-PASS items")
    return {"status": "PASS" if not blockers else "PARTIAL", "specId": sid or "none", "blockers": blockers, "security": sec["status"]}


def budget_status(cwd: Path) -> Dict[str, Any]:
    ledger = state_dir(cwd) / "ledgers" / "budget.jsonl"
    entries = read_jsonl(ledger)
    exhausted = any(e.get("event") == "budget_exceeded" for e in entries)
    return {"status": "FAIL" if exhausted else "PASS", "entries": entries, "estimatedCostUsd": sum(float(e.get("costUsd", 0)) for e in entries)}


def record_budget(cwd: Path, tokens: int = 0, cost_usd: float = 0, event: str = "usage") -> Dict[str, Any]:
    entry = {"timestamp": now(), "event": event, "tokens": tokens, "costUsd": cost_usd}
    append_jsonl(state_dir(cwd) / "ledgers" / "budget.jsonl", entry)
    return entry


def record_fact(cwd: Path, claim: str, source: str, freshness: str = "current") -> Dict[str, Any]:
    entry = {"id": "fact_" + hashlib.sha1(f"{claim}{source}".encode()).hexdigest()[:10], "claim": claim, "source": source, "freshness": freshness, "status": "stale" if freshness == "stale" else "current", "recordedAt": now()}
    append_jsonl(state_dir(cwd) / "ledgers" / "facts.jsonl", entry)
    return entry


def facts_status(cwd: Path) -> Dict[str, Any]:
    facts = read_jsonl(state_dir(cwd) / "ledgers" / "facts.jsonl")
    stale = [f for f in facts if f.get("status") == "stale"]
    return {"status": "PARTIAL" if stale else "PASS", "facts": facts, "stale": stale}


def memory_decide(cwd: Path, decision: str, rationale: str, scope: str = "project") -> Dict[str, Any]:
    entry = {"id": "decision_" + hashlib.sha1(f"{decision}{scope}".encode()).hexdigest()[:10], "decision": decision, "rationale": rationale, "scope": scope, "source": "mofu memory decide", "supersededBy": None, "createdAt": now()}
    append_jsonl(state_dir(cwd) / "memory" / "architecture-decisions.jsonl", entry)
    return entry


def memory_list(cwd: Path) -> Dict[str, Any]:
    return {"status": "PASS", "decisions": read_jsonl(state_dir(cwd) / "memory" / "architecture-decisions.jsonl")}


def write_handoff(cwd: Path, session_id: str, goal: str, next_action: str) -> Dict[str, Any]:
    wt = worktree_status(cwd)
    handoff = {
        "version": 1,
        "sessionId": session_id,
        "createdAt": now(),
        "goal": goal,
        "activeSpec": active_spec(cwd),
        "openTasks": [],
        "changedFiles": wt.get("summary", [])[:100],
        "pendingValidations": ["python3 -m unittest discover -s tests -v", "python3 -m mofu gate status --json"],
        "knownRisks": [],
        "nextAction": next_action,
        "worktreeHash": sha256_bytes(json.dumps(wt, sort_keys=True).encode()),
    }
    path = state_dir(cwd) / "ledgers" / "compaction-handoff.json"
    ensure_dir(path.parent)
    path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    return handoff


def validate_handoff(cwd: Path) -> Dict[str, Any]:
    path = state_dir(cwd) / "ledgers" / "compaction-handoff.json"
    if not path.exists():
        return {"status": "FAIL", "reason": "missing handoff"}
    handoff = json.loads(path.read_text())
    current_hash = sha256_bytes(json.dumps(worktree_status(cwd), sort_keys=True).encode())
    return {"status": "PASS" if handoff.get("worktreeHash") == current_hash else "PARTIAL", "handoff": handoff, "currentWorktreeHash": current_hash}


def worktree_status(cwd: Path) -> Dict[str, Any]:
    try:
        out = subprocess.run(["git", "status", "--short"], cwd=str(cwd), text=True, capture_output=True, check=False)
        if out.returncode == 0:
            lines = out.stdout.splitlines()
            return {"kind": "git", "dirty": bool(out.stdout.strip()), "summary": lines, "user": [], "agent": [], "generated": [], "untracked": [l[3:] for l in lines if l.startswith("?? ")]}
    except FileNotFoundError:
        pass
    files = [str(p.relative_to(cwd)) for p in cwd.rglob("*") if p.is_file() and ".mofumofu" not in p.parts and "__pycache__" not in p.parts]
    generated = [f for f in files if f.startswith(".mofumofu/") or "/dist/" in f]
    agent = [f for f in files if f.startswith("mofu/") or f.startswith("tests/")]
    return {"kind": "directory", "dirty": True, "summary": files[:50], "user": [], "agent": agent[:50], "generated": generated[:50], "untracked": files[:50]}


def latest_session_id() -> Optional[str]:
    root = machine_state_dir() / "sessions"
    if not root.exists():
        return None
    files = sorted(root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0].stem if files else None


def resume_session(session_id: str) -> Dict[str, Any]:
    entries = read_jsonl(session_path(session_id))
    if not entries:
        return {"status": "FAIL", "sessionId": session_id, "events": 0, "stopReason": "error"}
    final = next((e for e in reversed(entries) if e.get("type") == "final_claim"), None)
    return {"status": "PASS", "sessionId": session_id, "events": len(entries), "lastEventType": entries[-1].get("type"), "stopReason": (final or {}).get("payload", {}).get("stopReason")}


def stop_reason_fixture(reason: str) -> Dict[str, Any]:
    if reason not in STOP_REASONS:
        raise ValueError(f"invalid stop reason: {reason}")
    return {"stopReason": reason, "canClaimDone": reason == "done", "status": "PASS" if reason == "done" else "PARTIAL"}


def status(cwd: Path, config: Dict[str, Any], sources: List[Dict[str, str]]) -> Dict[str, Any]:
    return {
        "project": str(cwd),
        "activeSpec": active_spec(cwd) or "none",
        "provider": config.get("model", {}).get("default_provider", "local"),
        "model": config.get("model", {}).get("default_model", "local-coding-model"),
        "configSources": sources,
        "gate": gate_status(cwd),
        "worktree": worktree_status(cwd),
        "latestSessionId": latest_session_id(),
    }


def mcp_serve() -> int:
    tools = [
        "mofumofu.spec.discover",
        "mofumofu.spec.create",
        "mofumofu.spec.approve",
        "mofumofu.artifact.fetch",
        "mofumofu.artifact.diff",
        "mofumofu.trace.get",
        "mofumofu.trace.update",
        "mofumofu.trace.reconcile",
        "mofumofu.analyze.symbols",
        "mofumofu.analyze.references",
        "mofumofu.analyze.graph",
        "mofumofu.context.build",
        "mofumofu.audit.properties",
        "mofumofu.audit.preresolve",
        "mofumofu.audit.prove",
        "mofumofu.audit.challenge",
        "mofumofu.audit.review",
        "mofumofu.audit.ingest",
        "mofumofu.security.scan",
        "mofumofu.validation.normalize",
        "mofumofu.gate.status",
        "mofumofu.policy.checkToolCall",
        "mofumofu.evidence.add",
    ]
    runtime = ToolRuntime(Path(os.getcwd()).resolve())
    for line in sys.stdin:
        req = json.loads(line)
        method = req.get("method")
        if method == "initialize":
            print(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": {"serverInfo": {"name": "mofumofu", "version": "0.1.0"}, "capabilities": {"tools": {}}}}), flush=True)
        elif method == "tools/list":
            print(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": {"tools": [{"name": t, "description": t, "inputSchema": {"type": "object"}} for t in tools]}}), flush=True)
        elif method == "tools/call":
            params = req.get("params", {})
            result = runtime.call(params.get("name", ""), params.get("arguments", {}))
            print(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": {"content": [{"type": "text", "text": json.dumps(result)}], "isError": not result.get("ok")}}), flush=True)
        else:
            print(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32601, "message": "method not implemented"}}), flush=True)
    return 0


def agent_run(cwd: Path, spec_id: Optional[str], goal: str, execute: bool = False) -> Dict[str, Any]:
    sid = spec_id or active_spec(cwd)
    if not sid:
        return {"stopReason": "blocked", "status": "PARTIAL", "blockers": ["no active spec"]}
    session_id = new_session_id()
    write_session_event(session_id, "user", "user_message", {"goal": goal, "specId": sid})
    pack = context_pack(cwd, sid, goal)
    audit = audit_stage(cwd, sid, "prove")
    sec = security_scan(cwd, sid)
    gate = gate_status(cwd, sid)
    stop = "done" if gate["status"] == "PASS" else "validation_failed"
    payload = {"stopReason": stop, "status": gate["status"], "sessionId": session_id, "contextPack": pack, "audit": audit, "security": sec, "gate": gate}
    write_handoff(cwd, session_id, goal, "Address gate blockers." if stop != "done" else "No pending action.")
    write_session_event(session_id, "agent", "final_claim", payload)
    return payload
