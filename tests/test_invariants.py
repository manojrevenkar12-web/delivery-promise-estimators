import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "dpe"
PLATFORM = ["estimators", "features", "service", "warehouse", "ops"]


def _imports(path: Path) -> set[str]:
    mods = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


def test_the_platform_never_reads_the_truth():
    for pkg in PLATFORM:
        for f in (ROOT / pkg).rglob("*.py"):
            bad = {m for m in _imports(f) if m.startswith(("dpe.world", "dpe.sim"))}
            assert not bad, f"{f.relative_to(ROOT)} imports {bad}"


def test_the_world_does_not_read_the_platforms_settings():
    src = (ROOT / "world" / "__init__.py").read_text()
    for name in ("estimators", "planner", "value", "gate", "options"):
        assert f'"{name}"' not in src and f"'{name}'" not in src
    assert not {m for m in _imports(ROOT / "world" / "__init__.py") if m.startswith("dpe.") and m != "dpe.keyed"}
