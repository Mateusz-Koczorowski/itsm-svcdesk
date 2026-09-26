# ai-generated: 100% - Claude wrote the runner that prints the ITSMLAB-TESTS summary line
"""Runs the suite and prints `ITSMLAB-TESTS: passed=<n> failed=<m>` as the last stdout line."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tests.client import wait_for_health


class Counter:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def pytest_runtest_logreport(self, report) -> None:
        if report.when == "call" and report.passed:
            self.passed += 1
        elif report.failed:
            self.failed += 1


def main() -> int:
    wait_for_health()
    counter = Counter()
    code = pytest.main(["-q", "-p", "no:cacheprovider", str(Path(__file__).parent)], plugins=[counter])
    print(f"ITSMLAB-TESTS: passed={counter.passed} failed={counter.failed}", flush=True)
    return 0 if code == 0 and counter.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
