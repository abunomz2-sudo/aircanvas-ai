import mediapipe as mp
import cv2
import numpy as np
import time
import os
import datetime
import math
from collections import deque

# ─── MediaPipe Setup ──────────────────────────────────────────
mphands = mp.solutions.hands
hands_detector = mphands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    model_complexity=1,
    min_detection_confidence=0.75,
    min_tracking_confidence=0.75,
)
mp_draw = mp.solutions.drawing_utils

canvas = None

# ─── Colors ──────────────────────────────────────────────────
COLORS = {
    "Red":    (0,   60,  255),
    "Orange": (0,  140,  255),
    "Yellow": (0,  220,  255),
    "Green":  (50, 205,   50),
    "Cyan":   (255,220,    0),
    "Blue":   (255,  80,   0),
    "Purple": (200,  0,  180),
    "Pink":   (180,  0,  255),
    "White":  (255,255,  255),
}
COLOR_NAMES  = list(COLORS.keys())
COLOR_VALUES = list(COLORS.values())

# ─── Tools ───────────────────────────────────────────────────
TOOL_BRUSH  = "BRUSH"
TOOL_NEON   = "NEON"
TOOL_ERASER = "ERASER"
TOOL_LINE   = "LINE"
TOOL_RECT   = "RECT"
TOOL_CIRCLE = "CIRCLE"
TOOL_BUCKET = "BUCKET"

current_tool = TOOL_BRUSH

# ─── Background Modes ─────────────────────────────────────────
BG_WEBCAM = "WEBCAM"
BG_DARK   = "SOLID_DARK"
BG_LIGHT  = "SOLID_LIGHT"

bg_mode = BG_WEBCAM

# ─── State ───────────────────────────────────────────────────
current_color_idx  = 0
brush_size         = 8
is_drawing         = False
prev_point         = None
smooth_points      = deque(maxlen=6)
stroke_points      = []  # Store raw stroke points for Bezier interpolation
undo_stack         = []
redo_stack         = []
MAX_UNDO           = 20

# Shape Drawing State
shape_start_point   = None
shape_current_point = None
is_drawing_shape    = False

# Fullscreen state
is_fullscreen = False

# Message feedback state
save_msg = ""
save_msg_time = 0.0

# ─── Landmark IDs ────────────────────────────────────────────
INDEX_TIP  = 8;  INDEX_PIP  = 6
MIDDLE_TIP = 12; MIDDLE_PIP = 10
RING_TIP   = 16; RING_PIP   = 14
PINKY_TIP  = 20; PINKY_PIP  = 18
THUMB_TIP  = 4;  THUMB_IP   = 3

# ─── Gesture Detection ───────────────────────────────────────
def finger_up(lm, tip, pip, is_thumb=False, handedness="Right"):
    def dist_3d(a, b):
        return ((lm[a].x - lm[b].x)**2 + (lm[a].y - lm[b].y)**2 + (lm[a].z - lm[b].z)**2)**0.5
        
    if is_thumb:
        return dist_3d(tip, 0) > dist_3d(2, 0) * 1.08
        
    return dist_3d(tip, 0) > dist_3d(pip, 0) * 1.05

def get_gesture(lm, handedness="Right"):
    index  = finger_up(lm, INDEX_TIP,  INDEX_PIP)
    middle = finger_up(lm, MIDDLE_TIP, MIDDLE_PIP)
    ring   = finger_up(lm, RING_TIP,   RING_PIP)
    pinky  = finger_up(lm, PINKY_TIP,  PINKY_PIP)
    thumb  = finger_up(lm, THUMB_TIP,  THUMB_IP, is_thumb=True, handedness=handedness)

    if index and not middle and not ring and not pinky:
        return "DRAW"
    if index and middle and not ring and not pinky:
        return "HOVER"
    if not index and not middle and not ring and not pinky:
        return "FIST"
    if index and middle and ring and pinky:
        return "CLEAR"
    if thumb and not index and not middle and not ring and not pinky:
        return "UNDO"
    return "NONE"

def get_smooth_point(pt):
    smooth_points.append(pt)
    xs = [p[0] for p in smooth_points]
    ys = [p[1] for p in smooth_points]
    return (int(sum(xs)/len(xs)), int(sum(ys)/len(ys)))

def flood_fill(canvas, x, y, fill_color):
    h, w = canvas.shape[:2]
    if x < 0 or x >= w or y < 0 or y >= h:
        return
    target = tuple(canvas[y, x])
    if target == fill_color:
        return
    mask = np.zeros((h+2, w+2), np.uint8)
    cv2.floodFill(canvas, mask, (x, y), fill_color,
                  loDiff=(20,20,20), upDiff=(20,20,20),
                  flags=cv2.FLOODFILL_FIXED_RANGE)

# ─── Button Layout ────────────────────────────────────────────
class Button:
    def __init__(self, btn_id, btn_type, x1, y1, x2, y2, value, label=""):
        self.id = btn_id
        self.type = btn_type  # "color", "tool", "action"
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.value = value
        self.label = label

