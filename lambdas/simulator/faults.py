"""Fault profiles: push a healthy reading into the physical region of a failure mode.

Thresholds follow the AI4I 2020 generation rules:
  HDF  process-air temp diff < 8.6 K and rpm < 1380
  PWF  power < 3500 W or > 9000 W
  OSF  tool wear x torque > 11,000 (L) / 12,000 (M) / 13,000 (H) min*Nm
  TWF  tool wear between 200 and 240 min
"""

from __future__ import annotations

import random

from common.features import FAILURE_TYPES

FAULT_TICKS = 3  # readings affected per injection


def apply_fault(reading: dict, fault: str, rng: random.Random) -> dict:
    if fault not in FAILURE_TYPES:
        raise ValueError(f"unknown fault {fault!r}")
    r = dict(reading)
    if fault == "HDF":
        r["process_temp_k"] = round(r["air_temp_k"] + rng.uniform(7.2, 8.2), 1)
        r["rpm"] = rng.randint(1250, 1340)
        r["torque_nm"] = round(rng.uniform(50, 58), 1)
    elif fault == "PWF":
        r["rpm"] = rng.randint(1330, 1400)
        r["torque_nm"] = round(rng.uniform(68, 74), 1)
    elif fault == "OSF":
        # wear*torque > 13,000 even for H quality, while power stays under 9,000 W
        r["tool_wear_min"] = rng.randint(212, 225)
        r["torque_nm"] = round(rng.uniform(62, 66), 1)
        r["rpm"] = rng.randint(1240, 1290)
        r["process_temp_k"] = round(r["air_temp_k"] + rng.uniform(10.0, 11.0), 1)
    elif fault == "TWF":
        r["tool_wear_min"] = rng.randint(215, 238)
    return r
