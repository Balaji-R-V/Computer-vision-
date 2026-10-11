// App State
let appState = {
    uploadedFilename: null,
    fileType: null,
    imageWidth: 0,
    imageHeight: 0,
    firstFrameImage: new Image(),
    isImageLoaded: false,
    zones: [
        {
            name: 'Project Alpha Area',
            project_code: 'PRJ-ALPHA',
            color: '#ff8c00',
            points: [[0.05, 0.10], [0.45, 0.10], [0.48, 0.90], [0.05, 0.90]]
        },
        {
            name: 'Project Beta Zone',
            project_code: 'PRJ-BETA',
            color: '#00d2ff',
            points: [[0.52, 0.10], [0.95, 0.10], [0.95, 0.90], [0.52, 0.90]]
        }
    ],
    currentDraftPoints: [],
    draggingPointIndex: -1,
    draggingZoneIndex: -1,
    selectedZoneIndex: -1
};

// DOM Elements
const dropzone = document.getElementById('dropzone');
const mediaInput = document.getElementById('mediaInput');
const fileInfo = document.getElementById('fileInfo');
const yoloConf = document.getElementById('yoloConf');
const yoloConfVal = document.getElementById('yoloConfVal');
const genderConf = document.getElementById('genderConf');
const genderConfVal = document.getElementById('genderConfVal');

const canvas = document.getElementById('partitionCanvas');
const ctx = canvas.getContext('2d');
const canvasPlaceholder = document.getElementById('canvasPlaceholder');

const projNameInput = document.getElementById('projName');
const projCodeInput = document.getElementById('projCode');
const projColorInput = document.getElementById('projColor');
const saveShapeBtn = document.getElementById('saveShapeBtn');
const clearShapesBtn = document.getElementById('clearShapesBtn');
const runProcessBtn = document.getElementById('runProcessBtn');
const shapesListContainer = document.getElementById('shapesListContainer');
const shapeCountSpan = document.getElementById('shapeCount');


const loadingOverlay = document.getElementById('loadingOverlay');
const resultsSection = document.getElementById('resultsSection');
const mediaOutputContainer = document.getElementById('mediaOutputContainer');
const downloadContainer = document.getElementById('downloadContainer');
const downloadBtn = document.getElementById('downloadBtn');
const analyticsTableBody = document.getElementById('analyticsTableBody');

// Metrics elements
const metricMale = document.getElementById('metricMale');
const metricFemale = document.getElementById('metricFemale');
const metricSitting = document.getElementById('metricSitting');
const metricStanding = document.getElementById('metricStanding');
const metricTotal = document.getElementById('metricTotal');
const metricObjects = document.getElementById('metricObjects');
const metricFps = document.getElementById('metricFps');

const objConf = document.getElementById('objConf');
const objConfVal = document.getElementById('objConfVal');

// Initialize Sliders & Event Listeners
if (yoloConf && yoloConfVal) yoloConf.addEventListener('input', (e) => yoloConfVal.textContent = parseFloat(e.target.value).toFixed(2));
if (objConf && objConfVal) {
    objConf.addEventListener('input', (e) => {
        objConfVal.textContent = parseFloat(e.target.value).toFixed(2);
        updateActiveStreamSettings();
    });
}
if (genderConf && genderConfVal) genderConf.addEventListener('input', (e) => genderConfVal.textContent = parseFloat(e.target.value).toFixed(2));
if (yoloConf) yoloConf.addEventListener('change', updateActiveStreamSettings);

dropzone.addEventListener('click', () => mediaInput.click());

dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = '#00d2ff';
});

dropzone.addEventListener('dragleave', () => {
    dropzone.style.borderColor = '#475569';
});

dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = '#475569';
    if (e.dataTransfer.files.length > 0) {
        handleFileUpload(e.dataTransfer.files[0]);
    }
});

mediaInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileUpload(e.target.files[0]);
    }
});

clearShapesBtn.addEventListener('click', () => {
    appState.zones = [];
    appState.currentDraftPoints = [];
    updateShapesList();
    redrawCanvas();
});

saveShapeBtn.addEventListener('click', () => {
    if (appState.currentDraftPoints.length === 4) {
        const name = projNameInput.value.trim() || `Project ${String.fromCharCode(65 + appState.zones.length)}`;
        const code = projCodeInput.value.trim() || `PRJ-${String.fromCharCode(65 + appState.zones.length)}`;
        const color = projColorInput.value || '#ff8c00';

        appState.zones.push({
            name: name,
            project_code: code,
            color: color,
            points: [...appState.currentDraftPoints]
        });

        appState.currentDraftPoints = [];
        updateShapesList();
        redrawCanvas();
    } else {
        alert("Please click 4 corner dots on the image canvas first to define your custom shape!");
    }
});

// File Upload Handler
async function handleFileUpload(file) {
    const formData = new FormData();
    formData.append('file', file);

    fileInfo.classList.remove('hidden');
    fileInfo.innerHTML = `Uploading and extracting frame metadata for <strong>${file.name}</strong>...`;

    try {
        const resp = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        const data = await resp.json();

        if (data.success) {
            appState.uploadedFilename = data.filename;
            appState.fileType = data.file_type;
            appState.imageWidth = data.width;
            appState.imageHeight = data.height;

            fileInfo.innerHTML = `<strong>${file.name}</strong> loaded (${data.width}x${data.height} ${data.file_type === 'video' ? `@ ${data.fps} FPS` : ''})`;

            // Load first frame into Image object
            appState.firstFrameImage.onload = () => {
                appState.isImageLoaded = true;
                canvasPlaceholder.classList.add('hidden');
                canvas.width = data.width;
                canvas.height = data.height;
                runProcessBtn.disabled = false;
                updateShapesList();
                redrawCanvas();
            };
            appState.firstFrameImage.src = data.first_frame;
        } else {
            fileInfo.innerHTML = `Error: ${data.error}`;
        }
    } catch (err) {
        fileInfo.innerHTML = `Server connection failed: ${err.message}`;
    }
}

// Canvas Mouse Interactions
canvas.addEventListener('mousedown', (e) => {
    if (!appState.isImageLoaded) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const clickX = (e.clientX - rect.left) * scaleX;
    const clickY = (e.clientY - rect.top) * scaleY;

    const normX = clickX / canvas.width;
    const normY = clickY / canvas.height;

    // Check if clicking near an existing zone handle point to drag
    let foundHandle = false;
    const handleRadiusPx = 15;

    for (let zIdx = 0; zIdx < appState.zones.length; zIdx++) {
        const pts = appState.zones[zIdx].points;
        for (let pIdx = 0; pIdx < pts.length; pIdx++) {
            const px = pts[pIdx][0] * canvas.width;
            const py = pts[pIdx][1] * canvas.height;
            const dist = Math.hypot(clickX - px, clickY - py);
            if (dist <= handleRadiusPx) {
                appState.draggingZoneIndex = zIdx;
                appState.draggingPointIndex = pIdx;
                foundHandle = true;
                break;
            }
        }
        if (foundHandle) break;
    }

    if (!foundHandle) {
        // Add new dot to current draft points (up to 4)
        if (appState.currentDraftPoints.length < 4) {
            appState.currentDraftPoints.push([normX, normY]);
            redrawCanvas();
        }
    }
});

