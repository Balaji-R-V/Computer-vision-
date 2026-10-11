import streamlit as st
import cv2
import numpy as np
import tempfile
import os
import time
from PIL import Image
from detector import HeadGenderYOLODetector

# ---------------------------------------------------------
# Streamlit Page Config & Custom Styling
# ---------------------------------------------------------
st.set_page_config(
    page_title="Person Sitting/Standing & Zone Boundary Detector",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark glassmorphism aesthetic
st.markdown("""
<style>
    .stApp {
        background-color: #0b0f19;
        color: #f0f2f6;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 24px;
        border-radius: 16px;
        border: 1px solid #334155;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        margin-bottom: 24px;
        text-align: center;
    }
    
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8 0%, #ec4899 50%, #10b981 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 8px;
    }
    
    .subtitle {
        color: #94a3b8;
        font-size: 1.05rem;
    }

    /* Metric Cards */
    .metric-card {
        background: #1e293b;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        border-top: 4px solid #38bdf8;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .metric-card-male { border-top-color: #00d2ff; }
    .metric-card-female { border-top-color: #ff3cb4; }
    .metric-card-sitting { border-top-color: #f97316; }
    .metric-card-standing { border-top-color: #22c55e; }
    .metric-card-head { border-top-color: #a855f7; }
    .metric-card-fps { border-top-color: #f59e0b; }

    .metric-val {
        font-size: 1.8rem;
        font-weight: 700;
        color: #ffffff;
    }
    .metric-lbl {
        font-size: 0.8rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Header Banner
# ---------------------------------------------------------
st.markdown("""
<div class="main-header">
    <div class="main-title">Full Person Sitting/Standing & Virtual Project Boundary Segregation</div>
    <div class="subtitle">Custom Virtual Boundaries • Automated People Segregation by Project • Pose & Gender Analytics</div>
</div>
""", unsafe_allow_html=True)


def load_detector_engine(yolo_conf, gender_conf):
    """Instantiates HeadGenderYOLODetector."""
    return HeadGenderYOLODetector(yolo_model_name='yolov8n.pt', yolo_conf=yolo_conf, gender_conf=gender_conf)


# ---------------------------------------------------------
# Session State for Virtual Project Boundaries
# ---------------------------------------------------------
if 'zones' not in st.session_state:
    st.session_state.zones = [
        {'name': 'Project Alpha Area', 'project_code': 'PRJ-ALPHA', 'points': [[0.05, 0.10], [0.45, 0.10], [0.48, 0.90], [0.05, 0.90]]},
        {'name': 'Project Beta Zone', 'project_code': 'PRJ-BETA', 'points': [[0.52, 0.10], [0.95, 0.10], [0.95, 0.90], [0.52, 0.90]]}
    ]

# ---------------------------------------------------------
# Sidebar Controls
# ---------------------------------------------------------
st.sidebar.header("⚙️ Input & Settings")

input_type = st.sidebar.radio(
    "Select Mode:",
    ["🎥 Upload Video File", "📹 Live Webcam Stream", "📷 Upload Image"],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Detection Thresholds")

yolo_conf = st.sidebar.slider("YOLO Object Confidence", 0.10, 0.90, 0.35, 0.05)
gender_conf = st.sidebar.slider("Gender Classification Threshold", 0.10, 0.90, 0.40, 0.05)

st.sidebar.markdown("---")
st.sidebar.subheader("👁️ Display Overlays")
draw_heads = st.sidebar.checkbox("Show Person Bounding Boxes & Tags", value=True)
draw_objects = st.sidebar.checkbox("Show General Object Bounding Boxes", value=True)

# ---------------------------------------------------------
# Virtual Project Boundaries & Segregation Configurator
# ---------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("📁 Virtual Project Boundaries")

enable_zones = st.sidebar.checkbox("Enable Project Boundary Segregation", value=True)

if enable_zones:
    with st.sidebar.expander("➕ Active 4-Dot Project Zones", expanded=True):
        st.markdown("**⚡ Quick 4-Dot Presets:**")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            if st.button("2-Project Split"):
                st.session_state.zones = [
                    {'name': 'Project Alpha Area', 'project_code': 'PRJ-A', 'points': [[0.05, 0.10], [0.45, 0.10], [0.48, 0.90], [0.05, 0.90]]},
                    {'name': 'Project Beta Zone', 'project_code': 'PRJ-B', 'points': [[0.52, 0.10], [0.95, 0.10], [0.95, 0.90], [0.52, 0.90]]}
                ]
                st.success("Loaded 2-Project Split Presets!")
                st.rerun()
        with col_p2:
            if st.button("3-Team Layout"):
                st.session_state.zones = [
                    {'name': 'Dev Team Zone', 'project_code': 'PRJ-DEV', 'points': [[0.05, 0.10], [0.33, 0.12], [0.35, 0.90], [0.05, 0.90]]},
                    {'name': 'Design Sprint Area', 'project_code': 'PRJ-DSGN', 'points': [[0.38, 0.10], [0.63, 0.10], [0.65, 0.90], [0.38, 0.90]]},
                    {'name': 'AI Research Pod', 'project_code': 'PRJ-AI', 'points': [[0.68, 0.10], [0.95, 0.10], [0.95, 0.90], [0.68, 0.90]]}
                ]
                st.success("Loaded 3-Team Layout Presets!")
                st.rerun()

        if len(st.session_state.zones) > 0:
            st.write("**Active Defined Shapes:**")
            for idx, z in enumerate(st.session_state.zones):
                col_z1, col_z2 = st.columns([4, 1])
                with col_z1:
                    code_str = f" ({z['project_code']})" if z.get('project_code') else ""
                    st.caption(f"📁 **{z['name']}**{code_str} (4-Dot Shape)")
                with col_z2:
                    if st.button("🗑️", key=f"del_z_{idx}"):
                        st.session_state.zones.pop(idx)
                        st.rerun()
            
            if st.button("Clear All Shapes"):
                st.session_state.zones = []
                st.rerun()

# Initialize Detector
try:
    detector = load_detector_engine(yolo_conf, gender_conf)
    detector.yolo_conf = yolo_conf
    detector.gender_conf = gender_conf
except Exception as e:
    st.error(f"Error loading detector models: {e}")
    st.stop()


def display_st_image(placeholder_or_st, img_rgb):
    try:
        placeholder_or_st.image(img_rgb, use_container_width=True)
    except Exception:
        placeholder_or_st.image(img_rgb)


def render_metrics_bar(male=0, female=0, sitting=0, standing=0, person_count=0, objects=0, fps=0.0):
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.markdown(f"""
        <div class="metric-card metric-card-male">
            <div class="metric-val" style="color: #00d2ff;">👦 {male}</div>
            <div class="metric-lbl">Male</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card metric-card-female">
            <div class="metric-val" style="color: #ff3cb4;">👧 {female}</div>
            <div class="metric-lbl">Female</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card metric-card-sitting">
            <div class="metric-val" style="color: #f97316;">🪑 {sitting}</div>
            <div class="metric-lbl">Sitting</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card metric-card-standing">
            <div class="metric-val" style="color: #22c55e;">🧍 {standing}</div>
            <div class="metric-lbl">Standing</div>
        </div>
        """, unsafe_allow_html=True)
    with col5:
        st.markdown(f"""
        <div class="metric-card metric-card-head">
            <div class="metric-val" style="color: #c084fc;">👥 {person_count}</div>
            <div class="metric-lbl">Total People</div>
        </div>
        """, unsafe_allow_html=True)
    with col6:
        st.markdown(f"""
        <div class="metric-card metric-card-fps">
            <div class="metric-val" style="color: #fbbf24;">⚡ {fps}</div>
            <div class="metric-lbl">Inference FPS</div>
        </div>
        """, unsafe_allow_html=True)


def render_zone_analytics_table(zone_stats, unassigned_cnt=0):
    if zone_stats and len(zone_stats) > 0:
        st.markdown("### 📁 Project-wise People Segregation Analytics")
        table_data = []
        total_people_in_zones = sum(zdata.get('total', 0) for zdata in zone_stats.values())
        grand_total = total_people_in_zones + unassigned_cnt
        
        for zname, zdata in zone_stats.items():
            tot = zdata.get('total', 0)
            share_pct = (tot / max(grand_total, 1)) * 100
            table_data.append({
                "Project Zone Name": f"📁 {zname}",
                "Project Code": zdata.get('project_code', 'N/A') or 'N/A',
                "Total Occupants": tot,
                "Workforce Share": f"{share_pct:.1f}%",
                "Male": zdata.get('male', 0),
                "Female": zdata.get('female', 0),
                "Sitting": zdata.get('sitting', 0),
                "Standing": zdata.get('standing', 0),
            })
        
        if unassigned_cnt > 0:
            unassigned_pct = (unassigned_cnt / max(grand_total, 1)) * 100
            table_data.append({
                "Project Zone Name": "⚠️ Floating / Unassigned Area",
                "Project Code": "NONE",
                "Total Occupants": unassigned_cnt,
                "Workforce Share": f"{unassigned_pct:.1f}%",
                "Male": "-",
                "Female": "-",
                "Sitting": "-",
                "Standing": "-",
            })
            
        st.dataframe(table_data, use_container_width=True)


def extract_zone_points(z):
    """Extracts or converts 4 normalized corner points [[x,y],...] from zone object."""
    if 'points' in z and len(z['points']) == 4:
        return z['points']
    elif 'polygon' in z and len(z['polygon']) == 4:
        return z['polygon']
    elif 'box' in z:
        b = z['box']
        return [[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]]
    return [[0.10, 0.10], [0.50, 0.10], [0.50, 0.80], [0.10, 0.80]]


def draw_zones_on_preview(bgr_frame, zones):
    """Draws defined 4-dot custom project shapes onto a copy of the reference frame for visual partition drawing."""
    canvas = bgr_frame.copy()
    img_h, img_w, _ = canvas.shape
    
    colors = [
        (255, 140, 0),   # Orange
        (0, 255, 255),   # Yellow
        (255, 0, 128),   # Magenta
        (128, 255, 0),   # Lime
        (0, 191, 255),   # Sky Blue
        (186, 85, 211)   # Purple
    ]
    
    for idx, z in enumerate(zones):
        zname = z.get('name', f"Project {idx+1}")
        pcode = z.get('project_code', '')
        pts = extract_zone_points(z)
        color = colors[idx % len(colors)]
        
        abs_pts = []
        for pt in pts:
            abs_pts.append([int(pt[0] * img_w), int(pt[1] * img_h)])
        pts_np = np.array(abs_pts, dtype=np.int32)
        
        # Semi-transparent filled 4-point polygon overlay
        overlay = canvas.copy()
        cv2.fillPoly(overlay, [pts_np], color)
        cv2.addWeighted(overlay, 0.22, canvas, 0.78, 0, canvas)
        
        # Draw closed boundary outline
        cv2.polylines(canvas, [pts_np], isClosed=True, color=color, thickness=3)
        
        # Draw 4 Corner Dot Handles with Numbered Labels (1, 2, 3, 4)
        dot_labels = ["1", "2", "3", "4"]
        for p_i, pt in enumerate(abs_pts):
            cv2.circle(canvas, tuple(pt), 11, color, -1)
            cv2.circle(canvas, tuple(pt), 12, (255, 255, 255), 2)
            cv2.putText(canvas, dot_labels[p_i], (pt[0] - 5, pt[1] + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 0, 0), 2)
        
        # Draw Project Banner Header at Corner Dot 1 (P1)
        p1 = abs_pts[0]
        z_label = f"📁 {zname}" + (f" ({pcode})" if pcode else "")
        (tw, th), _ = cv2.getTextSize(z_label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        banner_top = max(0, p1[1] - 28)
        cv2.rectangle(canvas, (p1[0], banner_top), (p1[0] + tw + 14, p1[1]), color, -1)
        cv2.putText(canvas, z_label, (p1[0] + 6, max(18, p1[1] - 7)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
                    
    return canvas


def render_first_frame_partition_studio(bgr_first_frame):
    """Interactive visual drawer for 4-dot custom shapes overlaying project boundaries on top of the first frame."""
    st.markdown("### 🎨 Interactive 4-Point Custom Shape Partition Studio")
    st.caption("Visually place 4 corner dots (P1, P2, P3, P4) to create custom-shaped, angled, or rotated project team zones directly on your video/image.")
    
    col_canvas, col_controls = st.columns([7, 5])
    
    with col_controls:
        st.subheader("✏️ Configure 4 Corner Dots")
        
        edit_mode = st.radio("Mode:", ["➕ Add New Custom Shape", "✏️ Edit Existing Shape"], horizontal=True)
        
        selected_idx = 0
        if edit_mode == "✏️ Edit Existing Shape" and len(st.session_state.zones) > 0:
            zone_names = [f"📁 {z['name']} ({z.get('project_code','PRJ')})" for z in st.session_state.zones]
            selected_idx = st.selectbox("Select Partition to Edit:", range(len(zone_names)), format_func=lambda i: zone_names[i])
            cur_zone = st.session_state.zones[selected_idx]
            def_name = cur_zone['name']
            def_code = cur_zone.get('project_code', '')
            def_pts = extract_zone_points(cur_zone)
        else:
            def_name = f"Project {chr(65 + len(st.session_state.zones))}"
            def_code = f"PRJ-{chr(65 + len(st.session_state.zones))}"
            def_pts = [[0.10, 0.10], [0.50, 0.10], [0.50, 0.80], [0.10, 0.80]]
            
        p_name = st.text_input("Project Name", value=def_name, key="studio_p_name")
        p_code = st.text_input("Project Code", value=def_code, key="studio_p_code")
        
        st.markdown("**🔴 Dot 1 (Top-Left)**")
        col_d1_x, col_d1_y = st.columns(2)
        with col_d1_x:
            p1_x = st.slider("Dot 1 X %", 0, 100, int(def_pts[0][0]*100), key="d1_x")
        with col_d1_y:
            p1_y = st.slider("Dot 1 Y %", 0, 100, int(def_pts[0][1]*100), key="d1_y")

        st.markdown("**🟢 Dot 2 (Top-Right)**")
        col_d2_x, col_d2_y = st.columns(2)
        with col_d2_x:
            p2_x = st.slider("Dot 2 X %", 0, 100, int(def_pts[1][0]*100), key="d2_x")
        with col_d2_y:
            p2_y = st.slider("Dot 2 Y %", 0, 100, int(def_pts[1][1]*100), key="d2_y")

        st.markdown("**🔵 Dot 3 (Bottom-Right)**")
        col_d3_x, col_d3_y = st.columns(2)
        with col_d3_x:
            p3_x = st.slider("Dot 3 X %", 0, 100, int(def_pts[2][0]*100), key="d3_x")
        with col_d3_y:
            p3_y = st.slider("Dot 3 Y %", 0, 100, int(def_pts[2][1]*100), key="d3_y")

        st.markdown("**🟡 Dot 4 (Bottom-Left)**")
        col_d4_x, col_d4_y = st.columns(2)
        with col_d4_x:
            p4_x = st.slider("Dot 4 X %", 0, 100, int(def_pts[3][0]*100), key="d4_x")
        with col_d4_y:
            p4_y = st.slider("Dot 4 Y %", 0, 100, int(def_pts[3][1]*100), key="d4_y")

        new_points = [
            [p1_x / 100.0, p1_y / 100.0],
            [p2_x / 100.0, p2_y / 100.0],
            [p3_x / 100.0, p3_y / 100.0],
            [p4_x / 100.0, p4_y / 100.0]
        ]
        
        # Temporary zones array for real-time visual preview canvas
        preview_zones = [z for z in st.session_state.zones]
        active_draft = {'name': p_name, 'project_code': p_code, 'points': new_points}
        if edit_mode == "✏️ Edit Existing Shape" and len(preview_zones) > selected_idx:
            preview_zones[selected_idx] = active_draft
        else:
            preview_zones.append(active_draft)
            
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("💾 Save 4-Dot Shape", type="primary", use_container_width=True):
                if edit_mode == "✏️ Edit Existing Shape" and len(st.session_state.zones) > selected_idx:
                    st.session_state.zones[selected_idx] = active_draft
                else:
                    st.session_state.zones.append(active_draft)
                st.success(f"Saved 4-Dot custom shape for '{p_name}'!")
                st.rerun()
        with btn_col2:
            if st.button("🗑️ Clear All", use_container_width=True):
                st.session_state.zones = []
                st.rerun()

    with col_canvas:
        st.subheader("🖼️ First Frame Preview Canvas")
        annotated_preview = draw_zones_on_preview(bgr_first_frame, preview_zones)
        display_st_image(st, cv2.cvtColor(annotated_preview, cv2.COLOR_BGR2RGB))
        st.caption("📍 Dots 1, 2, 3, 4 mark the 4 corners of your custom shape overlaid on the video frame.")


# Active zones to pass to detector
active_zones = st.session_state.zones if enable_zones else []


# ---------------------------------------------------------
# Mode 1: Upload Video File (DEFAULT)
# ---------------------------------------------------------
if input_type == "🎥 Upload Video File":
    st.subheader("🎥 Video Detection & Analysis")
    uploaded_video = st.file_uploader(
        "Choose a video file to detect sitting/standing people and segregate by project boundary...",
        type=["mp4", "avi", "mov", "mkv"]
    )
    
    if uploaded_video is not None:
        tfile_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tfile:
                tfile.write(uploaded_video.read())
                tfile_path = tfile.name
            
            cap = cv2.VideoCapture(tfile_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps_video = cap.get(cv2.CAP_PROP_FPS) or 25
            width_v = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height_v = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Read First Frame for Interactive Partition Drawer
            ret_first, first_frame = cap.read()
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # reset to beginning
            
            st.info(f"Video Loaded: {width_v}x{height_v} @ {fps_video:.1f} FPS • Total Frames: {total_frames}")
            
            if ret_first:
                render_first_frame_partition_studio(first_frame)
                st.markdown("---")
            
            start_processing = st.button("▶️ Start Video Detection & Segregation", type="primary")
            
            if start_processing:
                metrics_placeholder = st.empty()
                progress_bar = st.progress(0)
                status_text = st.empty()
                video_placeholder = st.empty()
                zone_table_placeholder = st.empty()
                
                # Setup VideoWriter for annotated output
                output_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                output_temp_path = output_temp.name
                output_temp.close()
                
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out_writer = cv2.VideoWriter(output_temp_path, fourcc, fps_video, (width_v, height_v))
                
                frame_idx = 0
                latest_zone_stats = {}
                
                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break
                        
                    frame_idx += 1
                    
                    # Detect sitting/standing persons, objects & match defined zones
                    annotated_frame, stats = detector.process_frame(
                        frame,
                        draw_yolo_objects=draw_objects,
                        draw_heads=draw_heads,
                        zones=active_zones
                    )
                    
                    out_writer.write(annotated_frame)
                    
                    male_cnt = stats.get('male_count', 0)
                    female_cnt = stats.get('female_count', 0)
                    sitting_cnt = stats.get('sitting_count', 0)
                    standing_cnt = stats.get('standing_count', 0)
                    person_cnt = stats.get('person_count', stats.get('head_count', 0))
                    obj_cnt = stats.get('total_objects', 0)
                    fps_val = stats.get('fps', 0.0)
                    latest_zone_stats = stats.get('zone_stats', {})
                    latest_unassigned = stats.get('unassigned_count', 0)
                    
                    if frame_idx % 2 == 0 or frame_idx == total_frames:
                        with metrics_placeholder.container():
                            render_metrics_bar(
                                male=male_cnt,
                                female=female_cnt,
                                sitting=sitting_cnt,
                                standing=standing_cnt,
                                person_count=person_cnt,
                                objects=obj_cnt,
                                fps=fps_val
                            )
                        
                        display_st_image(video_placeholder, cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB))
                        
                        if len(latest_zone_stats) > 0:
                            with zone_table_placeholder.container():
                                render_zone_analytics_table(latest_zone_stats, latest_unassigned)
                        
                        if total_frames > 0:
                            prog_val = min(float(frame_idx) / float(total_frames), 1.0)
                            progress_bar.progress(prog_val)
                            status_text.text(f"Processing Frame {frame_idx}/{total_frames} ({prog_val*100:.1f}%)")
                
                cap.release()
                out_writer.release()
                
                status_text.success("🎉 Video Detection Completed!")
                progress_bar.progress(1.0)
                
                if len(latest_zone_stats) > 0:
                    render_zone_analytics_table(latest_zone_stats, latest_unassigned)
                
                st.markdown("---")
                st.subheader("📥 Download Processed Video")
                with open(output_temp_path, "rb") as f:
                    st.download_button(
                        label="💾 Download Classified Output Video (.mp4)",
                        data=f.read(),
                        file_name="classified_sitting_standing_zones_video.mp4",
                        mime="video/mp4"
                    )
                    
                if os.path.exists(output_temp_path):
                    try:
                        os.unlink(output_temp_path)
                    except Exception:
                        pass
            else:
                cap.release()
                
        finally:
            if tfile_path and os.path.exists(tfile_path):
                try:
                    os.unlink(tfile_path)
                except Exception:
                    pass

# ---------------------------------------------------------
# Mode 2: Live Webcam Stream
# ---------------------------------------------------------
elif input_type == "📹 Live Webcam Stream":
    st.subheader("📹 Live Camera Stream")
    
    run_webcam = st.checkbox("Start Live Camera Stream", value=False)
    
    if run_webcam:
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            st.error("Could not access local webcam camera.")
        else:
            metrics_placeholder = st.empty()
            webcam_placeholder = st.empty()
            zone_table_placeholder = st.empty()
            
            while run_webcam and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    st.warning("Failed to grab frame from camera.")
                    break
                    
                annotated_frame, stats = detector.process_frame(
                    frame,
                    draw_yolo_objects=draw_objects,
                    draw_heads=draw_heads,
                    zones=active_zones
                )
                
                male_cnt = stats.get('male_count', 0)
                female_cnt = stats.get('female_count', 0)
                sitting_cnt = stats.get('sitting_count', 0)
                standing_cnt = stats.get('standing_count', 0)
                person_cnt = stats.get('person_count', stats.get('head_count', 0))
                obj_cnt = stats.get('total_objects', 0)
                fps_val = stats.get('fps', 0.0)
                zone_stats = stats.get('zone_stats', {})
                unassigned_cnt = stats.get('unassigned_count', 0)
                
                with metrics_placeholder.container():
                    render_metrics_bar(
                        male=male_cnt,
                        female=female_cnt,
                        sitting=sitting_cnt,
                        standing=standing_cnt,
                        person_count=person_cnt,
                        objects=obj_cnt,
                        fps=fps_val
                    )
                
                display_st_image(webcam_placeholder, cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB))
                
                if len(zone_stats) > 0:
                    with zone_table_placeholder.container():
                        render_zone_analytics_table(zone_stats, unassigned_cnt)
                
            cap.release()

# ---------------------------------------------------------
# Mode 3: Upload Image
# ---------------------------------------------------------
elif input_type == "📷 Upload Image":
    st.subheader("📷 Single Image Analysis")
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        frame = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
        # Interactive Visual Partition Studio for uploaded image
        render_first_frame_partition_studio(frame)
        st.markdown("---")
        
        with st.spinner("Processing frame..."):
            annotated_frame, stats = detector.process_frame(
                frame,
                draw_yolo_objects=draw_objects,
                draw_heads=draw_heads,
                zones=active_zones
            )
        
        male_cnt = stats.get('male_count', 0)
        female_cnt = stats.get('female_count', 0)
        sitting_cnt = stats.get('sitting_count', 0)
        standing_cnt = stats.get('standing_count', 0)
        person_cnt = stats.get('person_count', stats.get('head_count', 0))
        obj_cnt = stats.get('total_objects', 0)
        fps_val = stats.get('fps', 0.0)
        zone_stats = stats.get('zone_stats', {})
        unassigned_cnt = stats.get('unassigned_count', 0)
        
        render_metrics_bar(
            male=male_cnt,
            female=female_cnt,
            sitting=sitting_cnt,
            standing=standing_cnt,
            person_count=person_cnt,
            objects=obj_cnt,
            fps=fps_val
        )
        st.markdown("<br>", unsafe_allow_html=True)
        
        col_orig, col_proc = st.columns(2)
        with col_orig:
            st.write("**Original Image**")
            display_st_image(st, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        with col_proc:
            st.write("**Classified Output**")
            display_st_image(st, cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB))
            
        if len(zone_stats) > 0:
            render_zone_analytics_table(zone_stats, unassigned_cnt)
