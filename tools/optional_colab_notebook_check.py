import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
NB = ROOT / "notebooks" / "p0_foundation_smoke.ipynb"


class NotebookFormatTests(unittest.TestCase):
    def test_notebook_structure_and_no_saved_outputs(self):
        nb = json.loads(NB.read_text(encoding="utf-8"))
        self.assertEqual(nb["nbformat"], 4)
        self.assertGreaterEqual(len(nb["cells"]), 3)
        for cell in nb["cells"]:
            if cell["cell_type"] == "code":
                self.assertIsNone(cell["execution_count"])
                self.assertEqual(cell["outputs"], [])
                source = "".join(cell["source"])
                compile(source, "<colab-code-cell>", "exec")

    def test_no_token_literals_or_broker_orders(self):
        text = NB.read_text(encoding="utf-8")
        self.assertNotIn("ghp_", text)
        self.assertNotIn("github_pat_", text)
        self.assertNotIn("git push", text.lower())


if __name__ == "__main__":
    unittest.main()
