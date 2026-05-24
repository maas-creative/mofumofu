from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .core import *
from .pi_wrapper import run_agent, wrapper_status


class MofuParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        raise SystemExit(2)


def emit(data: Any, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif isinstance(data, dict):
        for key, value in data.items():
            print(f"{key}: {value}")
    elif isinstance(data, list):
        for item in data:
            print(item if isinstance(item, str) else json.dumps(item, ensure_ascii=False))
    else:
        print(data)


def build_parser() -> argparse.ArgumentParser:
    p = MofuParser(
        prog="mofu",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="mofumofu control plane for spec-led coding-agent work.",
        epilog="""common workflows:
  mofu init --json
  mofu provider list --json
  mofu spec status product-release-baseline --json
  mofu audit properties --spec product-release-baseline --json
  mofu security scan --spec product-release-baseline --json
  mofu gate status --spec product-release-baseline --json
  mofu agent --help

release rule:
  A task is complete only when trace, validation, audit, security, and gate evidence agree.
""",
    )
    p.add_argument("--cwd")
    p.add_argument("--config")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-color", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--version", action="store_true")
    sub = p.add_subparsers(dest="cmd", metavar="command")

    agent = sub.add_parser("agent", help="run the vendored pi coding-agent wrapper")
    agent.add_argument("agent_args", nargs=argparse.REMAINDER)

    run = sub.add_parser("run", help="execute a gated agent loop for a spec")
    run.add_argument("--spec")
    run.add_argument("--goal", default="")
    run.add_argument("--execute", action="store_true")

    wrapper = sub.add_parser("wrapper", help="inspect the pi coding-agent wrapper")
    wrappers = wrapper.add_subparsers(dest="subcmd")
    wrappers.add_parser("status")

    session = sub.add_parser("session", help="resume sessions and inspect stop reasons")
    sessions = session.add_subparsers(dest="subcmd")
    resume_s = sessions.add_parser("resume"); resume_s.add_argument("session_id")
    stop_s = sessions.add_parser("stop-reason"); stop_s.add_argument("reason")

    init = sub.add_parser("init", help="create .mofumofu project state")
    init.add_argument("--force", action="store_true")
    init.add_argument("--template", default="default")

    sub.add_parser("status", help="show project status")

    cfg = sub.add_parser("config", help="read and write machine/project config")
    cfgs = cfg.add_subparsers(dest="subcmd")
    get = cfgs.add_parser("get"); get.add_argument("key")
    setp = cfgs.add_parser("set"); setp.add_argument("key"); setp.add_argument("value"); setp.add_argument("--global", dest="global_", action="store_true"); setp.add_argument("--project", action="store_true")
    cfgs.add_parser("explain")

    prov = sub.add_parser("provider", help="list, probe, and E2E provider contracts")
    ps = prov.add_subparsers(dest="subcmd")
    ps.add_parser("list")
    probe = ps.add_parser("probe"); probe.add_argument("provider_id"); probe.add_argument("--model")
    pe = ps.add_parser("e2e"); pe.add_argument("--local-model"); pe.add_argument("--hosted-model")
    default = ps.add_parser("default"); default.add_argument("provider_id"); default.add_argument("--model"); default.add_argument("--global", dest="global_", action="store_true"); default.add_argument("--project", action="store_true")

    spec = sub.add_parser("spec", help="manage spec authority and approvals")
    ss = spec.add_subparsers(dest="subcmd")
    ss.add_parser("init")
    new = ss.add_parser("new"); new.add_argument("spec_id"); new.add_argument("--title")
    st = ss.add_parser("status"); st.add_argument("spec_id", nargs="?")
    app = ss.add_parser("approve"); app.add_argument("spec_id"); app.add_argument("--stage", required=True)
    act = ss.add_parser("active"); act.add_argument("spec_id")

    art = sub.add_parser("artifact", help="fetch, cache, and diff spec artifacts")
    arts = art.add_subparsers(dest="subcmd")
    fetch = arts.add_parser("fetch"); fetch.add_argument("url"); fetch.add_argument("--kind", required=True); fetch.add_argument("--spec")
    al = arts.add_parser("list"); al.add_argument("--spec")
    diff = arts.add_parser("diff"); diff.add_argument("artifact_id"); diff.add_argument("--against")

    trace = sub.add_parser("trace", help="maintain requirement-to-evidence trace links")
    ts = trace.add_subparsers(dest="subcmd")
    tg = ts.add_parser("get"); tg.add_argument("--spec")
    tu = ts.add_parser("update"); tu.add_argument("--from", dest="src", required=True); tu.add_argument("--to", dest="dst", required=True); tu.add_argument("--relation", required=True); tu.add_argument("--status", default="PARTIAL"); tu.add_argument("--spec")
    tr = ts.add_parser("reconcile"); tr.add_argument("--spec")

    an = sub.add_parser("analyze", help="inspect symbols, references, graph, and drift")
    ans = an.add_subparsers(dest="subcmd")
    sy = ans.add_parser("symbols"); sy.add_argument("--path", default=".")
    ref = ans.add_parser("references"); ref.add_argument("symbol")
    ans.add_parser("graph")
    dr = ans.add_parser("drift"); dr.add_argument("--spec")

    ctx = sub.add_parser("context", help="build deterministic context packs")
    cs = ctx.add_subparsers(dest="subcmd")
    pack = cs.add_parser("pack"); pack.add_argument("--spec", required=True); pack.add_argument("--goal", default="")
    ex = cs.add_parser("explain"); ex.add_argument("context_pack_id")
    trim = cs.add_parser("trim"); trim.add_argument("context_pack_id"); trim.add_argument("--max-tokens", type=int, required=True)

    audit = sub.add_parser("audit", help="run native spec-driven audit stages")
    aus = audit.add_subparsers(dest="subcmd")
    for name in ("properties", "preresolve", "prove", "challenge", "review"):
        x = aus.add_parser(name); x.add_argument("--spec", required=True)
    ae = aus.add_parser("provider-e2e"); ae.add_argument("--spec", required=True)
    ingest = aus.add_parser("ingest"); ingest.add_argument("finding_file"); ingest.add_argument("--spec", required=True)

    sec = sub.add_parser("security", help="run product and generated-code security checks")
    secs = sec.add_subparsers(dest="subcmd")
    sc = secs.add_parser("scan"); sc.add_argument("--spec")
    ge = secs.add_parser("generated-e2e"); ge.add_argument("--spec")
    secs.add_parser("risks")
    ar = secs.add_parser("accept-risk"); ar.add_argument("finding_id"); ar.add_argument("--reason", required=True); ar.add_argument("--expires")

    val = sub.add_parser("validation", help="normalize validation outputs into findings")
    vals = val.add_subparsers(dest="subcmd")
    vn = vals.add_parser("normalize"); vn.add_argument("source"); vn.add_argument("--raw-path"); vn.add_argument("--spec")

    gate = sub.add_parser("gate", help="evaluate completion gates")
    gs = gate.add_subparsers(dest="subcmd")
    for name in ("status", "explain"):
        x = gs.add_parser(name); x.add_argument("--spec")

    budget = sub.add_parser("budget", help="inspect and record budget ledger entries")
    bs = budget.add_subparsers(dest="subcmd")
    bs.add_parser("status"); bs.add_parser("explain")
    bu = bs.add_parser("record"); bu.add_argument("--tokens", type=int, default=0); bu.add_argument("--cost-usd", type=float, default=0); bu.add_argument("--event", default="usage")

    compact = sub.add_parser("compact", help="write and validate compaction handoff state")
    comps = compact.add_subparsers(dest="subcmd")
    cw = comps.add_parser("write"); cw.add_argument("--session-id", default=""); cw.add_argument("--goal", default=""); cw.add_argument("--next-action", default="")
    comps.add_parser("validate")

    memory = sub.add_parser("memory", help="record architecture decisions")
    mems = memory.add_subparsers(dest="subcmd")
    md = mems.add_parser("decide"); md.add_argument("decision"); md.add_argument("--rationale", required=True); md.add_argument("--scope", default="project")
    mems.add_parser("list")

    fact = sub.add_parser("fact", help="record and inspect fact freshness")
    facts = fact.add_subparsers(dest="subcmd")
    fr = facts.add_parser("record"); fr.add_argument("claim"); fr.add_argument("--source", required=True); fr.add_argument("--freshness", default="current")
    facts.add_parser("status")

    wt = sub.add_parser("worktree", help="summarize changed worktree files")
    wts = wt.add_subparsers(dest="subcmd")
    wts.add_parser("status")

    mcp = sub.add_parser("mcp", help="serve MCP stdio tool contracts")
    ms = mcp.add_subparsers(dest="subcmd")
    serve = ms.add_parser("serve"); serve.add_argument("--stdio", action="store_true")
    return p


