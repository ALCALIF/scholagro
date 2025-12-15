(function(){
  // Initialize theme and page on DOM ready
  document.addEventListener('DOMContentLoaded', function(){
    document.body.classList.add('page-loaded');
    
    // Enable Bootstrap tooltips
    if (window.bootstrap){
      document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el=>{
        bootstrap.Tooltip.getOrCreateInstance(el);
      });
    }

  /* ========== RECENTLY VIEWED PRODUCTS ========== */
  (function(){
    const KEY = 'recent_products';
    function getRecent(){
      try{ return JSON.parse(localStorage.getItem(KEY) || '[]'); }catch{ return []; }
    }
    function setRecent(arr){
      try{ localStorage.setItem(KEY, JSON.stringify(arr.slice(0, 16))); }catch{}
    }
    function addRecent(p){
      if (!p || !p.slug) return;
      const items = getRecent().filter(x=>x.slug !== p.slug);
      items.unshift({ id: p.id, slug: p.slug, name: p.name, image: p.image, price: p.price });
      setRecent(items);
    }
    function money(x){ try{ return 'Ksh ' + Number(x).toFixed(0); }catch{ return 'Ksh 0'; } }
    function cardHTML(it){
      const img = it.image || 'https://placehold.co/400x300';
      return `
        <div class="col-6 col-md-3 mb-2">
          <div class="card h-100 product-card position-relative shadow-sm hover-lift">
            <div class="ratio ratio-4x3 overflow-hidden bg-light">
              <img loading="lazy" class="card-img-top object-fit-cover" src="${img}" alt="${it.name}">
            </div>
            <div class="card-body d-flex flex-column">
              <h6 class="card-title mb-2 text-truncate fw-600" title="${it.name}">${it.name}</h6>
              <div class="mb-3"><span class="text-success fw-bold">${money(it.price)}</span></div>
              <div class="mt-auto d-flex gap-2 flex-wrap">
                <a class="btn btn-sm btn-outline-success fw-600" href="/product/${it.slug}"><i class="bi bi-eye"></i> <span class="d-none d-lg-inline">View</span></a>
              </div>
            </div>
          </div>
        </div>`;
    }
    function render(containerId, excludeSlug){
      const root = document.getElementById(containerId);
      if (!root) return;
      const items = getRecent().filter(x=>x.slug !== excludeSlug).slice(0, 8);
      if (!items.length){ root.closest('[data-recently-section]')?.classList.add('d-none'); return; }
      const row = root.querySelector('.row');
      if (!row) return;
      row.innerHTML = items.map(cardHTML).join('');
    }
    // Expose a hook to add current product (set by inline script on product page)
    if (window.CURRENT_PRODUCT){ addRecent(window.CURRENT_PRODUCT); }
    // Render on pages with containers
    render('recentlyViewedHome', null);
    render('recentlyViewedProduct', (window.CURRENT_PRODUCT && window.CURRENT_PRODUCT.slug) || null);
  })();
  /* ========== SOCKET.IO (REALTIME) ========== */
  (function(){
    if (!window.io) return;
    try{
      const socket = io();
      socket.on('connect', ()=>{ console.log('Socket connected'); });
      socket.on('connected', (d)=>{ console.log('Connected to socket room', d.room); });
      // Realtime product reviews
      function initialsAvatar(name){
        try{
          const n = (name||'').trim();
          const parts = n.split(/\s+/).filter(Boolean);
          const initials = (parts[0]?.[0]||'S').toUpperCase() + (parts[1]?.[0]||'G').toUpperCase();
          const bg = '#0ea5e9';
          const fg = '#fff';
          const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
            <rect width="64" height="64" rx="8" fill="${bg}"/>
            <text x="50%" y="52%" dominant-baseline="middle" text-anchor="middle" font-family="Poppins, Arial, sans-serif" font-size="28" font-weight="700" fill="${fg}">${initials}</text>
          </svg>`;
          return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);
        }catch{ return 'https://placehold.co/64x64?text=%20'; }
      }
      function renderReviewItem(r){
        const img = r.avatar_url || initialsAvatar(r.author||'User');
        const rating = Math.max(0, Math.min(5, parseInt(r.rating||'5')));
        const stars = '★★★★★☆☆☆☆☆'.slice(5 - rating, 10 - rating);
        return `
          <div class="d-flex gap-3 align-items-start py-2 border-bottom">
            <img src="${img}" alt="${r.author||'User'}" class="rounded-circle" style="width:40px;height:40px;object-fit:cover;"/>
            <div class="flex-grow-1">
              <div class="d-flex justify-content-between align-items-center">
                <strong class="small">${r.author||'Customer'}</strong>
                <span class="text-warning small" aria-label="${rating} star rating">${'★'.repeat(rating)}${'☆'.repeat(5-rating)}</span>
              </div>
              <div class="small text-muted">${r.comment||''}</div>
            </div>
          </div>`;
      }
      function unshiftReview(container, r){
        try{
          if (!container) return;
          const wrapper = container.querySelector('[data-reviews-items]') || container;
          const el = document.createElement('div');
          el.innerHTML = renderReviewItem(r);
          wrapper.prepend(el.firstElementChild);
          const max = parseInt(container.getAttribute('data-max')||'10');
          const children = wrapper.children;
          while (children.length > max){ children[children.length-1].remove(); }
        }catch{}
      }
      socket.on('review.new', (r)=>{
        const containers = document.querySelectorAll('[data-reviews]');
        containers.forEach(c=> unshiftReview(c, r));
      });
      // Optional rotator
      (function reviewsRotator(){
        const root = document.querySelector('[data-reviews-rotator]');
        if (!root) return;
        const list = root.querySelector('[data-reviews-items]');
        if (!list) return;
        setInterval(()=>{
          const first = list.firstElementChild;
          if (!first) return;
          list.appendChild(first);
        }, 5000);
      })();
      socket.on('order.status', (payload)=>{
        try{
          const orderId = payload.order_id;
          const orderEl = document.getElementById('order-detail');
          if (orderEl && String(orderEl.getAttribute('data-order-id')) === String(orderId)){
            // emulate the polling update handler to update status badge & timeline
            // we'll just reload the period fetch for the order if present
            // call fetchStatus in global scope: if not present, simply reload
            if (typeof fetchOrderStatus === 'function') fetchOrderStatus(); else window.location.reload();
          }
          // Show toast for update
          showToast('Order ' + payload.order_id + ' status: ' + payload.status.replace('_',' '), true);
        }catch(e){/* ignore */}
      });
      socket.on('notification', (n)=>{ showToast(n.title + ' – ' + n.message, true); });
      socket.on('rider.location', (payload)=>{ 
        try{ 
          // For now, show toast; a map can later consume these events
          showToast('Rider ' + payload.rider_id + ' updated location', true);
          console.log('Rider location', payload);
        }catch(e){}
      });
    }catch(_e){}
  })();

  /* ========== MINI CART DRAWER ========== */
  (function(){
    const toggleEl = document.querySelector('[data-mini-cart-toggle]');
    const offcanvasEl = document.getElementById('offcanvasCart');
    const itemsEl = document.getElementById('mini-cart-items');
    const subtotalEl = document.getElementById('mini-cart-subtotal');
    let offcanvas;
    if (offcanvasEl && window.bootstrap){
      offcanvas = bootstrap.Offcanvas.getOrCreateInstance(offcanvasEl);
    }
      // Poll cart count every 10s to keep badge synchronized across tabs
      async function refreshCartCount(){
        try{
          const res = await fetch('/cart/mini');
          const data = await res.json();
          if (!res.ok || !data) return;
          const badge = document.getElementById('cart-count-badge');
          if (badge && typeof data.count !== 'undefined') badge.textContent = data.count;
          // If mini cart is open, refresh its content
          const itemsEl = document.getElementById('mini-cart-items');
          if (itemsEl && document.querySelector('.offcanvas.show')){
            // reuse existing rendering logic by calling fetchMiniCart via event
            document.querySelector('[data-mini-cart-toggle]')?.click();
          }
        }catch(_e){}
      }
      setInterval(refreshCartCount, 10000);
      // Initial refresh
      refreshCartCount();
    async function fetchMiniCart(){
      try{
        const res = await fetch('/cart/mini');
        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error('Failed');
        renderMiniCart(data);
        if (offcanvas) offcanvas.show();
      }catch(_e){
        // Fallback to full cart page
        window.location.href = '/cart/';
      }
    }
    function money(k){ try{ return 'Ksh ' + Number(k).toFixed(2); }catch{ return 'Ksh 0.00'; } }
    function renderMiniCart(data){
      if (!itemsEl || !subtotalEl) return;
      if (!data.items || !data.items.length){
        itemsEl.innerHTML = '<div class="text-center text-muted py-5"><i class="bi bi-bag"></i> Your cart is empty</div>';
        subtotalEl.textContent = money(0);
        const waBtn = document.getElementById('wa-mini-cart-order');
        if (waBtn) waBtn.href = 'https://wa.me/';
        const promo = document.getElementById('mini-cart-promo');
        if (promo) promo.textContent = '';
        return;
      }
      const html = data.items.map(it=>{
        const img = it.image_url ? `<img src="${it.image_url}" alt="${it.name}" class="rounded me-2" style="width:48px;height:48px;object-fit:cover;">` : '';
        return `
          <div class="d-flex align-items-center justify-content-between py-2 border-bottom" data-item-id="${it.item_id}">
            <div class="d-flex align-items-center flex-grow-1 me-2">
              ${img}
              <div class="small">
                <a class="text-decoration-none" href="/product/${it.slug}"><strong>${it.name}</strong></a><br>
                <span class="text-muted">${money(it.price)}</span>
              </div>
            </div>
            <div class="d-flex align-items-center gap-1">
              <button class="btn btn-sm btn-outline-secondary mc-dec" aria-label="Decrease">-</button>
              <input class="form-control form-control-sm text-center mc-qty" style="width:48px" type="number" min="0" max="99" value="${it.quantity}">
              <button class="btn btn-sm btn-outline-secondary mc-inc" aria-label="Increase">+</button>
            </div>
            <div class="text-end ms-2" style="width:90px;">
              <div class="small fw-600">${money(it.line_total)}</div>
              <button class="btn btn-link p-0 text-danger mc-remove">Remove</button>
            </div>
          </div>
        `;
      }).join('');
      itemsEl.innerHTML = html;
      subtotalEl.textContent = money(data.subtotal);
      try{
        const off = document.getElementById('offcanvasCart');
        const waBtn = document.getElementById('wa-mini-cart-order');
        if (off && waBtn){
          const site = (off.getAttribute('data-site') || 'ScholaGro');
          let wa = (off.getAttribute('data-wa') || '').replace(/\D/g,'');
          if (wa && wa.startsWith('0')) wa = '254' + wa.slice(1);
          if (wa && /^7\d{8}$/.test(wa)) wa = '254' + wa;
          const lines = [site + ' Order Request'];
          (data.items||[]).forEach(it=>{
            try{
              const img = it.image_url || '';
              lines.push(`- ${it.name} x${it.quantity} — Ksh ${Number(it.price||0).toFixed(2)}`);
              if (img) lines.push(img);
              lines.push(`${window.location.origin}/product/${it.slug}`);
            }catch(_e){}
          });
          lines.push('Subtotal: ' + money(data.subtotal));
          const msg = encodeURIComponent(lines.join('\n'));
          waBtn.href = wa ? (`https://wa.me/${wa}?text=${msg}`) : (`https://wa.me/?text=${msg}`);
        }
        // Free delivery promo hint
        const promo = document.getElementById('mini-cart-promo');
        if (promo){
          const offEl = document.getElementById('offcanvasCart');
          const thrRaw = offEl ? (offEl.getAttribute('data-free') || '') : '';
          const thr = parseFloat(thrRaw);
          if (!isNaN(thr) && thr > 0){
            const remaining = Math.max(0, thr - Number(data.subtotal||0));
            if (remaining > 0){
              promo.textContent = `Add Ksh ${remaining.toFixed(2)} more to get FREE delivery`;
              promo.classList.remove('text-success');
              promo.classList.add('text-muted');
            } else {
              promo.textContent = 'Free delivery applied!';
              promo.classList.remove('text-muted');
              promo.classList.add('text-success');
            }
          } else {
            promo.textContent = '';
          }
        }
      }catch(e){}
    }
    async function updateItem(itemId, qty){
      try{
        const res = await fetch('/cart/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
          body: JSON.stringify({ item_id: itemId, quantity: qty })
        });
        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error('Update failed');
        // Refresh list
        await fetchMiniCart();
        const badge = document.getElementById('cart-count-badge');
        if (badge && typeof data.cart_count !== 'undefined') badge.textContent = data.cart_count;
      }catch(_e){ /* ignore */ }
    }
    if (toggleEl){
      toggleEl.addEventListener('click', (e)=>{ e.preventDefault(); fetchMiniCart(); });
    }
    if (itemsEl){
      itemsEl.addEventListener('click', (e)=>{
        const row = e.target.closest('[data-item-id]');
        if (!row) return;
        const id = parseInt(row.getAttribute('data-item-id'));
        const qtyInput = row.querySelector('.mc-qty');
        let qty = parseInt(qtyInput && qtyInput.value || '0');
        if (e.target.closest('.mc-inc')){ qty = Math.min(99, qty + 1); updateItem(id, qty); }
        if (e.target.closest('.mc-dec')){ qty = Math.max(0, qty - 1); updateItem(id, qty); }
        if (e.target.closest('.mc-remove')){ updateItem(id, 0); }
      });
      itemsEl.addEventListener('change', (e)=>{
        const input = e.target.closest('.mc-qty');
        if (!input) return;
        const row = input.closest('[data-item-id]');
        const id = parseInt(row.getAttribute('data-item-id'));
        let qty = parseInt(input.value || '0');
        qty = Math.max(0, Math.min(99, isNaN(qty) ? 0 : qty));
        updateItem(id, qty);
      });
    }
  })();
    
    // Theme init on DOM ready
    initTheme();
    
    // Add scroll effect to navbar
    addNavbarScrollEffect();

    // Apply animation delays from data-anim-delay attributes
    document.querySelectorAll('[data-anim-delay]')
      .forEach(el => {
        const d = parseFloat(el.getAttribute('data-anim-delay'));
        if (!isNaN(d)) el.style.animationDelay = d + 's';
      });

    // ========== PREMIUM MOTION INIT ==========
    try {
      // Smooth scrolling via Lenis (desktop only and reduced-motion aware)
      if (window.Lenis && !window.matchMedia('(prefers-reduced-motion: reduce)').matches && window.innerWidth >= 768) {
        const lenis = new Lenis({ duration: 1.1, easing: (t)=>1-Math.pow(1-t,3) });
        function raf(time){ lenis.raf(time); requestAnimationFrame(raf); }
        requestAnimationFrame(raf);
        window.__lenis = lenis;
      }
    } catch(e) {}

    // VanillaTilt 3D tilt for product cards (desktop only)
    try {
      if (window.VanillaTilt && window.innerWidth >= 992) {
        document.querySelectorAll('.product-card').forEach(el => {
          if (!el.__tiltInited){
            VanillaTilt.init(el, { max: 6, speed: 400, glare: false, scale: 1.02, reverse: false });
            el.__tiltInited = true;
          }
        });
      }
    } catch(e) {}

    // Magnetic buttons (success/primary only to reduce cost)
    (function magnetic(){
      const btns = Array.from(document.querySelectorAll('.btn.btn-success, .btn.btn-outline-success'));
      if (!btns.length) return;
      const strength = 16;
      btns.forEach(btn => {
        let ox=0, oy=0;
        btn.addEventListener('mousemove', (e)=>{
          const r = btn.getBoundingClientRect();
          const x = e.clientX - r.left - r.width/2;
          const y = e.clientY - r.top - r.height/2;
          btn.style.transform = `translate(${Math.max(-strength, Math.min(strength, x*0.05))}px, ${Math.max(-strength, Math.min(strength, y*0.05))}px)`;
        });
        btn.addEventListener('mouseleave', ()=>{ btn.style.transform = 'translate(0,0)'; });
      });
    })();

    // GSAP timelines and scroll effects
    (function gsapMotion(){
      if (!window.gsap) return;
      const gsap = window.gsap;
      try { if (window.ScrollTrigger) gsap.registerPlugin(window.ScrollTrigger); } catch(e) {}

      // Hero entrance sequence
      try {
        const tl = gsap.timeline({ defaults:{ duration: 0.7, ease: 'power2.out' } });
        const brand = document.querySelector('.navbar .navbar-brand');
        const nav = document.querySelectorAll('.navbar .nav-link');
        const hero = document.querySelector('.hero');
        const h1 = hero && hero.querySelector('h1');
        const p = hero && hero.querySelector('.hero-subtitle');
        const ctas = hero && hero.querySelectorAll('.btn');
        if (brand) tl.from(brand, { y: -12, opacity: 0 }, 0);
        if (nav && nav.length) tl.from(nav, { y: -10, opacity: 0, stagger: 0.03 }, 0.1);
        if (h1) tl.from(h1, { y: 20, opacity: 0 }, 0.15);
        if (p) tl.from(p, { y: 16, opacity: 0 }, 0.25);
        if (ctas && ctas.length) tl.from(ctas, { y: 12, opacity: 0, stagger: 0.06 }, 0.35);
      } catch(e) {}

      // Parallax on hero content vs background (subtle)
      try {
        if (window.ScrollTrigger){
          const hero = document.querySelector('.hero');
          if (hero){
            gsap.to(hero.querySelector('.hero-title-main'), { yPercent: -8, scrollTrigger: { trigger: hero, start: 'top top', end: '+=40%', scrub: 0.3 }});
            gsap.to(hero.querySelector('.hero-gradient'), { yPercent: 6, scrollTrigger: { trigger: hero, start: 'top top', end: '+=40%', scrub: 0.3 }});
          }
        }
      } catch(e) {}

      // Product grid stagger (home/shop/category)
      try {
        const cards = document.querySelectorAll('.product-card');
        if (cards && cards.length){
          gsap.from(cards, { opacity: 0, y: 20, scale: 0.98, stagger: 0.05, duration: 0.5, ease: 'power2.out', scrollTrigger: cards[0] ? { trigger: cards[0].closest('.row, .section-alt') || cards[0], start: 'top 85%' } : undefined });
        }
      } catch(e) {}

      // Pinned section header progress (Top Selling if present)
      try {
        if (window.ScrollTrigger){
          const topSelling = Array.from(document.querySelectorAll('h3')).find(h => /Top Selling/i.test(h.textContent||''));
          if (topSelling){
            const bar = document.createElement('div');
            bar.style.height = '3px'; bar.style.background = 'linear-gradient(90deg,#10b981,#34d399)'; bar.style.width = '0%'; bar.style.borderRadius = '999px';
            topSelling.parentElement && topSelling.parentElement.appendChild(bar);
            gsap.to(bar, { width: '100%', ease:'none', scrollTrigger: { trigger: topSelling, start: 'top bottom', end: 'bottom top', scrub: 0.5 }});
          }
        }
      } catch(e) {}
    })();

    // Swup transitions (fade) and re-init hooks
    (function swupInit(){
      try {
        if (!window.Swup) return;
        const swup = new Swup({ containers: ['#swup'], plugins: [new window.SwupFadeTheme()] });
        function reinit(){
          try { AOS && AOS.refreshHard && AOS.refreshHard(); } catch(e){}
          // re-run minimal init for motion/tilt
          if (window.VanillaTilt && window.innerWidth >= 992){
            document.querySelectorAll('.product-card').forEach(el=>{
              if (!el.__tiltInited){ VanillaTilt.init(el, { max:6, speed:400, scale:1.02 }); el.__tiltInited = true; }
            });
          }
          if (window.gsap && window.ScrollTrigger){ window.ScrollTrigger.refresh(); }
        }
        document.addEventListener('swup:contentReplaced', reinit);
      } catch(e){}
    })();
  });
  
  const toastEl = document.getElementById('toast');
  const toastBody = document.getElementById('toast-body');
  const csrfToken = (document.querySelector('meta[name="csrf-token"]')||{}).content || '';
  let toast;
  
  if (toastEl && typeof bootstrap !== 'undefined') {
    toast = new bootstrap.Toast(toastEl, { delay: 2500 });
  }

  // Navbar scroll effect
  function addNavbarScrollEffect(){
    const navbar = document.getElementById('mainNavbar');
    if (!navbar) return;
    
    window.addEventListener('scroll', ()=>{
      if (window.scrollY > 50){
        navbar.classList.add('scrolled');
      } else {
        navbar.classList.remove('scrolled');
      }
    });
  }

  /* ========== HEADER ROTATOR (Green Basket inspired) ========== */
  (function headerRotator(){
    const elements = document.getElementById('header-rotator');
    if (!elements) return;
    const words = [
      'Fresh, Local Produce',
      'Same-day Delivery',
      'Farm to Doorstep',
      'Quality Guaranteed',
      'Best Prices in Town'
    ];
    let idx = 0;
    function showNext(){
      elements.classList.remove('show');
      elements.classList.add('fade');
      setTimeout(()=>{
        idx = (idx + 1) % words.length;
        elements.textContent = words[idx];
        elements.classList.remove('fade');
        elements.classList.add('show');
      }, 350);
    }
    // rotate every 3 seconds
    setInterval(showNext, 3000);
  })();

  // Promo marquee: sliding announcements
  (function promoMarquee(){
    const el = document.getElementById('promo-marquee');
    if (!el) return;
    let messages = [
      'Fresh groceries delivered to your doorstep—fast and affordable!',
      'Order today and enjoy same-day delivery across KU, Ruiru & Nairobi!',
      'Get the best prices on fruits, veggies, and household essentials!',
      'ScholaGro—We deliver exactly what you ordered, fresh and clean!',
      'Save more this season with our daily offers and discounts!'
    ];
    try{
      const dataEl = document.getElementById('promoMessagesData');
      if (dataEl){
        const parsed = JSON.parse(dataEl.textContent || '[]');
        if (Array.isArray(parsed) && parsed.length){
          messages = parsed.map(x=>String(x)).filter(s=>s && s.trim());
        }
      }
    }catch(_e){}
    let i = 0;
    // play one message at a time using CSS animation duration computed per text length
    function playMessage(){
      const msg = messages[i];
      // set text
      el.textContent = msg;
      // determine duration (base 8s + extra per long text)
      const duration = Math.max(6000, msg.length * 60);
      // apply animation
      el.style.animationDuration = duration + 'ms';
      el.classList.remove('marquee-anim');
      // force reflow
      void el.offsetWidth;
      el.classList.add('marquee-anim');
      // advance index when animation ends
      setTimeout(()=>{
        i = (i + 1) % messages.length;
        playMessage();
      }, duration + 300);
    }
    playMessage();
  })();

  // Premium Ripple effect for buttons
  document.addEventListener('click', (e)=>{
    const btn = e.target.closest('.btn');
    if (!btn) return;
    
    // Simple loading state support
    if (btn.matches('.btn-async')){
      btn.classList.add('disabled');
      const original = btn.innerHTML;
      btn.setAttribute('data-original-html', original);
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span><span class="d-none d-md-inline">Processing...</span>';
      
      setTimeout(()=>{
        // Auto restore after 2.5s if not restored by logic
        if (btn.getAttribute('data-original-html')){
          btn.innerHTML = btn.getAttribute('data-original-html');
          btn.removeAttribute('data-original-html');
          btn.classList.remove('disabled');
        }
      }, 2500);
    }
    
    // Create ripple effect
    const rect = btn.getBoundingClientRect();
    const ripple = document.createElement('span');
    const size = Math.max(rect.width, rect.height);
    const x = e.clientX - rect.left - size/2;
    const y = e.clientY - rect.top - size/2;
    
    ripple.style.position = 'absolute';
    ripple.style.left = x + 'px';
    ripple.style.top = y + 'px';
    ripple.style.width = ripple.style.height = size + 'px';
    ripple.style.background = 'rgba(255, 255, 255, 0.4)';
    ripple.style.borderRadius = '50%';
    ripple.style.transform = 'scale(0)';
    ripple.style.opacity = '1';
    ripple.style.pointerEvents = 'none';
    ripple.style.transition = 'transform 0.6s ease-out, opacity 0.8s ease-out';
    ripple.style.zIndex = '10';
    
    btn.appendChild(ripple);
    
    requestAnimationFrame(()=>{ 
      ripple.style.transform = 'scale(2.5)'; 
      ripple.style.opacity = '0'; 
    });
    
    setTimeout(()=>{ ripple.remove(); }, 800);
  });

  // Open Now indicator (timezone-aware: Africa/Nairobi)
  function parseTimeToMinutes(str){
    if (!str || /closed/i.test(str)) return null;
    const m = str.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
    if (!m) return null;
    let h = parseInt(m[1],10);
    const min = parseInt(m[2],10);
    const ampm = m[3].toUpperCase();
    if (ampm === 'PM' && h !== 12) h += 12;
    if (ampm === 'AM' && h === 12) h = 0;
    return h*60 + min;
  }
  function nairobiNowMinutes(){
    try{
      const parts = new Intl.DateTimeFormat('en-KE', {hour:'2-digit', minute:'2-digit', hourCycle:'h23', timeZone:'Africa/Nairobi'}).formatToParts(new Date());
      const h = parseInt(parts.find(p=>p.type==='hour').value,10);
      const m = parseInt(parts.find(p=>p.type==='minute').value,10);
      return h*60 + m;
    }catch{
      const d = new Date();
      return d.getHours()*60 + d.getMinutes();
    }
  }
  function updateOpenNow(){
    const nowMin = nairobiNowMinutes();
    document.querySelectorAll('.js-open-now').forEach(el=>{
      const o = parseTimeToMinutes(el.getAttribute('data-open'));
      const c = parseTimeToMinutes(el.getAttribute('data-close'));
      let openNow = false;
      if (o != null && c != null){
        openNow = nowMin >= o && nowMin <= c;
      }
      el.classList.remove('bg-success','bg-danger','text-bg-success','text-bg-danger');
      if (o != null && c != null){
        el.textContent = openNow ? 'Open now' : 'Closed now';
        el.classList.add(openNow ? 'text-bg-success' : 'text-bg-danger');
      } else {
        el.textContent = 'Closed today';
        el.classList.add('text-bg-danger');
      }
    });
  }
  updateOpenNow();
  setInterval(updateOpenNow, 60000);

  // Sale countdown timers: look for elements with data-sale-ends (ISO string)
  function updateSaleTimers(){
    const nodes = document.querySelectorAll('[data-sale-ends]');
    const now = Date.now();
    nodes.forEach(el=>{
      const ts = el.getAttribute('data-sale-ends');
      if (!ts) return;
      const end = Date.parse(ts);
      if (isNaN(end)) return;
      let diff = Math.max(0, end - now);
      const d = Math.floor(diff / (24*3600e3)); diff -= d*24*3600e3;
      const h = Math.floor(diff / 3600e3); diff -= h*3600e3;
      const m = Math.floor(diff / 60e3); diff -= m*60e3;
      const s = Math.floor(diff / 1e3);
      el.textContent = d>0 ? `${d}d ${h}h ${m}m` : `${h}h ${m}m ${s}s`;
    });
  }
  updateSaleTimers();
  setInterval(updateSaleTimers, 1000);

  // Quick View modal logic
  document.addEventListener('click', (e)=>{
    const qv = e.target.closest('.btn-quick-view');
    if (!qv) return;
    
    const name = qv.getAttribute('data-name');
    const price = qv.getAttribute('data-price');
    const oldp = qv.getAttribute('data-oldprice');
    const image = qv.getAttribute('data-image');
    const url = qv.getAttribute('data-url');
    const pid = qv.getAttribute('data-product-id');
    
    const titleEl = document.getElementById('qv-title');
    const priceEl = document.getElementById('qv-price');
    const oldEl = document.getElementById('qv-oldprice');
    const imgEl = document.getElementById('qv-image');
    const linkEl = document.getElementById('qv-view');
    const addEl = document.getElementById('qv-add');
    
    if (titleEl) titleEl.textContent = name || 'Quick View';
    if (priceEl) priceEl.textContent = `Ksh ${price}`;
    if (oldEl){
      if (oldp){ 
        oldEl.textContent = oldp; 
        oldEl.classList.add('visible');
      }
      else { 
        oldEl.classList.remove('visible');
      }
    }
    if (imgEl && image) imgEl.src = image;
    if (linkEl && url) linkEl.href = url;
    if (addEl){ addEl.setAttribute('data-product-id', pid || ''); }
    
    const modalEl = document.getElementById('quickViewModal');
    if (modalEl && typeof bootstrap !== 'undefined'){
      const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
      modal.show();
    }
  });

  document.addEventListener('click', async (e)=>{
    const add = e.target.closest('#qv-add');
    if (!add) return;
    const pid = add.getAttribute('data-product-id');
    if (!pid) return;
    try{
      const res = await fetch('/cart/add', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken': csrfToken}, body: JSON.stringify({product_id: pid, quantity: 1})});
      if (res.ok){
        showToast('Added to cart', true);
        const data = await res.json().catch(()=>({}));
        const badge = document.getElementById('cart-count-badge');
        if (badge && data && typeof data.cart_count !== 'undefined'){
          badge.textContent = data.cart_count;
        }
        // restore loading state
        const original = add.getAttribute('data-original-html');
        if (original){ add.innerHTML = original; add.classList.remove('disabled'); add.removeAttribute('data-original-html'); }
      } else {
        showToast('Unable to add to cart', false);
        const original = add.getAttribute('data-original-html');
        if (original){ add.innerHTML = original; add.classList.remove('disabled'); add.removeAttribute('data-original-html'); }
      }
    }catch(err){ showToast('Network error', false); }
  });
  function showToast(msg, success=true){
    if (!toastEl || !toastBody) return;
    toastEl.classList.remove('text-bg-success','text-bg-danger');
    toastEl.classList.add(success ? 'text-bg-success' : 'text-bg-danger');
    // Lottie micro animation (success only)
    try {
      toastBody.innerHTML = '';
      if (success && window.lottie){
        const wrap = document.createElement('span');
        wrap.style.display = 'inline-flex';
        wrap.style.width = '24px'; wrap.style.height = '24px'; wrap.style.marginRight = '8px';
        toastBody.appendChild(wrap);
        window.lottie.loadAnimation({ container: wrap, renderer: 'svg', loop: false, autoplay: true, path: 'https://assets10.lottiefiles.com/packages/lf20_jbrw3hcz.json' });
      }
      const span = document.createElement('span'); span.textContent = ' ' + msg; toastBody.appendChild(span);
    } catch(e) {
      toastBody.textContent = msg;
    }
    if (toast) toast.show();
  }
  async function addToCart(productId, btn){
    if (btn && btn.classList.contains('disabled')) return false;
    const badge = document.getElementById('cart-count-badge');
    let prev = null;
    if (badge){
      prev = parseInt(badge.textContent||'0');
      badge.textContent = String(prev + 1); // optimistic
    }
    if (btn){
      btn.classList.add('disabled');
      btn.setAttribute('data-original-html', btn.innerHTML);
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Adding...';
    }
    try{
      const res = await fetch('/cart/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: JSON.stringify({ product_id: productId })
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.message || 'Failed');
      if (badge && typeof data.cart_count !== 'undefined') badge.textContent = data.cart_count;
      showToast(data.message || 'Added to cart', true);
      if (btn){
        const original = btn.getAttribute('data-original-html');
        if (original){
          btn.innerHTML = original;
          btn.classList.remove('disabled');
          btn.removeAttribute('data-original-html');
        }
      }
      return true;
    }catch(err){
      if (badge && prev != null) badge.textContent = String(prev); // revert
      showToast(err.message || 'Error adding to cart', false);
      if (btn){
        const original = btn.getAttribute('data-original-html');
        if (original){
          btn.innerHTML = original;
          btn.classList.remove('disabled');
          btn.removeAttribute('data-original-html');
        }
      }
      return false;
    }
  }

  // Skeleton removal when images load
  function setupSkeletons(){
    document.querySelectorAll('.ratio .card-img-top').forEach(img=>{
      const wrapper = img.closest('.ratio');
      if (wrapper && !wrapper.classList.contains('skeleton-armed')){
        wrapper.classList.add('skeleton','skeleton-armed');
        if (img.complete){
          wrapper.classList.remove('skeleton');
        } else {
          img.addEventListener('load', ()=> wrapper.classList.remove('skeleton'), {once:true});
          img.addEventListener('error', ()=> wrapper.classList.remove('skeleton'), {once:true});
        }
      }
    });
  }
  setupSkeletons();
  document.addEventListener('DOMContentLoaded', setupSkeletons);
  async function toggleWishlist(productId, btn){
    if (btn.classList.contains('disabled')) return;
    btn.classList.add('disabled');
    const icon = btn.querySelector('i');
    const origHtml = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
    try{
      const res = await fetch('/wishlist/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId })
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.message || 'Failed');
      btn.classList.toggle('btn-outline-danger', !data.added);
      btn.classList.toggle('btn-danger', data.added);
      if (icon){
        icon.classList.toggle('bi-heart', !data.added);
        icon.classList.toggle('bi-heart-fill', data.added);
      }
      showToast(data.added ? 'Added to wishlist' : 'Removed from wishlist', true);
    }catch(err){
      showToast(err.message || 'Error updating wishlist', false);
    } finally {
      btn.classList.remove('disabled');
      btn.innerHTML = origHtml;
    }
  }
  document.addEventListener('click', (e)=>{
    const btn = e.target.closest('.btn-add-to-cart');
    if (btn){
      e.preventDefault();
      const pid = btn.getAttribute('data-product-id');
      if (pid) addToCart(pid, btn);
      return;
    }
    const wbtn = e.target.closest('.btn-wishlist');
    if (wbtn){
      e.preventDefault();
      const pid = wbtn.getAttribute('data-product-id');
      if (pid) toggleWishlist(pid, wbtn);
      return;
    }
  });

  /* ========== CATEGORY PAGE: Qty controls and Proceed bar ========== */
  (function(){
    const proceedBar = document.getElementById('catProceedBar');
    const proceedCountEl = document.getElementById('catProceedCount');
    function setProceed(count){
      if (!proceedBar || !proceedCountEl) return;
      const n = Math.max(0, parseInt(count||'0')); 
      proceedCountEl.textContent = String(n);
      proceedBar.classList.toggle('d-none', n<=0);
    }
    // initialize from navbar badge if present
    const badge = document.getElementById('cart-count-badge');
    if (badge) setProceed(badge.textContent || '0');

    async function fetchMini(){
      try{ const r = await fetch('/cart/mini'); return await r.json(); }catch{ return {items:[], subtotal:0, ok:false}; }
    }
    async function findItemByProduct(pid){
      const data = await fetchMini();
      if (!data || !Array.isArray(data.items)) return null;
      return data.items.find(it => String(it.product_id) === String(pid)) || null;
    }
    async function addProduct(pid, qty){
      try{
        const res = await fetch('/cart/add', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken': csrfToken}, body: JSON.stringify({product_id: pid, quantity: qty||1})});
        const data = await res.json().catch(()=>({}));
        if (res.ok && data){
          const b = document.getElementById('cart-count-badge');
          if (b && typeof data.cart_count !== 'undefined') b.textContent = data.cart_count;
          setProceed((b && b.textContent) || data.cart_count || 0);
          showToast(data.message || 'Added to cart', true);
          return true;
        }
      }catch{}
      showToast('Unable to add to cart', false);
      return false;
    }
    async function updateItemQtyByProduct(pid, newQty){
      const item = await findItemByProduct(pid);
      if (!item){
        if (newQty>0) return addProduct(pid, newQty); // fall back
        return false;
      }
      try{
        const res = await fetch('/cart/update', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken': csrfToken}, body: JSON.stringify({item_id: item.item_id, quantity: newQty})});
        const data = await res.json().catch(()=>({}));
        if (res.ok && data){
          const b = document.getElementById('cart-count-badge');
          if (b && typeof data.cart_count !== 'undefined') b.textContent = data.cart_count;
          setProceed((b && b.textContent) || data.cart_count || 0);
          return true;
        }
      }catch{}
      showToast('Unable to update cart', false);
      return false;
    }

    function getControlsFrom(el){
      const card = el.closest('[data-qty-controls]') || el.closest('.card');
      if (!card) return null;
      const controls = card.querySelector('[data-qty-controls]') || el.closest('[data-qty-controls]');
      const addBtn = card.querySelector('.btn-add-to-cart');
      const input = controls ? controls.querySelector('.cat-qty-input') : null;
      const pid = (controls && controls.getAttribute('data-product-id')) || (addBtn && addBtn.getAttribute('data-product-id'));
      return {card, controls, addBtn, input, pid};
    }

    document.addEventListener('click', async (e)=>{
      const add = e.target.closest('.btn-add-to-cart');
      if (add){
        e.preventDefault();
        const pid = add.getAttribute('data-product-id');
        const ctx = getControlsFrom(add);
        if (!pid || !ctx) return;
        const ok = await addProduct(pid, 1);
        if (ok && ctx.controls && ctx.addBtn){ ctx.controls.hidden = false; ctx.addBtn.classList.add('d-none'); }
      }
      const inc = e.target.closest('.cat-qty-inc');
      if (inc){
        const ctx = getControlsFrom(inc);
        if (!ctx || !ctx.input || !ctx.pid) return;
        let v = Math.min(99, (parseInt(ctx.input.value)||1) + 1);
        ctx.input.value = v;
        await addProduct(ctx.pid, 1);
      }
      const dec = e.target.closest('.cat-qty-dec');
      if (dec){
        const ctx = getControlsFrom(dec);
        if (!ctx || !ctx.input || !ctx.pid) return;
        let v = Math.max(0, (parseInt(ctx.input.value)||1) - 1);
        ctx.input.value = v;
        await updateItemQtyByProduct(ctx.pid, v);
        if (v<=0 && ctx.addBtn && ctx.controls){ ctx.addBtn.classList.remove('d-none'); ctx.controls.hidden = true; }
      }
    });
    document.addEventListener('change', async (e)=>{
      const input = e.target.closest('.cat-qty-input');
      if (!input) return;
      const ctx = getControlsFrom(input);
      if (!ctx || !ctx.pid) return;
      let v = parseInt(input.value||'1');
      v = Math.max(0, Math.min(99, isNaN(v)?1:v));
      input.value = v;
      await updateItemQtyByProduct(ctx.pid, v);
      if (v<=0 && ctx.addBtn && ctx.controls){ ctx.addBtn.classList.remove('d-none'); ctx.controls.hidden = true; }
    });
  })();

  // Autosuggest with keyboard navigation
  const searchForm = document.querySelector('.nav-search');
  const searchInput = searchForm ? searchForm.querySelector('input[name="q"]') : null;
  let suggestBox;
  if (searchInput){
    suggestBox = document.createElement('div');
    suggestBox.className = 'dropdown-menu show shadow-sm';
    suggestBox.style.position = 'absolute';
    suggestBox.style.transform = 'translate3d(0, 40px, 0)';
    suggestBox.style.display = 'none';
    searchForm.style.position = 'relative';
    searchForm.appendChild(suggestBox);

    let timer;
    let activeIndex = -1;
    function renderItems(items){
      suggestBox.innerHTML = '';
      items.forEach((it, idx)=>{
        const a = document.createElement('a');
        a.className = 'dropdown-item';
        a.textContent = it.name;
        a.href = '/product/' + it.slug;
        a.setAttribute('data-index', String(idx));
        a.addEventListener('mouseenter', ()=> setActive(idx));
        suggestBox.appendChild(a);
      });
      activeIndex = items.length ? 0 : -1;
      setActive(activeIndex);
      suggestBox.style.display = items.length ? 'block' : 'none';
    }
    function setActive(idx){
      const children = Array.from(suggestBox.querySelectorAll('.dropdown-item'));
      children.forEach((el, i)=> el.classList.toggle('active', i === idx));
      activeIndex = idx;
    }
    async function fetchSuggest(q){
      try{
        const res = await fetch('/api/suggest?q=' + encodeURIComponent(q));
        const data = await res.json();
        renderItems((data && data.items) ? data.items : []);
      }catch{
        suggestBox.style.display = 'none';
      }
    }
    searchInput.addEventListener('input', ()=>{
      clearTimeout(timer);
      const q = searchInput.value.trim();
      if (!q){ suggestBox.style.display = 'none'; return; }
      timer = setTimeout(()=> fetchSuggest(q), 200);
    });
    searchInput.addEventListener('keydown', (e)=>{
      if (suggestBox.style.display !== 'block') return;
      const items = Array.from(suggestBox.querySelectorAll('.dropdown-item'));
      if (!items.length) return;
      if (e.key === 'ArrowDown'){
        e.preventDefault();
        setActive(Math.min(items.length - 1, activeIndex + 1));
      } else if (e.key === 'ArrowUp'){
        e.preventDefault();
        setActive(Math.max(0, activeIndex - 1));
      } else if (e.key === 'Enter'){
        if (activeIndex >= 0 && items[activeIndex]){
          e.preventDefault();
          window.location.href = items[activeIndex].href;
        }
      } else if (e.key === 'Escape'){
        suggestBox.style.display = 'none';
      }
    });
    document.addEventListener('click', (e)=>{
      if (!suggestBox.contains(e.target) && e.target !== searchInput){
        suggestBox.style.display = 'none';
      }
    });
  }

  // Confirm Modal for destructive actions
  const confirmModalEl = document.getElementById('confirmModal');
  const confirmModalBody = document.getElementById('confirmModalBody');
  const confirmYesBtn = document.getElementById('confirmModalYes');
  let confirmTargetForm = null;
  if (confirmModalEl){
    const confirmModal = new bootstrap.Modal(confirmModalEl);
    document.addEventListener('submit', (e)=>{
      const form = e.target.closest('form.js-confirm');
      if (form){
        e.preventDefault();
        confirmTargetForm = form;
        const msg = form.getAttribute('data-confirm') || 'Are you sure?';
        if (confirmModalBody) confirmModalBody.textContent = msg;
        confirmModal.show();
      }
    });
    if (confirmYesBtn){
      confirmYesBtn.addEventListener('click', ()=>{
        if (confirmTargetForm){
          confirmModal.hide();
          confirmTargetForm.submit();
          confirmTargetForm = null;
        }
      });
    }
  }

  // Star rating picker on product review
  const reviewForm = document.querySelector('form[action*="/review"]');
  if (reviewForm){
    const select = reviewForm.querySelector('select[name="rating"]');
    if (select){
      // Create star UI replacing select
      const container = document.createElement('div');
      container.className = 'mb-2';
      const hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.name = 'rating';
      reviewForm.replaceChild(container, select.parentElement);
      reviewForm.insertBefore(hidden, reviewForm.querySelector('div.mb-2'));
      const pid = reviewForm.getAttribute('data-product-id');
      const storageKey = pid ? `rating:${pid}` : null;
      const setStars = (val)=>{
        container.querySelectorAll('.star-btn i').forEach((icon, idx)=>{
          icon.className = idx < val ? 'bi bi-star-fill text-warning' : 'bi bi-star';
        });
      };
      for (let i=1;i<=5;i++){
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-link p-0 me-1 star-btn';
        btn.setAttribute('data-value', i);
        btn.innerHTML = '<i class="bi bi-star"></i>';
        btn.addEventListener('click', ()=>{
          hidden.value = String(i);
          setStars(i);
          if (storageKey) try{ localStorage.setItem(storageKey, String(i)); }catch{}
        });
        container.appendChild(btn);
      }
      // Apply persisted selection
      if (storageKey){
        try{
          const saved = parseInt(localStorage.getItem(storageKey));
          if (!isNaN(saved) && saved>=1 && saved<=5){ hidden.value = String(saved); setStars(saved); }
        }catch{}
      }
    }
  }

  // Flash messages -> Bootstrap Toasts
  const toastElFlash = document.getElementById('toast');
  const toastBodyFlash = document.getElementById('toast-body');
  const flashesJsonEl = document.getElementById('flashes-data');
  let FL = [];
  if (flashesJsonEl){
    try { FL = JSON.parse(flashesJsonEl.textContent || '[]'); } catch(_e) {}
  }
  if (toastElFlash && toastBodyFlash && FL.length){
    const variant = (cat)=>{
      switch(cat){
        case 'success': return 'text-bg-success';
        case 'info': return 'text-bg-info';
        case 'warning': return 'text-bg-warning';
        case 'danger':
        case 'error': return 'text-bg-danger';
        default: return 'text-bg-secondary';
      }
    };
    const bsToast = new bootstrap.Toast(toastElFlash, {delay: 5000});
    const queue = Array.from(FL);
    const flashContainer = document.getElementById('flashes-data');
    // Keep inline alerts visible for accessibility and persistence
    const step = ()=>{
      if (!queue.length) return;
      const item = queue.shift();
      toastBodyFlash.textContent = item.message;
      toastElFlash.className = `toast align-items-center ${variant(item.category)} border-0`;
      bsToast.show();
      setTimeout(step, 5200);
    };
    step();
  }

  // Auto-dismiss inline flash alerts after 5 seconds
  (function(){
    const fc = document.getElementById('flash-container');
    if (fc){ setTimeout(()=>{ try{ fc.remove(); }catch{} }, 5000); }
  })();

  // Password reveal + confirm validation (storefront)
  document.addEventListener('change', (e)=>{
    const chk = e.target.closest('.js-show-pass');
    if (!chk) return;
    const form = chk.closest('form');
    if (!form) return;
    form.querySelectorAll('input[type="password"], input.js-pass').forEach(inp=>{
      try{ inp.type = chk.checked ? 'text' : 'password'; }catch{}
    });
  });
  // Toggle password visibility per field (eye button)
  document.addEventListener('click', (e)=>{
    const btn = e.target.closest('.js-toggle-pass');
    if (!btn) return;
    const group = btn.closest('.input-group');
    const input = group && group.querySelector('.js-pass');
    if (!input) return;
    const isHidden = input.type === 'password';
    input.type = isHidden ? 'text' : 'password';
    const icon = btn.querySelector('i');
    if (icon){
      icon.className = isHidden ? 'bi bi-eye-slash' : 'bi bi-eye';
    }
    // sync checkbox if present
    try{
      const chk = group.closest('form')?.querySelector('.js-show-pass');
      if (chk) chk.checked = isHidden;
    }catch{}
  });
  document.addEventListener('submit', (e)=>{
    const form = e.target.closest('form');
    if (!form) return;
    const p = form.querySelector('input[name="password"]');
    const c = form.querySelector('input[name="confirm_password"]');
    if (p && c){
      if ((p.value||'') !== (c.value||'')){
        e.preventDefault();
        showToast('Passwords do not match', false);
        try{ c.focus(); }catch{}
      }
    }
  });

  // Theme toggle with persistence and OS preference fallback
  function applyTheme(theme){
    const root = document.documentElement;
    if (theme === 'dark'){
      root.setAttribute('data-theme', 'dark');
      document.body.style.colorScheme = 'dark';
    } else {
      root.removeAttribute('data-theme');
      document.body.style.colorScheme = 'light';
    }
    
    const icon = document.getElementById('themeIcon');
    if (icon){
      icon.className = theme === 'dark' ? 'bi bi-sun' : 'bi bi-moon-stars';
      icon.style.animation = 'spin 0.6s ease-in-out';
      setTimeout(()=>{ icon.style.animation = 'none'; }, 600);
    }
  }
  
  function currentPreferredTheme(){
    let saved = null;
    try{ saved = localStorage.getItem('theme'); }catch{}
    
    if (saved === 'dark' || saved === 'light') return saved;
    
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    return prefersDark ? 'dark' : 'light';
  }
  
  function initTheme(){
    applyTheme(currentPreferredTheme());
    
    const btn = document.getElementById('themeToggle');
    if (btn){
      btn.addEventListener('click', ()=>{
        const next = (document.documentElement.getAttribute('data-theme') === 'dark') ? 'light' : 'dark';
        try{ localStorage.setItem('theme', next); }catch{}
        applyTheme(next);
      });
    }
    
    if (window.matchMedia){
      try{
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', ()=>{
          let saved = null;
          try{ saved = localStorage.getItem('theme'); }catch{}
          if (!saved) applyTheme(currentPreferredTheme());
        });
      }catch{}
    }
  }

  /* ========== DYNAMIC FEATURES ========== */

  // Newsletter subscription handler
  const newsletterForm = document.getElementById('newsletterForm');
  if (newsletterForm) {
    newsletterForm.addEventListener('submit', function(e) {
      e.preventDefault();
      const input = this.querySelector('input[type="email"]');
      const btn = this.querySelector('button');
      const originalBtnText = btn.innerHTML;
      
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Subscribing...';
      
      // Simulate subscription
      setTimeout(() => {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-check-lg me-2"></i>Subscribed!';
        btn.classList.add('btn-success');
        input.value = '';
        
        // Show success message
        if (toast && toastBody) {
          toastBody.textContent = '✓ Successfully subscribed to our newsletter!';
          toast.show();
        }
        
        setTimeout(() => {
          btn.innerHTML = originalBtnText;
          btn.classList.remove('btn-success');
        }, 3000);
      }, 1500);
    });
  }

  // Carousel auto-pause on hover for better UX
  const carousel = document.getElementById('bannerCarousel');
  if (carousel && window.bootstrap) {
    const carouselInstance = bootstrap.Carousel.getInstance(carousel) || new bootstrap.Carousel(carousel);
    
    carousel.addEventListener('mouseenter', () => {
      carouselInstance.pause();
    });
    
    carousel.addEventListener('mouseleave', () => {
      carouselInstance.cycle();
    });

    // Add keyboard navigation
    document.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') carouselInstance.prev();
      if (e.key === 'ArrowRight') carouselInstance.next();
    });
  }

  // Intersection Observer for scroll animations (lazy animations)
  if ('IntersectionObserver' in window) {
    const observerOptions = {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('in-view');
          observer.unobserve(entry.target);
        }
      });
    }, observerOptions);

    // Observe elements with animation classes
    document.querySelectorAll('[class*="animate-"]').forEach(el => {
      if (!el.classList.contains('in-view')) {
        observer.observe(el);
      }
    });

    // Observe product cards
    document.querySelectorAll('.product-card').forEach(card => {
      observer.observe(card);
    });
  }

  // Live product counter animation
  function animateCounter(element, start, end, duration = 1500) {
    const range = end - start;
    const increment = range / (duration / 16);
    let current = start;

    const counter = setInterval(() => {
      current += increment;
      if ((increment > 0 && current >= end) || (increment < 0 && current <= end)) {
        current = end;
        clearInterval(counter);
      }
      element.textContent = Math.floor(current);
    }, 16);
  }

  // Search functionality enhancement with debounce (scoped to avoid name collisions)
  (function(){
    const navSearchInput = document.querySelector('.nav-search input');
    if (!navSearchInput) return;
    let searchTimeout;
    navSearchInput.addEventListener('input', function() {
      clearTimeout(searchTimeout);
      const query = this.value.trim();
      if (query.length < 2) return;
      searchTimeout = setTimeout(() => {
        // Could add autocomplete or search suggestions here
        console.log('Searching for:', query);
      }, 300);
    });
  })();

  /* ========== ORDER DETAIL POLLING ========== */
  (function(){
    const orderEl = document.getElementById('order-detail');
    if (!orderEl) return;
    const orderId = orderEl.getAttribute('data-order-id');
    if (!orderId) return;
    const statusBadge = orderEl.querySelector('.card-body .badge');
    const timelineList = orderEl.querySelector('.card-body + .card .card-body ul') || document.querySelector('.card-body ul.list-unstyled');
    async function fetchStatus(){
      try{
        const res = await fetch(`/orders/${orderId}/status_json`);
        const data = await res.json();
        if (!res.ok || !data.ok) return;
        const newStatus = data.order && data.order.status;
        if (newStatus && statusBadge && statusBadge.textContent.trim().toLowerCase() !== newStatus.replace('_',' ').toLowerCase()){
          // Replace badge classes and text
          const map = {
            'pending': 'bg-warning', 'confirmed': 'bg-info', 'packed': 'bg-info', 'on_the_way': 'bg-primary', 'delivered': 'bg-success', 'cancelled': 'bg-danger'
          };
          // set classes
          for (const cls of ['bg-warning','bg-info','bg-primary','bg-success','bg-danger','bg-secondary']){ statusBadge.classList.remove(cls); }
          statusBadge.classList.add(map[newStatus] || 'bg-secondary');
          statusBadge.textContent = newStatus.replace('_',' ').replace(/\b\w/g, c => c.toUpperCase());
        }
        // Update timeline if logs have changed
        if (Array.isArray(data.logs) && data.logs.length && timelineList){
          const html = data.logs.map(l=>{
            const date = l.created_at ? new Date(l.created_at).toLocaleString() : '';
            const color = ['confirmed','delivered'].includes(l.status) ? 'bg-success' : 'bg-secondary';
            return `<li class="d-flex align-items-start mb-3"><span class="badge rounded-circle me-3 ${color}" style="width: 10px; height: 10px;">&nbsp;</span><div><div class="small text-muted">${date}</div><div class="fw-semibold">${l.status.replace('_',' ')}</div>${l.notes?`<div class="text-muted small">${l.notes}</div>`:''}</div></li>`;
          }).join('');
          timelineList.innerHTML = html;
        }
      }catch(e){ /* ignore */ }
    }
    // expose globally so socket updates can call it directly
    window.fetchOrderStatus = fetchStatus;
    // initial fetch
    fetchStatus();
    // poll every 6 seconds
    setInterval(fetchStatus, 6000);
  })();

  /* ========== POLL USER NOTIFICATIONS ========== */
  (function(){
    async function pollNotifications(){
      try{
        const res = await fetch('/account/notifications/json');
        const data = await res.json();
        if (!res.ok || !data || !Array.isArray(data.notifications)) return;
        for (const n of data.notifications){
          // Show toast
          showToast(n.title + (n.message ? ' – ' + n.message : ''), true);
          // mark as read
          try{ await fetch(`/account/notifications/${n.id}/read`, { method: 'POST', headers: {'X-CSRFToken': csrfToken} }); }catch(_e){}
        }
      }catch(_e){}
    }
    // initial and then every 15s
    setTimeout(()=> pollNotifications(), 5000);
    setInterval(pollNotifications, 15000);
  })();

  // Product card hover effect enhancement
  document.querySelectorAll('.product-card').forEach(card => {
    card.addEventListener('mouseenter', function() {
      this.style.transform = 'translateY(-4px)';
    });
    
    card.addEventListener('mouseleave', function() {
      this.style.transform = 'translateY(0)';
    });
  });

  // Dynamic wishlist counter update
  function updateWishlistCounter() {
    const counter = document.querySelector('[data-wishlist-count]');
    if (!counter) return;
    
    let count = parseInt(counter.getAttribute('data-wishlist-count')) || 0;
    const savedWishlist = localStorage.getItem('wishlist_count');
    if (savedWishlist) count = parseInt(savedWishlist);
    
    counter.textContent = count;
    if (count > 0) {
      counter.style.display = 'inline-block';
    }
  }
  updateWishlistCounter();

  // Add to cart animations
  document.querySelectorAll('.btn-add-to-cart').forEach(btn => {
    btn.addEventListener('click', function(e) {
      if (this.classList.contains('disabled')) return;
      
      // Create flying cart animation
      const rect = this.getBoundingClientRect();
      const particle = document.createElement('div');
      particle.style.position = 'fixed';
      particle.style.left = rect.left + 'px';
      particle.style.top = rect.top + 'px';
      particle.style.width = '40px';
      particle.style.height = '40px';
      particle.style.background = 'linear-gradient(135deg, #10b981, #059669)';
      particle.style.borderRadius = '50%';
      particle.style.zIndex = '9999';
      particle.style.pointerEvents = 'none';
      particle.style.display = 'flex';
      particle.style.alignItems = 'center';
      particle.style.justifyContent = 'center';
      particle.style.color = 'white';
      particle.style.fontSize = '20px';
      particle.innerHTML = '<i class="bi bi-bag-check"></i>';
      particle.style.boxShadow = '0 4px 12px rgba(16, 185, 129, 0.4)';
      
      document.body.appendChild(particle);
      
      // Animate to cart
      const cartIcon = document.querySelector('[data-cart-icon]');
      if (cartIcon) {
        const targetRect = cartIcon.getBoundingClientRect();
        particle.style.transition = 'all 0.8s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
        
        setTimeout(() => {
          particle.style.left = targetRect.left + 'px';
          particle.style.top = targetRect.top + 'px';
          particle.style.transform = 'scale(0.1)';
          particle.style.opacity = '0';
        }, 10);
        
        setTimeout(() => particle.remove(), 850);
      } else {
        setTimeout(() => particle.remove(), 100);
      }
    });
  });

  // Smooth scroll to sections
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const href = this.getAttribute('href');
      if (href === '#') return;
      
      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // Lazy loading for images with fade-in
  if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          img.style.opacity = '0';
          img.addEventListener('load', () => {
            img.style.transition = 'opacity 0.5s ease-in';
            img.style.opacity = '1';
          });
          if (img.complete) {
            img.style.opacity = '1';
          }
          observer.unobserve(img);
        }
      });
    });

    document.querySelectorAll('img[loading="lazy"]').forEach(img => {
      imageObserver.observe(img);
    });
  }

  // Dynamically add WhatsApp Order buttons to listing cards (category/shop)
  function addWhatsAppButtonsForListings(){
    try{
      const off = document.getElementById('offcanvasCart');
      let wa = off ? (off.getAttribute('data-wa') || '') : '';
      wa = (wa || '').replace(/\D/g,'');
      if (wa && wa.startsWith('0')) wa = '254' + wa.slice(1);
      if (wa && /^7\d{8}$/.test(wa)) wa = '254' + wa;
      document.querySelectorAll('.card .card-body').forEach(body=>{
        const actions = body.querySelector('.mt-auto.d-flex.gap-2');
        if (!actions || actions.querySelector('.wa-order-card')) return;
        const site = (off && (off.getAttribute('data-site')||'')) || (document.title || 'ScholaGro');
        // Extract product details
        const nameEl = body.querySelector('h6, .card-title, .fw-600');
        const name = (nameEl && (nameEl.textContent||'').trim()) || '';
        let price = '';
        const priceEl = body.querySelector('.text-success.fw-bold, .h5.fw-bold');
        if (priceEl){ const t = (priceEl.textContent||'').replace(/[^0-9.]/g,''); if (t) price = t; }
        const viewLink = body.querySelector('a[href^="/product/"]');
        const url = viewLink ? (viewLink.getAttribute('href') || '') : '';
        const imgEl = body.closest('.card')?.querySelector('img');
        const img = imgEl ? (imgEl.getAttribute('src')||'') : '';
        const a = document.createElement('a');
        a.className = 'btn btn-sm btn-outline-success wa-order-card';
        a.target = '_blank'; a.rel = 'noopener'; a.title = 'Order on WhatsApp';
        a.innerHTML = '<i class="bi bi-whatsapp"></i>';
        const full = url && url[0] === '/' ? (window.location.origin + url) : (url || window.location.href);
        const lines = [site + ' Order Request'];
        lines.push(name + (price ? (' — Ksh ' + price) : ''));
        if (img) lines.push(img);
        lines.push(full);
        const msg = encodeURIComponent(lines.join('\n'));
        a.href = wa ? ('https://wa.me/' + wa + '?text=' + msg) : ('https://wa.me/?text=' + msg);
        actions.appendChild(a);
      });
    }catch(e){}
  }
  try{ addWhatsAppButtonsForListings(); }catch(e){}
  document.addEventListener('swup:contentReplaced', function(){ try{ addWhatsAppButtonsForListings(); }catch(e){} });

})();
