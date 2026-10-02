"""Evaluate integer token vesting, cliffs, revocation snapshots and treasury obligations."""

import json


def integer(value):
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("integer required")
    return value


def vested(schedule, timestamp):
    total = integer(schedule["total"])
    start = integer(schedule["start"])
    duration = integer(schedule["duration"])
    cliff = integer(schedule.get("cliff", start))
    timestamp = integer(timestamp)
    if total < 0 or duration <= 0 or cliff < start or cliff > start + duration:
        raise ValueError("invalid schedule")
    stop = schedule.get("revoked_at")
    if stop is not None:
        stop = integer(stop)
        if stop < start:
            raise ValueError("revocation precedes start")
        timestamp = min(timestamp, stop)
    if timestamp < cliff:
        return 0
    return total * min(max(timestamp - start, 0), duration) // duration


def analyze(data):
    timestamp = integer(data["timestamp"])
    output = []
    seen = set()
    for schedule in data["schedules"]:
        identity = schedule["id"]
        if identity in seen:
            raise ValueError("duplicate schedule id")
        seen.add(identity)
        earned = vested(schedule, timestamp)
        claimed = integer(schedule.get("claimed", 0))
        if claimed < 0 or claimed > earned:
            raise ValueError("claims exceed vested amount at snapshot")
        revoked = schedule.get("revoked_at") is not None
        final = vested(schedule, schedule["start"] + schedule["duration"])
        output.append(
            {
                "id": identity,
                "vested": earned,
                "claimable": earned - claimed,
                "unvested": schedule["total"] - earned,
                "returned_to_treasury": schedule["total"] - final if revoked else 0,
                "remaining_obligation": final - claimed,
            }
        )
    return {
        "timestamp": timestamp,
        "schedules": output,
        "claimable_total": sum(r["claimable"] for r in output),
        "remaining_obligation": sum(r["remaining_obligation"] for r in output),
    }


import argparse
import csv
import io
import sys
from pathlib import Path


def load_input(path):
    raw = Path(path).read_text(encoding="utf-8")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("invalid JSON constant: " + value)

    data = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")
    return data


def flatten(value, prefix=""):
    rows = []
    if isinstance(value, dict):
        for key, item in value.items():
            rows.extend(flatten(item, f"{prefix}.{key}" if prefix else key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(flatten(item, f"{prefix}[{index}]"))
    else:
        rows.append((prefix, json.dumps(value, ensure_ascii=False)))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON input file")
    parser.add_argument("--output", help="write result atomically to a file")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    args = parser.parse_args(argv)
    try:
        result = analyze(load_input(args.input))
        if args.format == "json":
            content = (
                json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
            )
        else:
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["path", "value"])
            writer.writerows(flatten(result))
            content = buffer.getvalue()
        if args.output:
            import os, tempfile

            target = Path(args.output)
            fd, temporary = tempfile.mkstemp(
                prefix="." + target.name + ".", dir=target.parent
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(content)
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        else:
            sys.stdout.write(content)
    except (ValueError, KeyError, TypeError, OSError, ArithmeticError) as error:
        parser.exit(2, f"error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
