// Shared across every page: adds the newer navigation links, the unread-alerts badge and the signed-in user chip.
(async function () {
    const nav = document.querySelector('header nav');
    if (!nav) return;

    let me = { role: 'admin', username: null, auth_enabled: false };
    try { me = await (await fetch('/api/me')).json(); } catch (e) {}

    const template = nav.querySelector('a:last-of-type') || nav.querySelector('a');
    function addLink(href, text) {
        if (!template || nav.querySelector(`a[href="${href}"]`)) return nav.querySelector(`a[href="${href}"]`);
        const a = template.cloneNode(true);
        a.removeAttribute('id');
        a.href = href;
        a.textContent = text;
        a.classList.remove('active');
        if (location.pathname === href) a.classList.add('active');
        nav.appendChild(a);
        return a;
    }

    const alertsLink = addLink('/alerts', 'ALERTS');
    addLink('/reports', 'REPORTS');
    if (me.role === 'admin') {
        addLink('/settings', 'SETTINGS');
        if (me.auth_enabled) addLink('/admin/users', 'USERS');
    }

    async function refreshBadge() {
        if (!alertsLink) return;
        try {
            const r = await (await fetch('/api/alerts/count')).json();
            let badge = alertsLink.querySelector('.alert-badge');
            if (!r.open_count) { if (badge) badge.remove(); return; }
            if (!badge) {
                badge = document.createElement('span');
                badge.className = 'alert-badge';
                badge.style.cssText = 'margin-left:6px;background:#ef4444;color:#fff;border-radius:9px;padding:1px 6px;font-size:10px;';
                alertsLink.appendChild(badge);
            }
            badge.textContent = r.open_count;
        } catch (e) {}
    }
    refreshBadge();
    setInterval(refreshBadge, 15000);

    // Engine Status Pill (AWS Rekognition Cloud)
    try {
        const holder = document.querySelector('.header-right') || document.querySelector('header');
        const engBtn = document.createElement('div');
        engBtn.id = 'headerEngineSwitcher';
        engBtn.style.cssText = "font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;padding:4px 10px;border-radius:6px;display:inline-flex;align-items:center;gap:6px;margin-right:12px;border:1px solid rgba(245,158,11,0.5);background:rgba(245,158,11,0.12);color:#fbbf24;cursor:default;";
        engBtn.innerHTML = `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#f59e0b;box-shadow:0 0 6px #f59e0b;"></span> AWS REKOGNITION <span style="font-size:9px;opacity:0.9;background:#050810;padding:1px 5px;border-radius:3px;color:#34d399;">ONLINE</span>`;
        engBtn.title = "Vision Engine: AWS Rekognition Cloud Video Analytics";

        if (holder) {
            holder.insertBefore(engBtn, holder.firstChild);
        }
    } catch (e) {}

    if (me.auth_enabled && me.username) {
        const holder = document.querySelector('.header-right') || document.querySelector('header');
        const chip = document.createElement('div');
        chip.style.cssText = "font-family:'JetBrains Mono',monospace;font-size:11px;color:#8494ad;margin-left:14px;white-space:nowrap;";
        const uEsc = String(me.username).replace(/[&<>"']/g, "");
        const rEsc = String(me.role).replace(/[&<>"']/g, "");
        chip.innerHTML = `<span style="color:#22d3ee;font-weight:700;">USER:</span> ${uEsc} <span style="opacity:.6">(${rEsc})</span> · <a href="/logout" style="color:#22d3ee;text-decoration:none;">SIGN OUT</a>`;
        holder.appendChild(chip);
    }
    window.AEGIS_ME = me;
})();
