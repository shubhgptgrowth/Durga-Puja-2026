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