buttons = []

# 1. Colors Section (9 circular swatches)
for i, name in enumerate(COLOR_NAMES):
    bx1 = 25 + i * 42
    bx2 = bx1 + 36
    buttons.append(Button(f"color_{name}", "color", bx1, 20, bx2, 60, name))

# 2. Tools Section (7 tools)
TOOLS_LIST = [
    (TOOL_BRUSH, "Brush"),
    (TOOL_NEON, "Neon"),
    (TOOL_ERASER, "Eraser"),
    (TOOL_LINE, "Line"),
    (TOOL_RECT, "Rect"),
    (TOOL_CIRCLE, "Circle"),
    (TOOL_BUCKET, "Bucket"),
]
for i, (tool_val, name) in enumerate(TOOLS_LIST):
    bx1 = 420 + i * 42
    bx2 = bx1 + 36
    buttons.append(Button(f"tool_{tool_val}", "tool", bx1, 20, bx2, 60, tool_val, name))

# 3. Actions Section (4 actions)
ACTIONS_LIST = [
    ("UNDO", "Undo"),
    ("REDO", "Redo"),
    ("SAVE", "Save"),
    ("BG_MODE", "BG"),
]
for i, (act_val, name) in enumerate(ACTIONS_LIST):
    bx1 = 730 + i * 42
    bx2 = bx1 + 36
    buttons.append(Button(f"action_{act_val}", "action", bx1, 20, bx2, 60, act_val, name))

# Dwell Clicking State
DWELL_THRESHOLD = 15
dwell_btn = None
dwell_frames = 0
dwell_triggered = False

def get_hovered_button(cx, cy):
    for btn in buttons:
        if btn.x1 <= cx <= btn.x2 and btn.y1 <= cy <= btn.y2:
            return btn
    return None

def check_brush_size(cx, cy):
    bx = 915
    bar_w = 80
    if 12 <= cy <= 68 and bx <= cx <= bx + bar_w:
        return max(2, min(40, int((cx - bx) / bar_w * 38) + 2))
    return None

def show_message(msg):
    global save_msg, save_msg_time
    save_msg = msg
    save_msg_time = time.time()

def trigger_undo():
    global canvas, undo_stack, redo_stack
    if undo_stack:
        redo_stack.append(canvas.copy())
        canvas = undo_stack.pop()
        show_message("Undo Done")
    else:
        show_message("Nothing to Undo")

def trigger_redo():
    global canvas, undo_stack, redo_stack
    if redo_stack:
        undo_stack.append(canvas.copy())
        canvas = redo_stack.pop()
        show_message("Redo Done")
    else:
        show_message("Nothing to Redo")

def trigger_bg_toggle():
    global bg_mode
    if bg_mode == BG_WEBCAM:
        bg_mode = BG_DARK
        show_message("Mode: Solid Dark")
    elif bg_mode == BG_DARK:
        bg_mode = BG_LIGHT
        show_message("Mode: Solid Light")
    else:
        bg_mode = BG_WEBCAM
        show_message("Mode: Webcam")

def trigger_save():
    global canvas, bg_mode
    if not os.path.exists("output"):
        os.makedirs("output")
        
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"output/drawing_{now}.png"
    h, w = canvas.shape[:2]
    
    if bg_mode == BG_WEBCAM:
        saved_img = canvas[TOOLBAR_H:, :]
    elif bg_mode == BG_DARK:
        bg = np.zeros((h, w, 3), dtype=np.uint8)
        bg[:, :] = (28, 20, 20)
        canvas_gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(canvas_gray, 5, 255, cv2.THRESH_BINARY)
        mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        blended = np.where(mask_3ch == 255, canvas, bg)
        saved_img = blended[TOOLBAR_H:, :]
    else:
        bg = np.zeros((h, w, 3), dtype=np.uint8)
        bg[:, :] = (250, 244, 244)
        canvas_gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(canvas_gray, 5, 255, cv2.THRESH_BINARY)
        mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        blended = np.where(mask_3ch == 255, canvas, bg)
        saved_img = blended[TOOLBAR_H:, :]
        
    cv2.imwrite(filename, saved_img)
    show_message(f"Saved to {filename}")

def trigger_button_action(btn):
    global current_color_idx, current_tool
    if btn.type == "color":
        idx = COLOR_NAMES.index(btn.value)
        current_color_idx = idx
        if current_tool == TOOL_ERASER:
            current_tool = TOOL_BRUSH
            show_message("Tool: Brush")
    elif btn.type == "tool":
        current_tool = btn.value
        show_message(f"Tool: {btn.label}")
    elif btn.type == "action":
        if btn.value == "UNDO":
            trigger_undo()
        elif btn.value == "REDO":
            trigger_redo()
        elif btn.value == "SAVE":
            trigger_save()
        elif btn.value == "BG_MODE":
            trigger_bg_toggle()

