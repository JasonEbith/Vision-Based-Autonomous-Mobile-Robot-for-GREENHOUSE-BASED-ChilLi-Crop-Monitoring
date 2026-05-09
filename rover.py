import cv2
import numpy as np
from ai_edge_litert.interpreter import Interpreter
from picamera2 import Picamera2
from gpiozero import DigitalInputDevice
import yaml, time, threading, socket, serial, datetime, json
from http.server import BaseHTTPRequestHandler, HTTPServer

# ══════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════
MODEL     = '/home/jason1412/chili_pest/best_int8new.tflite'
YAML_PATH = '/home/jason1412/chili_pest/metadata.yaml'
SIZE      = 416
PORT         = 8080
SERIAL_PORT  = '/dev/ttyUSB0'
BAUD         = 115200

HSV_LO       = np.array([38, 124,  48])
HSV_HI       = np.array([81, 212, 215])

BASE_SPEED   = 100
Kp           = 0.6
CENTRE_DEAD  = 15
TURN_MODE    = "ARC"
TURN_BOOST   = 30

PEST_ZOOM    = 2.0
SENSOR_W     = 3280
SENSOR_H     = 2464

ROW_DRIVE_SECONDS  = 3
MOTOR_RUN_SECONDS  = 1.5
PEST_SCAN_SECONDS  = 10

BLACK_THRESHOLD    = 0.75
NUDGE_SPEED        = 80
NUDGE_DURATION     = 1.0

TILT_ROW_ANGLE  = 60
TILT_PEST_ANGLE = 90
PAN_ROW_ANGLE   = 50
PAN_PEST_ANGLE  = 0

MOISTURE_GPIO = 4

# ══════════════════════════════════════════════════════════════
#  MOISTURE SENSOR
# ══════════════════════════════════════════════════════════════
try:
    moisture_sensor = DigitalInputDevice(MOISTURE_GPIO)
    moisture_ok     = True
    print(f"[MOISTURE] YL-69 connected on GPIO{MOISTURE_GPIO}")
except Exception as e:
    moisture_sensor = None
    moisture_ok     = False
    print(f"[MOISTURE] Not found: {e} — moisture will show as N/A")

def read_moisture():
    if not moisture_ok:
        return None, "N/A"
    moist = not moisture_sensor.value
    label = "Moist" if moist else "Dry — needs water"
    return moist, label

# ══════════════════════════════════════════════════════════════
#  DETECTION LOG
# ══════════════════════════════════════════════════════════════
detection_log  = []
log_lock       = threading.Lock()
plant_counter  = 0

def add_log_entry(pests, moisture_label, row_found):
    """Only logs and increments counter when a real plant row was detected."""
    global plant_counter

    if not row_found:
        print("[LOG] Skipped — no plant row detected this cycle")
        return

    plant_counter += 1
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    entry = {
        "time":     ts,
        "plant":    f"plant{plant_counter}",
        "pests":    pests if pests else ["Healthy"],
        "moisture": moisture_label,
    }
    with log_lock:
        detection_log.append(entry)
        if len(detection_log) > 50:
            detection_log.pop(0)
    print(f"\n[LOG] {ts} - {entry['plant']}: "
          f"pests={entry['pests']}  moisture={moisture_label}")

# ══════════════════════════════════════════════════════════════
#  SERIAL
# ══════════════════════════════════════════════════════════════
try:
    ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
    time.sleep(2)
    print(f"[SERIAL] Connected on {SERIAL_PORT}")
except Exception as e:
    print(f"[SERIAL] Failed: {e}")
    ser = None

def send_motor(left, right):
    if ser is None: return
    try:   ser.write(f"move:{left},{right}\n".encode())
    except Exception as e: print(f"[SERIAL] {e}")

def send_cmd(cmd):
    if ser is None: return
    try:   ser.write((cmd + '\n').encode())
    except Exception as e: print(f"[SERIAL] {e}")

def set_tilt(angle):
    send_cmd(f"tilt:{angle}")
    print(f"[SERVO] tilt → {angle}°")

def set_pan(angle):
    send_cmd(f"pan:{angle}")
    print(f"[SERVO] pan  → {angle}°")

def enter_row_mode():
    send_cmd("mode:ROW")

