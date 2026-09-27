import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('surfaces', ROOT / 'scripts/validate_ai_search_surfaces.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class DeploymentDiscoveryTest(unittest.TestCase):
    def run_validation(self, base, href, tamper=False):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            for name in module.REQUIRED:
                shutil.copy(ROOT / 'static' / name, output / name)
            if tamper:
                p = output / 'ai-search-readiness.json'
                data = json.loads(p.read_text())
                data['canonical_origin'] = base
                p.write_text(json.dumps(data))
            (output / 'index.html').write_text(f'<link rel="describedby" type="text/markdown" href="{href}">')
            with patch.object(module, 'PUBLIC', output), patch.dict(os.environ, {'DEPLOYMENT_BASE_URL': base}), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return module.main()

    def test_project_pages_base_is_accepted(self):
        self.assertEqual(self.run_validation('https://example.invalid/repo/', 'https://example.invalid/repo/llms.txt'), 0)

    def test_wrong_deployment_link_is_rejected(self):
        self.assertEqual(self.run_validation('https://example.invalid/repo/', 'https://aisearcharab.com/llms.txt'), 1)

    def test_canonical_identity_cannot_be_changed_by_deployment(self):
        self.assertEqual(self.run_validation('https://example.invalid/repo/', 'https://example.invalid/repo/llms.txt', True), 1)

    def test_insecure_base_is_rejected(self):
        self.assertEqual(self.run_validation('http://example.invalid/', 'http://example.invalid/llms.txt'), 1)
