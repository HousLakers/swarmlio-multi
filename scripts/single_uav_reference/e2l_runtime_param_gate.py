#!/usr/bin/env python3
"""Parse roslaunch parameter dumps and compare typed expected values."""

import math
import re


PARAM_LINE = re.compile(r"^\s*\*\s*(/\S+):\s*(.*?)\s*$")


def parse_runtime_params(text):
    values = {}
    for line in text.splitlines():
        match = PARAM_LINE.match(line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def check_runtime_params(text, expected):
    parsed = parse_runtime_params(text)
    actual = {}
    errors = []
    for name, wanted in expected.items():
        raw = parsed.get(name)
        actual[name] = raw
        if raw is None:
            errors.append("missing_param:" + name)
            continue
        if isinstance(wanted, bool):
            normalized = raw.strip().lower()
            if normalized not in ("true", "false") or (normalized == "true") != wanted:
                errors.append(f"param_mismatch:{name}:expected={wanted}:actual={raw}")
        elif isinstance(wanted, (int, float)):
            try:
                observed = float(raw)
            except ValueError:
                errors.append(f"param_not_numeric:{name}:actual={raw}")
                continue
            if not math.isclose(observed, float(wanted), rel_tol=1e-9, abs_tol=1e-9):
                errors.append(f"param_mismatch:{name}:expected={wanted}:actual={raw}")
        elif raw != str(wanted):
            errors.append(f"param_mismatch:{name}:expected={wanted}:actual={raw}")
    return actual, errors
