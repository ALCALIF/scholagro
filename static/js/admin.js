(function(){
  const doc = document.documentElement;
  const qs = (s)=>document.querySelector(s);
  const sidebar = qs('#sidebar');
  const burger = qs('#burger');
  const themeBtn = qs('#themeToggle');
  const themeIcon = qs('#themeIcon');
  const userBtn = qs('#userMenuBtn');
  const userMenu = qs('#userMenu');
  const collapseToggle = qs('#collapseToggle');
  const topbarForm = (function(){
    // topbar search form lives inside admin/base.html header
    const forms = document.querySelectorAll('header form[action="/admin/"]');
    return forms && forms[0];
  })();

  function setTheme(mode){
    const isDark = mode === 'dark';
    doc.classList.toggle('dark', isDark);
    doc.setAttribute('data-theme', isDark ? 'dark' : 'light');
    try { localStorage.setItem('admin-theme', isDark ? 'dark' : 'light'); } catch(e){}
    if (themeIcon) themeIcon.textContent = isDark ? '☀️' : '🌙';
  }
  // Init theme
  try {
    const saved = localStorage.getItem('admin-theme');
    if (saved) setTheme(saved); else if (window.matchMedia('(prefers-color-scheme: dark)').matches) setTheme('dark');
  } catch(e){}

  if (burger && sidebar){
    burger.addEventListener('click', function(){
      sidebar.classList.toggle('-translate-x-full');
    });
  }

  if (themeBtn){
    themeBtn.addEventListener('click', function(){
      setTheme(doc.classList.contains('dark') ? 'light' : 'dark');
    });
  }

  if (userBtn && userMenu){
    userBtn.addEventListener('click', function(){
      userMenu.classList.toggle('hidden');
    });
    document.addEventListener('click', function(e){
      if (!userMenu.classList.contains('hidden')){
        if (!userMenu.contains(e.target) && !userBtn.contains(e.target)){
          userMenu.classList.add('hidden');
        }
      }
    });
  }

  // Collapsible grouped nav
  document.querySelectorAll('[data-group-toggle]').forEach(function(btn){
    btn.addEventListener('click', function(){
      const content = btn.parentElement.querySelector('[data-group-content]');
      if (content){ content.classList.toggle('hidden'); }
    });
  });

  // Sidebar collapsed view toggle
  function applySidebarCollapsed(v){
    doc.classList.toggle('sidebar-collapsed', !!v);
  }
  try {
    applySidebarCollapsed(localStorage.getItem('admin-sidebar-collapsed') === '1');
  } catch(e){}
  if (collapseToggle){
    collapseToggle.addEventListener('click', function(){
      const newVal = !doc.classList.contains('sidebar-collapsed');
      applySidebarCollapsed(newVal);
      try { localStorage.setItem('admin-sidebar-collapsed', newVal ? '1' : '0'); } catch(e){}
    });
  }

  // ---- Client-side filtering for products/orders ----
  function filterTable(q){
    const term = (q || '').trim().toLowerCase();
    document.querySelectorAll('table[data-search] tbody tr').forEach(function(tr){
      const txt = tr.textContent.toLowerCase();
      tr.style.display = term && !txt.includes(term) ? 'none' : '';
    });
  }

  function getParam(name){
    try { return new URLSearchParams(location.search).get(name) || ''; } catch(e){ return ''; }
  }

  // Initialize with ?q param if present
  (function initSearch(){
    const qp = getParam('q');
    if (qp){ filterTable(qp); const inp = topbarForm && topbarForm.querySelector('input[name="q"]'); if (inp) inp.value = qp; }
    if (topbarForm){
      topbarForm.addEventListener('submit', function(ev){ ev.preventDefault(); const inp = topbarForm.querySelector('input[name="q"]'); filterTable(inp && inp.value); });
      const inp = topbarForm.querySelector('input[name="q"]');
      if (inp){ inp.addEventListener('input', function(){ filterTable(inp.value); }); }
    }
  })();

  // Open feature modals (Chat, Calendar, Customization)
  document.querySelectorAll('[data-open]')?.forEach(function(el){
    el.addEventListener('click', function(ev){
      ev.preventDefault();
      const t = el.getAttribute('data-open');
      let id = null;
      if (t === 'chat') id = 'chatModal';
      else if (t === 'calendar') id = 'calendarModal';
      else if (t === 'customize') id = 'customizeModal';
      if (id && window.bootstrap){
        const m = new bootstrap.Modal(document.getElementById(id));
        m.show();
      }
    });
  });

  // Auto-dismiss inline flash alerts after 5 seconds (admin)
  (function(){
    const fc = document.getElementById('flash-container');
    if (fc){ setTimeout(()=>{ try{ fc.remove(); }catch{} }, 5000); }
  })();

  // Password reveal + confirm validation (admin)
  document.addEventListener('change', function(e){
    const chk = e.target.closest('.js-show-pass');
    if (!chk) return;
    const form = chk.closest('form');
    if (!form) return;
    form.querySelectorAll('input[type="password"], input.js-pass').forEach(function(inp){
      try{ inp.type = chk.checked ? 'text' : 'password'; }catch{}
    });
  });
  document.addEventListener('submit', function(e){
    const form = e.target.closest('form');
    if (!form) return;
    const p = form.querySelector('input[name="password"]');
    const c = form.querySelector('input[name="confirm_password"]');
    if (p && c && (p.value||'') !== (c.value||'')){
      e.preventDefault();
      alert('Passwords do not match');
      try{ c.focus(); }catch{}
    }
  });
})();
