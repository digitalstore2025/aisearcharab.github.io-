#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("generate_cyclonedx_sbom.py")
spec = importlib.util.spec_from_file_location("generate_cyclonedx_sbom", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load SBOM generator")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CycloneDxSbomTests(unittest.TestCase):
    def test_build_bom_collects_nested_runtime_dependencies_deterministically(self) -> None:
        graph = [
            {
                "name": "@aisearcharab/web",
                "version": "0.1.0",
                "dependencies": {
                    "next": {
                        "version": "16.3.4(react@19.2.8)",
                        "dependencies": {
                            "react": {"version": "19.2.8"},
                        },
                    },
                    "@scope/pkg": {"version": "2.0.0"},
                },
            }
        ]

        first = module.build_bom(graph, "runtime")
        second = module.build_bom(graph, "runtime")

        self.assertEqual(first["serialNumber"], second["serialNumber"])
        components = first["components"]
        refs = {item["bom-ref"] for item in components}
        self.assertIn("pkg:npm/next@16.3.4", refs)
        self.assertIn("pkg:npm/react@19.2.8", refs)
        self.assertIn("pkg:npm/%40scope/pkg@2.0.0", refs)
        self.assertEqual(first["bomFormat"], "CycloneDX")
        self.assertEqual(first["specVersion"], "1.5")

    def test_link_and_workspace_dependencies_are_excluded(self) -> None:
        graph = [
            {
                "name": "@aisearcharab/web",
                "version": "0.1.0",
                "dependencies": {
                    "local-a": {"version": "link:../a"},
                    "local-b": {"version": "workspace:*"},
                    "safe": {"version": "1.2.3"},
                },
            }
        ]
        bom = module.build_bom(graph, "build")
        refs = {item["bom-ref"] for item in bom["components"]}
        self.assertEqual(refs, {"pkg:npm/safe@1.2.3"})

    def test_cli_style_graph_round_trip_is_valid_json(self) -> None:
        graph = [{"name": "@aisearcharab/web", "version": "0.1.0", "dependencies": {"safe": {"version": "1.0.0"}}}]
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "graph.json"
            source.write_text(json.dumps(graph), encoding="utf-8")
            loaded = module.load_graph(source)
            bom = module.build_bom(loaded, "runtime")
            rendered = json.dumps(bom, sort_keys=True)
            parsed = json.loads(rendered)
            self.assertEqual(len(parsed["components"]), 1)


if __name__ == "__main__":
    unittest.main()
