"""One JSON model call, shared by the classifier and the selector (step 4a)."""

import json
import time
from dataclasses import dataclass

from cta.index.embed import ApiError, with_retries
from cta.settings import cost_usd


@dataclass
class JsonCall:
    data: (
        dict | None
    )  # the parsed JSON object, None if the call failed or the reply was not a JSON object
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    ms: float = 0.0
    error: str | None = None  # why data is None


def json_call(client, cfg: dict, messages: list[dict], what: str) -> JsonCall:
    """Call the answer model with the router settings (temperature 0, reasoning off, JSON output).
    Never raises: a failed call or an unusable reply comes back with `data` None and an error."""
    r = cfg["router"]
    started = time.perf_counter()
    try:
        response = with_retries(
            lambda: client.chat.completions.create(
                model=cfg["chat_model"],
                messages=messages,
                temperature=r["temperature"],
                reasoning_effort=r["reasoning_effort"],
                max_completion_tokens=r["max_output_tokens"],
                response_format={"type": "json_object"},
            ),
            what,
        )
    except ApiError as e:
        return JsonCall(None, ms=(time.perf_counter() - started) * 1000, error=str(e))
    ms = (time.perf_counter() - started) * 1000
    usage = response.usage
    spent = cost_usd(cfg, cfg["chat_model"], usage.prompt_tokens, usage.completion_tokens)
    call = JsonCall(None, usage.prompt_tokens, usage.completion_tokens, spent, ms)
    try:
        data = json.loads(response.choices[0].message.content or "")
    except ValueError:
        call.error = "reply is not JSON"
        return call
    if not isinstance(data, dict):
        call.error = "reply is not a JSON object"
        return call
    call.data = data
    return call
