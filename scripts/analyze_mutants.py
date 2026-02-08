#!/usr/bin/env python3
"""Analyze mutation testing results to identify high-value mutants to investigate.

Run from WSL: cd ~/smartnest-project && python3 /mnt/d/Programowanie/College/Champlain/SDEV435/SmartNest/scripts/analyze_mutants.py
"""

from __future__ import annotations

import subprocess
from collections import defaultdict

# Maximum number of mutants to display per category
_MAX_DISPLAY = 10


def get_surviving_mutants() -> list[str]:
    """Get list of surviving/timeout mutants from mutmut."""
    result = subprocess.run(
        ["mutmut", "results"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return [
        line.strip()
        for line in result.stdout.splitlines()
        if "survived" in line or "timeout" in line
    ]


def categorize_mutants(mutants: list[str]) -> dict[str, list[str]]:
    """Categorize mutants by file and priority."""
    categories: dict[str, list[str]] = defaultdict(list)

    for mutant in mutants:
        # Extract module path
        if "backend.mqtt.client" in mutant:
            categories["MQTT Client (High Priority)"].append(mutant)
        elif "backend.mqtt.topics" in mutant:
            categories["Topics/Validation (High Priority)"].append(mutant)
        elif "backend.mqtt.config" in mutant:
            categories["MQTT Config (Medium Priority)"].append(mutant)
        elif "backend.logging" in mutant:
            categories["Logging Infrastructure (Low Priority)"].append(mutant)
        else:
            categories["Other"].append(mutant)

    return categories


def main() -> None:
    """Analyze and categorize surviving mutants."""
    print("Analyzing mutation testing results...\n")

    mutants = get_surviving_mutants()
    if not mutants:
        print("No surviving mutants found!")
        return

    categories = categorize_mutants(mutants)

    print(f"Total surviving/timeout mutants: {len(mutants)}\n")

    for category, items in sorted(categories.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"\n{'=' * 80}")
        print(f"{category}: {len(items)} mutants")
        print(f"{'=' * 80}")

        # Show first mutants from each category
        for i, mutant in enumerate(items[:_MAX_DISPLAY], 1):
            print(f"{i:3}. {mutant}")

        if len(items) > _MAX_DISPLAY:
            print(f"    ... and {len(items) - _MAX_DISPLAY} more")

    # High-priority recommendations
    print(f"\n{'=' * 80}")
    print("HIGH-VALUE TARGETS (investigate first):")
    print(f"{'=' * 80}")

    high_priority: list[str] = []
    if "MQTT Client (High Priority)" in categories:
        # Focus on callback handlers and connection logic
        high_priority.extend(
            mutant
            for mutant in categories["MQTT Client (High Priority)"]
            if any(
                x in mutant
                for x in [
                    "_on_connect",
                    "_on_disconnect",
                    "_on_message",
                    "connect__",
                    "disconnect__",
                ]
            )
        )

    if "Topics/Validation (High Priority)" in categories:
        high_priority.extend(categories["Topics/Validation (High Priority)"])

    for i, mutant in enumerate(high_priority[:_MAX_DISPLAY], 1):
        print(f"{i:3}. {mutant}")

    print("\n\nTo investigate a mutant:")
    print("  ./mutmut.sh show <full-mutant-id>")
    print("  ./mutmut.sh apply <full-mutant-id>  # See actual code")


if __name__ == "__main__":
    main()
