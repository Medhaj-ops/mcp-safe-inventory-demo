"""
Run the eval suite.

    python -m evals.run --agent oracle                      # no API key needed
    python -m evals.run --agent anthropic --model claude-sonnet-5-5 --trials 3 --ablations
    python -m evals.run --agent openai --model gpt-5-mini --trials 3 --ablations

    # iterate on the agent: same suite, a changed system prompt, a tagged result file
    python -m evals.run --agent anthropic --model claude-sonnet-5-5 --trials 3 --prompt prompts/v2.txt --tag v2

--ablations runs three configurations of the same server:
    baseline       everything on (production config)
    bare_errors    errors are bare codes, with no "what to do next"
    no_approval    valid drafts commit without asking the human

Writes evals/results/<agent>.json (every trial, with full transcripts)
and evals/results/<agent>.md (the summary tables). --update-readme also
pastes the summary into README.md between the EVAL_RESULTS markers.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from evals.env import Environment
from evals.graders import TrialResult, grade
from evals.report import render_markdown, summarize
from evals.tasks import TASKS
from safety import audit

CONFIGS = {
    "baseline": {"require_approval": True, "actionable_errors": True},
    "bare_errors": {"require_approval": True, "actionable_errors": False},
    "no_approval": {"require_approval": False, "actionable_errors": True},
}

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "evals" / "results"


def make_agent(name: str, model: str | None, system_prompt: str | None = None):
    if name == "oracle":
        from evals.agents.oracle import OracleAgent
        return OracleAgent()
    if not model:
        raise SystemExit("--model is required for LLM agents")
    if name == "anthropic":
        from evals.agents.anthropic_agent import AnthropicAgent
        return AnthropicAgent(model, system_prompt=system_prompt)
    if name == "openai":
        from evals.agents.openai_agent import OpenAIAgent
        return OpenAIAgent(model, system_prompt=system_prompt)
    raise SystemExit(f"unknown agent {name}")


def run_config(agent, config: dict, trials: int, task_filter: str | None, log) -> list[dict]:
    rows = []
    tasks = [t for t in TASKS if not task_filter or task_filter in t.id or task_filter == t.category]
    for task in tasks:
        for trial in range(trials):
            env = Environment(task, **config)
            error = None
            try:
                agent.run(env)
            except Exception as e:  # an agent crash is a failed trial, not a crashed eval
                error = f"{type(e).__name__}: {e}"
            finally:
                env.close()
            result: TrialResult = grade(env, error)
            log(f"  {task.id:<26} trial {trial + 1}: {'PASS' if result.passed else 'FAIL'}")
            rows.append({**result.to_dict(), "trial": trial, "transcript": env.transcript(),
                         "final_reply": env.final_reply})
    return rows


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--agent", default="oracle", choices=["oracle", "anthropic", "openai"])
    p.add_argument("--model")
    p.add_argument("--trials", type=int, default=1)
    p.add_argument("--ablations", action="store_true", help="also run bare_errors and no_approval")
    p.add_argument("--tasks", help="only tasks whose id contains this, or a category name")
    p.add_argument("--prompt", help="file with a system prompt to use instead of the default")
    p.add_argument("--tag", help="label for this run, added to the result file names")
    p.add_argument("--update-readme", action="store_true")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    audit.ECHO = False
    log = (lambda *_: None) if args.quiet else print
    system_prompt = Path(args.prompt).read_text() if args.prompt else None
    agent = make_agent(args.agent, args.model, system_prompt)
    if args.tag:
        agent.name = f"{agent.name}@{args.tag}"
    configs = list(CONFIGS) if args.ablations else ["baseline"]

    started = time.time()
    all_rows: dict[str, list[dict]] = {}
    for name in configs:
        log(f"[{name}]")
        all_rows[name] = run_config(agent, CONFIGS[name], args.trials, args.tasks, log)

    meta = {
        "agent": agent.name,
        "trials": args.trials,
        "configs": configs,
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seconds": round(time.time() - started, 1),
    }
    summaries = {name: summarize(rows, args.trials) for name, rows in all_rows.items()}
    markdown = render_markdown(meta, summaries)

    RESULTS.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9.-]+", "_", agent.name)
    (RESULTS / f"{slug}.json").write_text(json.dumps({"meta": meta, "summaries": summaries,
                                                      "trials": all_rows}, indent=2))
    (RESULTS / f"{slug}.md").write_text(markdown)
    print(markdown)

    if args.update_readme:
        readme = ROOT / "README.md"
        text = readme.read_text()
        start, end = "<!-- EVAL_RESULTS_START -->", "<!-- EVAL_RESULTS_END -->"
        if start in text and end in text:
            before, rest = text.split(start, 1)
            _, after = rest.split(end, 1)
            readme.write_text(f"{before}{start}\n{markdown}\n{end}{after}")
            print("README.md updated.")


if __name__ == "__main__":
    main()
