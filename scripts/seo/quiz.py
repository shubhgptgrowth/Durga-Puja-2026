"""'Which Kolkata pandal matches your pujo vibe?': a six-question quiz at /quiz/which-pandal/ with a result page per
answer (/quiz/which-pandal/<type>/), so a shared result shows its own title and photo in the WhatsApp preview.
Each result points at real pandals from the guide (their page, best time, nearest metro and 2026 theme), and the
result can go to WhatsApp or out as a 1080x1920 story card drawn on the phone. Nothing is sent anywhere."""
import json

from .common import NAME, esc

# The six types: who they are, and the guide's pandals that suit them (first one is "your pandal").
TYPES = [
    {"id": "bonedi", "en": "Bonedi Bari soul", "bn": "বনেদি বাড়ির মন",
     "line": "You want the pujo the way it was: dhak at dawn, chandeliers over a thakur-dalan, the protima in daker saaj.",
     "pandals": ["sovabazar_rajbari", "bagbazar", "kumartuli_sarbojanin"], "more": ("guide/trails/north_heritage/", "The North Kolkata heritage trail")},
    {"id": "critic", "en": "Theme-pandal critic", "bn": "থিম-পুজোর বিচারক",
     "line": "You walk past the queue to read the idea behind the walls. Folk art, lanes turned into galleries, the thinking in every panel.",
     "pandals": ["tala_prattoy", "kashi_bose_lane", "chaltabagan"], "more": ("guide/themes-2026/", "Every 2026 theme announced so far")},
    {"id": "blockbuster", "en": "Blockbuster chaser", "bn": "ব্লকবাস্টার শিকারি",
     "line": "If the whole city is talking about it, you're there: the biggest replica, the brightest lights, the photo everyone posts.",
     "pandals": ["sreebhumi", "santosh_mitra", "suruchi_sangha"], "more": ("guide/best-pandals-2026/", "The 25 best-known pandals of 2026")},
    {"id": "classic", "en": "South Kolkata classicist", "bn": "দক্ষিণের ক্লাসিক",
     "line": "Anjali in a new sari or panjabi, a grand traditional protima, dhunuchi naach in the evening, and lunch with family.",
     "pandals": ["ekdalia", "singhi_park", "deshapriya_park"], "more": ("guide/south-kolkata/", "South Kolkata pandals by area")},
    {"id": "adda", "en": "Adda-and-phuchka hopper", "bn": "আড্ডাবাজ পুজো-হপার",
     "line": "The pandal is the excuse; the gang is the point. Phuchka, egg roll, a corner to sit, and three hours that feel like ten minutes.",
     "pandals": ["maddox_square", "badamtala", "hindustan_park"], "more": ("guide/areas/south_lakemarket/", "Lake Market and Kalighat, pandal by pandal")},
    {"id": "nightowl", "en": "All-nighter", "bn": "সারা রাতের পরিক্রমাকারী",
     "line": "You start at 10 pm and finish with tea at sunrise. The famous queues are short at 3 am, and you know it.",
     "pandals": ["md_ali_park", "college_square", "chetla_agrani"], "more": ("guide/late-night-pandal-hopping/", "Late-night pandal hopping, hour by hour")},
]

