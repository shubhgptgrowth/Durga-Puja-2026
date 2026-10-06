/* Static guide pages (scripts/build_seo.py): share buttons, tick-box checklists, countdowns and site search.
 * Plain script, no dependencies; every feature is optional and the page reads fine without it. */
(function () {
  'use strict';
  var store = {
    get: function (k) { try { return JSON.parse(localStorage.getItem('ppg:' + k)); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem('ppg:' + k, JSON.stringify(v)); } catch (e) { /* private mode */ } },
  };

  // Share: the phone's share sheet where there is one, WhatsApp otherwise; and copy link
  document.querySelectorAll('[data-share]').forEach(function (b) {
    b.addEventListener('click', function (e) {
      var url = location.href.split('#')[0], title = document.title.split(' | ')[0];
      if (b.dataset.share === 'native' && navigator.share) { e.preventDefault(); navigator.share({ title: title, url: url }).catch(function () {}); }
      else if (b.dataset.share === 'copy') {
        e.preventDefault();
        (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(function () { b.textContent = '✓ Link copied'; }, function () { prompt('Copy this link', url); });
      }
    });
  });
  if (!navigator.share) document.querySelectorAll('[data-share="native"]').forEach(function (b) { b.hidden = true; });

  var post = document.querySelector('.post');
  if (post) {
    // Reading progress along the top
    var bar = document.createElement('div'); bar.className = 'progress'; bar.setAttribute('aria-hidden', 'true'); bar.innerHTML = '<span></span>';
    document.body.appendChild(bar);
    var fill = bar.firstChild, ticking = false;
    var wa = post.querySelector('[data-wa]'), fab = null, first = post.querySelector('.share'), last = post.querySelector('.share-end');
    if (wa) {   // a WhatsApp button that follows the reader once the top share buttons scroll away
      fab = document.createElement('a'); fab.className = 'fab'; fab.href = wa.href; fab.rel = 'noopener';
      fab.innerHTML = wa.querySelector('svg').outerHTML + ' Share'; fab.setAttribute('aria-label', 'Share on WhatsApp');
      document.body.appendChild(fab);
    }
    var onScroll = function () {
      ticking = false;
      var r = post.getBoundingClientRect(), total = r.height - innerHeight;
      fill.style.width = Math.max(0, Math.min(1, -r.top / (total > 0 ? total : 1))) * 100 + '%';
      if (fab) {
        var past = first && first.getBoundingClientRect().bottom < 0, atEnd = last && last.getBoundingClientRect().top < innerHeight;
        fab.classList.toggle('on', !!past && !atEnd);
      }
    };
    addEventListener('scroll', function () { if (!ticking) { ticking = true; requestAnimationFrame(onScroll); } }, { passive: true });
    onScroll();
    // "In this article" starts open on wide screens
    var toc = post.querySelector('details.toc'); if (toc && matchMedia('(min-width: 900px)').matches) toc.open = true;
    // Mantras: copy, or send on WhatsApp with the link
    post.querySelectorAll('blockquote.verse').forEach(function (q) {
      var text = q.innerText.trim(), tools = document.createElement('div'); tools.className = 'verse-tools';
      var page = location.href.split('#')[0];
      tools.innerHTML = '<button type="button">Copy</button><a rel="noopener">Send on WhatsApp</a>';
      tools.lastChild.href = 'https://wa.me/?text=' + encodeURIComponent(text + '\n\n— ' + document.title.split(' | ')[0] + '\n' + page);
      tools.firstChild.addEventListener('click', function () {
        var b = tools.firstChild;
        (navigator.clipboard ? navigator.clipboard.writeText(text + '\n' + page) : Promise.reject()).then(function () { b.textContent = '✓ Copied'; }, function () { prompt('Copy', text); });
      });
      q.appendChild(tools);
    });
  }


  // Listen: reads the guide aloud with the phone's own voice (Web Speech API; nothing is recorded or sent anywhere)
  var listenBtn = document.querySelector('[data-listen]');
  if (listenBtn && post && 'speechSynthesis' in window && window.SpeechSynthesisUtterance) {
    var synth = window.speechSynthesis, INDIC = /[ऀ-৿]/;
    var voices = [], pickVoice = function (lang) {
      var v = voices.filter(function (x) { return x.lang && x.lang.replace('_', '-').toLowerCase().indexOf(lang) === 0; });
      return v.filter(function (x) { return /google|natural|enhanced|premium/i.test(x.name); })[0] || v[0] || null;
    };
    var loadVoices = function () { voices = synth.getVoices() || []; };
    loadVoices(); if (synth.addEventListener) synth.addEventListener('voiceschanged', loadVoices);
    listenBtn.hidden = false;

    // What to read, in order: title, the short answer, then the body (skipping captions, credits, buttons and cards).
    // Built on the first tap, once the phone's voices have loaded.
    var blocks = [], build = function () {
    var add = function (el, text, lang) { text = (text || '').replace(/\s+/g, ' ').trim(); if (text) blocks.push({ el: el, text: text, lang: lang }); };
    var sentences = function (el, text, lang) {   // long paragraphs in sentence-sized pieces (some browsers stop after ~15 s)
      var parts = text.match(/[^.!?]+[.!?]+["”’)]*\s*|[^.!?]+$/g) || [text], buf = '';
      parts.forEach(function (x) { if ((buf + x).length > 220 && buf) { add(el, buf, lang); buf = ''; } buf += x; });
      add(el, buf, lang);
    };
    add(post.querySelector('h1'), post.querySelector('h1').textContent);
    var tl = post.querySelector('.tldr p'); if (tl) sentences(tl, tl.textContent);
    var scope = post.querySelectorAll('.timeline li, .recipe-facts, .ingredients h2, .ingredients li, .box h2, .box li, #method, #steps, .steps li, .prose > h2, .prose > h3, .prose > p, .prose > ul > li, .prose > ol > li, .prose > blockquote, .prose > .callout, .prose .table, .glossary dt, .glossary dd, .faq h2, .faq details');
    scope.forEach(function (el) {
      if (el.matches('blockquote.verse')) {   // mantras: each line in its own script's voice, if the phone has one
        el.querySelectorAll('p').forEach(function (pp) {
          pp.innerHTML.split(/<br\s*\/?>/i).forEach(function (line) {
            var t = line.replace(/<[^>]+>/g, '').trim();
            if (!t) return;
            if (INDIC.test(t)) { var bn = /[ঀ-৿]/.test(t) ? 'bn' : 'hi'; if (pickVoice(bn) || pickVoice('hi')) add(pp, t, pickVoice(bn) ? bn : 'hi'); }
            else add(pp, t);
          });
        });
        return;
      }
      if (el.matches('.faq details')) { add(el, el.querySelector('summary').textContent); var a = el.querySelector('p'); if (a) sentences(el, a.textContent); return; }
      if (el.matches('.table')) { add(el, 'There is a table here; it is easier to read on screen.'); return; }
      if (el.matches('.recipe-facts')) { add(el, Array.prototype.map.call(el.querySelectorAll('div'), function (d) { return d.querySelector('dt').textContent.replace(/[^\w\s]/g, '').trim() + ': ' + d.querySelector('dd').textContent; }).join('. ')); return; }
      var clone = el.cloneNode(true);
      clone.querySelectorAll('figure, .verse-tools, .thumb, small.hint').forEach(function (x) { x.remove(); });
      sentences(el, clone.textContent);
    });
    };

    // The player
    var bar = document.createElement('div'); bar.className = 'player'; bar.hidden = true; bar.setAttribute('role', 'region'); bar.setAttribute('aria-label', 'Listen');
    bar.innerHTML = '<button type="button" data-a="prev" aria-label="Back">⏮</button><button type="button" data-a="play" class="pp" aria-label="Pause">⏸</button>' +
      '<button type="button" data-a="next" aria-label="Forward">⏭</button><span class="pl-t"><b>Listening</b><span class="pl-n"></span></span>' +
      '<button type="button" data-a="rate" class="rate" aria-label="Speed">1×</button><button type="button" data-a="close" aria-label="Stop">✕</button>' +
      '<span class="pl-bar"><span></span></span>';
    document.body.appendChild(bar);
    var RATES = [1, 1.25, 1.5, 0.85], rate = store.get('listen:rate') || 1, i = 0, playing = false, current = null, fails = 0;
    var ppBtn = bar.querySelector('.pp'), nEl = bar.querySelector('.pl-n'), fillEl = bar.querySelector('.pl-bar span'), rateBtn = bar.querySelector('.rate');
    rateBtn.textContent = rate + '×';
    var mark = function () {
      document.querySelectorAll('.speaking').forEach(function (x) { x.classList.remove('speaking'); });
      var b = blocks[i]; if (!b || !b.el) return;
      b.el.classList.add('speaking');
      var r = b.el.getBoundingClientRect();
      if (r.top < 60 || r.bottom > innerHeight - 90) b.el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      nEl.textContent = (i + 1) + ' of ' + blocks.length;
      fillEl.style.width = ((i + 1) / blocks.length * 100) + '%';
    };
    var speak = function () {
      synth.cancel();
      if (i >= blocks.length) { stop(); return; }
      var b = blocks[i], u = new SpeechSynthesisUtterance(b.text), v = pickVoice(b.lang || 'en-in') || pickVoice('en-gb') || pickVoice('en');
      u.lang = v ? v.lang : (b.lang ? b.lang + '-IN' : 'en-IN'); try { if (v) u.voice = v; } catch (e) { /* lang alone picks a voice */ }
      u.rate = rate; current = u;
      u.onstart = function () { fails = 0; };
      u.onend = function () { if (current === u && playing) { i++; speak(); } };
      u.onerror = function (e) {
        if (current !== u || !playing || e.error === 'interrupted' || e.error === 'canceled') return;
        if (++fails >= 3) { stop(); listenBtn.innerHTML = 'Your browser can\u2019t read aloud here. Try Chrome or Safari, or install a text-to-speech voice.'; listenBtn.disabled = true; return; }
        i++; speak();
      };
      mark(); synth.speak(u);
    };
    var play = function () { playing = true; bar.hidden = false; document.body.classList.add('listening'); ppBtn.textContent = '⏸'; ppBtn.setAttribute('aria-label', 'Pause'); speak(); };
    var pause = function () { playing = false; current = null; synth.cancel(); ppBtn.textContent = '▶'; ppBtn.setAttribute('aria-label', 'Play'); };
    var stop = function () { pause(); bar.hidden = true; document.body.classList.remove('listening'); document.querySelectorAll('.speaking').forEach(function (x) { x.classList.remove('speaking'); }); i = 0; };
    listenBtn.addEventListener('click', function () { loadVoices(); if (!blocks.length) build(); if (!playing) { if (bar.hidden) i = 0; play(); } });
    bar.addEventListener('click', function (e) {
      var a = e.target.closest('button'); if (!a) return;
      var act = a.dataset.a;
      if (act === 'play') { playing ? pause() : play(); }
      else if (act === 'prev') { i = Math.max(0, i - 1); if (playing) speak(); else mark(); }
      else if (act === 'next') { i = Math.min(blocks.length - 1, i + 1); if (playing) speak(); else mark(); }
      else if (act === 'rate') { rate = RATES[(RATES.indexOf(rate) + 1) % RATES.length]; a.textContent = rate + '×'; store.set('listen:rate', rate); if (playing) speak(); }
      else if (act === 'close') stop();
    });
    // Tap a paragraph while listening to jump there
    post.addEventListener('click', function (e) {
      if (bar.hidden || e.target.closest('a, button, summary, input, label')) return;
      for (var k = 0; k < blocks.length; k++) if (blocks[k].el && blocks[k].el.contains(e.target)) { i = k; if (playing) speak(); else mark(); return; }
    });
    addEventListener('pagehide', function () { synth.cancel(); });
  }

  // Checklists: ticks are remembered on this device, per page
  var boxes = document.querySelectorAll('.checklist input[type=checkbox]');
  if (boxes.length) {
    var key = 'check:' + location.pathname, saved = store.get(key) || {};
    boxes.forEach(function (c) {
      c.checked = !!saved[c.dataset.k];
      c.addEventListener('change', function () { saved[c.dataset.k] = c.checked; store.set(key, saved); });
    });
  }

  // Countdowns: <span data-countdown="2026-10-17" data-label="Shashthi">
  document.querySelectorAll('[data-countdown]').forEach(function (el) {
    var target = new Date(el.dataset.countdown + 'T00:00:00+05:30'), days = Math.ceil((target - Date.now()) / 864e5);
    var label = el.dataset.label || 'the puja';
    el.textContent = days > 1 ? days + ' days to ' + label : days === 1 ? label + ' is tomorrow' : days === 0 ? label + ' is today' : '';
    el.hidden = !el.textContent;
  });

  // Search: /search/ loads search-index.json once and filters as you type
  var q = document.getElementById('q'), out = document.getElementById('results');
  if (q && out) {
    var index = null;
    var norm = function (s) { return s.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, ''); };
    var run = function () {
      var words = norm(q.value).split(/\s+/).filter(Boolean);
      if (!words.length) { out.innerHTML = ''; return; }
      var hits = index.map(function (d) {
        var hay = norm(d.t + ' ' + d.k + ' ' + d.s), score = 0;
        for (var i = 0; i < words.length; i++) { if (hay.indexOf(words[i]) < 0) return null; score += norm(d.t).indexOf(words[i]) >= 0 ? 3 : 1; }
        return { d: d, score: score + (d.y === 'Article' ? 1 : 0) };
      }).filter(Boolean).sort(function (a, b) { return b.score - a.score; }).slice(0, 30);
      out.innerHTML = hits.length ? hits.map(function (h) {
        var e = document.createElement('a'); e.href = h.d.u; e.textContent = h.d.t;
        var li = document.createElement('li'); li.appendChild(e);
        var s = document.createElement('span'); s.textContent = h.d.s; li.appendChild(s);
        return li.outerHTML;
      }).join('') : '<li class="none">No matches. Try “anjali”, “Ashtami”, “khichuri” or a pandal name.</li>';
      history.replaceState(null, '', '?q=' + encodeURIComponent(q.value));
    };
    fetch(out.dataset.index).then(function (r) { return r.json(); }).then(function (j) {
      index = j; q.disabled = false;
      var start = new URLSearchParams(location.search).get('q'); if (start) { q.value = start; }
      run(); q.focus();
    });
    q.addEventListener('input', function () { if (index) run(); });
  }
})();