def enter_pest_mode():
    send_cmd("mode:PEST")

def init_esp32():
    time.sleep(0.5)
    send_cmd(f"mode:{TURN_MODE}")
    set_pan(PAN_ROW_ANGLE)
    print(f"[SERIAL] mode={TURN_MODE}  pan={PAN_ROW_ANGLE}°")

# ══════════════════════════════════════════════════════════════
#  SHARED FRAME
# ══════════════════════════════════════════════════════════════
latest_frame = None
frame_lock   = threading.Lock()

# ══════════════════════════════════════════════════════════════
#  HTML DASHBOARD
# ══════════════════════════════════════════════════════════════
DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Chili Robot Dashboard</title>
  <meta http-equiv="refresh" content="5">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0d1117;
      color: #e6edf3;
      font-family: 'Segoe UI', sans-serif;
      min-height: 100vh;
      padding: 20px;
    }
    h1 { color: #22c55e; font-size: 1.6rem; margin-bottom: 6px; text-align: center; }
    .subtitle { color: #8b949e; font-size: 0.8rem; text-align: center; margin-bottom: 20px; }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      max-width: 1100px;
      margin: 0 auto;
    }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 16px; }
    .card h2 {
      color: #22c55e; font-size: 0.95rem; margin-bottom: 12px;
      border-bottom: 1px solid #30363d; padding-bottom: 6px;
    }
    .stream-card { grid-column: 1 / -1; text-align: center; }
    .stream-card img { border: 2px solid #22c55e; border-radius: 8px; max-width: 100%; max-height: 400px; }
    .log-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
    .log-table th {
      color: #8b949e; text-align: left; padding: 4px 8px;
      border-bottom: 1px solid #30363d;
    }
    .log-table td { padding: 5px 8px; border-bottom: 1px solid #21262d; vertical-align: top; }
    .log-table tr:last-child td { border-bottom: none; }
    .pest-tag {
      display: inline-block; background: #2d1b00; color: #f97316;
      border: 1px solid #f97316; border-radius: 4px;
      padding: 1px 6px; font-size: 0.75rem; margin: 1px;
    }
    .pest-none { color: #22c55e; font-size: 0.8rem; }
    .moist-ok  { color: #22c55e; font-weight: bold; }
    .moist-dry { color: #ef4444; font-weight: bold; }
    .moist-na  { color: #8b949e; }
    .status-bar { display: flex; gap: 16px; flex-wrap: wrap; font-size: 0.82rem; }
    .stat {
      background: #21262d; border-radius: 6px; padding: 8px 14px;
      flex: 1; min-width: 120px; text-align: center;
    }
    .stat .val { font-size: 1.3rem; color: #22c55e; font-weight: bold; }
    .stat .lbl { color: #8b949e; font-size: 0.7rem; margin-top: 2px; }
    .refresh-note { text-align: center; color: #484f58; font-size: 0.72rem; margin-top: 14px; }
  </style>
</head>
<body>
  <h1>Chili Robot Dashboard</h1>
  <p class="subtitle">Pi Camera v2 &nbsp;|&nbsp; YOLOv8n TFLite INT8 &nbsp;|&nbsp; YL-69 Moisture &nbsp;|&nbsp; MODE_PLACEHOLDER</p>
  <div class="grid">
    <div class="card stream-card">
      <h2>Live Camera Feed</h2>
      <img src="/stream" alt="Live feed"/>
    </div>
    <div class="card">
      <h2>Session Stats</h2>
      <div class="status-bar">
        <div class="stat">
          <div class="val">PLANT_COUNT_PLACEHOLDER</div>
          <div class="lbl">Plants scanned</div>
        </div>
        <div class="stat">
          <div class="val">PEST_COUNT_PLACEHOLDER</div>
          <div class="lbl">Pest detections</div>
        </div>
        <div class="stat">
          <div class="val">DRY_COUNT_PLACEHOLDER</div>
          <div class="lbl">Dry soil alerts</div>
        </div>
      </div>
    </div>
    <div class="card">
      <h2>Detection Log</h2>
      <table class="log-table">
        <thead>
          <tr><th>Time</th><th>Plant</th><th>Pests</th><th>Moisture</th></tr>
        </thead>
        <tbody>
          LOG_ROWS_PLACEHOLDER
        </tbody>
      </table>
    </div>
  </div>
  <p class="refresh-note">Page auto-refreshes every 5 seconds</p>
</body>
</html>
"""

def build_dashboard():
    with log_lock:
        log_copy = list(reversed(detection_log))

    plant_count = plant_counter
    pest_count  = sum(1 for e in log_copy
                      if e["pests"] not in [["Healthy"], ["None detected"]])
    dry_count   = sum(1 for e in log_copy if "Dry" in e.get("moisture", ""))

    if not log_copy:
        rows_html = ('<tr><td colspan="4" style="color:#484f58;text-align:center;">'
                     'No scans yet</td></tr>')
    else:
        rows = []
        for e in log_copy:
            if e["pests"] in [["Healthy"], ["None detected"]]:
                pest_html = '<span class="pest-none">&#10003; Healthy</span>'
            else:
                pest_html = " ".join(
                    f'<span class="pest-tag">{p}</span>'
                    for p in e["pests"])

            moisture = e.get("moisture", "")
            if "N/A" in moisture:
                m_cls = "moist-na"
            elif "Dry" in moisture:
                m_cls = "moist-dry"
            else:
                m_cls = "moist-ok"

            rows.append(
                f'<tr>'
                f'<td>{e["time"]}</td>'
                f'<td>{e["plant"]}</td>'
                f'<td>{pest_html}</td>'
                f'<td class="{m_cls}">{moisture}</td>'
                f'</tr>'
            )
        rows_html = "\n".join(rows)

    html = DASHBOARD_HTML \
        .replace("MODE_PLACEHOLDER",        TURN_MODE + " turn mode") \
        .replace("PLANT_COUNT_PLACEHOLDER", str(plant_count)) \
        .replace("PEST_COUNT_PLACEHOLDER",  str(pest_count)) \
        .replace("DRY_COUNT_PLACEHOLDER",   str(dry_count)) \
        .replace("LOG_ROWS_PLACEHOLDER",    rows_html)
    return html

# ══════════════════════════════════════════════════════════════
#  MJPEG SERVER
# ══════════════════════════════════════════════════════════════
class StreamHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def do_GET(self):
        if self.path == '/':
            html = build_dashboard().encode('utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(html))
            self.end_headers()
            self.wfile.write(html)

        elif self.path == '/stream':
            self.send_response(200)
            self.send_header('Content-type',
                             'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            try:
                while True:
                    with frame_lock:
                        frame = latest_frame
                    if frame is None:
                        time.sleep(0.05)
                        continue
                    _, jpg = cv2.imencode('.jpg', frame,
                                         [cv2.IMWRITE_JPEG_QUALITY, 85])
                    self.wfile.write(b'--frame\r\n')
                    self.send_header('Content-Type',   'image/jpeg')
                    self.send_header('Content-Length', len(jpg))
                    self.end_headers()
                    self.wfile.write(jpg.tobytes())
                    self.wfile.write(b'\r\n')
                    time.sleep(0.05)
            except (BrokenPipeError, ConnectionResetError):
                pass

        elif self.path == '/log.json':
            with log_lock:
                data = json.dumps(detection_log).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-Length', len(data))
            self.end_headers()
            self.wfile.write(data)

        else:
            self.send_response(404)
            self.end_headers()

threading.Thread(
    target=lambda: HTTPServer(('0.0.0.0', PORT), StreamHandler).serve_forever(),
    daemon=True
).start()
time.sleep(1)

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
pi_ip = s.getsockname()[0]
s.close()
print(f"\n{'='*50}")
print(f"  Dashboard: http://{pi_ip}:{PORT}")
print(f"  Stream:    http://{pi_ip}:{PORT}/stream")
print(f"  Log JSON:  http://{pi_ip}:{PORT}/log.json")
print(f"{'='*50}\n")

# ══════════════════════════════════════════════════════════════
#  CAMERA
# ══════════════════════════════════════════════════════════════
cam = Picamera2()

row_cfg  = cam.create_preview_configuration(
    main={"size": (640, 480)},
    controls={"AwbEnable":True,"AeEnable":True,
              "NoiseReductionMode":1,"Sharpness":1.0,
              "Contrast":1.0,"Saturation":1.0,"Brightness":0.0})

pest_cfg = cam.create_preview_configuration(
    main={"size": (1280, 960)},
    controls={"AwbEnable":True,"AeEnable":True,
              "NoiseReductionMode":1,"Sharpness":3.0,
              "Contrast":1.3,"Saturation":1.4,"Brightness":0.05})

cam.configure(row_cfg)
cam.start()
time.sleep(2)
current_cam_mode = "ROW"
print("Camera started in ROW mode.\n")

def set_zoom(zoom=1.0):
    zoom   = max(1.0, zoom)
    crop_w = int(SENSOR_W / zoom)
    crop_h = int(SENSOR_H / zoom)
    x = (SENSOR_W - crop_w) // 2
    y = (SENSOR_H - crop_h) // 2
    cam.set_controls({"ScalerCrop": (x, y, crop_w, crop_h)})

def switch_camera(target_mode):
    global current_cam_mode
    if current_cam_mode == target_mode:
        return
    try:
        cam.stop()
        time.sleep(0.2)
        cam.configure(pest_cfg if target_mode == "PEST" else row_cfg)
        cam.start()
        time.sleep(0.6)
        set_zoom(PEST_ZOOM if target_mode == "PEST" else 1.0)
        current_cam_mode = target_mode
        print(f"\n[CAM] → {target_mode}")
    except RuntimeError as e:
        print(f"\n[CAM] Switch failed: {e}")
        cam.start()

# ══════════════════════════════════════════════════════════════
#  ROW DETECTION
# ══════════════════════════════════════════════════════════════
def detect_row(frame):
    h, w = frame.shape[:2]
    roi  = frame[int(h * 0.55):h, :]
    hsv  = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, HSV_LO, HSV_HI)
    k    = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,   k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, k)
    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[int(h * 0.55):h, :] = mask
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        cv2.putText(frame, "NO ROW DETECTED", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
        return None, frame, full_mask
    biggest = max(cnts, key=cv2.contourArea)
    M = cv2.moments(biggest)
    if M["m00"] == 0:
        return None, frame, full_mask
    cx       = int(M["m10"] / M["m00"])
    error_px = cx - w // 2
    cv2.drawContours(roi, [biggest], -1, (0,255,0), 2)
    cv2.line(roi, (cx,   0), (cx,   roi.shape[0]), (0,0,255), 2)
    cv2.line(roi, (w//2, 0), (w//2, roi.shape[0]), (255,0,0), 1)
    frame[int(h * 0.55):h, :] = roi
    return error_px, frame, full_mask

def is_black_ahead(frame):
    h, w   = frame.shape[:2]
    bottom = frame[int(h * 0.70):h, :]
    gray   = cv2.cvtColor(bottom, cv2.COLOR_BGR2GRAY)
    ratio  = np.sum(gray < 40) / (bottom.shape[0] * bottom.shape[1])
    return ratio >= BLACK_THRESHOLD, ratio

def p_control(error_px):
    correction = int(Kp * error_px)
    if abs(error_px) <= CENTRE_DEAD:
        return BASE_SPEED, BASE_SPEED
    if correction > 0:
        left_speed  = min(255, BASE_SPEED + correction + TURN_BOOST)
        right_speed = max(0,   BASE_SPEED - correction)
    else:
        left_speed  = max(0,   BASE_SPEED + correction)
        right_speed = min(255, BASE_SPEED - correction + TURN_BOOST)
    return left_speed, right_speed

def draw_row_overlay(vis, error, left, right, fps, phase_label, time_left):
    direction, col = "  CENTRE  ", (0, 200, 100)
    if   error >  CENTRE_DEAD: direction, col = ">>> STEER RIGHT", (0,140,255)
    elif error < -CENTRE_DEAD: direction, col = "<<< STEER LEFT",  (255,140,0)
    cv2.rectangle(vis, (0,0), (480,115), (0,0,0), -1)
    cv2.putText(vis,
        f"FPS:{fps:.1f} | {phase_label} | {time_left:.1f}s | {TURN_MODE}",
        (8,18), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0,255,80), 1)
    cv2.putText(vis, f"Row err: {error:+d} px",
                (8,40), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (255,255,0), 2)
    cv2.putText(vis, f"L={left}  R={right}",
                (8,64), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (255,255,0), 2)
    cv2.putText(vis, direction,
                (8,90), cv2.FONT_HERSHEY_SIMPLEX, 0.60, col, 2)
    return direction

# ══════════════════════════════════════════════════════════════
#  PEST DETECTION
# ══════════════════════════════════════════════════════════════
# Class 3 (Healthy) threshold set to 1.10 so it is never reported as a detection
CLASS_CONF = {0:0.45, 1:0.50, 2:0.65, 3:1.10, 4:0.60, 5:0.45, 6:0.45}
CONF       = 0.45
MIN_BOX_AREA_FRACTION = 0.015
COLORS = [(0,255,80),(0,180,255),(255,80,80),
          (255,255,0),(200,0,255),(255,128,0),(0,255,255)]

with open(YAML_PATH) as f:
    data  = yaml.safe_load(f)
    names = data['names']
    if isinstance(names, dict):
        names = [names[i] for i in sorted(names.keys())]
print(f"Classes ({len(names)}): {names}")

interp = Interpreter(model_path=MODEL, num_threads=4)
interp.allocate_tensors()
inp = interp.get_input_details()
out = interp.get_output_details()
print(f"Model loaded. Input:{inp[0]['shape']}  Output:{out[0]['shape']}")

def preprocess(frame):
    return np.expand_dims(
        cv2.resize(frame, (SIZE, SIZE)).astype(np.float32) / 255.0, axis=0)

def postprocess(output, h, w):
    dets, results = np.squeeze(output), []
    for row in dets:
        x1, y1, x2, y2, conf, cid = row
        cid = int(cid)
        if cid >= len(names): continue
        if conf < CLASS_CONF.get(cid, CONF): continue
        if x2 <= 1.0 and y2 <= 1.0:
            x1,y1,x2,y2 = int(x1*w),int(y1*h),int(x2*w),int(y2*h)
        else:
            x1,y1,x2,y2 = (int(x1*w/SIZE),int(y1*h/SIZE),
                            int(x2*w/SIZE),int(y2*h/SIZE))
        x1,y1 = max(0,x1), max(0,y1)
        x2,y2 = min(x2,w), min(y2,h)
        bw,bh = x2-x1, y2-y1
        area  = bw*bh
        if area < MIN_BOX_AREA_FRACTION*w*h or area > 0.85*w*h: continue
        if bw/(bh+1e-6) > 4.0 or bw/(bh+1e-6) < 0.25: continue
        results.append((x1,y1,x2,y2,float(conf),cid))
    return results

def run_pest_detection(frame):
    h, w = frame.shape[:2]
    interp.set_tensor(inp[0]['index'], preprocess(frame))
    interp.invoke()
    detections = postprocess(interp.get_tensor(out[0]['index']), h, w)
    for (x1,y1,x2,y2,conf,cid) in detections:
        color = COLORS[cid % len(COLORS)]
        label = f"{names[cid]} {conf:.2f}"
        cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
        (tw,th),_ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(frame, (x1,y1-th-8), (x1+tw+4,y1), color, -1)
        cv2.putText(frame, label, (x1+2,y1-4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,0,0), 1)
    return frame, detections

# ══════════════════════════════════════════════════════════════
#  WINDOWS
# ══════════════════════════════════════════════════════════════
cv2.namedWindow("Raw Camera", cv2.WINDOW_NORMAL)
cv2.namedWindow("Green Mask", cv2.WINDOW_NORMAL)
cv2.namedWindow("Main View",  cv2.WINDOW_NORMAL)
cv2.moveWindow("Raw Camera",    0,   0)
cv2.moveWindow("Green Mask",  650,   0)
cv2.moveWindow("Main View",  1300,   0)
cv2.resizeWindow("Raw Camera", 640, 480)
cv2.resizeWindow("Green Mask", 640, 480)
cv2.resizeWindow("Main View",  640, 480)

# ══════════════════════════════════════════════════════════════
#  STATE MACHINE
# ══════════════════════════════════════════════════════════════
PHASE_ROW   = "ROW_DRIVE"
PHASE_PEST  = "PEST_SCAN"
PHASE_NUDGE = "NUDGE"

current_phase         = PHASE_ROW
phase_timer           = time.time()
no_row_count          = 0
nudge_done            = False
prev_time             = time.time()
no_plant_logged       = False
pest_phase_detections = []
moisture_checked      = False
moisture_label        = "N/A"
moist                 = None
row_was_found         = False   # ← KEY FIX: tracks if row seen this cycle

set_tilt(TILT_ROW_ANGLE)
time.sleep(0.3)
init_esp32()

print("=" * 55)
print(f" CYCLE: {ROW_DRIVE_SECONDS}s ROW  →  {PEST_SCAN_SECONDS}s PEST")
print(f" TURN MODE : {TURN_MODE}")
print(f" MOISTURE  : GPIO{MOISTURE_GPIO}  ok={moisture_ok}")
print("=" * 55)

# ══════════════════════════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════════════════════════
try:
    while True:
        raw   = cam.capture_array()
        frame = cv2.cvtColor(raw, cv2.COLOR_RGBA2BGR)
        frame = cv2.rotate(frame, cv2.ROTATE_180)

        fps       = 1.0 / max(time.time() - prev_time, 1e-6)
        prev_time = time.time()
        elapsed   = time.time() - phase_timer

        raw_disp = cv2.resize(frame, (640, 480))
        cv2.imshow("Raw Camera", raw_disp)

        # ══════════════════════════════════════════════════════
        #  NUDGE
        # ══════════════════════════════════════════════════════
        if current_phase == PHASE_NUDGE:
            send_motor(NUDGE_SPEED, NUDGE_SPEED)
            cv2.putText(raw_disp,
                f"NUDGE — {NUDGE_DURATION - elapsed:.1f}s",
                (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0,200,255), 2)
            cv2.imshow("Main View", raw_disp)
            with frame_lock: latest_frame = raw_disp.copy()
            if elapsed >= NUDGE_DURATION:
                send_cmd("stop")
                nudge_done    = True
                current_phase = PHASE_ROW
                phase_timer   = time.time()

        # ══════════════════════════════════════════════════════
        #  ROW DRIVE
        # ══════════════════════════════════════════════════════
        elif current_phase == PHASE_ROW:
            time_left = ROW_DRIVE_SECONDS - elapsed
            switch_camera("ROW")
            error, vis, mask = detect_row(frame.copy())

            if elapsed < MOTOR_RUN_SECONDS:
                if error is not None:
                    no_row_count    = 0
                    no_plant_logged = False
                    row_was_found   = True   # ← row confirmed this cycle

                    black, ratio = is_black_ahead(frame)
                    if black and not nudge_done:
                        send_cmd("stop")
                        current_phase = PHASE_NUDGE
                        phase_timer   = time.time()
                        continue

                    left, right = p_control(error)
                    send_motor(left, right)
                    draw_row_overlay(vis, error, left, right, fps,
                                     "ROW DRIVE", time_left)
                else:
                    no_row_count += 1
                    if no_row_count >= 5:
                        send_cmd("stop")
                        if not no_plant_logged:
                            print("[ROW] No row for 5+ frames — motors stopped")
                            no_plant_logged = True
                    cv2.putText(vis, f"NO ROW ({no_row_count})",
                                (10,120), cv2.FONT_HERSHEY_SIMPLEX,
                                0.65, (0,0,255), 2)
            else:
                send_cmd("stop")
                cv2.putText(vis, "Motors stopped — tilting camera",
                            (10,30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (0,200,255), 2)

            mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            roi_line = int(mask_bgr.shape[0] * 0.55)
            cv2.line(mask_bgr, (0,roi_line),
                     (mask_bgr.shape[1],roi_line), (0,200,200), 1)
            cv2.putText(mask_bgr, "ROI starts here", (10,roi_line-6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,200,200), 1)
            cv2.imshow("Green Mask", mask_bgr)
            cv2.imshow("Main View",  vis)
            with frame_lock: latest_frame = vis.copy()

            print(f"[ROW ] FPS:{fps:.1f} | err={error} | "
                  f"row_found={row_was_found} | {time_left:.1f}s   ", end='\r')

            # ── Phase transition ──────────────────────────────
            if elapsed >= ROW_DRIVE_SECONDS:
                send_cmd("stop")

                if not row_was_found:
                    # ── No plant detected — skip pest scan ────
                    print("\n[SKIP] No row detected this cycle "
                          "— skipping pest scan, restarting ROW")
                    # Reset for next ROW cycle without going to PEST
                    row_was_found   = False
                    no_row_count    = 0
                    no_plant_logged = False
                    phase_timer     = time.time()
                    # Stay in PHASE_ROW — don't switch phase or camera

                else:
                    # ── Row was found — proceed to pest scan ──
                    print("\n[PHASE] ROW → PEST")
                    set_tilt(TILT_PEST_ANGLE)
                    enter_pest_mode()
                    time.sleep(0.6)
                    pest_phase_detections = []
                    moisture_checked      = False
                    moisture_label        = "N/A"
                    moist                 = None
                    nudge_done            = False
                    row_was_found         = False   # reset for next cycle
                    current_phase         = PHASE_PEST
                    phase_timer           = time.time()
                    switch_camera("PEST")

        # ══════════════════════════════════════════════════════
        #  PEST SCAN — only runs when row_was_found was True
        # ══════════════════════════════════════════════════════
        elif current_phase == PHASE_PEST:
            time_left = PEST_SCAN_SECONDS - elapsed
            send_cmd("stop")

            # Read moisture once at start of scan
            if not moisture_checked:
                moist, moisture_label = read_moisture()
                moisture_checked = True
                if moist is not None:
                    status = "Moisture threshold reached!" if moist \
                             else "You need to water your plant"
                    print(f"\n[MOISTURE] {status}  ({moisture_label})")
            else:
                _, moisture_label = read_moisture()

            vis, detections = run_pest_detection(frame.copy())

            # Accumulate unique pest names
            for d in detections:
                pname = names[d[5]]
                if pname not in pest_phase_detections:
                    pest_phase_detections.append(pname)

            vis_disp = cv2.resize(vis, (640, 480))
            cv2.rectangle(vis_disp, (0,0), (640,22), (0,0,0), -1)
            cv2.putText(vis_disp,
                f"FPS:{fps:.1f} | PEST SCAN | Det:{len(detections)} | {time_left:.1f}s",
                (6,16), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255,140,0), 1)

            m_col = (0,200,100) if moist else (0,80,255)
            cv2.putText(vis_disp, f"Moisture: {moisture_label}",
                        (6,40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, m_col, 1)

            blank = np.zeros((480,640,3), dtype=np.uint8)
            cv2.putText(blank, "PEST SCAN", (220,40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,140,0), 2)
            cv2.putText(blank, f"Detections: {len(detections)}",
                        (80,100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,200,100), 1)
            cv2.putText(blank, f"Moisture: {moisture_label}",
                        (80,140), cv2.FONT_HERSHEY_SIMPLEX, 0.7, m_col, 1)
            for i, pn in enumerate(pest_phase_detections):
                cv2.putText(blank, f"  - {pn}",
                            (80, 180 + i*30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,80,80), 1)

            cv2.imshow("Green Mask", blank)
            cv2.imshow("Main View",  vis_disp)
            with frame_lock: latest_frame = vis_disp.copy()

            det_names = [names[d[5]] for d in detections]
            print(f"[PEST] FPS:{fps:.1f} | moisture={moisture_label} | "
                  f"Det:{len(detections)} {det_names} | {time_left:.1f}s   ",
                  end='\r')

            # ── End of pest phase ─────────────────────────────
            if elapsed >= PEST_SCAN_SECONDS:
                # row_was_found is already True here (guaranteed by transition logic)
                add_log_entry(pest_phase_detections, moisture_label,
                              row_found=True)
                print("\n[PHASE] PEST → ROW")
                set_tilt(TILT_ROW_ANGLE)
                enter_row_mode()
                time.sleep(0.6)
                current_phase = PHASE_ROW
                phase_timer   = time.time()
                no_row_count  = 0
                switch_camera("ROW")

        if cv2.waitKey(1) & 0xFF == 27:
            break

except KeyboardInterrupt:
    print("\nStopped.")
finally:
    send_cmd("stop")
    set_tilt(TILT_ROW_ANGLE)
    set_pan(PAN_ROW_ANGLE)
    cam.stop()
    if ser: ser.close()
    cv2.destroyAllWindows()
    print("Shutdown complete.")