"""scripts/narrate.py: text clean-up for the voice, and the text hash it shares with guide.js."""
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import narrate  # noqa: E402


class NarrateTest(unittest.TestCase):
    def test_speakable(self):
        t = narrate.speakable("Cook 30–35 minutes with 1½ tbsp ghee, 150 g rice & ¼ tsp salt, from 9 am")
        self.assertEqual(t, "Cook 30 to 35 minutes with 1 and a half tablespoons ghee, 150 grams rice and a quarter teaspoons salt, from 9 a.m.")

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_hash_matches_guide_js(self):
        """The player only plays a recording whose hash matches its own text, so both sides must agree."""
        js = (ROOT / "scripts/seo/guide.js").read_text(encoding="utf-8")
        fn = re.search(r"var fnv1a = (function \(str\) \{.*?\n  \});", js, re.S).group(1)
        for s in ["Durga Puja", "Maha Ashtami\nওঁ জয়ন্তী মঙ্গলা কালী", "emoji 😀 and “quotes”", ""]:
            out = subprocess.run(["node", "-e", f"process.stdout.write(({fn})({s!r}))"], capture_output=True, text=True, check=True).stdout
            self.assertEqual(out, narrate.fnv1a(s), s)


if __name__ == "__main__":
    unittest.main()