# Six questions; each option counts towards one type (same order as TYPES ids in each tuple).
QUESTIONS = [
    ("Your ideal pujo morning?", "পুজোর সকালটা কেমন চাই?", [
        ("bonedi", "Dhak in a rajbari courtyard", "রাজবাড়ির দালানে ঢাকের আওয়াজ"),
        ("critic", "Close-ups of the craft before anyone arrives", "ভিড়ের আগে শিল্পের খুঁটিনাটি দেখা"),
        ("blockbuster", "Beating the queue at the famous one", "নামী পুজোয় লাইনের আগে পৌঁছনো"),
        ("classic", "Anjali, then lunch with family", "অঞ্জলি, তারপর বাড়ির সবার সঙ্গে খাওয়া"),
        ("adda", "Phuchka and adda with the para gang", "পাড়ার বন্ধুদের সঙ্গে ফুচকা আর আড্ডা"),
        ("nightowl", "Asleep. The night was long", "ঘুম। রাতটা লম্বা ছিল"),
    ]),
    ("A two-hour queue. You…", "দু'ঘণ্টার লাইন। আপনি…", [
        ("bonedi", "skip it: old houses have no queue", "বাদ: বনেদি বাড়িতে লাইন নেই"),
        ("critic", "skip it: the lane next door is the real art", "বাদ: পাশের গলিতেই আসল শিল্প"),
        ("blockbuster", "join it. Worth it for the big one", "দাঁড়াই। বড় পুজোর জন্য চলে"),
        ("classic", "go to your para pujo instead", "নিজের পাড়ার পুজোয় চলে যাই"),
        ("adda", "join it if the gang's talking", "আড্ডা জমলে দাঁড়িয়ে যাই"),
        ("nightowl", "come back at 4 am", "ভোর চারটেয় ফিরে আসি"),
    ]),
    ("Pick a pujo snack", "পুজোর খাবার বাছুন", [
        ("bonedi", "Kabiraji at an old cabin", "পুরনো কেবিনের কবিরাজি"),
        ("critic", "Whatever the stall outside the art pandal has", "আর্ট-পুজোর বাইরের স্টলে যা পাওয়া যায়"),
        ("blockbuster", "Biryani after the big queue", "লম্বা লাইনের পরে বিরিয়ানি"),
        ("classic", "Bhog khichuri and labra", "ভোগের খিচুড়ি আর লাবড়া"),
        ("adda", "Phuchka, then an egg roll", "ফুচকা, তারপর এগ রোল"),
        ("nightowl", "Mughlai paratha at 2 am", "রাত দুটোয় মোগলাই পরোটা"),
    ]),
    ("What makes a pandal great?", "পুজো ভাল লাগে কিসে?", [
        ("bonedi", "The protima's daker saaj", "প্রতিমার ডাকের সাজ"),
        ("critic", "The idea behind the theme", "থিমের পেছনের ভাবনা"),
        ("blockbuster", "Scale and lights", "আকার আর আলো"),
        ("classic", "Anjali and dhunuchi naach", "অঞ্জলি আর ধুনুচি নাচ"),
        ("adda", "Space to sit and stalls to eat", "বসার জায়গা আর খাবারের স্টল"),
        ("nightowl", "Calm at 3 am", "রাত তিনটের শান্তি"),
    ]),
    ("Your pujo shoes?", "পুজোয় পায়ে কী?", [
        ("bonedi", "Kolhapuris with a dhoti or taant", "ধুতি বা তাঁতের সঙ্গে কোলাপুরি"),
        ("critic", "Whatever lets me stand and look for long", "যাতে অনেকক্ষণ দাঁড়িয়ে দেখতে পারি"),
        ("blockbuster", "New ones, for the photos", "নতুন জুতো, ছবির জন্য"),
        ("classic", "Whatever goes with the new sari or panjabi", "নতুন শাড়ি বা পাঞ্জাবির সঙ্গে যা মানায়"),
        ("adda", "Chappals. We're sitting most of the time", "চটি। বেশিরভাগ সময় তো বসেই"),
        ("nightowl", "Sneakers. 10 km tonight", "স্নিকার। আজ দশ কিলোমিটার"),
    ]),
    ("Midnight on Ashtami, you're…", "অষ্টমীর মাঝরাতে আপনি…", [
        ("bonedi", "in a rajbari, after Sandhi Puja", "সন্ধিপুজোর পরে রাজবাড়িতে"),
        ("critic", "in a lane where artists built something new", "যে গলিতে শিল্পীরা নতুন কিছু বানিয়েছেন"),
        ("blockbuster", "at the pandal everyone's posting", "যে পুজোর ছবি সবাই দিচ্ছে, সেখানে"),
        ("classic", "home, after the evening arati", "সন্ধ্যারতির পরে বাড়িতে"),
        ("adda", "at a phuchka stall with the gang", "বন্ধুদের সঙ্গে ফুচকার স্টলে"),
        ("nightowl", "just getting started", "সবে শুরু করছি"),
    ]),
]