canvas.addEventListener('mousemove', (e) => {
    if (!appState.isImageLoaded) return;

    if (appState.draggingZoneIndex >= 0 && appState.draggingPointIndex >= 0) {
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;

        const normX = Math.max(0, Math.min(1, ((e.clientX - rect.left) * scaleX) / canvas.width));
        const normY = Math.max(0, Math.min(1, ((e.clientY - rect.top) * scaleY) / canvas.height));

        appState.zones[appState.draggingZoneIndex].points[appState.draggingPointIndex] = [normX, normY];
        redrawCanvas();
    }
});

canvas.addEventListener('mouseup', () => {
    appState.draggingZoneIndex = -1;
    appState.draggingPointIndex = -1;
});

// Canvas Renderer
function redrawCanvas() {
    if (!appState.isImageLoaded) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(appState.firstFrameImage, 0, 0, canvas.width, canvas.height);

    // 1. Draw saved project shapes
    appState.zones.forEach((zone, zIdx) => {
        drawPolygon(zone.points, zone.color, zone.name, zone.project_code, true);
    });

    // 2. Draw active draft points being clicked
    if (appState.currentDraftPoints.length > 0) {
        const draftColor = projColorInput.value || '#ff8c00';
        drawPolygon(appState.currentDraftPoints, draftColor, projNameInput.value || 'New Draft Shape', '', false);
    }
}

function drawPolygon(points, color, name, code, isClosed) {
    if (points.length === 0) return;

    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;

    // Fill polygon if closed
    if (isClosed && points.length >= 3) {
        ctx.beginPath();
        ctx.moveTo(points[0][0] * canvas.width, points[0][1] * canvas.height);
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(points[i][0] * canvas.width, points[i][1] * canvas.height);
        }
        ctx.closePath();
        ctx.fillStyle = hexToRgba(color, 0.22);
        ctx.fill();
        ctx.stroke();
    } else {
        ctx.beginPath();
        ctx.moveTo(points[0][0] * canvas.width, points[0][1] * canvas.height);
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(points[i][0] * canvas.width, points[i][1] * canvas.height);
        }
        if (isClosed) ctx.closePath();
        ctx.stroke();
    }

    // Draw Dot Handles with labels 1, 2, 3, 4
    const dotLabels = ["1", "2", "3", "4"];
    points.forEach((pt, pIdx) => {
        const px = pt[0] * canvas.width;
        const py = pt[1] * canvas.height;

        ctx.beginPath();
        ctx.arc(px, py, 10, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = "#ffffff";
        ctx.stroke();

        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 11px Inter, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(dotLabels[pIdx] || `${pIdx + 1}`, px, py);
    });

    // Draw Title Banner at Point 1
    if (points.length > 0 && name) {
        const p1x = points[0][0] * canvas.width;
        const p1y = points[0][1] * canvas.height;
        const titleText = `${name}` + (code ? ` (${code})` : '');

        ctx.font = "bold 14px Inter, sans-serif";
        const textMetrics = ctx.measureText(titleText);
        const tw = textMetrics.width;

        const bannerY = Math.max(0, p1y - 28);
        ctx.fillStyle = color;
        ctx.fillRect(p1x, bannerY, tw + 16, 26);

        ctx.fillStyle = "#000000";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(titleText, p1x + 8, bannerY + 13);
    }

    ctx.restore();
}

function hexToRgba(hex, alpha) {
    let c = hex.replace('#', '');
    if (c.length === 3) c = c.split('').map(x => x + x).join('');
    const num = parseInt(c, 16);
    return `rgba(${(num >> 16) & 255}, ${(num >> 8) & 255}, ${num & 255}, ${alpha})`;
}

// Update Active Shapes List UI
function updateShapesList() {
    shapeCountSpan.textContent = appState.zones.length;
    shapesListContainer.innerHTML = '';

    appState.zones.forEach((zone, idx) => {
        const item = document.createElement('div');
        item.className = 'shape-item';
        item.innerHTML = `
            <span><strong style="color:${zone.color};">${zone.name}</strong> (${zone.project_code || 'PRJ'})</span>
            <button class="shape-item-del" data-idx="${idx}" title="Delete boundary" style="background:none;border:none;color:#f87171;font-size:12px;cursor:pointer;font-weight:700;">✕</button>
        `;
        shapesListContainer.appendChild(item);
    });

    document.querySelectorAll('.shape-item-del').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = parseInt(e.target.dataset.idx);
            appState.zones.splice(idx, 1);
            updateShapesList();
            redrawCanvas();
        });
    });
}

// Initial populate of active boundary list
updateShapesList();

let liveStatsInterval = null;

// Toggle Studio Mapping Panel Collapse/Expand
const toggleStudioBtn = document.getElementById('toggleStudioBtn');
const studioSection = document.getElementById('studioSection');
if (toggleStudioBtn && studioSection) {
    toggleStudioBtn.addEventListener('click', () => {
        studioSection.classList.toggle('collapsed');
        const isCollapsed = studioSection.classList.contains('collapsed');
        toggleStudioBtn.textContent = isCollapsed ? 'EXPAND MAPPING STUDIO' : 'COLLAPSE MAPPING STUDIO';
    });
}

