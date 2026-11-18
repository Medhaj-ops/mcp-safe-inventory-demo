"""Same agent loop on the OpenAI Chat Completions API, for comparing providers."""

from __future__ import annotations

import json
import os

from evals.agents.anthropic_agent import SYSTEM_PROMPT
from evals.env import TOOL_SPECS, Environment

OPENAI_TOOLS = [
    {"type": "function", "function": {"name": t["name"], "description": t["description"],
                                      "parameters": t["input_schema"]}}
    for t in TOOL_SPECS
]


class OpenAIAgent:
    def __init__(self, model: str, max_turns: int = 15, client=None, system_prompt: str | None = None):
        if client is None:
            import openai
            client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.client = client
        self.model = model
        self.max_turns = max_turns
        self.system_prompt = system_prompt or SYSTEM_PROMPT
        self.name = f"openai:{model}"

    def run(self, env: Environment) -> None:
        messages = [{"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": env.task.prompt}]
        for _ in range(self.max_turns):
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, tools=OPENAI_TOOLS)
            msg = response.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))
            if not msg.tool_calls:
                return
            for call in msg.tool_calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = env.call(call.function.name, args)
                messages.append({"role": "tool", "tool_call_id": call.id,
                                 "content": json.dumps(result, default=str)})
        raise RuntimeError(f"agent did not finish within {self.max_turns} turns")
