"""Print the Instagram caption (with CC credits) for every reel in spec3.json, without rendering video.

    python3 captions3.py spec3.json footage3.json out_dir
"""
import json, os, sys
import build2

spec, fjson, out = sys.argv[1:4]
footage = json.load(open(fjson, encoding="utf-8"))
os.makedirs(out, exist_ok=True)
for r in json.load(open(spec, encoding="utf-8"))["reels"]:
    c = r["caption"]
    credit = build2.credits_for(r, footage).replace("Footage: Wikimedia Commons — ", "🎥 Credits (Wikimedia Commons): ")
    sa = " This reel: CC BY-SA 4.0." if any("SA" in footage[x[0]]["license"] for x in r["segments"] if x[0] in footage) else ""
    text = f"{c['en']}\n\n{c['bn']}\n\n{c['tags']}\n\n{credit}.{sa}\n".replace("..", ".")
    open(f"{out}/{r['id']}.caption.txt", "w", encoding="utf-8").write(text)
    print(f"=== {r['id']}\n{text}")