def main(argv: Any = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if "agent" in argv:
        agent_index = argv.index("agent")
        before = argv[:agent_index]
        after = argv[agent_index + 1 :]
        cwd_value = None
        i = 0
        while i < len(before):
            if before[i] == "--cwd" and i + 1 < len(before):
                cwd_value = before[i + 1]
                i += 2
            else:
                i += 1
        return run_agent(after, str(project_root(cwd_value)))
    leading_flags = []
    normalize_global_flags = "agent" not in argv
    for flag in ("--json", "--no-color", "--verbose", "--dry-run"):
        if normalize_global_flags and flag in argv:
            leading_flags.append(flag)
            argv = [item for item in argv if item != flag]
    late_json = "--json" in leading_flags
    late_verbose = "--verbose" in leading_flags
    late_dry = "--dry-run" in leading_flags
    argv = leading_flags + argv
    parser = build_parser()
    args = parser.parse_args(argv)
    args.json = args.json or late_json
    args.verbose = args.verbose or late_verbose
    args.dry_run = args.dry_run or late_dry
    if args.version:
        print(__version__)
        return 0
    cwd = project_root(args.cwd)
    cfg, sources = effective_config(cwd, Path(args.config).expanduser() if args.config else None)
    try:
        if args.cmd == "init":
            if args.dry_run:
                emit([".mofumofu/config.toml", ".mofumofu/policy.toml", ".mofumofu/steering/product.md"], args.json)
            else:
                emit({"changedPaths": init_project(cwd, args.force), "status": "PASS"}, args.json)
        elif args.cmd == "status":
            emit(status(cwd, cfg, sources), args.json)
        elif args.cmd == "wrapper":
            emit(wrapper_status(), args.json)
        elif args.cmd == "session":
            if args.subcmd == "resume":
                emit(resume_session(args.session_id), args.json)
            elif args.subcmd == "stop-reason":
                emit(stop_reason_fixture(args.reason), args.json)
        elif args.cmd == "agent":
            return run_agent(args.agent_args, str(cwd))
        elif args.cmd == "run":
            emit(agent_run(cwd, args.spec, args.goal, args.execute), args.json)
        elif args.cmd == "config":
            if args.subcmd == "get":
                emit(get_config_value(cfg, args.key), args.json)
            elif args.subcmd == "set":
                target = machine_config_dir() / "config.toml" if args.global_ else state_dir(cwd) / "config.toml"
                set_config_value(target, args.key, args.value)
                emit({"changedPaths": [str(target)], "status": "PASS"}, args.json)
            elif args.subcmd == "explain":
                emit({"effective": cfg, "sources": sources}, args.json)
        elif args.cmd == "provider":
            if args.subcmd == "list":
                emit(providers(), args.json)
            elif args.subcmd == "probe":
                emit(provider_probe(cwd, args.provider_id, args.model), args.json)
            elif args.subcmd == "e2e":
                emit(provider_e2e(cwd, args.local_model, args.hosted_model), args.json)
            elif args.subcmd == "default":
                target = machine_config_dir() / "config.toml" if args.global_ else state_dir(cwd) / "config.toml"
                set_config_value(target, "model.default_provider", args.provider_id)
                if args.model:
                    set_config_value(target, "model.default_model", args.model)
                emit({"changedPaths": [str(target)], "status": "PASS"}, args.json)
        elif args.cmd == "spec":
            if args.subcmd == "init":
                emit({"changedPaths": init_project(cwd), "status": "PASS"}, args.json)
            elif args.subcmd == "new":
                emit({"specId": args.spec_id, "createdPaths": spec_new(cwd, args.spec_id, args.title or args.spec_id)}, args.json)
            elif args.subcmd == "status":
                emit(spec_status(cwd, args.spec_id), args.json)
            elif args.subcmd == "approve":
                emit(approve_spec(cwd, args.spec_id, args.stage), args.json)
            elif args.subcmd == "active":
                write_active_spec(cwd, args.spec_id); emit({"activeSpec": args.spec_id, "status": "PASS"}, args.json)
        elif args.cmd == "artifact":
            sid = getattr(args, "spec", None) or active_spec(cwd)
            if args.subcmd == "fetch":
                emit(artifact_fetch(cwd, sid, args.url, args.kind), args.json)
            elif args.subcmd == "list":
                emit(artifact_list(cwd, args.spec), args.json)
            elif args.subcmd == "diff":
                emit(artifact_diff(cwd, args.artifact_id, args.against), args.json)
        elif args.cmd == "trace":
            sid = getattr(args, "spec", None) or active_spec(cwd)
            if args.subcmd == "get":
                emit(read_trace(cwd, sid), args.json)
            elif args.subcmd == "update":
                emit(trace_update(cwd, sid, args.src, args.dst, args.relation, args.status), args.json)
            elif args.subcmd == "reconcile":
                emit(reconcile_trace(cwd, sid), args.json)
        elif args.cmd == "analyze":
            if args.subcmd == "symbols":
                emit(analyze_symbols(cwd, args.path), args.json)
            elif args.subcmd == "references":
                emit(analyze_references(cwd, args.symbol), args.json)
            elif args.subcmd in ("graph", "drift"):
                emit(analyze_graph(cwd), args.json)
        elif args.cmd == "context":
            if args.subcmd == "pack":
                emit(context_pack(cwd, args.spec, args.goal), args.json)
            else:
                emit({"status": "PASS", "contextPackId": args.context_pack_id}, args.json)
        elif args.cmd == "audit":
            if args.subcmd == "properties":
                emit(audit_properties(cwd, args.spec), args.json)
            elif args.subcmd == "provider-e2e":
                emit(audit_provider_e2e(cwd, args.spec), args.json)
            else:
                emit(audit_stage(cwd, args.spec, args.subcmd), args.json)
        elif args.cmd == "security":
            if args.subcmd == "scan":
                emit(security_scan(cwd, args.spec), args.json)
            elif args.subcmd == "generated-e2e":
                emit(generated_security_e2e(cwd, args.spec), args.json)
            elif args.subcmd == "risks":
                emit([], args.json)
            elif args.subcmd == "accept-risk":
                emit({"status": "PASS", "risk": args.finding_id, "reason": args.reason, "expires": args.expires}, args.json)
        elif args.cmd == "validation":
            if args.subcmd == "normalize":
                emit(validation_normalize(cwd, args.spec or active_spec(cwd), args.source, args.raw_path), args.json)
        elif args.cmd == "gate":
            emit(gate_status(cwd, args.spec), args.json)
        elif args.cmd == "budget":
            if args.subcmd == "record":
                emit(record_budget(cwd, args.tokens, args.cost_usd, args.event), args.json)
            else:
                emit(budget_status(cwd), args.json)
        elif args.cmd == "compact":
            if args.subcmd == "write":
                emit(write_handoff(cwd, args.session_id, args.goal, args.next_action), args.json)
            elif args.subcmd == "validate":
                emit(validate_handoff(cwd), args.json)
        elif args.cmd == "memory":
            if args.subcmd == "decide":
                emit(memory_decide(cwd, args.decision, args.rationale, args.scope), args.json)
            elif args.subcmd == "list":
                emit(memory_list(cwd), args.json)
        elif args.cmd == "fact":
            if args.subcmd == "record":
                emit(record_fact(cwd, args.claim, args.source, args.freshness), args.json)
            elif args.subcmd == "status":
                emit(facts_status(cwd), args.json)
        elif args.cmd == "worktree":
            emit(worktree_status(cwd), args.json)
        elif args.cmd == "mcp" and args.subcmd == "serve":
            return mcp_serve()
        else:
            parser.print_help()
            return 2
        return 0
    except KeyError as exc:
        print(f"mofu: missing config key {exc}", file=sys.stderr)
        return 2
    except PermissionError as exc:
        print(f"mofu: permission denied: {exc}", file=sys.stderr)
        return 4
    except Exception as exc:
        if args.verbose:
            raise
        print(f"mofu: error: {redact(str(exc))}", file=sys.stderr)
        return 1