# ─── Alpha & Neon Rendering ────────────────────────────────────
def draw_line_alpha(img, pt1, pt2, color, thickness, alpha):
    if alpha >= 1.0:
        cv2.line(img, pt1, pt2, color, thickness, cv2.LINE_AA)
        return
    overlay = img.copy()
    cv2.line(overlay, pt1, pt2, color, thickness, cv2.LINE_AA)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

def draw_line_neon(img, pt1, pt2, color, size):
    core_col = tuple(min(255, int(c * 0.4 + 255 * 0.6)) for c in color)
    draw_line_alpha(img, pt1, pt2, color, size * 4, 0.12)
    draw_line_alpha(img, pt1, pt2, color, int(size * 2.2), 0.28)
    draw_line_alpha(img, pt1, pt2, color, int(size * 1.2), 0.55)
    draw_line_alpha(img, pt1, pt2, core_col, max(2, int(size * 0.4)), 1.0)

def draw_circle_alpha(img, center, radius, color, thickness, alpha):
    overlay = img.copy()
    cv2.circle(overlay, center, radius, color, thickness, cv2.LINE_AA)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

def draw_circle_neon(img, center, color, size):
    core_col = tuple(min(255, int(c * 0.4 + 255 * 0.6)) for c in color)
    r = max(2, size // 2)
    draw_circle_alpha(img, center, r * 4, color, -1, 0.12)
    draw_circle_alpha(img, center, int(r * 2.2), color, -1, 0.28)
    draw_circle_alpha(img, center, int(r * 1.2), color, -1, 0.55)
    draw_circle_alpha(img, center, max(1, int(r * 0.4)), core_col, -1, 1.0)

def draw_bezier_curve(img, p0, p1, p2, color, thickness, tool):
    steps = 15
    pts = []
    for i in range(steps + 1):
        t = i / steps
        # B(t) = (1-t)^2 * P0 + 2(1-t)t * P1 + t^2 * P2
        x = (1 - t)**2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0]
        y = (1 - t)**2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1]
        pts.append((int(x), int(y)))
        
    for j in range(len(pts) - 1):
        if tool == TOOL_NEON:
            draw_line_neon(img, pts[j], pts[j+1], color, thickness)
        else:
            cv2.line(img, pts[j], pts[j+1], color, thickness, cv2.LINE_AA)

def draw_shape_on(img, p1, p2, color, size, tool):
    if tool == TOOL_LINE:
        cv2.line(img, p1, p2, color, size, cv2.LINE_AA)
    elif tool == TOOL_RECT:
        cv2.rectangle(img, p1, p2, color, size, cv2.LINE_AA)
    elif tool == TOOL_CIRCLE:
        radius = int(((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)**0.5)
        cv2.circle(img, p1, radius, color, size, cv2.LINE_AA)

# ─── UI Constants ────────────────────────────────────────────
TOOLBAR_H   = 80

# ─── UI Drawing ──────────────────────────────────────────────
def draw_pill(frame, x1, y1, x2, y2, color, radius=8):
    """Draw a rounded rectangle."""
    cv2.rectangle(frame, (x1 + radius, y1), (x2 - radius, y2), color, -1)
    cv2.rectangle(frame, (x1, y1 + radius), (x2, y2 - radius), color, -1)
    cv2.circle(frame, (x1 + radius, y1 + radius), radius, color, -1)
    cv2.circle(frame, (x2 - radius, y1 + radius), radius, color, -1)
    cv2.circle(frame, (x1 + radius, y2 - radius), radius, color, -1)
    cv2.circle(frame, (x2 - radius, y2 - radius), radius, color, -1)

def draw_pill_outline(frame, x1, y1, x2, y2, color, radius=8, thickness=1):
    cv2.line(frame, (x1 + radius, y1), (x2 - radius, y1), color, thickness, cv2.LINE_AA)
    cv2.line(frame, (x1 + radius, y2), (x2 - radius, y2), color, thickness, cv2.LINE_AA)
    cv2.line(frame, (x1, y1 + radius), (x1, y2 - radius), color, thickness, cv2.LINE_AA)
    cv2.line(frame, (x2, y1 + radius), (x2, y2 - radius), color, thickness, cv2.LINE_AA)
    
    cv2.ellipse(frame, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color, thickness, cv2.LINE_AA)
    cv2.ellipse(frame, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color, thickness, cv2.LINE_AA)
    cv2.ellipse(frame, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color, thickness, cv2.LINE_AA)
    cv2.ellipse(frame, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color, thickness, cv2.LINE_AA)

def draw_tool_icon(frame, tool, cx, cy, active):
    col = (255, 255, 255) if active else (180, 170, 195)
    if tool == TOOL_BRUSH:
        # Fine brush tip slant
        cv2.circle(frame, (cx, cy-4), 2, col, -1, cv2.LINE_AA)
        cv2.line(frame, (cx-3, cy+7), (cx, cy-4), col, 2, cv2.LINE_AA)
    elif tool == TOOL_NEON:
        # Glowing sun/core pattern
        cv2.circle(frame, (cx, cy), 6, col, 1, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), 2, col, -1, cv2.LINE_AA)
    elif tool == TOOL_ERASER:
        # Angled slice block
        cv2.rectangle(frame, (cx-7, cy-5), (cx+7, cy+5), col, -1)
        cv2.line(frame, (cx-7, cy-5), (cx-7, cy+5), (100, 90, 110), 1, cv2.LINE_AA)
    elif tool == TOOL_LINE:
        # Diagonal line with cap endpoints
        cv2.line(frame, (cx-8, cy+8), (cx+8, cy-8), col, 1, cv2.LINE_AA)
        cv2.circle(frame, (cx-8, cy+8), 2, col, -1, cv2.LINE_AA)
        cv2.circle(frame, (cx+8, cy-8), 2, col, -1, cv2.LINE_AA)
    elif tool == TOOL_RECT:
        # Rectangle outline
        cv2.rectangle(frame, (cx-8, cy-7), (cx+8, cy+7), col, 1)
    elif tool == TOOL_CIRCLE:
        # Perfect circle
        cv2.circle(frame, (cx, cy), 8, col, 1, cv2.LINE_AA)
    elif tool == TOOL_BUCKET:
        # Pouring paint bucket
        cv2.line(frame, (cx-7, cy-4), (cx-3, cy+6), col, 1, cv2.LINE_AA)
        cv2.line(frame, (cx+7, cy-4), (cx+3, cy+6), col, 1, cv2.LINE_AA)
        cv2.line(frame, (cx-3, cy+6), (cx+3, cy+6), col, 1, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy-4), 3, col, 1, cv2.LINE_AA)
        cv2.circle(frame, (cx+2, cy+1), 1, col, -1, cv2.LINE_AA)