def a_an(word):
    return "an" if word[:1].lower() in "aeiou" else "a"


class QuizMixin:
    def quiz_types(self):
        """TYPES with each pandal's facts from the guide; pandals not in the guide are dropped."""
        out = []
        for t in TYPES:
            ps = [self.pandal[i] for i in t["pandals"] if i in self.pandal]
            if not ps:
                continue
            p = ps[0]
            m = p["nearest_metro"]
            far = self.metro_far(p)
            th = p.get("theme_2026") or {}
            photo = self.pandal_photo(p)
            out.append({**t, "pandal": {"id": p["id"], "name": p["name"], "bn": p.get("name_bn", ""), "best": p["best_slot_label"],
                                        "metro": "" if far else f"{m['name'].split(' (')[0]}, {m['walk_min']} min walk",
                                        "theme": th.get("title", ""), "area": self.zone[p["zone"]]["name"],
                                        "photo": photo["src"] if photo else "", "credit": (f"{photo['alt']}{', ' + str(photo['year']) if photo.get('year') else ''}. "
                                                                                      f"Photo: {photo['author']}, {photo['license']}, Wikimedia Commons.") if photo else ""},
                        "also": [{"id": q["id"], "name": q["name"]} for q in ps[1:]]})
        return out

    def quiz_pages(self):
        types = self.quiz_types()
        if len(types) < 4:
            return
        self.quiz_index(types)
        for t in types:
            self.quiz_result(t, types)
        short = self.out / "quiz" / "index.html"   # /quiz, the short address printed on the story card
        short.write_text(f'<!doctype html><meta charset="utf-8"><title>Pujo quiz</title><meta name="robots" content="noindex">'
                         f'<link rel="canonical" href="{self.url("quiz/which-pandal/")}"><meta http-equiv="refresh" content="0; url=which-pandal/">'
                         f'<a href="which-pandal/">Which Kolkata pandal matches your pujo vibe?</a>', encoding="utf-8")

    def quiz_result_html(self, t, up):
        p = t["pandal"]
        facts = " · ".join(x for x in [f"Best time: {esc(p['best'])}", f"Metro: {esc(p['metro'])}" if p["metro"] else "",
                                         f"2026 theme: {esc(p['theme'])}" if p["theme"] else ""] if x)
        photo = (f"<figure class='photo'><img src='{esc(p['photo'])}' alt='{esc(p['name'])}' loading='lazy' decoding='async'>"
                 f"<figcaption>{esc(p['credit'])}</figcaption></figure>") if p["photo"] else ""
        also = ", ".join(f"<a href='{up}guide/pandals/{a['id']}/?src=quiz'>{esc(a['name'])}</a>" for a in t["also"])
        more_path, more_label = t["more"]
        return (f"<p class='kicker'>You're {a_an(t['en'])}</p><h2 class='q-type'>{esc(t['en'])} <span lang='bn'>· {esc(t['bn'])}</span></h2>"
                f"<p>{esc(t['line'])}</p>{photo}"
                f"<p><b>Your pandal: <a href='{up}guide/pandals/{p['id']}/?src=quiz'>{esc(p['name'])}</a></b> <small>({esc(p['area'])})</small><br>"
                f"<small>{facts}</small></p>"
                + (f"<p>Also your kind of pujo: {also}.</p>" if also else "")
                + f"<p><a href='{up}{more_path}?src=quiz'>{esc(more_label)} →</a></p>")

    def quiz_index(self, types):
        up = "../../"
        path = "quiz/which-pandal/"
        qs = "".join(
            f"<fieldset class='q' data-q='{i}'><legend><b>{i + 1}. {esc(en)}</b><br><span lang='bn'>{esc(bn)}</span></legend>"
            + "".join(f"<label class='opt'><input type='radio' name='q{i}' value='{tid}'> <span>{esc(oen)}<br><small lang='bn'>{esc(obn)}</small></span></label>"
                      for tid, oen, obn in opts) + "</fieldset>"
            for i, (en, bn, opts) in enumerate(QUESTIONS))
        results = "".join(f"<section class='q-result' id='r-{t['id']}' hidden>{self.quiz_result_html(t, up)}</section>" for t in types)
        data = json.dumps([{"id": t["id"], "en": t["en"], "a": a_an(t["en"]), "bn": t["bn"], "pandal": t["pandal"]["name"], "best": t["pandal"]["best"],
                           "metro": t["pandal"]["metro"]} for t in types], ensure_ascii=False)
        host = self.base.split("//")[1].strip("/")
        body = f"""<article>
<h1>Which Kolkata pandal matches your pujo vibe?</h1>
<p class="lead">Six quick questions, in English and Bengali, and you get your pujo type and the real pandal that suits it: its best time to
visit, the nearest metro and its 2026 theme. Then send it to the group and see who's the All-nighter. Takes about a minute.</p>
<form id="quiz" onsubmit="return false">{qs}
<button class="cta" type="submit" id="qGo">See my pandal →</button></form>
<div id="qOut" hidden>{results}
<div class="share"><a class="sb wa" id="qWa" rel="noopener" href="#">Send on WhatsApp</a><button class="sb" type="button" id="qStory">Story card</button><button class="sb" type="button" id="qAgain">Take it again</button></div>
<canvas id="qCard" width="1080" height="1920" hidden></canvas>
</div>
</article>
<style>.q{{border:1px solid var(--line);border-radius:14px;margin:14px 0;padding:10px 14px}}.q legend{{padding:0 6px}}
.opt{{display:flex;gap:10px;align-items:flex-start;padding:8px 4px;border-top:1px solid var(--line);cursor:pointer}}.opt:first-of-type{{border-top:0}}
.opt input{{margin-top:6px}}.q.miss{{border-color:#B91C1C}}.q-type{{margin-top:0}}.q-result .photo img{{width:100%;height:auto;border-radius:12px}}</style>
<script>
(function () {{
  var T = {data}, f = document.getElementById('quiz'), out = document.getElementById('qOut'), cur = null;
  var order = T.map(function (t) {{ return t.id; }});
  f.addEventListener('submit', function () {{
    var score = {{}}, miss = null;
    document.querySelectorAll('.q').forEach(function (q) {{
      var c = q.querySelector('input:checked'); q.classList.toggle('miss', !c);
      if (!c && !miss) miss = q; if (c) score[c.value] = (score[c.value] || 0) + 1;
    }});
    if (miss) {{ miss.scrollIntoView({{ behavior: 'smooth', block: 'center' }}); return; }}
    cur = T.slice().sort(function (a, b) {{ return (score[b.id] || 0) - (score[a.id] || 0) || order.indexOf(a.id) - order.indexOf(b.id); }})[0];
    document.querySelectorAll('.q-result').forEach(function (s) {{ s.hidden = s.id !== 'r-' + cur.id; }});
    f.hidden = true; out.hidden = false; out.scrollIntoView({{ behavior: 'smooth' }});
    var url = location.origin + location.pathname + cur.id + '/?src=wa_quiz';
    document.getElementById('qWa').href = 'https://wa.me/?text=' + encodeURIComponent('I\\'m ' + cur.a + ' ' + cur.en + ' (' + cur.bn + ')! My pujo pandal: ' + cur.pandal + '.\\nWhich pandal are you? ' + url);
  }});
  document.getElementById('qAgain').onclick = function () {{ f.reset(); f.hidden = false; out.hidden = true; f.scrollIntoView({{ behavior: 'smooth' }}); }};
  function card() {{
    var cv = document.getElementById('qCard'), x = cv.getContext('2d'), g = x.createLinearGradient(0, 0, 0, 1920);
    g.addColorStop(0, '#9F1239'); g.addColorStop(1, '#3B0A1C'); x.fillStyle = g; x.fillRect(0, 0, 1080, 1920);
    x.strokeStyle = '#FDE68A'; x.lineWidth = 6; x.strokeRect(50, 50, 980, 1820);
    x.textAlign = 'center'; x.fillStyle = '#FDE68A'; x.font = '600 52px system-ui, sans-serif'; x.fillText('MY PUJO TYPE', 540, 300);
    x.fillStyle = '#FFFFFF'; x.font = 'bold 104px Georgia, serif';
    var words = cur.en.split(' '), lines = [], l = '';
    words.forEach(function (w) {{ var n = l ? l + ' ' + w : w; if (x.measureText(n).width > 900 && l) {{ lines.push(l); l = w; }} else l = n; }}); lines.push(l);
    lines.forEach(function (s, i) {{ x.fillText(s, 540, 520 + i * 120); }});
    var y = 520 + lines.length * 120 + 40;
    x.fillStyle = '#FDE68A'; x.font = 'bold 84px "Noto Sans Bengali", "Hind Siliguri", sans-serif'; x.fillText(cur.bn, 540, y);
    x.fillStyle = '#FFFFFF'; x.font = '52px system-ui, sans-serif'; x.fillText('My pandal:', 540, y + 230);
    x.font = 'bold 72px Georgia, serif'; x.fillText(cur.pandal, 540, y + 330);
    x.fillStyle = '#F5E6C8'; x.font = '44px system-ui, sans-serif'; x.fillText('Best time: ' + cur.best, 540, y + 450);
    if (cur.metro) x.fillText('Metro: ' + cur.metro, 540, y + 520);
    x.fillStyle = '#FDE68A'; x.font = '600 50px system-ui, sans-serif'; x.fillText('Which pandal are you?', 540, 1640);
    x.fillStyle = '#FFFFFF'; x.globalAlpha = 0.85; x.font = '42px system-ui, sans-serif'; x.fillText('{esc(host)}/quiz', 540, 1720); x.globalAlpha = 1;
    return cv;
  }}
  document.getElementById('qStory').onclick = function () {{
    card().toBlob(function (b) {{
      var file = new File([b], 'my-pujo-type.png', {{ type: 'image/png' }});
      if (navigator.canShare && navigator.canShare({{ files: [file] }})) navigator.share({{ files: [file], text: 'Which pandal are you?' }}).catch(function () {{}});
      else {{ var a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = 'my-pujo-type.png'; a.click(); }}
    }}, 'image/png');
  }};
}})();
</script>"""
        self.page(path, f"Which Kolkata Pandal Matches Your Pujo Vibe? Durga Puja {self.year} Quiz",
                  f"Six quick questions, in English and Bengali, then your pujo type and the Kolkata pandal that suits it, with its best time, metro and {self.year} theme.",
                  body, crumbs=(("Pujo quiz", path),), priority=0.8, app_link="",
                  ld=({"@context": "https://schema.org", "@type": "Quiz", "name": "Which Kolkata pandal matches your pujo vibe?", "url": self.url(path),
                       "about": {"@type": "Thing", "name": "Durga Puja in Kolkata"}, "educationalUse": "entertainment", "inLanguage": ["en", "bn"]},),
                  note="Your answers stay on your phone; nothing is sent anywhere.")

    def quiz_result(self, t, types):
        up = "../../../"
        path = f"quiz/which-pandal/{t['id']}/"
        p = t["pandal"]
        others = " · ".join(f"<a href='../{x['id']}/'>{esc(x['en'])}</a>" for x in types if x["id"] != t["id"])
        body = f"""<article>
<h1>{esc(t['en'])}: my pujo pandal is {esc(p['name'])}</h1>
<p class="lead">Someone sent you their pujo type. {esc(t['line'])} Their pandal is {esc(p['name'])}. What's yours?</p>
<p><a class="cta" href="../?src=quiz_result">Take the quiz: which pandal are you? →</a></p>
<section class="q-result">{self.quiz_result_html(t, up)}</section>
<p><small>The other types: {others}</small></p>
</article>"""
        self.page(path, f"I'm {a_an(t['en'])} {t['en']}: my Durga Puja pandal is {p['name']}",
                  f"{t['en']} ({t['bn']}): {t['line']} Take the six-question quiz to find your Kolkata pandal.",
                  body, crumbs=(("Pujo quiz", "quiz/which-pandal/"), (t["en"], path)), priority=0.4, app_link="",
                  og_image=p["photo"] or None, og_alt=p["name"] if p["photo"] else "")
