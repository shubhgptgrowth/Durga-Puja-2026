set -e
# Bengali-first posts (marketing/posts4). Run in the build sandbox next to design.py, spec4.json and
# ../reels/{commons_meta.py,photos3.tsv,footage.json}. ONLY=w01-bangla-words,... renders a subset.
UA="PujoParikramaBot/1.0 (https://github.com/shubhgptgrowth/Durga-Puja-2026)"
mkdir -p src out fonts
G=https://github.com/google/fonts/raw/main/ofl
for f in galada/Galada-Regular tirobangla/TiroBangla-Regular hindsiliguri/HindSiliguri-Bold hindsiliguri/HindSiliguri-SemiBold \
         hindsiliguri/HindSiliguri-Medium dmserifdisplay/DMSerifDisplay-Italic dmserifdisplay/DMSerifDisplay-Regular poppins/Poppins-SemiBold; do
  n=${f#*/}.ttf; [ -s fonts/$n ] || curl -sfL -o fonts/$n "$G/$f.ttf"; done
[ -s footage3.json ] || python3 commons_meta.py photos3.tsv footage.json > footage3.json
python3 - <<'PY'
import json, os, subprocess, time
spec = json.load(open("spec4.json", encoding="utf-8")); f = json.load(open("footage3.json"))
only = set(filter(None, os.environ.get("ONLY", "").split(",")))
refs = set()
for p in spec["posts"]:
    if only and p["id"] not in only: continue
    for s in p["slides"]:
        refs |= {s[k] for k in ("img", "left", "right") if s.get(k)} | set(s.get("grid", []))
for r in sorted(refs):
    ext = ".png" if r.startswith("k") else ".jpg"
    if os.path.exists(f"src/{r}{ext}"): continue
    url = spec["art"][r] if r.startswith("k") else f[r]["url"]
    subprocess.run(["curl", "-sfL", "-A", "PujoParikramaBot/1.0", "-o", f"src/{r}{ext}", url], check=True)
    print("dl", r, flush=True); time.sleep(0.3)
PY
python3 design.py spec4.json footage3.json src out ${ONLY:-}
echo ALLDONE
