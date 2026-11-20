#!/usr/bin/env python3
"""Behavior eval runner for skill, agent and CLI contracts.

Unit tests protect deterministic Python logic. These evals protect the layer
above it: required prompt steps, step ordering, forbidden shortcuts, subagent
permissions and the review-result CLI contract. A skill edit that quietly
drops a gate should fail here.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "skill-eval-report/v1"
DEFAULT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVALS_DIR = DEFAULT_ROOT / "tests" / "evals"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    result: dict[str, str] = {}
    for line in text[4:end].splitlines():
        key, separator, value = line.partition(":")
        if separator:
            result[key.strip()] = value.strip()
    return result


def make_result(
    case: dict[str, Any],
    *,
    passed: bool,
    reason: str,
    evidence: list[str] | None = None,
    duration_ms: int = 0,
) -> dict[str, Any]:
    return {
        "id": case.get("id", "unnamed"),
        "type": case.get("type", ""),
        "passed": passed,
        "reason": reason,
        "evidence": evidence or [],
        "duration_ms": duration_ms,
    }


def tokens_for(root: Path, evals_dir: Path, tmp: Path) -> dict[str, str]:
    return {
        "root": str(root),
        "fixtures": str(evals_dir / "fixtures"),
        "tmp": str(tmp),
        "python": sys.executable,
    }


def substitute(value: Any, tokens: dict[str, str]) -> Any:
    if isinstance(value, str):
        result = value
        for key, replacement in tokens.items():
            result = result.replace("{" + key + "}", replacement)
        return result
    if isinstance(value, list):
        return [substitute(item, tokens) for item in value]
    if isinstance(value, dict):
        return {key: substitute(item, tokens) for key, item in value.items()}
    return value


# ---------------------------------------------------------------------------
# Case types
# ---------------------------------------------------------------------------


def eval_frontmatter_glob(case: dict[str, Any], root: Path) -> dict[str, Any]:
    pattern = str(case.get("glob") or "skills/*/SKILL.md")
    min_count = int(case.get("min_count", 1))
    required_keys = [str(key) for key in case.get("required_keys") or ["name", "description"]]
    paths = sorted(root.glob(pattern))
    if len(paths) < min_count:
        return make_result(
            case,
            passed=False,
            reason=f"matched {len(paths)} files, expected >= {min_count}",
            evidence=[str(path.relative_to(root)) for path in paths],
        )

    problems: list[str] = []
    names: list[str] = []
    for path in paths:
        rel = str(path.relative_to(root))
        fm = frontmatter(read_text(path))
        missing = [key for key in required_keys if not fm.get(key)]
        if missing:
            problems.append(f"{rel}: missing {', '.join(missing)}")
        if "name" in required_keys and fm.get("name"):
            names.append(fm["name"])
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        problems.append(f"duplicate names: {', '.join(duplicates)}")

    return make_result(
        case,
        passed=not problems,
        reason="frontmatter contract ok" if not problems else "frontmatter contract violations",
        evidence=problems,
    )


def eval_agent_frontmatter(case: dict[str, Any], root: Path) -> dict[str, Any]:
    directory = root / str(case.get("dir") or "agents")
    required_agents = [str(name) for name in case.get("required_agents") or []]
    forbidden_tools = [str(name) for name in case.get("forbidden_tools") or ["Write", "Edit"]]
    problems: list[str] = []

    if not directory.is_dir():
        return make_result(case, passed=False, reason=f"agent dir missing: {directory}")

    for agent in required_agents:
        path = directory / f"{agent}.md"
        if not path.is_file():
            problems.append(f"{agent}: file missing")
            continue
        fm = frontmatter(read_text(path))
        for key in ("name", "description", "tools"):
            if not fm.get(key):
                problems.append(f"{agent}: missing frontmatter {key}")
        if fm.get("name") and fm["name"] != agent:
            problems.append(f"{agent}: name mismatch ({fm['name']})")
        tools = fm.get("tools", "")
        for tool in forbidden_tools:
            if tool in tools:
                problems.append(f"{agent}: forbidden tool {tool}")

    return make_result(
        case,
        passed=not problems,
        reason="agent contract ok" if not problems else "agent contract violations",
        evidence=problems,
    )


def eval_text_contract(case: dict[str, Any], root: Path) -> dict[str, Any]:
    target = root / str(case.get("path") or "")
    if not target.is_file():
        return make_result(case, passed=False, reason=f"file missing: {target}")

    text = read_text(target)
    problems: list[str] = []

    for item in case.get("required") or []:
        if str(item) not in text:
            problems.append(f"missing required text: {item}")

    for group in case.get("required_any") or []:
        options = [str(option) for option in group]
        if options and not any(option in text for option in options):
            problems.append("missing one of: " + " | ".join(options))

    for pair in case.get("ordered") or []:
        if not isinstance(pair, list) or len(pair) != 2:
            problems.append(f"invalid ordered pair: {pair}")
            continue
        left, right = str(pair[0]), str(pair[1])
        left_pos = text.find(left)
        right_pos = text.find(right)
        if left_pos == -1:
            problems.append(f"ordered left missing: {left}")
        elif right_pos == -1:
            problems.append(f"ordered right missing: {right}")
        elif left_pos >= right_pos:
            problems.append(f"out of order: {left} should appear before {right}")

    for item in case.get("forbidden") or []:
        if str(item) in text:
            problems.append(f"forbidden text found: {item}")

    min_length = case.get("min_length")
    if isinstance(min_length, int) and len(text) < min_length:
        problems.append(f"text too short: {len(text)} < {min_length}")

    return make_result(
        case,
        passed=not problems,
        reason="text contract ok" if not problems else "text contract violations",
        evidence=problems,
    )


def _tail(value: str, limit: int = 1200) -> str:
    return value if len(value) <= limit else "…" + value[-limit:]


def eval_command_sequence(
    case: dict[str, Any],
    root: Path,
    evals_dir: Path,
) -> dict[str, Any]:
    steps = case.get("steps")
    if not isinstance(steps, list) or not steps:
        return make_result(case, passed=False, reason="command_sequence requires steps")

    evidence: list[str] = []
    with tempfile.TemporaryDirectory(prefix="novel-eval-") as tmp:
        tokens = tokens_for(root, evals_dir, Path(tmp))
        for index, raw_step in enumerate(steps, 1):
            if not isinstance(raw_step, dict):
                return make_result(
                    case, passed=False, reason=f"step {index} is not an object", evidence=evidence
                )
            step = substitute(raw_step, tokens)
            args = [str(item) for item in step.get("args") or []]
            if not args:
                return make_result(
                    case, passed=False, reason=f"step {index} has no args", evidence=evidence
                )

            expected_exit = int(step.get("expect_exit", 0))
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env.update({str(key): str(value) for key, value in (step.get("env") or {}).items()})
            try:
                completed = subprocess.run(
                    args,
                    cwd=root,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    env=env,
                    timeout=float(step.get("timeout", 60)),
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return make_result(
                    case,
                    passed=False,
                    reason=f"step {index} failed to run: {exc}",
                    evidence=evidence,
                )

            command_label = " ".join(args)
            if completed.returncode != expected_exit:
                evidence.append(f"step {index}: {command_label}")
                evidence.append(f"  exit {completed.returncode}, expected {expected_exit}")
                evidence.append(f"  stdout: {_tail(completed.stdout)}")
                evidence.append(f"  stderr: {_tail(completed.stderr)}")
                return make_result(
                    case,
                    passed=False,
                    reason=f"step {index} exit code mismatch",
                    evidence=evidence,
                )

            for expected in step.get("stdout_contains") or []:
                if str(expected) not in completed.stdout:
                    evidence.append(f"step {index}: stdout missing {expected!r}")
                    evidence.append(f"  stdout: {_tail(completed.stdout)}")
                    return make_result(
                        case,
                        passed=False,
                        reason=f"step {index} stdout assertion failed",
                        evidence=evidence,
                    )

            for expected in step.get("stderr_contains") or []:
                if str(expected) not in completed.stderr:
                    evidence.append(f"step {index}: stderr missing {expected!r}")
                    evidence.append(f"  stderr: {_tail(completed.stderr)}")
                    return make_result(
                        case,
                        passed=False,
                        reason=f"step {index} stderr assertion failed",
                        evidence=evidence,
                    )

            for expected_file in step.get("expect_files") or []:
                path = Path(str(expected_file))
                if not path.is_file():
                    evidence.append(f"step {index}: expected file missing: {path}")
                    return make_result(
                        case,
                        passed=False,
                        reason=f"step {index} artifact assertion failed",
                        evidence=evidence,
                    )
                evidence.append(f"step {index}: created {path}")

            evidence.append(f"step {index}: ok — {command_label}")

    return make_result(
        case,
        passed=True,
        reason=f"{len(steps)} command steps passed",
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

CASE_RUNNERS = {
    "frontmatter_glob": lambda case, root, evals_dir: eval_frontmatter_glob(case, root),
    "agent_frontmatter": lambda case, root, evals_dir: eval_agent_frontmatter(case, root),
    "text_contract": lambda case, root, evals_dir: eval_text_contract(case, root),
    "command_sequence": lambda case, root, evals_dir: eval_command_sequence(case, root, evals_dir),
}


def load_cases(evals_dir: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(evals_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        file_cases = payload.get("cases") if isinstance(payload, dict) else payload
        if not isinstance(file_cases, list):
            raise ValueError(f"{path}: expected a JSON object with a cases array")
        for index, case in enumerate(file_cases, 1):
            if not isinstance(case, dict):
                raise ValueError(f"{path}: case #{index} is not an object")
            case.setdefault("id", f"{path.stem}-{index}")
            case.setdefault("__source", str(path.relative_to(evals_dir.parents[1])))
            cases.append(case)
    return cases


def run(evals_dir: Path, root: Path) -> dict[str, Any]:
    cases = load_cases(evals_dir)
    results: list[dict[str, Any]] = []
    for case in cases:
        started = time.perf_counter()
        case_type = str(case.get("type") or "")
        runner = CASE_RUNNERS.get(case_type)
        if runner is None:
            result = make_result(
                case,
                passed=False,
                reason=f"unknown case type: {case_type}",
            )
        else:
            try:
                result = runner(case, root, evals_dir)
            except Exception as exc:  # noqa: BLE001 - eval runner must report, not crash
                result = make_result(
                    case,
                    passed=False,
                    reason=f"runner error: {type(exc).__name__}: {exc}",
                )
        result["duration_ms"] = round((time.perf_counter() - started) * 1000)
        result["source"] = case.get("__source", "")
        results.append(result)

    passed = sum(1 for item in results if item["passed"])
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "evals_dir": str(evals_dir),
        "summary": {
            "cases": len(results),
            "passed": passed,
            "failed": len(results) - passed,
        },
        "results": results,
    }
    return report


def print_report(report: dict[str, Any], *, verbose: bool) -> None:
    for item in report["results"]:
        status = "PASS" if item["passed"] else "FAIL"
        print(f"[{status}] {item['id']} ({item['type']}) — {item['reason']}")
        if verbose or not item["passed"]:
            for line in item["evidence"]:
                print(f"  {line}")
    summary = report["summary"]
    print(
        f"\ncases={summary['cases']} passed={summary['passed']} failed={summary['failed']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="运行技能、子代理与 CLI 行为评测")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="插件仓库根目录")
    parser.add_argument("--evals-dir", default=str(DEFAULT_EVALS_DIR), help="评测用例目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    parser.add_argument("--report", default="", help="把 JSON 报告写入文件")
    parser.add_argument("--verbose", action="store_true", help="打印全部证据")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    evals_dir = Path(args.evals_dir)
    if not evals_dir.is_absolute():
        evals_dir = root / evals_dir

    report = run(evals_dir, root)
    if args.report:
        output = Path(args.report)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if not args.json:
            print(f"[OK] 评测报告已写入: {output}")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report, verbose=args.verbose)
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
