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
    const messages = [
      'Fresh groceries delivered to your doorstep—fast and affordable!',
      'Order today and enjoy same-day delivery across KU, Ruiru & Nairobi!',
      'Get the best prices on fruits, veggies, and household essentials!',
      'ScholaGro—We deliver exactly what you ordered, fresh and clean!',
      'Save more this season with our daily offers and discounts!'
    ];
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
    toastBody.textContent = msg;
    if (toast) toast.show();
  }
  async function addToCart(productId){
    try{
      const res = await fetch('/cart/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: JSON.stringify({ product_id: productId })
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.message || 'Failed');
      const badge = document.getElementById('cart-count-badge');
      if (badge) badge.textContent = data.cart_count;
      showToast(data.message, true);
    }catch(err){
      showToast(err.message || 'Error adding to cart', false);
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
    try{
      const res = await fetch('/wishlist/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId })
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.message || 'Failed');
      if (btn){
        btn.classList.toggle('btn-outline-danger', !data.added);
        btn.classList.toggle('btn-danger', data.added);
        const icon = btn.querySelector('i');
        if (icon){
          icon.classList.toggle('bi-heart', !data.added);
          icon.classList.toggle('bi-heart-fill', data.added);
        }
      }
      showToast(data.added ? 'Added to wishlist' : 'Removed from wishlist', true);
    }catch(err){
      showToast(err.message || 'Error updating wishlist', false);
    }
  }
  document.addEventListener('click', (e)=>{
    const btn = e.target.closest('.btn-add-to-cart');
    if (btn){
      e.preventDefault();
      const pid = btn.getAttribute('data-product-id');
      if (pid) addToCart(pid);
    }
    const wbtn = e.target.closest('.btn-wishlist');
    if (wbtn){
      e.preventDefault();
      const pid = wbtn.getAttribute('data-product-id');
      if (pid) toggleWishlist(pid, wbtn);
    }
  });

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
    const bsToast = new bootstrap.Toast(toastElFlash, {delay: 2500});
    const queue = Array.from(FL);
    const flashContainer = document.getElementById('flash-container');
    if (flashContainer){
      // hide inline alerts when JS toasts are active
      flashContainer.style.display = 'none';
    }
    const step = ()=>{
      if (!queue.length) return;
      const item = queue.shift();
      toastBodyFlash.textContent = item.message;
      toastElFlash.className = `toast align-items-center ${variant(item.category)} border-0`;
      bsToast.show();
      setTimeout(step, 2700);
    };
    step();
  }

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

})();