def draw_action_icon(frame, val, cx, cy, active):
    col = (255, 255, 255) if active else (180, 170, 195)
    if val == "UNDO":
        cv2.ellipse(frame, (cx, cy+2), (7, 6), 0, 45, 300, col, 1, cv2.LINE_AA)
        cv2.line(frame, (cx-7, cy-1), (cx-4, cy-4), col, 1, cv2.LINE_AA)
        cv2.line(frame, (cx-7, cy-1), (cx-10, cy-3), col, 1, cv2.LINE_AA)
    elif val == "REDO":
        cv2.ellipse(frame, (cx, cy+2), (7, 6), 0, -120, 135, col, 1, cv2.LINE_AA)
        cv2.line(frame, (cx+7, cy-1), (cx+4, cy-4), col, 1, cv2.LINE_AA)
        cv2.line(frame, (cx+7, cy-1), (cx+10, cy-3), col, 1, cv2.LINE_AA)
    elif val == "SAVE":
        # Downward arrow pointing into a flat tray
        cv2.line(frame, (cx, cy-8), (cx, cy+2), col, 1, cv2.LINE_AA)
        cv2.line(frame, (cx-4, cy-1), (cx, cy+2), col, 1, cv2.LINE_AA)
        cv2.line(frame, (cx+4, cy-1), (cx, cy+2), col, 1, cv2.LINE_AA)
        # Tray
        cv2.line(frame, (cx-7, cy+6), (cx+7, cy+6), col, 1, cv2.LINE_AA)
        cv2.line(frame, (cx-7, cy+3), (cx-7, cy+6), col, 1, cv2.LINE_AA)
        cv2.line(frame, (cx+7, cy+3), (cx+7, cy+6), col, 1, cv2.LINE_AA)
    elif val == "BG_MODE":
        # Monitor display screen
        cv2.rectangle(frame, (cx-9, cy-6), (cx+9, cy+4), col, 1)
        cv2.line(frame, (cx-3, cy+7), (cx+3, cy+7), col, 1, cv2.LINE_AA)
        cv2.line(frame, (cx, cy+4), (cx, cy+7), col, 1, cv2.LINE_AA)
        if bg_mode == BG_WEBCAM:
            cv2.circle(frame, (cx, cy-1), 2, (0, 229, 255), -1, cv2.LINE_AA)
        elif bg_mode == BG_DARK:
            cv2.rectangle(frame, (cx-6, cy-4), (cx+6, cy+2), (50, 40, 60), -1)
        else:
            cv2.rectangle(frame, (cx-6, cy-4), (cx+6, cy+2), (240, 240, 240), -1)

