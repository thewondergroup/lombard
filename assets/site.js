
  document.documentElement.classList.add('js');
  const root = document.documentElement;

  // Years since 1998
  document.querySelectorAll('.years').forEach(el => el.textContent = new Date().getFullYear() - 1998);

  // Header state
  const hero = document.querySelector('.hero, .page-hero');
  const onScroll = () => root.classList.toggle('scrolled', !hero || hero.classList.contains('page-hero') || window.scrollY > hero.offsetHeight - 100);
  onScroll(); window.addEventListener('scroll', onScroll, { passive: true });

  // Overlay menu
  const btn = document.querySelector('.menu-btn');
  const overlay = document.getElementById('overlay');
  const setMenu = open => {
    root.classList.toggle('menu-open', open);
    document.body.style.overflow = open ? 'hidden' : '';
    btn.setAttribute('aria-expanded', open);
    btn.querySelector('.word').textContent = open ? 'Close' : 'Menu';
    overlay.setAttribute('aria-hidden', !open);
  };
  btn.addEventListener('click', () => setMenu(!root.classList.contains('menu-open')));
  overlay.querySelectorAll('a').forEach(a => a.addEventListener('click', () => setMenu(false)));
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && root.classList.contains('menu-open')) { setMenu(false); btn.focus(); } });
  let rt; window.addEventListener('resize', () => { root.classList.add('resizing'); clearTimeout(rt); rt = setTimeout(() => root.classList.remove('resizing'), 250); });

  // Open now (London time)
  (function () {
    const hours = {1:[7,23],2:[7,23],3:[7,23],4:[7,23],5:[7,23],6:[12,17],0:[12,18]};
    const fmt = h => (h % 12 || 12) + (h < 12 ? 'am' : 'pm');
    const names = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
    const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', weekday: 'short', hour: 'numeric', minute: 'numeric', hourCycle: 'h23' }).formatToParts(new Date());
    const get = t => parts.find(p => p.type === t).value;
    const day = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].indexOf(get('weekday'));
    const now = Number(get('hour')) + Number(get('minute')) / 60;
    const t = hours[day];
    let text, closed = false;
    if (t && now >= t[0] && now < t[1]) text = 'Open now until ' + fmt(t[1]);
    else {
      closed = true;
      if (t && now < t[0]) text = 'Opens ' + fmt(t[0]) + ' today';
      else for (let i = 1; i <= 7; i++) { const d = (day + i) % 7, h = hours[d]; if (h) { text = 'Opens ' + fmt(h[0]) + (i === 1 ? ' tomorrow' : ' ' + names[d]); break; } }
    }
    document.querySelectorAll('.status').forEach(el => { el.textContent = text; el.classList.toggle('closed', closed); });
  })();

  // Reveal on scroll
  const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }), { threshold: .12, rootMargin: '0px 0px -40px 0px' });
  document.querySelectorAll('.reveal').forEach(el => io.observe(el));

  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Dome parallax
  const domeImg = document.querySelector('.dome img');
  if (!reduce && domeImg) {
    let tick = false;
    const move = () => { const r = domeImg.parentElement.getBoundingClientRect(); if (r.bottom > 0 && r.top < innerHeight) { domeImg.style.transform = 'translateY(' + ((r.top + r.height / 2 - innerHeight / 2) / innerHeight * -70) + 'px)'; } tick = false; };
    addEventListener('scroll', () => { if (!tick) { requestAnimationFrame(move); tick = true; } }, { passive: true }); move();
  }


  // Intro: remove the loader once it has played
  if (root.classList.contains('show-loader')) setTimeout(() => { const l = document.querySelector('.loader'); if (l) l.remove(); root.classList.remove('show-loader'); }, 2900);

  // Menu photos (desktop): load on first open, swap on hover
  (function () {
    const imgs = [...document.querySelectorAll('.overlay-photos img')];
    const links = [...document.querySelectorAll('.overlay [data-photo]')];
    let loaded = false;
    const on = n => imgs.forEach((im, k) => im.classList.toggle('is-on', k === n));
    btn.addEventListener('click', () => { if (!loaded) { imgs.forEach(im => { im.src = im.dataset.src; }); loaded = true; } on(imgs.length - 1); });
    links.forEach(a => { a.addEventListener('mouseenter', () => on(+a.dataset.photo)); a.addEventListener('focus', () => on(+a.dataset.photo)); });
  })();

  // Booking bar: date / time / guests, opens SevenRooms pre-filled
  (function () {
    const form = document.getElementById('book-bar'); if (!form) return;
    const dSel = form.querySelector('#bb-date'), tSel = form.querySelector('#bb-time'), gSel = form.querySelector('#bb-guests');
    const seat = {1:[7,22],2:[7,22],3:[7,22],4:[7,22],5:[7,22],6:[12,16.5],0:[12,17]}; // first and last seating
    const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date());
    const g = t => +parts.find(p => p.type === t).value;
    const nowH = g('hour') + g('minute') / 60;
    const base = Date.UTC(g('year'), g('month') - 1, g('day'));
    const days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'], months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const pad = n => String(n).padStart(2, '0');
    let added = 0;
    for (let i = 0; added < 21 && i < 40; i++) {
      const d = new Date(base + i * 864e5), wd = d.getUTCDay(), s = seat[wd];
      if (!s) continue;
      if (i === 0 && nowH + .5 > s[1]) continue;
      const iso = d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate());
      const label = i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : days[wd] + ' ' + d.getUTCDate() + ' ' + months[d.getUTCMonth()];
      const o = new Option(label, iso); o.dataset.wd = wd; o.dataset.today = i === 0 ? '1' : ''; dSel.add(o); added++;
    }
    const fmt = h => { const hh = Math.floor(h), mm = h % 1 ? '30' : '00'; return { val: pad(hh) + ':' + mm, label: ((hh % 12) || 12) + (mm === '30' ? '.30' : '') + (hh < 12 ? 'am' : 'pm') }; };
    const fillTimes = () => {
      const o = dSel.selectedOptions[0]; if (!o) return;
      const s = seat[o.dataset.wd], prev = tSel.value; tSel.innerHTML = '';
      for (let h = s[0]; h <= s[1]; h += .5) { if (o.dataset.today && h < nowH + .5) continue; const f = fmt(h); tSel.add(new Option(f.label, f.val)); }
      const want = prev && [...tSel.options].some(x => x.value === prev) ? prev : ((o.dataset.wd === '6' || o.dataset.wd === '0') ? '13:00' : '19:00');
      tSel.value = [...tSel.options].some(x => x.value === want) ? want : (tSel.options[0] && tSel.options[0].value);
    };
    for (let n = 1; n <= 10; n++) gSel.add(new Option(n + (n === 1 ? ' guest' : ' guests'), n));
    gSel.add(new Option('Larger group', 'large'));
    gSel.value = '2';
    dSel.addEventListener('change', fillTimes); fillTimes();
    form.addEventListener('submit', e => {
      e.preventDefault();
      if (gSel.value === 'large') { location.href = 'mailto:events@1lombardstreet.com?subject=' + encodeURIComponent('Group booking ' + dSel.selectedOptions[0].text + ' ' + tSel.selectedOptions[0].text); return; }
      const q = new URLSearchParams({ date: dSel.value, party_size: gSel.value, start_time: tSel.value, default_date: dSel.value, default_party_size: gSel.value, default_time: tSel.value });
      const url = 'https://www.sevenrooms.com/reservations/1lombardstreet?' + q.toString();
      const w = window.open(url, '_blank', 'noopener'); if (!w) location.href = url;
    });
  })();


  // Producers map: hover / tap hello
  (function(){
    const spots=[...document.querySelectorAll('.spots .hl')];
    const crw={}; document.querySelectorAll('.crw').forEach(c=>crw[c.dataset.i]=c);
    const hello=i=>{const c=crw[i]; if(!c) return; c.classList.remove('hello'); void c.offsetWidth; c.classList.add('hello');};
    document.querySelectorAll('.crw').forEach(c=>c.addEventListener('animationend',e=>{if(e.target===c) c.classList.remove('hello');}));
    spots.forEach((h,i)=>{
      h.addEventListener('mouseenter',()=>hello(i));
      h.addEventListener('click',()=>{hello(i); spots.forEach(o=>o.classList.remove('tap')); h.classList.add('tap'); clearTimeout(h._t); h._t=setTimeout(()=>h.classList.remove('tap'),1800);});
    });
  })();

  // Video: respect reduced motion
  const vid = document.querySelector('.hero video');
  if (reduce && vid) { vid.removeAttribute('autoplay'); vid.pause(); }

  // Menu tabs: highlight the menu in view
  (function () {
    const tabs = [...document.querySelectorAll('.tabs a')]; if (!tabs.length) return;
    const bar = tabs[0].parentElement, byId = {};
    tabs.forEach(a => byId[a.getAttribute('href').slice(1)] = a);
    const on = a => { tabs.forEach(t => t.classList.toggle('on', t === a)); bar.scrollTo({ left: a.offsetLeft - bar.clientWidth / 2 + a.offsetWidth / 2, behavior: 'smooth' }); };
    const spy = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting && byId[e.target.id]) on(byId[e.target.id]); }), { rootMargin: '-35% 0px -60% 0px' });
    document.querySelectorAll('.menu-sec').forEach(s => spy.observe(s));
  })();

  // Enquiry forms: open an email with the details filled in
  document.querySelectorAll('form[data-mailto]').forEach(f => f.addEventListener('submit', e => {
    e.preventDefault();
    const d = new FormData(f), lines = [];
    for (const [k, v] of d) if (String(v).trim()) lines.push(k + ': ' + v);
    const subject = f.dataset.subject + (d.get('Name') ? ' from ' + d.get('Name') : '');
    location.href = 'mailto:' + f.dataset.mailto + '?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(lines.join('\n'));
    const b = f.querySelector('button'); if (b) b.textContent = 'Opening your email…';
  }));

  // Producers map: zoom buttons, drag to pan, double-click to zoom
  (function () {
    const map = document.querySelector('.producers .map'); if (!map) return;
    const view = document.createElement('div'); view.className = 'map-view' + (map.classList.contains('reveal') ? ' reveal' : '');
    map.classList.remove('reveal'); map.parentNode.insertBefore(view, map); view.appendChild(map);
    const ui = document.createElement('div'); ui.className = 'map-zoom';
    ui.innerHTML = '<button type="button" class="in" aria-label="Zoom in">+</button><button type="button" class="out" aria-label="Zoom out">&minus;</button><button type="button" class="rs" aria-label="Reset zoom">1:1</button>';
    view.appendChild(ui);
    const MAX = 3; let s = 1, x = 0, y = 0;
    const clamp = () => { const w = view.clientWidth, h = view.clientHeight; x = Math.min(0, Math.max(w - w * s, x)); y = Math.min(0, Math.max(h - h * s, y)); };
    const apply = () => { clamp(); map.style.transform = s === 1 ? '' : 'translate(' + x + 'px,' + y + 'px) scale(' + s + ')'; map.style.setProperty('--inv', 1 / s); view.classList.toggle('zoomed', s > 1);
      ui.querySelector('.in').disabled = s >= MAX; ui.querySelector('.out').disabled = s <= 1; ui.querySelector('.rs').disabled = s <= 1; };
    const zoomTo = (ns, cx, cy) => { ns = Math.max(1, Math.min(MAX, ns)); if (cx == null) { cx = view.clientWidth / 2; cy = view.clientHeight / 2; }
      x = cx - (cx - x) * ns / s; y = cy - (cy - y) * ns / s; s = ns; apply(); };
    ui.querySelector('.in').onclick = () => zoomTo(s + .75);
    ui.querySelector('.out').onclick = () => zoomTo(s - .75);
    ui.querySelector('.rs').onclick = () => { s = 1; x = y = 0; apply(); };
    view.addEventListener('dblclick', e => { if (e.target.closest('.map-zoom')) return; const r = view.getBoundingClientRect(); zoomTo(s >= MAX ? 1 : s + 1, e.clientX - r.left, e.clientY - r.top); });
    let drag = null;
    view.addEventListener('pointerdown', e => { if (s === 1 || e.target.closest('.map-zoom')) return; drag = { px: e.clientX, py: e.clientY, x, y, moved: false }; });
    window.addEventListener('pointermove', e => { if (!drag) return; const dx = e.clientX - drag.px, dy = e.clientY - drag.py;
      if (!drag.moved && Math.hypot(dx, dy) < 4) return; drag.moved = true; view.classList.add('dragging'); x = drag.x + dx; y = drag.y + dy; apply(); });
    window.addEventListener('pointerup', () => { drag = null; view.classList.remove('dragging'); });
    window.addEventListener('resize', apply);
    if (view.classList.contains('reveal') && 'IntersectionObserver' in window) {
      const io = new IntersectionObserver(es => es.forEach(en => { if (en.isIntersecting) { view.classList.add('in'); io.disconnect(); } }), { threshold: .12 }); io.observe(view);
    } else view.classList.add('in');
    apply();
  })();
