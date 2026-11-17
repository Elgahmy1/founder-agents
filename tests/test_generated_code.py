"""Re-runs the committed demo run's generated core code against its own acceptance
checks in the sandbox, so the "N/N checks passed" in outputs/ is reproducible on
every push (no model call)."""
import re
from pathlib import Path

import pytest

from app import sandbox

OUTPUTS = Path(__file__).resolve().parent.parent / "outputs"
FILES = sorted(OUTPUTS.glob("phase3_step4_code-*.md"))


def _parse(md: str) -> tuple[str, list[str], tuple[int, int]]:
    core = md.split("## core.py", 1)[1].split("## Checks", 1)
    code = re.search(r"```python\n(.*?)```", core[0], re.S).group(1)
    checks = re.findall(r"```python\n(.*?)```", core[1], re.S)
    m = re.search(r"\*\*Result: (\d+)/(\d+) acceptance checks passed", md)
    return code, checks, (int(m.group(1)), int(m.group(2)))


def test_a_generated_code_output_is_committed():
    assert FILES, "the demo run's phase3_step4_code output is missing"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_committed_generated_code_still_passes_its_acceptance_checks(path):
    code, checks, (passed, total) = _parse(path.read_text(encoding="utf-8"))
    assert len(checks) == total
    res = sandbox.run(code, checks)
    assert not res.static_problems and not res.load_error and not res.timed_out
    assert res.passed == passed == total
