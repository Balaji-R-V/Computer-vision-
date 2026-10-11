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

    const alertsLink = addLink('/alerts', '🚨 ALERTS');
    addLink('/reports', '📈 REPORTS');
    if (me.role === 'admin') {
        addLink('/settings', '⚙ SETTINGS');
        if (me.auth_enabled) addLink('/admin/users', '🔑 USERS');
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

    // Engine Switcher Pill (Dual Architecture: GPU Local vs AWS Rekognition)
    try {
        const engRes = await (await fetch('/api/engine_mode')).json();
        let curEngine = engRes.current_engine || (me.engine_mode || 'gpu_local');
        const holder = document.querySelector('.header-right') || document.querySelector('header');
        
        const engBtn = document.createElement('button');
        engBtn.id = 'headerEngineSwitcher';
        engBtn.style.cssText = "font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;padding:4px 10px;border-radius:6px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;margin-right:12px;transition:all .2s;border:1px solid rgba(255,255,255,0.15);background:#050810;";
        
        function updateEngBtn(mode) {
            curEngine = mode;
            if (mode === 'aws_rekognition') {
                engBtn.style.borderColor = 'rgba(245,158,11,0.5)';
                engBtn.style.background = 'rgba(245,158,11,0.12)';
                engBtn.style.color = '#fbbf24';
                engBtn.innerHTML = `☁️ AWS REKOGNITION <span style="font-size:9px;opacity:0.75;background:#050810;padding:1px 4px;border-radius:3px;">SWITCH</span>`;
                engBtn.title = "Current Engine: AWS Rekognition Cloud Service. Click to switch to Local GPU Engine.";
            } else {
                engBtn.style.borderColor = 'rgba(34,211,238,0.5)';
                engBtn.style.background = 'rgba(34,211,238,0.12)';
                engBtn.style.color = '#22d3ee';
                engBtn.innerHTML = `⚡ GPU ACCELERATED <span style="font-size:9px;opacity:0.75;background:#050810;padding:1px 4px;border-radius:3px;">SWITCH</span>`;
                engBtn.title = "Current Engine: Local GPU Hardware (YOLO + OpenCV). Click to switch to AWS Rekognition Cloud.";
            }
        }
        updateEngBtn(curEngine);

        engBtn.onclick = async () => {
            const nextMode = (curEngine === 'aws_rekognition') ? 'gpu_local' : 'aws_rekognition';
            engBtn.disabled = true;
            engBtn.style.opacity = '0.6';
            try {
                const sw = await (await fetch('/api/engine_mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: nextMode })
                })).json();
                if (sw.success) {
                    updateEngBtn(nextMode);
                    if (typeof toast === 'function') {
                        toast(nextMode === 'aws_rekognition' ? '☁️ Live Switched to AWS Rekognition Cloud' : '⚡ Live Switched to Local GPU Hardware');
                    }
                    window.dispatchEvent(new CustomEvent('engineChanged', { detail: { mode: nextMode } }));
                } else {
                    if (typeof toast === 'function') toast(sw.error || 'Failed to switch engine', true);
                }
            } catch (err) {
                if (typeof toast === 'function') toast('Engine switch error', true);
            } finally {
                engBtn.disabled = false;
                engBtn.style.opacity = '1';
            }
        };

        if (holder) {
            holder.insertBefore(engBtn, holder.firstChild);
        }
    } catch (e) {}

    if (me.auth_enabled && me.username) {
        const holder = document.querySelector('.header-right') || document.querySelector('header');
        const chip = document.createElement('div');
        chip.style.cssText = "font-family:'JetBrains Mono',monospace;font-size:11px;color:#8494ad;margin-left:14px;white-space:nowrap;";
        chip.innerHTML = `👤 ${me.username} <span style="opacity:.6">(${me.role})</span> · <a href="/logout" style="color:#22d3ee;text-decoration:none;">sign out</a>`;
        holder.appendChild(chip);
    }
    window.AEGIS_ME = me;
})();
