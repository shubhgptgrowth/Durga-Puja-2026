set -e
# Run in the build sandbox next to build2.py, spec2.json, footage.json and ai_urls.txt ("cNN <cdn suffix>" lines for the AI clips).
UA="PujoParikramaBot/1.0 (https://github.com/shubhgptgrowth/Durga-Puja-2026)"
mkdir -p src out fonts
for w in ExtraBold Bold SemiBold Medium; do [ -s fonts/Poppins-$w.ttf ] || curl -sfLo fonts/Poppins-$w.ttf https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-$w.ttf; done
NEED=$(python3 -c "import json;s=json.load(open('spec2.json'));print(' '.join(sorted({x[0] for r in s['reels'] for x in r['segments']}|{r['music'][0] for r in s['reels']})))")
for id in $NEED; do
 ls src/$id.* >/dev/null 2>&1 && continue
 if [ ${id:0:1} = c ]; then s=$(grep "^$id " ai_urls.txt | cut -d' ' -f2); curl -sfo src/$id.mp4 "https://d8j0ntlcm91z4.cloudfront.net/user_3C4ckPluFiRw2Fro30FUIlIR0V7/hf_20261003_$s.mp4"; continue; fi
 read u w h <<<"$(python3 -c "import json;f=json.load(open('footage.json'))['$id'];print(f['url'],f['w'],f['h'])")"
 n=${u##*/}; ext=${n##*.}; got=""
 if [ "$w" -gt 1920 ] || { [ "$w" -gt "$h" ] && [ "$h" -ge 1080 ] && [ "$ext" = ogv ]; }; then
   tb=${u%/*}; tb=${tb/commons\//commons/transcoded/}/$n
   for s in 1080p.vp9.webm 1080p.webm; do curl -sfL -A "$UA" -o src/$id.webm "$tb/$n.$s" && { got=1; break; }; sleep 2; done
 fi
 [ -n "$got" ] || curl -sfL -A "$UA" -o src/$id.$ext "$u"
 echo "dl $id $(du -sh src/$id.* | cut -f1)"; sleep 1
done
python3 build2.py spec2.json footage.json src out ${ONLY:-}
for f in out/r*.mp4; do b=$(basename $f .mp4); d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 $f); echo "$b $d"
  ffmpeg -v error -y -i $f -vf "fps=4/$d,scale=135:240,tile=4x1" -frames:v 1 out/qa_$b.jpg; done
echo ALLDONE
