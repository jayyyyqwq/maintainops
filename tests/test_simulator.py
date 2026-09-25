from __future__ import annotations

import random

import pytest

from common.features import power_watts
from simulator.faults import FAULT_TICKS, apply_fault
from simulator.handler import TOOL_CHANGE_AT, next_reading

OSF_LIMIT = {"L": 11_000, "M": 12_000, "H": 13_000}
POOL = [
    {"air_temp_k": 300.0, "process_temp_k": 310.0, "rpm": 1500, "torque_nm": 40.0, "quality": q}
    for q in ("L", "M", "H")
]


@pytest.mark.parametrize("seed", range(20))
@pytest.mark.parametrize("quality", ["L", "M", "H"])
def test_fault_profiles_land_in_failure_regions(seed, quality, healthy_reading):
    rng = random.Random(seed)
    base = healthy_reading | {"quality": quality}

    hdf = apply_fault(base, "HDF", rng)
    assert hdf["process_temp_k"] - hdf["air_temp_k"] < 8.6 and hdf["rpm"] < 1380

    pwf = apply_fault(base, "PWF", rng)
    assert power_watts(pwf["torque_nm"], pwf["rpm"]) > 9000

    osf = apply_fault(base, "OSF", rng)
    assert osf["tool_wear_min"] * osf["torque_nm"] > OSF_LIMIT[quality]
    assert 3500 < power_watts(osf["torque_nm"], osf["rpm"]) < 9000  # not a power failure

    twf = apply_fault(base, "TWF", rng)
    assert 200 <= twf["tool_wear_min"] <= 240


def test_unknown_fault_rejected(healthy_reading):
    with pytest.raises(ValueError):
        apply_fault(healthy_reading, "XYZ", random.Random(0))


def test_tool_wear_grows_and_resets_on_tool_change():
    rng = random.Random(1)
    reading, state = next_reading("m1", {"cursor_pos": 0, "tool_wear_min": 10}, POOL, rng)
    assert 11 <= reading["tool_wear_min"] <= 13
    assert state["cursor"] == 1

    reading, state = next_reading("m1", {"cursor_pos": 5, "tool_wear_min": TOOL_CHANGE_AT - 1}, POOL, rng)
    assert reading["tool_wear_min"] == 0


def test_pending_fault_applies_for_fixed_ticks_then_clears():
    rng = random.Random(2)
    state = {"cursor_pos": 0, "tool_wear_min": 20, "pending_fault": "PWF", "fault_ticks": FAULT_TICKS}
    for remaining in range(FAULT_TICKS - 1, -1, -1):
        reading, updates = next_reading("m2", state, POOL, rng)
        assert reading["injected_fault"] == "PWF"
        assert updates["fault_ticks"] == remaining
        state = {"cursor_pos": updates["cursor"], "tool_wear_min": updates["tool_wear_min"],
                 "pending_fault": updates["pending_fault"], "fault_ticks": updates["fault_ticks"]}
    reading, updates = next_reading("m2", state, POOL, rng)
    assert reading["injected_fault"] is None
    assert updates["pending_fault"] is None
