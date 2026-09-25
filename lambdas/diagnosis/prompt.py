"""Prompt construction for grounded diagnosis with Bedrock RetrieveAndGenerate."""

from __future__ import annotations

from common.features import power_watts

FAILURE_NAMES = {
    "TWF": "tool wear failure",
    "HDF": "heat dissipation failure",
    "PWF": "power failure",
    "OSF": "overstrain failure",
}

NO_CONTEXT_MARKER = "INSUFFICIENT MANUAL CONTEXT"

# $search_results$ and $output_format_instructions$ are filled in by Bedrock; the latter is what
# makes the service return citations. Kept deliberately plain: asking Llama 3 for markdown headings
# on top of Bedrock's citation markup made the response unparseable ("unable to assist").
PROMPT_TEMPLATE = (
    "You are a maintenance engineer assistant. Answer the question using ONLY the maintenance manual "
    "excerpts below. Never invent procedures or limits. Cite manual section numbers (e.g. HDF-MAN Section 5.2). "
    "Cover: likely cause, evidence from the readings, numbered steps to fix, safety warnings. "
    f"If the excerpts do not cover this failure, say {NO_CONTEXT_MARKER}.\n\n"
    "$search_results$\n\n$output_format_instructions$"
)


def build_query(reading: dict, prediction: dict) -> str:
    """Natural-language query that carries both the retrieval intent and the evidence."""
    failure = prediction["failure_type"]
    temp_diff = reading["process_temp_k"] - reading["air_temp_k"]
    power = power_watts(reading["torque_nm"], reading["rpm"])
    strain = reading["torque_nm"] * reading["tool_wear_min"]
    return (
        f"Machine {reading['machine_id']} (product quality {reading['quality']}) has a predicted "
        f"{FAILURE_NAMES.get(failure, failure)} ({failure}) with failure risk "
        f"{prediction['risk']:.0%}. Current readings: air temperature {reading['air_temp_k']:.1f} K, "
        f"process temperature {reading['process_temp_k']:.1f} K (difference {temp_diff:.1f} K), "
        f"rotational speed {reading['rpm']:.0f} rpm, torque {reading['torque_nm']:.1f} Nm, "
        f"mechanical power {power:.0f} W, tool wear {reading['tool_wear_min']:.0f} min, "
        f"tool wear x torque {strain:.0f} min*Nm. "
        f"What is the likely cause, how do the readings support it, how do I fix it safely, "
        f"and does this need escalation?"
    )