def draw_toolbar(frame, w):
    # Breathing sine-wave calculation
    breath = 0.5 + 0.5 * math.sin(time.time() * 5.0)

    # Frosted glass floating panels
    overlay = frame.copy()
    draw_pill(overlay, 15, 12, 1045, 68, (15, 12, 22), radius=12)
    draw_pill(overlay, 1060, 12, 1265, 68, (15, 12, 22), radius=12)
    alpha = 0.85
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    draw_pill_outline(frame, 15, 12, 1045, 68, (65, 55, 75), radius=12)
    draw_pill_outline(frame, 1060, 12, 1265, 68, (65, 55, 75), radius=12)

    def draw_separator(x):
        cv2.line(frame, (x, 18), (x, 62), (60, 50, 70), 1)

    # 1. Colors Section (Circular 3D spheres with breathing selection halo)
    for btn in buttons:
        if btn.type != "color":
            continue
        bgr = COLORS[btn.value]
        selected = (COLOR_NAMES[current_color_idx] == btn.value)
        cx_sw = (btn.x1 + btn.x2) // 2
        cy_sw = (btn.y1 + btn.y2) // 2
        
        if selected:
            # breathing selection halo circle
            glow_r = 13 + int(3 * breath)
            gc = tuple(min(255, int(c * (0.12 + 0.20 * breath))) for c in bgr)
            cv2.circle(frame, (cx_sw, cy_sw), glow_r, gc, -1, cv2.LINE_AA)
            cv2.circle(frame, (cx_sw, cy_sw), 14, (240, 235, 250), 1, cv2.LINE_AA)
            
        # Marble sphere base
        cv2.circle(frame, (cx_sw, cy_sw), 11, bgr, -1, cv2.LINE_AA)
        # 3D sphere upper-left highlights
        cv2.circle(frame, (cx_sw - 3, cy_sw - 3), 3, (255, 255, 255), -1, cv2.LINE_AA)

    draw_separator(407)

    # 2. Tools Section
    for btn in buttons:
        if btn.type != "tool":
            continue
        active = (btn.value == current_tool)
        cx_sw = (btn.x1 + btn.x2) // 2
        cy_sw = (btn.y1 + btn.y2) // 2
        bg_col = (45, 35, 65) if active else (24, 20, 34)
        cv2.rectangle(frame, (btn.x1, btn.y1), (btn.x2, btn.y2), bg_col, -1)
        
        # Breathing active border thickness
        if active:
            border_thickness = 1 + int(1.2 * breath)
            cv2.rectangle(frame, (btn.x1, btn.y1), (btn.x2, btn.y2), (0, 229, 255), border_thickness, cv2.LINE_AA)
        else:
            cv2.rectangle(frame, (btn.x1, btn.y1), (btn.x2, btn.y2), (60, 50, 70), 1)
            
        draw_tool_icon(frame, btn.value, cx_sw, cy_sw, active)

    draw_separator(718)

    # 3. Actions Section
    for btn in buttons:
        if btn.type != "action":
            continue
        active = False
        if btn.value == "BG_MODE" and bg_mode != BG_WEBCAM:
            active = True
        cx_sw = (btn.x1 + btn.x2) // 2
        cy_sw = (btn.y1 + btn.y2) // 2
        bg_col = (45, 35, 65) if active else (24, 20, 34)
        cv2.rectangle(frame, (btn.x1, btn.y1), (btn.x2, btn.y2), bg_col, -1)
        cv2.rectangle(frame, (btn.x1, btn.y1), (btn.x2, btn.y2), (60, 50, 70), 1)
        draw_action_icon(frame, btn.value, cx_sw, cy_sw, active)

    draw_separator(902)

    # 4. Brush Size Slider
    bx = 915
    by_bar_y = 40
    bar_w = 80
    cv2.line(frame, (bx, by_bar_y), (bx + bar_w, by_bar_y), (60, 50, 75), 2, cv2.LINE_AA)
    
    fill_w = int(bar_w * ((brush_size - 2) / 38))
    fill_col = COLOR_VALUES[current_color_idx]
    cv2.line(frame, (bx, by_bar_y), (bx + fill_w, by_bar_y), fill_col, 3, cv2.LINE_AA)
    
    thumb_x = bx + fill_w
    cv2.circle(frame, (thumb_x, by_bar_y), 6, (230, 225, 245), -1, cv2.LINE_AA)
    cv2.circle(frame, (thumb_x, by_bar_y), 6, (150, 140, 165), 1, cv2.LINE_AA)
    cv2.putText(frame, f"{brush_size}px", (bx + bar_w + 10, by_bar_y + 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180, 170, 200), 1, cv2.LINE_AA)

    # 5. Right Status Badge (FPS, Tool, Gesture)
    global last_time, fps
    curr_time = time.time()
    if 'last_time' in globals():
        diff = curr_time - last_time
        if diff > 0:
            fps = int(1.0 / diff)
    else:
        fps = 30
    last_time = curr_time
    
    cv2.putText(frame, f"FPS: {fps}", (1075, 33),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 229, 255), 1, cv2.LINE_AA)
                
    tool_labels = {
        TOOL_BRUSH: "Brush", TOOL_NEON: "Neon", TOOL_ERASER: "Eraser",
        TOOL_LINE: "Line", TOOL_RECT: "Rect", TOOL_CIRCLE: "Circle", TOOL_BUCKET: "Fill"
    }
    label_text = tool_labels.get(current_tool, "Draw")
    cv2.putText(frame, label_text, (1075, 52),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (140, 130, 160), 1, cv2.LINE_AA)
                
    # Gesture badge
    gx1 = 1165
    gy1 = 22
    gx2 = 1250
    gy2 = 58
    gest_colors = {
        "DRAW":  ((20, 200, 120), (10, 80, 50)),
        "HOVER": ((0, 229, 255), (0, 90, 100)),
        "FIST":  ((255, 100, 100), (100, 40, 40)),
        "CLEAR": ((255, 180, 60), (100, 70, 20)),
        "UNDO":  ((180, 100, 255), (70, 30, 100)),
    }
    gcol, gdark = gest_colors.get(gesture, ((150, 140, 165), (50, 45, 55)))
    draw_pill(frame, gx1, gy1, gx2, gy2, gdark, radius=4)
    cv2.rectangle(frame, (gx1, gy1), (gx2, gy2), gcol, 1)
    
    (tw, th), _ = cv2.getTextSize(gesture, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)
    cv2.putText(frame, gesture, (gx1 + (gx2 - gx1 - tw) // 2, gy1 + (gy2 - gy1 + th) // 2 - 1),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, gcol, 1, cv2.LINE_AA)

def draw_cursor(frame, cx, cy, gesture):
    col = COLOR_VALUES[current_color_idx]
    if gesture == "DRAW":
        if current_tool == TOOL_ERASER:
            cv2.circle(frame, (cx, cy), brush_size * 3, (100, 100, 255), 1, cv2.LINE_AA)
            cv2.putText(frame, "ERASE", (cx + 12, cy - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 255), 1, cv2.LINE_AA)
        elif current_tool == TOOL_BUCKET:
            cv2.circle(frame, (cx, cy), 6, col, 1, cv2.LINE_AA)
            cv2.putText(frame, "FILL", (cx + 12, cy - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, col, 1, cv2.LINE_AA)
        elif current_tool in (TOOL_LINE, TOOL_RECT, TOOL_CIRCLE):
            cv2.drawMarker(frame, (cx, cy), col, cv2.MARKER_CROSS, 12, 1, cv2.LINE_AA)
        else:
            glow = tuple(max(0, c // 3) for c in col)
            cv2.circle(frame, (cx, cy), brush_size + 5, glow, 2, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy), brush_size, col, -1, cv2.LINE_AA)
            hi = tuple(min(255, c + 80) for c in col)
            cv2.circle(frame, (cx - brush_size//4, cy - brush_size//4),
                       max(2, brush_size//3), hi, -1, cv2.LINE_AA)
                       
    elif gesture == "HOVER":
        if dwell_btn is not None:
            cv2.circle(frame, (cx, cy), 14, (0, 229, 255), 1, cv2.LINE_AA)
            if not dwell_triggered:
                progress = dwell_frames / DWELL_THRESHOLD
                end_angle = int(progress * 360)
                cv2.ellipse(frame, (cx, cy), (14, 14), -90, 0, end_angle, (0, 229, 255), 2, cv2.LINE_AA)
        else:
            cv2.circle(frame, (cx, cy), 16, (160, 150, 180), 1, cv2.LINE_AA)
            cv2.line(frame, (cx-20, cy), (cx+20, cy), (160, 150, 180), 1)
            cv2.line(frame, (cx, cy-20), (cx, cy+20), (160, 150, 180), 1)
            cv2.circle(frame, (cx, cy), 3, (160, 150, 180), -1)
            
    elif gesture == "FIST":
        cv2.circle(frame, (cx, cy), 10, (100, 100, 120), 1, cv2.LINE_AA)
        cv2.putText(frame, "PAUSED", (cx + 12, cy - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 120), 1, cv2.LINE_AA)

# ─── Main ────────────────────────────────────────────────────
WINDOW_NAME = "Air Drawing"
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)

ret, test_frame = cap.read()
h, w = (test_frame.shape[:2] if ret else (720, 1280))
canvas = np.zeros((h, w, 3), dtype=np.uint8)

cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
cv2.resizeWindow(WINDOW_NAME, w, h)

clear_start    = None
undo_last_time = 0
gesture_last   = "NONE"

print("[Canvas] Air Drawing - Ultimate Creative Suite")
print("   1 finger  = DRAW / SELECT / FILL")
print("   2 fingers = HOVER (Dwell 0.5s to select buttons)")
print("   thumb up  = UNDO")
print("   4 fingers = CLEAR (hold 1.5 s)")
print("   B  = toggle background (Webcam / Solid Dark / Solid Light)")
print("   S  = save artwork to output/ directory")
print("   T  = cycle drawing tools")
print("   Y  = redo stroke")
print("   F  = toggle fullscreen")
print("   Q / ESC = quit\n")

while True:
    success, frame = cap.read()
    if not success:
        time.sleep(0.03)
        continue

    frame = cv2.flip(frame, 1)
    fh, fw = frame.shape[:2]

    # Resize canvas if camera resolution changed
    if canvas.shape[:2] != (fh, fw):
        canvas = cv2.resize(canvas, (fw, fh))

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb.flags.writeable = False
    results = hands_detector.process(rgb)
    rgb.flags.writeable = True

    gesture  = "NONE"
    cx, cy   = -1, -1
    handedness_label = "Right"

    if results.multi_hand_landmarks and results.multi_handedness:
        handLms  = results.multi_hand_landmarks[0]
        handInfo = results.multi_handedness[0]
        handedness_label = handInfo.classification[0].label
        lm = handLms.landmark

        cx = int(lm[INDEX_TIP].x * fw)
        cy = int(lm[INDEX_TIP].y * fh)

        gesture = get_gesture(lm, handedness_label)

        mp_draw.draw_landmarks(
            frame, handLms, mphands.HAND_CONNECTIONS,
            mp_draw.DrawingSpec(color=(30, 200, 140), thickness=1, circle_radius=2),
            mp_draw.DrawingSpec(color=(160, 155, 175), thickness=1),
        )

    # ── Gesture actions ──
    if gesture == "HOVER" and cy < TOOLBAR_H and cx > 0:
        btn = get_hovered_button(cx, cy)
        if btn is not None:
            if dwell_btn == btn:
                if not dwell_triggered:
                    dwell_frames += 1
                    if dwell_frames >= DWELL_THRESHOLD:
                        trigger_button_action(btn)
                        dwell_triggered = True
            else:
                dwell_btn = btn
                dwell_frames = 0
                dwell_triggered = False
        else:
            bs = check_brush_size(cx, cy)
            if bs is not None:
                brush_size = bs
            dwell_btn = None
            dwell_frames = 0
            dwell_triggered = False
    else:
        dwell_btn = None
        dwell_frames = 0
        dwell_triggered = False

    if gesture == "CLEAR":
        if clear_start is None:
            clear_start = time.time()
        elif time.time() - clear_start > 1.5:
            undo_stack.append(canvas.copy())
            redo_stack.clear()
            canvas[:] = 0
            clear_start = None
            show_message("Canvas Cleared")
    else:
        clear_start = None

    if gesture == "UNDO" and gesture_last != "UNDO":
        if time.time() - undo_last_time > 0.5:
            trigger_undo()
            undo_last_time = time.time()

    # Shape and tool drawing logic
    is_shape_tool = current_tool in (TOOL_LINE, TOOL_RECT, TOOL_CIRCLE)
    
    if gesture == "DRAW" and cy > TOOLBAR_H and cx > 0:
        smooth = get_smooth_point((cx, cy))
        
        if current_tool == TOOL_ERASER:
            if not is_drawing:
                if len(undo_stack) < MAX_UNDO:
                    undo_stack.append(canvas.copy())
                redo_stack.clear()
            cv2.circle(canvas, smooth, brush_size * 3, (0, 0, 0), -1)
            is_drawing = True
            
        elif current_tool == TOOL_BUCKET:
            if not is_drawing:
                if len(undo_stack) < MAX_UNDO:
                    undo_stack.append(canvas.copy())
                redo_stack.clear()
                draw_col = COLOR_VALUES[current_color_idx]
                flood_fill(canvas, smooth[0], smooth[1], draw_col)
            is_drawing = True
            
        elif is_shape_tool:
            if not is_drawing_shape:
                shape_start_point = smooth
                is_drawing_shape = True
                if len(undo_stack) < MAX_UNDO:
                    undo_stack.append(canvas.copy())
                redo_stack.clear()
            shape_current_point = smooth
            is_drawing = True
            
        else:
            # TOOL_BRUSH or TOOL_NEON
            if not is_drawing:
                if len(undo_stack) < MAX_UNDO:
                    undo_stack.append(canvas.copy())
                redo_stack.clear()
                stroke_points = []
            
            stroke_points.append(smooth)
            draw_col = COLOR_VALUES[current_color_idx]
            
            if len(stroke_points) == 1:
                if current_tool == TOOL_NEON:
                    draw_circle_neon(canvas, smooth, draw_col, brush_size)
                else:
                    cv2.circle(canvas, smooth, brush_size // 2, draw_col, -1)
            elif len(stroke_points) == 2:
                if current_tool == TOOL_NEON:
                    draw_line_neon(canvas, stroke_points[0], stroke_points[1], draw_col, brush_size)
                else:
                    cv2.line(canvas, stroke_points[0], stroke_points[1], draw_col, brush_size, cv2.LINE_AA)
            else:
                p0 = stroke_points[-3]
                p1 = stroke_points[-2]
                p2 = stroke_points[-1]
                mid1 = ((p0[0] + p1[0]) // 2, (p0[1] + p1[1]) // 2)
                mid2 = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
                draw_bezier_curve(canvas, mid1, p1, mid2, draw_col, brush_size, current_tool)
                
            is_drawing = True
    else:
        if is_drawing_shape and shape_start_point is not None and shape_current_point is not None:
            draw_col = COLOR_VALUES[current_color_idx]
            draw_shape_on(canvas, shape_start_point, shape_current_point, draw_col, brush_size, current_tool)
            is_drawing_shape = False
            shape_start_point = None
            shape_current_point = None
            
        prev_point = None
        is_drawing = False
        smooth_points.clear()
        stroke_points = []

    gesture_last = gesture

    # ── Blend canvas & Background modes ──
    if bg_mode == BG_WEBCAM:
        canvas_gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(canvas_gray, 5, 255, cv2.THRESH_BINARY)
        mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        blended_frame = np.where(mask_3ch == 255, canvas, frame)
    else:
        bg_col = (28, 20, 20) if bg_mode == BG_DARK else (250, 244, 244)
        bg = np.zeros_like(frame)
        bg[:, :] = bg_col
        canvas_gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(canvas_gray, 5, 255, cv2.THRESH_BINARY)
        mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        blended_frame = np.where(mask_3ch == 255, canvas, bg)
        
        # Overlay Picture-in-Picture window of webcam frame
        pip_w = 240
        pip_h = 135
        pip_x = fw - pip_w - 20
        pip_y = fh - pip_h - 20
        pip_frame = cv2.resize(frame, (pip_w, pip_h))
        border_col = (0, 229, 255) if bg_mode == BG_DARK else (0, 80, 255)
        cv2.rectangle(blended_frame, (pip_x - 2, pip_y - 2), (pip_x + pip_w + 2, pip_y + pip_h + 2), border_col, 2)
        blended_frame[pip_y:pip_y+pip_h, pip_x:pip_x+pip_w] = pip_frame
        cv2.putText(blended_frame, "WEBCAM FEED", (pip_x, pip_y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, border_col, 1, cv2.LINE_AA)

    frame = blended_frame

    # Draw shape preview if currently dragging shape
    if is_drawing_shape and shape_start_point is not None and shape_current_point is not None:
        draw_col = COLOR_VALUES[current_color_idx]
        draw_shape_on(frame, shape_start_point, shape_current_point, draw_col, brush_size, current_tool)

    # ── Draw toolbar ──
    draw_toolbar(frame, fw)

    # ── Draw cursor ──
    if cx > 0 and cy > 0:
        draw_cursor(frame, cx, cy, gesture)

    # ── Clear progress bar ──
    if clear_start is not None:
        progress = min(1.0, (time.time() - clear_start) / 1.5)
        bar_w    = int(fw * progress)
        cv2.rectangle(frame, (0, TOOLBAR_H + 1), (bar_w, TOOLBAR_H + 4),
                      (80, 100, 255), -1)
        msg = "HOLD TO CLEAR..."
        (tw, _), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        cv2.putText(frame, msg, ((fw - tw) // 2, TOOLBAR_H + 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 100, 255), 1, cv2.LINE_AA)

    # ── Transient Message Notification ──
    if save_msg and time.time() - save_msg_time < 2.0:
        (tw, th), _ = cv2.getTextSize(save_msg, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        bx = (fw - tw) // 2
        by = fh - 40
        age = time.time() - save_msg_time
        banner_alpha = 0.85
        if age > 1.5:
            banner_alpha = 0.85 * (1.0 - (age - 1.5) / 0.5)
            
        overlay = frame.copy()
        cv2.rectangle(overlay, (bx - 12, by - th - 10), (bx + tw + 12, by + 8), (15, 12, 22), -1)
        cv2.rectangle(overlay, (bx - 12, by - th - 10), (bx + tw + 12, by + 8), (0, 229, 255), 1)
        cv2.addWeighted(overlay, banner_alpha, frame, 1 - banner_alpha, 0, frame)
        cv2.putText(frame, save_msg, (bx, by - 1),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 229, 255), 1, cv2.LINE_AA)

    cv2.imshow(WINDOW_NAME, frame)

    # Detect window close button
    if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
        break
          
    key = cv2.waitKey(1) & 0xFF

    if key in (ord('q'), 27):
        break
    elif key == ord('f') or key == ord('F'):
        is_fullscreen = not is_fullscreen
        if is_fullscreen:
            cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        else:
            cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
    elif key == ord('z') or key == ord('Z'):
        trigger_undo()
    elif key == ord('y') or key == ord('Y'):
        trigger_redo()
    elif key == ord('b') or key == ord('B'):
        trigger_bg_toggle()
    elif key == ord('s') or key == ord('S'):
        trigger_save()
    elif key == ord('t') or key == ord('T'):
        # Cycle tools
        tool_keys = [TOOL_BRUSH, TOOL_NEON, TOOL_ERASER, TOOL_LINE, TOOL_RECT, TOOL_CIRCLE, TOOL_BUCKET]
        current_tool = tool_keys[(tool_keys.index(current_tool) + 1) % len(tool_keys)]
        show_message(f"Tool: {current_tool}")
    elif key == ord('c') or key == ord('C'):
        undo_stack.append(canvas.copy())
        redo_stack.clear()
        canvas[:] = 0
        show_message("Canvas Cleared")
    elif key == ord('['):
        brush_size = max(2, brush_size - 2)
    elif key == ord(']'):
        brush_size = min(40, brush_size + 2)
    elif ord('1') <= key <= ord('9'):
        idx = key - ord('1')
        if idx < len(COLORS):
            current_color_idx = idx
            if current_tool == TOOL_ERASER:
                current_tool = TOOL_BRUSH
            show_message(f"Color: {COLOR_NAMES[idx]}")

cap.release()
cv2.destroyAllWindows()
print("Canvas closed.")