// Process Media API Call (Live Stream Mode for Videos like Streamlit)
runProcessBtn.addEventListener('click', async () => {
    if (!appState.uploadedFilename) return;

    // Auto-collapse mapping studio panel to prioritize live AI stream viewport (~90% page prominence)
    if (studioSection) {
        studioSection.classList.add('collapsed');
        if (toggleStudioBtn) toggleStudioBtn.textContent = 'EXPAND MAPPING STUDIO';
    }

    resultsSection.classList.remove('hidden');
    resultsSection.scrollIntoView({ behavior: 'smooth' });
    
    if (liveStatsInterval) clearInterval(liveStatsInterval);

    if (appState.fileType === 'video') {
        const payload = {
            filename: appState.uploadedFilename,
            zones: appState.zones,
            yolo_conf: parseFloat(yoloConf.value),
            gender_conf: parseFloat(genderConf.value),
            draw_heads: document.getElementById('drawHeads').checked,
            draw_objects: document.getElementById('drawObjects').checked,
            draw_trails: document.getElementById('drawTrails').checked,
            draw_zones: document.getElementById('drawZones') ? document.getElementById('drawZones').checked : false,
            target_person_id: targetPersonSelect ? targetPersonSelect.value : 'All'
        };

        try {
            const initResp = await fetch('/api/init_stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const initData = await initResp.json();

            if (initData.success) {
                // Set MJPEG video stream img source
                mediaOutputContainer.innerHTML = `<img src="${initData.stream_url}" alt="Live AI Detection Stream" style="width:100%; border-radius:12px; border:2px solid var(--accent-cyan); display:block;">`;
                downloadContainer.classList.add('hidden');

                // Poll live stats every 400ms — crops are now embedded in stats.current_person_crops
                liveStatsInterval = setInterval(async () => {
                    try {
                        const sResp = await fetch(`/api/live_stats/${encodeURIComponent(appState.uploadedFilename)}`);
                        const sData = await sResp.json();
                        if (sData.success && sData.stats) {
                            renderStatsInUI(sData.stats);
                        }
                    } catch (e) {}
                }, 400);

            } else {
                alert(`Stream Init Error: ${initData.error}`);
            }
        } catch (err) {
            alert(`Stream Connection Error: ${err.message}`);
        }

    } else if (appState.fileType === 'rtsp') {
        // Live RTSP Stream Mode with Defined Boundary Zones
        const payload = {
            zones: appState.zones,
            yolo_conf: parseFloat(yoloConf.value),
            gender_conf: parseFloat(genderConf.value),
            draw_heads: document.getElementById('drawHeads').checked,
            draw_objects: document.getElementById('drawObjects').checked,
            draw_trails: document.getElementById('drawTrails').checked,
            draw_zones: document.getElementById('drawZones') ? document.getElementById('drawZones').checked : false,
            obj_conf: objConf ? parseFloat(objConf.value) : 0.10,
            target_person_id: targetPersonSelect ? targetPersonSelect.value : 'All'
        };

        try {
            await fetch(`/api/update_rtsp_zones/${encodeURIComponent(appState.uploadedFilename)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            startRtspViewer(appState.uploadedFilename);

        } catch (err) {
            alert(`RTSP Stream Error: ${err.message}`);
        }

    } else {
        // Single Image Mode
        loadingOverlay.classList.remove('hidden');
        try {
            const resp = await fetch('/api/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filename: appState.uploadedFilename,
                    zones: appState.zones,
                    yolo_conf: parseFloat(yoloConf.value),
                    gender_conf: parseFloat(genderConf.value),
                    draw_heads: document.getElementById('drawHeads').checked,
                    draw_objects: document.getElementById('drawObjects').checked
                })
            });
            const data = await resp.json();
            loadingOverlay.classList.add('hidden');
            if (data.success) {
                renderAnalytics(data);
            } else {
                alert(`Detection Error: ${data.error}`);
            }
        } catch (err) {
            loadingOverlay.classList.add('hidden');
            alert(`Server Error: ${err.message}`);
        }
    }
});

// Render Analytics Results
function renderAnalytics(data) {
    if (data.file_type === 'image') {
        mediaOutputContainer.innerHTML = `<img src="${data.output_image}" style="width:100%; border-radius:12px; border:1px solid var(--border-color); display:block;">`;
        downloadContainer.classList.add('hidden');
    }
    renderStatsInUI(data.stats || {});
}

const targetPersonSelect = document.getElementById('targetPersonSelect');
const drawTrails = document.getElementById('drawTrails');
const targetLockHudBanner = document.getElementById('targetLockHudBanner');
const targetHudTitle = document.getElementById('targetHudTitle');
const targetHudStatus = document.getElementById('targetHudStatus');
const targetHudZone = document.getElementById('targetHudZone');
const targetHudGender = document.getElementById('targetHudGender');
const targetHudPosture = document.getElementById('targetHudPosture');

// Unified Live Stream Overlay Control Updater
async function updateActiveStreamSettings() {
    if (!appState.uploadedFilename) return;
    const drawObjectsEl = document.getElementById('drawObjects');
    const drawHeadsEl = document.getElementById('drawHeads');
    const drawTrailsEl = document.getElementById('drawTrails');
    const drawZonesEl = document.getElementById('drawZones');
    const targetSelectEl = document.getElementById('targetPersonSelect');
    const objConfEl = document.getElementById('objConf');
    const yoloConfEl = document.getElementById('yoloConf');

    try {
        await fetch(`/api/update_target/${encodeURIComponent(appState.uploadedFilename)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                target_person_id: targetSelectEl ? targetSelectEl.value : 'All',
                draw_trails: drawTrailsEl ? drawTrailsEl.checked : false,
                draw_zones: drawZonesEl ? drawZonesEl.checked : false,
                draw_objects: drawObjectsEl ? drawObjectsEl.checked : true,
                draw_heads: drawHeadsEl ? drawHeadsEl.checked : true,
                obj_conf: objConfEl ? parseFloat(objConfEl.value) : 0.10,
                yolo_conf: yoloConfEl ? parseFloat(yoloConfEl.value) : 0.35
            })
        });
    } catch (err) {
        console.error('Error updating active stream settings:', err);
    }
}

// Bind Change Event Listeners to Sidebar Overlay Toggles
const drawObjects = document.getElementById('drawObjects');
const drawHeads = document.getElementById('drawHeads');
const drawZones = document.getElementById('drawZones');

if (targetPersonSelect) targetPersonSelect.addEventListener('change', updateActiveStreamSettings);
if (drawTrails) drawTrails.addEventListener('change', updateActiveStreamSettings);
if (drawZones) drawZones.addEventListener('change', updateActiveStreamSettings);
if (drawObjects) drawObjects.addEventListener('change', updateActiveStreamSettings);
if (drawHeads) drawHeads.addEventListener('change', updateActiveStreamSettings);

// Render Real-Time Metric Cards, Project Breakdown Table & Live Person Crops
function renderStatsInUI(stats) {
    metricMale.textContent = stats.male_count || 0;
    metricFemale.textContent = stats.female_count || 0;
    metricSitting.textContent = stats.sitting_count || 0;
    metricStanding.textContent = stats.standing_count || 0;
    metricTotal.textContent = stats.person_count || 0;
    if (metricObjects) metricObjects.textContent = stats.total_objects || 0;
    metricFps.textContent = stats.fps || 0.0;

    // Render Non-Person Office Object Breakdown List
    const objectsBreakdownStrip = document.getElementById('objectsBreakdownStrip');
    const objectsBreakdownList = document.getElementById('objectsBreakdownList');
    const objectsEngineTag = document.getElementById('objectsEngineTag');
    if (objectsBreakdownStrip && objectsBreakdownList) {
        const counts = stats.object_counts || {};
        const entries = Object.entries(counts);
        if (entries.length > 0) {
            objectsBreakdownStrip.classList.remove('hidden');
            objectsBreakdownList.innerHTML = entries.map(([objName, count]) => {
                let tagColor = 'rgba(16,185,129,0.18)';
                let borderColor = 'rgba(16,185,129,0.4)';
                let textColor = '#34d399';
                const lower = objName.toLowerCase();
                if (lower.includes('chair') || lower.includes('seat')) {
                    tagColor = 'rgba(16,185,129,0.22)';
                    borderColor = 'rgba(16,185,129,0.6)';
                    textColor = '#34d399';
                } else if (lower.includes('laptop')) {
                    tagColor = 'rgba(245,158,11,0.22)';
                    borderColor = 'rgba(245,158,11,0.6)';
                    textColor = '#fbbf24';
                } else if (lower.includes('desk') || lower.includes('table')) {
                    tagColor = 'rgba(14,165,233,0.22)';
                    borderColor = 'rgba(14,165,233,0.6)';
                    textColor = '#38bdf8';
                } else if (lower.includes('monitor') || lower.includes('screen') || lower.includes('display')) {
                    tagColor = 'rgba(168,85,247,0.22)';
                    borderColor = 'rgba(168,85,247,0.6)';
                    textColor = '#c084fc';
                } else if (lower.includes('phone') || lower.includes('mobile')) {
                    tagColor = 'rgba(236,72,153,0.22)';
                    borderColor = 'rgba(236,72,153,0.6)';
                    textColor = '#f472b6';
                }
                return `
                    <span style="background: ${tagColor}; border: 1px solid ${borderColor}; padding: 3px 8px; border-radius: 5px; color: #ffffff; font-weight: 700; display:inline-flex; align-items:center; gap:5px; font-size:11px;">
                        <span style="width:6px;height:6px;border-radius:50%;background:${textColor};display:inline-block;box-shadow:0 0 4px ${textColor};"></span>
                        <span style="letter-spacing:0.04em;">${objName.toUpperCase()}:</span>
                        <strong style="color:${textColor};">${count}</strong>
                    </span>
                `;
            }).join('');
            if (objectsEngineTag) {
                objectsEngineTag.textContent = 'AWS Rekognition Cloud Vision (Office Object Engine)';
            }
        } else {
            objectsBreakdownStrip.classList.add('hidden');
        }
    }

    // Update Video Scrubber & Playback Controls Deck
    const totalFrames = stats.total_frames || 0;
    const currentFrame = stats.current_frame || 0;
    const videoControlDeck = document.getElementById('videoControlDeck');
    
    if (totalFrames > 0 && videoControlDeck) {
        videoControlDeck.classList.remove('hidden');
        
        const fpsRef = 25.0;
        const curSec = Math.floor(currentFrame / fpsRef);
        const totSec = Math.floor(totalFrames / fpsRef);
        
        const curMinStr = Math.floor(curSec / 60) + ':' + String(curSec % 60).padStart(2, '0');
        const totMinStr = Math.floor(totSec / 60) + ':' + String(totSec % 60).padStart(2, '0');
        
        const elCurTime = document.getElementById('videoCurrentTime');
        const elTotTime = document.getElementById('videoTotalTime');
        const elBar = document.getElementById('videoProgressBar');
        const elBadge = document.getElementById('videoFrameBadge');
        const elPlayBtn = document.getElementById('btnPlayPause');
        
        if (elCurTime) elCurTime.textContent = curMinStr;
        if (elTotTime) elTotTime.textContent = totMinStr;
        if (elBar) elBar.style.width = ((currentFrame / Math.max(totalFrames, 1)) * 100) + '%';
        if (elBadge) elBadge.textContent = `F: ${currentFrame}/${totalFrames}`;
        
        if (elPlayBtn) {
            if (stats.is_paused) {
                elPlayBtn.innerHTML = 'PLAY';
                elPlayBtn.style.background = '#10b981';
                elPlayBtn.style.color = '#000';
            } else {
                elPlayBtn.innerHTML = 'PAUSE';
                elPlayBtn.style.background = '#00d2ff';
                elPlayBtn.style.color = '#050810';
            }
        }
        
        const curSpeed = stats.speed || 1;
        [1, 2, 4].forEach(s => {
            const b = document.getElementById(`speedBtn${s}`);
            if (b) {
                if (s === curSpeed) b.classList.add('active-speed');
                else b.classList.remove('active-speed');
            }
        });
    }

    // Update Target Filter Focus Badge
    const targetFilterIndicator = document.getElementById('targetFilterIndicator');
    const targetFilterText = document.getElementById('targetFilterText');
    const currentTarget = targetPersonSelect ? targetPersonSelect.value : 'All';
    if (targetFilterIndicator && targetFilterText) {
        if (currentTarget && currentTarget !== 'All') {
            targetFilterIndicator.style.display = 'inline-flex';
            targetFilterText.textContent = `FOCUS: PERSON #${currentTarget}`;
        } else {
            targetFilterIndicator.style.display = 'none';
        }
    }

    // Render live person crops from current frame (all ByteTrack IDs)
    if (stats.current_person_crops && stats.current_person_crops.length > 0) {
        renderLivePersonCrops(stats.current_person_crops);
    }

    // Dynamically Populate Target Person Selector Dropdown with Active Person IDs
    if (targetPersonSelect && stats.active_person_ids && Array.isArray(stats.active_person_ids)) {
        const existingValues = Array.from(targetPersonSelect.options).map(o => o.value);
        stats.active_person_ids.forEach(pid => {
            const val = String(pid);
            if (!existingValues.includes(val)) {
                const opt = document.createElement('option');
                opt.value = val;
                opt.textContent = `Lock Person ID #${val}`;
                targetPersonSelect.appendChild(opt);
            }
        });
    }

    // Update Target Lock Telemetry HUD Banner
    if (stats.target_info && targetLockHudBanner) {
        targetLockHudBanner.classList.remove('hidden');
        const ti = stats.target_info;
        if (ti.found) {
            targetHudTitle.textContent = ti.reacquired 
                ? `TARGET RE-ACQUIRED: ID #${ti.track_id}` 
                : `TARGET LOCKED: PERSON ID #${ti.track_id}`;
            targetHudStatus.textContent = ti.status || 'ACTIVE TRACKING';
            targetHudStatus.style.color = '#00ffcc';
        } else {
            targetHudTitle.textContent = `TARGET LOCK: ID #${ti.track_id || ti.target_id}`;
            targetHudStatus.textContent = ti.status || 'SEARCHING / RE-ACQUIRING...';
            targetHudStatus.style.color = '#ffb300';
        }
        targetHudZone.textContent = ti.zone || 'Floating / Unassigned';
        targetHudGender.textContent = ti.gender || 'Unknown';
        targetHudPosture.textContent = ti.posture || 'Unknown';
    } else if (targetLockHudBanner && targetPersonSelect && targetPersonSelect.value === 'All') {
        targetLockHudBanner.classList.add('hidden');
    }

    // Render Table Rows
    analyticsTableBody.innerHTML = '';
    const zoneStats = stats.zone_stats || {};
    const unassignedCnt = stats.unassigned_count || 0;
    let grandTotal = (stats.person_count || 0);

    Object.entries(zoneStats).forEach(([zname, zdata]) => {
        const tot = zdata.total || 0;
        const sharePct = ((tot / Math.max(grandTotal, 1)) * 100).toFixed(1);

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${zname}</strong></td>
            <td><code>${zdata.project_code || 'N/A'}</code></td>
            <td><strong>${tot}</strong></td>
            <td>${sharePct}%</td>
            <td style="color:#00d2ff; font-weight:700;">${zdata.male || 0}</td>
            <td style="color:#ff3cb4; font-weight:700;">${zdata.female || 0}</td>
            <td style="color:#ff8c00; font-weight:700;">${zdata.sitting || 0}</td>
            <td style="color:#22c55e; font-weight:700;">${zdata.standing || 0}</td>
        `;
        analyticsTableBody.appendChild(tr);
    });

    if (unassignedCnt > 0) {
        const unassignedPct = ((unassignedCnt / Math.max(grandTotal, 1)) * 100).toFixed(1);
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong style="color:#f59e0b;">FLOATING / UNASSIGNED</strong></td>
            <td><code>NONE</code></td>
            <td><strong>${unassignedCnt}</strong></td>
            <td>${unassignedPct}%</td>
            <td>-</td>
            <td>-</td>
            <td>-</td>
            <td>-</td>
        `;
        analyticsTableBody.appendChild(tr);
    }
}

// Digital HUD Clock Updater
function updateHudClock() {
    const hudClockEl = document.getElementById('hudClock');
    if (hudClockEl) {
        const now = new Date();
        const hrs = String(now.getHours()).padStart(2, '0');
        const mins = String(now.getMinutes()).padStart(2, '0');
        const secs = String(now.getSeconds()).padStart(2, '0');
        hudClockEl.textContent = `${hrs}:${mins}:${secs}`;
    }
}
setInterval(updateHudClock, 1000);
updateHudClock();

// Aegis OS Mode Toggle Buttons
const modeShowBtn = document.getElementById('modeShowBtn');
const modeNightBtn = document.getElementById('modeNightBtn');
if (modeShowBtn && modeNightBtn) {
    modeShowBtn.addEventListener('click', () => {
        modeShowBtn.classList.add('active');
        modeNightBtn.classList.remove('active');
    });
    modeNightBtn.addEventListener('click', () => {
        modeNightBtn.classList.add('active');
        modeShowBtn.classList.remove('active');
    });
}

// Source Tab Switcher (File Upload vs RTSP Stream)
const sourceFileTab = document.getElementById('sourceFileTab');
const sourceRtspTab = document.getElementById('sourceRtspTab');
const fileSourceView = document.getElementById('fileSourceView');
const rtspSourceView = document.getElementById('rtspSourceView');
const connectRtspBtn = document.getElementById('connectRtspBtn');

if (sourceFileTab && sourceRtspTab) {
    sourceFileTab.addEventListener('click', () => {
        sourceFileTab.classList.add('active');
        sourceRtspTab.classList.remove('active');
        fileSourceView.classList.remove('hidden');
        rtspSourceView.classList.add('hidden');
    });

    sourceRtspTab.addEventListener('click', () => {
        sourceRtspTab.classList.add('active');
        sourceFileTab.classList.remove('active');
        rtspSourceView.classList.remove('hidden');
        fileSourceView.classList.add('hidden');
    });
}

// Connect to RTSP Stream API Event - Captures first reference frame and loads onto Canvas Studio for zone drawing!
if (connectRtspBtn) {
    connectRtspBtn.addEventListener('click', async () => {
        const rtspUrl = document.getElementById('rtspUrlInput').value.trim();
        const username = document.getElementById('rtspUserInput').value.trim();
        const password = document.getElementById('rtspPassInput').value.trim();

        if (!rtspUrl) {
            alert("Please enter a valid RTSP stream URL.");
            return;
        }

        fileInfo.classList.remove('hidden');
        fileInfo.innerHTML = `Connecting to RTSP stream & capturing reference frame for <strong>${rtspUrl}</strong>...`;

        const payload = {
            rtsp_url: rtspUrl,
            username: username,
            password: password,
            zones: appState.zones,
            yolo_conf: parseFloat(yoloConf.value),
            gender_conf: parseFloat(genderConf.value),
            draw_heads: document.getElementById('drawHeads').checked,
            draw_objects: document.getElementById('drawObjects').checked,
            draw_trails: document.getElementById('drawTrails').checked,
            obj_conf: objConf ? parseFloat(objConf.value) : 0.10,
            target_person_id: targetPersonSelect ? targetPersonSelect.value : 'All'
        };

        try {
            const resp = await fetch('/api/connect_rtsp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await resp.json();

            if (data.success) {
                appState.uploadedFilename = data.stream_id;
                appState.fileType = 'rtsp';
                appState.imageWidth = data.width;
                appState.imageHeight = data.height;

                if (liveStatsInterval) clearInterval(liveStatsInterval);
                mediaOutputContainer.innerHTML = '';
                clearLivePersonCrops();

                fileInfo.innerHTML = data.camera_online
                    ? `<strong>RTSP Stream Connected:</strong> Reference frame captured (${data.width}x${data.height}). Mark your project boundary zones on the canvas below, then click <strong>START AI DETECTION & SEGREGATION</strong>.`
                    : `<strong>Camera not reachable right now.</strong> You can still draw zones; detection starts automatically once the camera responds (it keeps retrying).`;

                // Load first snapshot frame onto Canvas Studio for zone drawing
                appState.firstFrameImage.onload = () => {
                    appState.isImageLoaded = true;
                    canvasPlaceholder.classList.add('hidden');
                    canvas.width = data.width;
                    canvas.height = data.height;
                    runProcessBtn.disabled = false;
                    updateShapesList();
                    redrawCanvas();

                    // Smoothly scroll down to Interactive 4-Point Canvas Studio so user can mark boundaries!
                    const studioSec = document.getElementById('studioSection');
                    if (studioSec) studioSec.scrollIntoView({ behavior: 'smooth' });
                };
                appState.firstFrameImage.src = data.first_frame;
            } else {
                fileInfo.innerHTML = `RTSP Connection Error: ${data.error}`;
            }
        } catch (err) {
            fileInfo.innerHTML = `RTSP Server Connection Failed: ${err.message}`;
        }
    });
}

// Populate target person lock dropdown with DB registered people
async function populateDbPeoplesDropdown() {
    try {
        const res = await fetch('/api/peoples');
        const data = await res.json();
        if (data.success && data.peoples && targetPersonSelect) {
            data.peoples.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.person_code;
                opt.textContent = `${p.person_code} | ${p.name} (${p.department || 'Staff'})`;
                targetPersonSelect.appendChild(opt);
            });
        }
    } catch (err) {}
}
populateDbPeoplesDropdown();


// ─────────────────────────────────────────────────────────────────────────────
// LIVE PERSON CROP GALLERY — Renders directly from stats.current_person_crops
// Updated every 400ms alongside live_stats (no separate endpoint needed)
// ─────────────────────────────────────────────────────────────────────────────

const livePersonCropsSection = document.getElementById('livePersonCropsSection');
const livePersonCropsGrid    = document.getElementById('livePersonCropsGrid');
const livePersonCropCount    = document.getElementById('livePersonCropCount');

/**
 * Build HTML for a single person crop card.
 * Uses ByteTrack ID (track_id) so ALL people in frame appear.
 * Click to Lock & Track person directly!
 */
function buildCropCardHTML(p) {
    const tid      = p.track_id;
    const gender   = p.gender  || 'Unknown';
    const posture  = p.posture || '-';
    const zone     = p.zone    || 'Unassigned';
    const face_b64 = p.face_b64 || '';
    const isTarget = !!p.is_target;
    const isMale   = gender === 'Male';
    const accColor = isTarget ? '#00d2ff' : (isMale ? '#00d2ff' : '#ff3cb4');
    const zShort   = zone.length > 16 ? zone.slice(0, 14) + '…' : zone;

    const targetBadge = isTarget 
        ? `<div style="position:absolute;top:4px;right:4px;background:#00d2ff;color:#050810;font-size:8px;font-weight:900;padding:1px 5px;border-radius:3px;box-shadow:0 0 10px #00d2ff;z-index:2;letter-spacing:0.06em;">LOCKED</div>`
        : '';

    const borderStyle = isTarget 
        ? `border:2px solid #00d2ff; box-shadow:0 0 20px rgba(0,210,255,0.7);`
        : `border:1px solid ${accColor}44; border-top:3px solid ${accColor}; box-shadow:0 4px 16px rgba(0,0,0,0.5);`;

    return `<div id="crop_card_${tid}" onclick="lockPersonTarget('${tid}')" class="crop-card" style="
            width:115px; flex-shrink:0; cursor:pointer;
            background:rgba(15,20,35,0.95);
            ${borderStyle}
            border-radius:8px; overflow:hidden;
            animation:cropCardIn 0.3s ease;
            transition:transform 0.15s,box-shadow 0.15s;"
        onmouseover="this.style.transform='scale(1.06)';"
        onmouseout="this.style.transform='scale(1)';"
        title="Click to Lock & Track Person #${tid} | ${gender} | ${posture} | ${zone}">
        <div class="crop-img-wrap" style="width:100%;height:100px;overflow:hidden;background:#050812;position:relative;">
            ${face_b64
                ? `<img src="${face_b64}" style="width:100%;height:100%;object-fit:cover;display:block;" alt="#${tid}">`
                : `<div class="crop-fallback" style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:#050812;">
                    <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="${accColor}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity:0.4;">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                        <circle cx="12" cy="7" r="4"></circle>
                    </svg>
                   </div>`}
            <div style="position:absolute;top:4px;left:4px;background:rgba(0,0,0,0.85);border:1px solid ${accColor};
                        border-radius:3px;padding:1px 5px;font-family:'JetBrains Mono';font-size:9px;color:${accColor};font-weight:700;">
                #${tid}
            </div>
            ${targetBadge}
        </div>
        <div class="cc-info" style="padding:6px 7px;font-family:'JetBrains Mono';font-size:9px;line-height:1.55;">
            <div style="color:${accColor};font-weight:700;display:flex;align-items:center;gap:4px;"><span style="width:5px;height:5px;border-radius:50%;background:${accColor};display:inline-block;"></span>${gender.toUpperCase()}</div>
            <div style="color:#94a3b8;font-size:8.5px;letter-spacing:0.04em;">${posture.toUpperCase()}</div>
            <div style="color:#64748b;font-size:8px;letter-spacing:0.04em;" title="${zone}">${zShort.toUpperCase()}</div>
        </div>
    </div>`;
}

// Global 1-Click Target Lock function on any crop card
window.lockPersonTarget = async function(tid) {
    const val = String(tid);
    const targetFilterIndicator = document.getElementById('targetFilterIndicator');
    const targetFilterText = document.getElementById('targetFilterText');

    if (val === 'All' || val === 'None') {
        if (targetPersonSelect) targetPersonSelect.value = 'All';
        // Reset all card highlights & restore opacity for all cards
        document.querySelectorAll('[id^="crop_card_"]').forEach(el => {
            el.style.border = '1px solid rgba(255,255,255,0.1)';
            el.style.boxShadow = '0 4px 16px rgba(0,0,0,0.5)';
            el.style.opacity = '1';
            const b = el.querySelector('[style*="z-index:2"]');
            if (b) b.remove();
        });
        if (targetFilterIndicator) targetFilterIndicator.style.display = 'none';
        if (targetLockHudBanner) targetLockHudBanner.classList.add('hidden');
    } else {
        if (targetPersonSelect) {
            let found = false;
            for (let opt of targetPersonSelect.options) {
                if (opt.value === val) {
                    targetPersonSelect.value = val;
                    found = true;
                    break;
                }
            }
            if (!found) {
                const opt = document.createElement('option');
                opt.value = val;
                opt.textContent = `Lock Person ID #${val}`;
                targetPersonSelect.appendChild(opt);
                targetPersonSelect.value = val;
            }
        }
        
        // Highlight clicked card and dim other cards
        document.querySelectorAll('[id^="crop_card_"]').forEach(el => {
            el.style.border = '1px solid rgba(255,255,255,0.06)';
            el.style.boxShadow = 'none';
            el.style.opacity = '0.35';
            const b = el.querySelector('[style*="z-index:2"]');
            if (b) b.remove();
        });
        const c = document.getElementById(`crop_card_${val}`);
        if (c) {
            c.style.border = '2px solid #00d2ff';
            c.style.boxShadow = '0 0 24px rgba(0,210,255,0.9)';
            c.style.opacity = '1';
        }

        if (targetFilterIndicator && targetFilterText) {
            targetFilterIndicator.style.display = 'inline-flex';
            targetFilterText.textContent = `FOCUS: PERSON #${val}`;
        }
    }

    if (appState.uploadedFilename) {
        try {
            await fetch(`/api/update_target/${encodeURIComponent(appState.uploadedFilename)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    target_person_id: val,
                    draw_trails: document.getElementById('drawTrails') ? document.getElementById('drawTrails').checked : false,
                    draw_zones: document.getElementById('drawZones') ? document.getElementById('drawZones').checked : false
                })
            });
        } catch (e) {}
    }
};

/**
 * Called every 400ms from renderStatsInUI with stats.current_person_crops.
 * Shows ALL ByteTrack-detected persons in the current frame.
 */
function renderLivePersonCrops(crops) {
    if (!livePersonCropsSection || !livePersonCropsGrid) return;

    // Show the section
    livePersonCropsSection.classList.remove('hidden');
    if (livePersonCropCount) {
        livePersonCropCount.textContent = `${crops.length} person${crops.length !== 1 ? 's' : ''} in frame`;
    }

    const currentIds = new Set(crops.map(p => String(p.track_id)));

    // 1. Remove cards that are no longer in the current frame (show ONLY current frame faces)
    livePersonCropsGrid.querySelectorAll('[id^="crop_card_"]').forEach(el => {
        const tid = el.id.replace('crop_card_', '');
        if (!currentIds.has(tid)) {
            el.remove();
        }
    });

    // 2. Add new cards / update existing ones
    crops.forEach(p => {
        const tid = String(p.track_id);
        const existing = document.getElementById(`crop_card_${tid}`);

        if (existing) {
            // Update crop image if changed
            const imgWrap = existing.querySelector('.crop-img-wrap') || existing.querySelector('div[style*="height:90px"]') || existing.querySelector('div[style*="height:100px"]');
            if (imgWrap && p.face_b64) {
                let img = imgWrap.querySelector('img');
                if (img) {
                    if (img.src !== p.face_b64) img.src = p.face_b64;
                    img.style.display = 'block';
                } else {
                    const fallback = imgWrap.querySelector('.crop-fallback') || imgWrap.querySelector('div:not([style*="position:absolute"])');
                    if (fallback) fallback.remove();
                    imgWrap.insertAdjacentHTML(
                        'afterbegin',
                        `<img src="${p.face_b64}" style="width:100%;height:100%;object-fit:cover;display:block;" alt="#${tid}">`
                    );
                }
            }
            
            // Highlight target card
            if (p.is_target) {
                existing.style.border = '2px solid #00d2ff';
                existing.style.boxShadow = '0 0 20px rgba(0,210,255,0.7)';
                if (imgWrap && !imgWrap.querySelector('[style*="z-index:2"]')) {
                    imgWrap.insertAdjacentHTML('beforeend', `<div style="position:absolute;top:4px;right:4px;background:#00d2ff;color:#050810;font-size:8px;font-weight:900;padding:1px 5px;border-radius:3px;box-shadow:0 0 10px #00d2ff;z-index:2;letter-spacing:0.06em;">LOCKED</div>`);
                }
            }

            // Update gender/posture/zone labels
            const infoDiv = existing.querySelector('.cc-info');
            if (infoDiv) {
                const isMale   = (p.gender || '') === 'Male';
                const accColor = p.is_target ? '#00d2ff' : (isMale ? '#00d2ff' : '#ff3cb4');
                const zone     = p.zone || 'Unassigned';
                const zShort   = zone.length > 16 ? zone.slice(0, 14) + '…' : zone;
                infoDiv.innerHTML = `
                    <div style="color:${accColor};font-weight:700;display:flex;align-items:center;gap:4px;"><span style="width:5px;height:5px;border-radius:50%;background:${accColor};display:inline-block;"></span>${(p.gender || 'Unknown').toUpperCase()}</div>
                    <div style="color:#94a3b8;font-size:8.5px;letter-spacing:0.04em;">${(p.posture || '-').toUpperCase()}</div>
                    <div style="color:#64748b;font-size:8px;letter-spacing:0.04em;" title="${zone}">${zShort.toUpperCase()}</div>`;
            }
            existing.style.opacity = '1';
        } else {
            // New person detected — append card
            livePersonCropsGrid.insertAdjacentHTML('beforeend', buildCropCardHTML(p));
        }
    });
}

/** Clear and hide the crops section (e.g. on new video upload) */
function clearLivePersonCrops() {
    if (livePersonCropsGrid)    livePersonCropsGrid.innerHTML = '';
    if (livePersonCropsSection) livePersonCropsSection.classList.add('hidden');
    if (livePersonCropCount)    livePersonCropCount.textContent = '0 persons';
}



// ─────────────────────────────────────────────────────────────────────────────
// LIVE SESSION VIEWERS & RESTORE
// Detection runs in a server-side worker, so leaving this page never stops it.
// On load we ask the server for the running session and re-attach to it.
// ─────────────────────────────────────────────────────────────────────────────

const disconnectRtspBtn = document.getElementById('disconnectRtspBtn');

function startLiveStatsPolling(streamKey) {
    if (liveStatsInterval) clearInterval(liveStatsInterval);
    liveStatsInterval = setInterval(async () => {
        try {
            const sResp = await fetch(`/api/live_stats/${encodeURIComponent(streamKey)}`);
            const sData = await sResp.json();
            if (sData.success && sData.stats) {
                renderStatsInUI(sData.stats);
                updateCameraStatusBadge(sData.stats.camera_status, sData.stats.status_message);
            }
        } catch (e) {}
    }, 400);
}

function updateCameraStatusBadge(status, message) {
    const badge = document.getElementById('rtspLiveBadge');
    if (!badge || !status) return;
    const map = {
        live:       { text: 'ONLINE (LIVE)', color: 'var(--cyan)' },
        connecting: { text: 'CONNECTING…', color: '#facc15' },
        offline:    { text: `OFFLINE${message ? ' — ' + message : ''}`, color: '#fb7185' },
        stopped:    { text: 'STANDBY', color: '#94a3b8' }
    };
    const s = map[status] || map.connecting;
    badge.textContent = `RTSP: ${s.text}`;
    badge.style.color = s.color;
    badge.style.borderColor = s.color;
}

function startRtspViewer(streamId) {
    resultsSection.classList.remove('hidden');
    mediaOutputContainer.innerHTML = `
        <div style="position:relative;">
            <div id="rtspLiveBadge" style="position:absolute; top:12px; left:12px; z-index:10; background:rgba(0,0,0,0.85); border:1px solid var(--cyan); padding:4px 10px; border-radius:4px; font-family:'JetBrains Mono'; font-size:11px; color:var(--cyan);">
                RTSP CONNECTING…
            </div>
            <img src="/api/rtsp_feed/${encodeURIComponent(streamId)}" alt="Live RTSP AI Detection Feed" style="width:100%; border-radius:12px; border:2px solid var(--cyan); display:block;">
        </div>`;
    downloadContainer.classList.add('hidden');
    startLiveStatsPolling(streamId);
    if (disconnectRtspBtn) disconnectRtspBtn.classList.remove('hidden');
}

function startVideoViewer(filename) {
    resultsSection.classList.remove('hidden');
    mediaOutputContainer.innerHTML = `<img src="/api/video_feed/${encodeURIComponent(filename)}" alt="Live AI Detection Stream" style="width:100%; border-radius:12px; border:2px solid var(--accent-cyan); display:block;">`;
    downloadContainer.classList.add('hidden');
    startLiveStatsPolling(filename);
}

if (disconnectRtspBtn) {
    disconnectRtspBtn.addEventListener('click', async () => {
        if (appState.fileType !== 'rtsp' || !appState.uploadedFilename) return;
        if (!confirm('Disconnect the live feed? Detection stops. Occupant logs recorded so far are kept.')) return;
        try {
            await fetch(`/api/disconnect_rtsp/${encodeURIComponent(appState.uploadedFilename)}`, { method: 'POST' });
        } catch (e) {}
        if (liveStatsInterval) clearInterval(liveStatsInterval);
        mediaOutputContainer.innerHTML = '';
        clearLivePersonCrops();
        disconnectRtspBtn.classList.add('hidden');
        appState.uploadedFilename = null;
        appState.fileType = null;
        runProcessBtn.disabled = true;
        if (fileInfo) {
            fileInfo.classList.remove('hidden');
            fileInfo.innerHTML = 'Camera disconnected. Occupant logs were saved.';
        }
        restoreActiveSession();
    });
}

function setSliderValue(slider, label, value) {
    if (!slider || value === undefined || value === null) return;
    slider.value = value;
    if (label) label.textContent = parseFloat(value).toFixed(2);
}

function setChecked(id, value) {
    const el = document.getElementById(id);
    if (el && typeof value === 'boolean') el.checked = value;
}

async function restoreActiveSession(streamId) {
    let s;
    try {
        const resp = await fetch('/api/active_session' + (streamId ? `?stream_id=${encodeURIComponent(streamId)}` : ''));
        s = await resp.json();
    } catch (e) { return; }
    renderCameraList((s && s.cameras) || [], s && s.stream_id);
    if (!s || !s.success || !s.has_active) return;

    appState.zones = Array.isArray(s.zones) ? s.zones : appState.zones;
    setSliderValue(yoloConf, yoloConfVal, s.yolo_conf);
    setSliderValue(genderConf, genderConfVal, s.gender_conf);
    setSliderValue(objConf, objConfVal, s.obj_conf);
    setChecked('drawHeads', s.draw_heads);
    setChecked('drawObjects', s.draw_objects);
    setChecked('drawTrails', s.draw_trails);
    setChecked('drawZones', s.draw_zones);

    if (targetPersonSelect && s.target_person_id && s.target_person_id !== 'All') {
        const val = String(s.target_person_id);
        if (![...targetPersonSelect.options].some(o => o.value === val)) {
            const opt = document.createElement('option');
            opt.value = val;
            opt.textContent = `Lock Person ID #${val}`;
            targetPersonSelect.appendChild(opt);
        }
        targetPersonSelect.value = val;
    }

    if (s.type === 'rtsp') {
        appState.uploadedFilename = s.stream_id;
        appState.fileType = 'rtsp';
        appState.imageWidth = s.width;
        appState.imageHeight = s.height;

        if (sourceRtspTab) sourceRtspTab.click();
        const urlInput = document.getElementById('rtspUrlInput');
        const userInput = document.getElementById('rtspUserInput');
        const passInput = document.getElementById('rtspPassInput');
        if (urlInput && s.rtsp_url) urlInput.value = s.rtsp_url;
        if (userInput) userInput.value = s.username || '';
        if (passInput) passInput.value = '';   // never sent back to the browser
        if (fileInfo) {
            fileInfo.classList.remove('hidden');
            fileInfo.innerHTML = '<strong>Live session restored</strong> — detection has been running in the background.';
        }

        if (s.first_frame) {
            appState.firstFrameImage.onload = () => {
                appState.isImageLoaded = true;
                canvasPlaceholder.classList.add('hidden');
                canvas.width = s.width;
                canvas.height = s.height;
                runProcessBtn.disabled = false;
                updateShapesList();
                redrawCanvas();
            };
            appState.firstFrameImage.src = s.first_frame;
        }

        if (studioSection) {
            studioSection.classList.add('collapsed');
            if (toggleStudioBtn) toggleStudioBtn.textContent = 'EXPAND MAPPING STUDIO';
        }
        startRtspViewer(s.stream_id);
        updateCameraStatusBadge(s.camera_status);
    } else if (s.type === 'video') {
        appState.uploadedFilename = s.filename;
        appState.fileType = 'video';
        if (studioSection) {
            studioSection.classList.add('collapsed');
            if (toggleStudioBtn) toggleStudioBtn.textContent = 'EXPAND MAPPING STUDIO';
        }
        startVideoViewer(s.filename);
    }
}

restoreActiveSession();


// ─────────────────────────────────────────────────────────────────────────────
// MULTI-CAMERA SWITCHER — every connected camera keeps detecting in the background;
// this just chooses which one the viewer is showing.
// ─────────────────────────────────────────────────────────────────────────────
const cameraListEl = document.getElementById('cameraList');

function renderCameraList(cameras, activeId) {
    if (!cameraListEl) return;
    if (!cameras || cameras.length === 0) { cameraListEl.classList.add('hidden'); cameraListEl.innerHTML = ''; return; }
    const dot = { live: '#34d399', connecting: '#facc15', offline: '#f87171', stopped: '#94a3b8' };
    cameraListEl.classList.remove('hidden');
    cameraListEl.innerHTML = '<div style="font-size:10px;font-family:JetBrains Mono;color:var(--cyan);letter-spacing:.1em;">CONNECTED CAMERAS</div>' +
        cameras.map(c => `<button class="btn btn-secondary" data-cam="${c.stream_id}" style="text-align:left;font-size:11px;${c.stream_id === activeId ? 'border-color:var(--cyan);color:var(--cyan);' : ''}">
            <span style="color:${dot[c.camera_status] || dot.connecting}">●</span> ${c.label} <span style="opacity:.6">(${c.camera_status})</span></button>`).join('');
    cameraListEl.querySelectorAll('[data-cam]').forEach(b => b.onclick = () => restoreActiveSession(b.dataset.cam));
}

setInterval(async () => {
    if (!cameraListEl) return;
    try {
        const r = await (await fetch('/api/cameras')).json();
        if (r.success) renderCameraList(r.cameras.map(c => ({ stream_id: c.stream_id, label: c.label, camera_status: c.status })),
                                        appState.fileType === 'rtsp' ? appState.uploadedFilename : null);
    } catch (e) {}
}, 5000);
