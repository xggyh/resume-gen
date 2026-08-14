"""Anthropic client wrapper.

Key choices:
- Structured output is enforced via tool_use with `tool_choice={"type":"tool"}`,
  which is more reliable than asking the model to emit JSON.
- The same system prompt is reused across many calls in one run, so we mark it
  cache_control=ephemeral to amortize cost.
- `model_heavy` is used for creative rewriting; `model_light` for parsing /
  classification / scoring where latency and cost matter.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional, Type, TypeVar

from anthropic import Anthropic
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


DEFAULT_HEAVY = "claude-opus-4-7"
DEFAULT_LIGHT = "claude-sonnet-4-6"


@dataclass
class LLM:
    client: Anthropic
    model_heavy: str
    model_light: str

    # -- raw text ----------------------------------------------------------

    def chat(
        self,
        *,
        system: str,
        user: str,
        heavy: bool = False,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        cache_system: bool = True,
    ) -> str:
        """Plain text completion. Use sparingly; prefer structured()."""
        model = self.model_heavy if heavy else self.model_light
        system_blocks: list[dict[str, Any]] = [{"type": "text", "text": system}]
        if cache_system:
            system_blocks[0]["cache_control"] = {"type": "ephemeral"}
        resp = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_blocks,
            messages=[{"role": "user", "content": user}],
        )
        return _join_text(resp.content)

    # -- structured (Pydantic) --------------------------------------------

    def structured(
        self,
        *,
        schema: Type[T],
        system: str,
        user: str,
        tool_name: str = "emit",
        tool_description: str = "Emit the structured result.",
        heavy: bool = False,
        max_tokens: int = 8192,
        temperature: float = 0.2,
        cache_system: bool = True,
    ) -> T:
        """Return a pydantic instance of `schema`, forced via tool_use."""
        model = self.model_heavy if heavy else self.model_light
        tool = {
            "name": tool_name,
            "description": tool_description,
            "input_schema": _pydantic_input_schema(schema),
        }
        system_blocks: list[dict[str, Any]] = [{"type": "text", "text": system}]
        if cache_system:
            system_blocks[0]["cache_control"] = {"type": "ephemeral"}

        resp = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_blocks,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": user}],
        )

        for block in resp.content:
            if block.type == "tool_use" and block.name == tool_name:
                return schema.model_validate(block.input)

        raise RuntimeError(
            f"Model did not return tool_use for '{tool_name}'. "
            f"Text was: {_join_text(resp.content)[:500]}"
        )


def _join_text(blocks: list[Any]) -> str:
    parts: list[str] = []
    for b in blocks:
        if getattr(b, "type", None) == "text":
            parts.append(b.text)
    return "\n".join(parts)


def _pydantic_input_schema(schema: Type[BaseModel]) -> dict[str, Any]:
    """Pydantic v2 JSON schema, inlined (no $ref) so Anthropic tool_use accepts it cleanly."""
    raw = schema.model_json_schema(mode="serialization")
    return _inline_refs(raw)


def _inline_refs(schema: dict) -> dict:
    """Resolve all internal $ref pointers. Anthropic tool schemas don't deref."""
    defs = schema.get("$defs", {}) or schema.get("definitions", {}) or {}

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                key = ref.rsplit("/", 1)[-1]
                if key in defs:
                    return resolve(defs[key])
            return {k: resolve(v) for k, v in node.items() if k not in ("$defs", "definitions")}
        if isinstance(node, list):
            return [resolve(x) for x in node]
        return node

    resolved = resolve(schema)
    if isinstance(resolved, dict):
        resolved.pop("$defs", None)
        resolved.pop("definitions", None)
    return resolved


def get_llm() -> LLM:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in, "
            "or export the variable in your shell."
        )
    return LLM(
        client=Anthropic(api_key=api_key),
        model_heavy=os.environ.get("RESUME_GEN_MODEL_HEAVY", DEFAULT_HEAVY),
        model_light=os.environ.get("RESUME_GEN_MODEL_LIGHT", DEFAULT_LIGHT),
    )
