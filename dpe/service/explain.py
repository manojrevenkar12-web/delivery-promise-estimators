"""Why the roster says what it says, for a hub lead.

Code decides the facts: how many drivers are needed, how many to ask, how many are expected to come, and which
features pull the show probabilities down, straight from the trees (XGBoost `pred_contribs`). A language model
may only re-word those facts. Its text is accepted if every number in it is one of the facts' numbers;
otherwise the plain template is used (`tests/test_service.py`).
"""
from __future__ import annotations

import json
import os
import re
from typing import Protocol

import numpy as np
import pandas as pd

LABELS = {
    "hub_absence_7": "absences across the hub in the last 7 days",
    "hub_absence_2": "absences across the hub in the last 2 days",
    "driver_absence": "these drivers' own absences in the last 4 weeks",
    "driver_shifts": "how often these drivers worked recently",
    "new": "drivers in their first weeks",
    "tenure": "time with the company",
    "weekday": "the day of the week",
    "late": "the late shift",
    "rain_p": "rain in the forecast",
    "temp": "the temperature",
}


def roster_facts(contrib: pd.DataFrame, p: np.ndarray, needed: int, asked: int, quantile: float | None,
                 planned: float) -> dict:
    mean = contrib.drop(columns=["bias"]).iloc[:asked].mean()
    lowers = mean[mean < -0.05].sort_values().head(3)
    raises = mean[mean > 0.05].sort_values(ascending=False).head(2)
    return {
        "needed": int(needed), "asked": int(asked), "expected_shows": round(float(p[:asked].sum()), 1),
        "planned_shows": round(float(planned), 1),
        "percentile": None if quantile is None else round(quantile * 100),
        "unlikely_drivers": int((p[:asked] < 0.8).sum()),
        "lowers": [LABELS.get(k, k) for k in lowers.index], "raises": [LABELS.get(k, k) for k in raises.index],
    }


def template(f: dict) -> str:
    plan = (f"plans for {f['planned_shows']} (the {f['percentile']}th percentile)" if f["percentile"] is not None
            else f"plans for the expected {f['expected_shows']}")
    s = (f"Ask {f['asked']} drivers to have {f['needed']} on the road: {f['expected_shows']} are expected to come, "
         f"and the roster {plan}.")
    if f["lowers"]:
        s += " Fewer are likely to come because of " + _join(f["lowers"]) + "."
    if f["unlikely_drivers"]:
        s += f" {f['unlikely_drivers']} of those asked are less than 80% likely to come."
    return s


def _join(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


class Phraser(Protocol):
    def __call__(self, facts: dict) -> str | None: ...


def numbers(text: str) -> set[str]:
    return {n.rstrip(".") for n in re.findall(r"\d+(?:\.\d+)?", text)}


def phrase(facts: dict, phraser: Phraser | None = None) -> tuple[str, str]:
    """(text, source). The model's text is used only if it adds no number the facts do not hold."""
    base = template(facts)
    if phraser is None:
        return base, "template"
    try:
        text = phraser(facts)
    except Exception:
        return base, "template"
    if not text or not numbers(text) <= numbers(json.dumps(facts)) | numbers(base):
        return base, "template"
    return text.strip(), "model"


def claude_phraser() -> Phraser | None:
    """Re-words the facts for a hub lead with Claude, if an API key is configured; otherwise None."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    import httpx

    def call(facts: dict) -> str | None:
        prompt = ("Rewrite these roster facts as two short sentences for a delivery hub lead. Use only these "
                  "numbers and do not add any: " + json.dumps(facts))
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=10,
                       headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                       json={"model": os.environ.get("DPE_EXPLAIN_MODEL", "claude-haiku-5-5"), "max_tokens": 200,
                             "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))

    return call
