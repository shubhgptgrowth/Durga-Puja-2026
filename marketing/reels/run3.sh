set -e
# Batch 2 (11–21 Oct): photos with a slow pan plus real footage. Run in the build sandbox next to build2.py,
# commons_meta.py, photos3.tsv, spec3.json and footage.json. ONLY=b01-final-touches,b02-pujo-shopping builds a subset.
UA="PujoParikramaBot/1.0 (https://github.com/shubhgptgrowth/Durga-Puja-2026)"
mkdir -p src out fonts
for w in ExtraBold Bold SemiBold Medium; do [ -s fonts/Poppins-$w.ttf ] || curl -sfLo fonts/Poppins-$w.ttf https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-$w.ttf; done
for f in galada/Galada-Regular hindsiliguri/HindSiliguri-Bold; do n=${f#*/}.ttf; [ -s fonts/$n ] || curl -sfLo fonts/$n https://github.com/google/fonts/raw/main/ofl/$f.ttf; done
[ -s footage3.json ] || python3 commons_meta.py photos3.tsv footage.json > footage3.json
NEED=$(python3 -c "
import json,os
only=set(filter(None,os.environ.get('ONLY','').split(',')))
s=[r for r in json.load(open('spec3.json'))['reels'] if not only or r['id'] in only]
print(' '.join(sorted({x[0] for r in s for x in r['segments']}|{r['music'][0] for r in s})))")
for id in $NEED; do
 ls src/$id.* >/dev/null 2>&1 && continue
 read u w h <<<"$(python3 -c "import json;f=json.load(open('footage3.json'))['$id'];print(f['url'],f['w'],f['h'])")"
 n=${u##*/}; ext=${n##*.}; got=""
 case $id in p*) curl -sfL -A "$UA" -o src/$id.jpg "$u" || { sleep 5; curl -sfL -A "$UA" -o src/$id.jpg "$u"; }; echo "dl $id"; sleep 0.5; continue;; esac
 if [ "$w" -gt "$h" ] && { [ "$w" -gt 1920 ] || [ "$ext" = ogv ]; }; then
   tb=${u%/*}; tb=${tb/commons\//commons/transcoded/}/$n
   for s in 1080p.vp9.webm 1080p.webm; do curl -sfL -A "$UA" -o src/$id.webm "$tb/$n.$s" && { got=1; break; }; sleep 2; done
 fi
 [ -n "$got" ] || curl -sfL -A "$UA" -o src/$id.$ext "$u"
 echo "dl $id $(du -sh src/$id.* | cut -f1)"; sleep 1
done
python3 build2.py spec3.json footage3.json src out ${ONLY:-}
for f in out/b*.mp4; do b=$(basename $f .mp4); d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 $f); echo "$b $d"
  ffmpeg -v error -y -i $f -vf "fps=7/$d,scale=120:213,tile=7x1" -frames:v 1 out/qa_$b.jpg; done
echo ALLDONE
