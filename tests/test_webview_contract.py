import ast
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_TYPES = ROOT / "web" / "src" / "types" / "index.ts"
FRONTEND_SOURCE = ROOT / "web" / "src"
BRIDGE_SOURCE = ROOT / "src" / "maple_reporter" / "gui" / "pywebview_bridge.py"


def _frontend_api_methods() -> set[str]:
    source = FRONTEND_TYPES.read_text(encoding="utf-8")
    api_block = source.split("api: {", 1)[1].split("\n      };", 1)[0]
    return set(re.findall(r"^\s{8}([A-Za-z_]\w*)\s*:", api_block, re.MULTILINE))


def _frontend_api_calls() -> set[str]:
    methods = set()
    for source_path in FRONTEND_SOURCE.rglob("*.ts*"):
        source = source_path.read_text(encoding="utf-8")
        methods.update(re.findall(r"window\.pywebview\.api\.([A-Za-z_]\w*)", source))
    return methods


def _bridge_methods() -> set[str]:
    tree = ast.parse(BRIDGE_SOURCE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "PyWebViewBridge":
            return {
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not item.name.startswith("_")
            }
    raise AssertionError("PyWebViewBridge class not found")


class TestWebViewBridgeContract(unittest.TestCase):
    def test_every_typed_frontend_api_method_exists_on_bridge(self):
        frontend_methods = _frontend_api_methods()
        bridge_methods = _bridge_methods()
        missing = sorted(frontend_methods - bridge_methods)
        self.assertEqual(missing, [], f"Frontend API methods missing from PyWebViewBridge: {missing}")

    def test_every_frontend_api_call_is_typed(self):
        typed_methods = _frontend_api_methods()
        called_methods = _frontend_api_calls()
        missing = sorted(called_methods - typed_methods)
        self.assertEqual(missing, [], f"Frontend calls missing from Window.pywebview.api: {missing}")


if __name__ == "__main__":
    unittest.main()
