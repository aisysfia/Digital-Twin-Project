import omni.ui as ui
import json
import math
import os
from pxr import UsdGeom, Gf
import omni.usd

# --- CONFIGURATION ---
JSON_FILE_PATH = r"C:\Users\sofia\proj_dt\EV Range Prediction\live_telemetry.json"
WHEEL_PATHS = [
    "/root/root/Sketchfab_model/_2e6acfb837fa495687fc45736746c77f_obj_cleaner_materialmerger_gles/Wheel_FL",
    "/root/root/Sketchfab_model/_2e6acfb837fa495687fc45736746c77f_obj_cleaner_materialmerger_gles/Wheel_FR",
    "/root/root/Sketchfab_model/_2e6acfb837fa495687fc45736746c77f_obj_cleaner_materialmerger_gles/Wheel_RL",
    "/root/root/Sketchfab_model/_2e6acfb837fa495687fc45736746c77f_obj_cleaner_materialmerger_gles/Wheel_RR"
]
SPIN_AXIS = 2 # Z-Axis

# Change this to -1 if the wheels are spinning backward!
SPIN_DIRECTION = 1 

def setup(db):
    # Initializes state variables
    db.internal_state.current_rotations = [0.0, 0.0, 0.0, 0.0]
    db.internal_state.last_mtime = 0
    db.internal_state.latest_data = {}
    db.internal_state.is_spinning = True
    
    # Button Callbacks
    def toggle_spin():
        db.internal_state.is_spinning = not db.internal_state.is_spinning
        db.internal_state.btn_spin.text = "Resume Spin" if not db.internal_state.is_spinning else "Stop Spin"
        db.internal_state.btn_spin.style = {"background_color": 0xFF33AA33} if not db.internal_state.is_spinning else {"background_color": 0xFF3333FF}

    def reset_rotations():
        db.internal_state.current_rotations = [0.0, 0.0, 0.0, 0.0]
        stage = omni.usd.get_context().get_stage()
        if not stage: return
        for path in WHEEL_PATHS:
            prim = stage.GetPrimAtPath(path)
            if prim.IsValid() and prim.HasAttribute('xformOp:rotateXYZ'):
                attr = prim.GetAttribute('xformOp:rotateXYZ')
                current_val = list(attr.Get() or Gf.Vec3d(0,0,0))
                current_val[SPIN_AXIS] = 0.0
                attr.Set(Gf.Vec3d(*current_val))

    # Create the Unified UI Window
    db.internal_state.window = ui.Window("EV Digital Twin Dashboard", width=300, height=220)
    with db.internal_state.window.frame:
        with ui.VStack(spacing=8, padding=10):
            ui.Label("EV LIVE TELEMETRY", style={"color": 0xFF00AAFF, "font_size": 18})
            db.internal_state.range_label = ui.Label("Predicted Range: -- km")
            db.internal_state.speed_label = ui.Label("Current Speed: -- km/h")
            db.internal_state.battery_label = ui.Label("Battery Status: -- %")
            
            ui.Spacer(height=5)
            ui.Line()
            ui.Spacer(height=5)
            
            db.internal_state.btn_spin = ui.Button("Stop Spin", style={"background_color": 0xFF3333FF}, height=30)
            db.internal_state.btn_spin.set_clicked_fn(toggle_spin)
            
            # --- CHANGED: Button text updated here ---
            btn_reset = ui.Button("Reset to default position", style={"background_color": 0xFF555555}, height=30)
            btn_reset.set_clicked_fn(reset_rotations)

def cleanup(db):
    # Safely destroys the window if the graph is deleted or Playback is stopped completely
    if hasattr(db.internal_state, 'window') and db.internal_state.window:
        db.internal_state.window.destroy()

def compute(db):
    dt = db.inputs.dt
    WHEEL_RADIUS_METERS = 0.35

    # 1. Read JSON Telemetry
    try:
        if os.path.exists(JSON_FILE_PATH):
            current_mtime = os.path.getmtime(JSON_FILE_PATH)
            if current_mtime != db.internal_state.last_mtime:
                with open(JSON_FILE_PATH, "r") as f:
                    db.internal_state.latest_data = json.load(f)
                db.internal_state.last_mtime = current_mtime
    except Exception:
        pass

    speed_kmh = db.internal_state.latest_data.get("speed_kmh", 0.0)
    
    # 2. Update the UI Labels
    if hasattr(db.internal_state, 'speed_label'):
        db.internal_state.range_label.text = f"Predicted Range: {db.internal_state.latest_data.get('predicted_range', 0.0):.2f} km"
        db.internal_state.speed_label.text = f"Current Speed: {speed_kmh:.1f} km/h"
        db.internal_state.battery_label.text = f"Battery Status: {db.internal_state.latest_data.get('battery_status', 0.0):.1f} %"

    # 3. Check Spin State (Return early if paused)
    if not db.internal_state.is_spinning:
        return True

    # 4. Execute Spin Math (Z-Axis)
    stage = omni.usd.get_context().get_stage()
    if not stage: return True

    speed_ms = speed_kmh / 3.6
    if speed_ms > 0:
        rotation_delta = math.degrees(speed_ms / WHEEL_RADIUS_METERS) * dt * SPIN_DIRECTION
    else:
        rotation_delta = 0.0

    for i, path in enumerate(WHEEL_PATHS):
        prim = stage.GetPrimAtPath(path)
        if prim.IsValid():
            db.internal_state.current_rotations[i] += rotation_delta
            xformable = UsdGeom.Xformable(prim)
            op_name = 'xformOp:rotateXYZ'
            attr = prim.GetAttribute(op_name)
            
            if not attr.IsValid():
                xformable.AddRotateXYZOp()
                attr = prim.GetAttribute(op_name)

            current_val = list(attr.Get() or Gf.Vec3d(0, 0, 0))
            current_val[SPIN_AXIS] = db.internal_state.current_rotations[i]
            attr.Set(Gf.Vec3d(*current_val))

    return True