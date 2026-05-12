import mediapipe as mp
import cv2
import numpy as np
import time
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
    "Eraser": (0,    0,    0),
}
COLOR_NAMES  = list(COLORS.keys())
COLOR_VALUES = list(COLORS.values())

# ─── State ───────────────────────────────────────────────────
current_color_idx  = 0
brush_size         = 8
is_drawing         = False
prev_point         = None
smooth_points      = deque(maxlen=6)
undo_stack         = []
MAX_UNDO           = 20

MODE_DRAW   = "DRAW"
MODE_ERASE  = "ERASE"
current_mode = MODE_DRAW

# Fullscreen state
is_fullscreen = False

# ─── Landmark IDs ────────────────────────────────────────────
INDEX_TIP  = 8;  INDEX_PIP  = 6
MIDDLE_TIP = 12; MIDDLE_PIP = 10
RING_TIP   = 16; RING_PIP   = 14
PINKY_TIP  = 20; PINKY_PIP  = 18
THUMB_TIP  = 4;  THUMB_IP   = 3

# ─── Gesture Detection ───────────────────────────────────────
def finger_up(lm, tip, pip, is_thumb=False, handedness="Right"):
    if is_thumb:
        return lm[tip].x < lm[pip].x if handedness == "Right" else lm[tip].x > lm[pip].x
    return lm[tip].y < lm[pip].y

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

# ─── UI Constants ────────────────────────────────────────────
TOOLBAR_H   = 72
SWATCH_W    = 48
SWATCH_GAP  = 5
SWATCH_Y1   = 12
SWATCH_Y2   = 60
SWATCH_X0   = 14

# ─── UI Drawing ──────────────────────────────────────────────
def draw_pill(frame, x1, y1, x2, y2, color, radius=10):
    """Draw a rounded rectangle (pill/swatch shape)."""
    cv2.rectangle(frame, (x1 + radius, y1), (x2 - radius, y2), color, -1)
    cv2.rectangle(frame, (x1, y1 + radius), (x2, y2 - radius), color, -1)
    cv2.circle(frame, (x1 + radius, y1 + radius), radius, color, -1)
    cv2.circle(frame, (x2 - radius, y1 + radius), radius, color, -1)
    cv2.circle(frame, (x1 + radius, y2 - radius), radius, color, -1)
    cv2.circle(frame, (x2 - radius, y2 - radius), radius, color, -1)

def draw_toolbar(frame, w):
    # Frosted glass background panel
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, TOOLBAR_H), (12, 12, 18), -1)
    alpha = 0.82
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    # Subtle bottom border line
    cv2.line(frame, (0, TOOLBAR_H), (w, TOOLBAR_H), (55, 50, 65), 1)

    # ── Color swatches ──
    for i, (name, bgr) in enumerate(COLORS.items()):
        x1 = SWATCH_X0 + i * (SWATCH_W + SWATCH_GAP)
        x2 = x1 + SWATCH_W
        y1, y2 = SWATCH_Y1, SWATCH_Y2
        cx_sw = (x1 + x2) // 2

        selected = (i == current_color_idx)

        # Glow ring behind selected swatch
        if selected:
            glow_col = bgr if name != "Eraser" else (100, 100, 110)
            for t in range(3, 0, -1):
                gc = tuple(max(0, int(c * 0.3)) for c in glow_col)
                draw_pill(frame, x1 - t - 2, y1 - t - 2, x2 + t + 2, y2 + t + 2, gc, radius=11)
            cv2.rectangle(frame, (x1 - 3, y1 - 3), (x2 + 3, y2 + 3), (220, 215, 230), 2)

        if name == "Eraser":
            draw_pill(frame, x1, y1, x2, y2, (32, 30, 42), radius=9)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (75, 70, 90), 1)
            # Eraser icon
            ex, ey = cx_sw, (y1 + y2) // 2
            cv2.rectangle(frame, (ex - 10, ey - 7), (ex + 10, ey + 7), (160, 150, 175), -1)
            cv2.rectangle(frame, (ex - 10, ey - 7), (ex - 1,  ey + 7), (100,  90, 115), -1)
        else:
            draw_pill(frame, x1, y1, x2, y2, bgr, radius=9)
            # Shine highlight strip
            shine = tuple(min(255, c + 70) for c in bgr)
            draw_pill(frame, x1 + 3, y1 + 3, x2 - 3, y1 + 16, shine, radius=6)

        # Active dot indicator
        if selected:
            cv2.circle(frame, (cx_sw, y2 + 8), 3, (220, 215, 230), -1)

    # ── Brush size section ──
    bx = SWATCH_X0 + len(COLORS) * (SWATCH_W + SWATCH_GAP) + 18
    by_label = 24
    by_bar1  = 32
    by_bar2  = 46

    cv2.putText(frame, "SIZE", (bx, by_label),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (110, 100, 130), 1, cv2.LINE_AA)

    bar_w = 110
    # Track background
    cv2.rectangle(frame, (bx, by_bar1), (bx + bar_w, by_bar2), (30, 28, 40), -1)
    cv2.rectangle(frame, (bx, by_bar1), (bx + bar_w, by_bar2), (55, 50, 70), 1)

    # Track fill
    fill_w = int(bar_w * (brush_size / 40))
    fill_col = COLOR_VALUES[current_color_idx] if COLOR_NAMES[current_color_idx] != "Eraser" else (130, 120, 145)
    cv2.rectangle(frame, (bx, by_bar1), (bx + fill_w, by_bar2), fill_col, -1)

    # Thumb knob
    thumb_x = bx + fill_w
    cv2.circle(frame, (thumb_x, (by_bar1 + by_bar2) // 2), 8, (220, 215, 235), -1)
    cv2.circle(frame, (thumb_x, (by_bar1 + by_bar2) // 2), 8, (160, 155, 175), 1)

    cv2.putText(frame, str(brush_size), (bx + bar_w + 8, by_bar2 - 1),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (170, 160, 190), 1, cv2.LINE_AA)

    # ── Mode badge ──
    mode_colors = {
        MODE_DRAW:  ((20, 200, 120), (10, 100, 60)),
        MODE_ERASE: ((60, 130, 255), (30,  65, 130)),
    }
    badge_col, badge_dark = mode_colors.get(current_mode, ((180, 180, 180), (80, 80, 80)))
    bm_x = bx
    bm_y = 58
    label = current_mode
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
    cv2.rectangle(frame, (bm_x - 4, bm_y - th - 4), (bm_x + tw + 4, bm_y + 2),
                  badge_dark, -1)
    cv2.rectangle(frame, (bm_x - 4, bm_y - th - 4), (bm_x + tw + 4, bm_y + 2),
                  badge_col, 1)
    cv2.putText(frame, label, (bm_x, bm_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, badge_col, 1, cv2.LINE_AA)

    # ── Gesture hints (right side) ──
    hint_x = w - 300
    hints = [
        ("index  DRAW",   (0, 210, 140)),
        ("peace  HOVER",  (180, 170, 200)),
        ("thumb  UNDO",   (255, 180,  60)),
        ("fist+  CLEAR",  (100, 140, 255)),
    ]
    for j, (txt, col) in enumerate(hints):
        hx = hint_x + (j % 2) * 150
        hy = 28 if j < 2 else 56
        cv2.putText(frame, txt, (hx, hy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, col, 1, cv2.LINE_AA)

    # ── Fullscreen hint ──
    cv2.putText(frame, "F  fullscreen   Q  quit   Z  undo   C  clear",
                (hint_x, TOOLBAR_H - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.32, (70, 65, 85), 1, cv2.LINE_AA)


def draw_cursor(frame, cx, cy, gesture):
    if gesture == "DRAW":
        col = COLOR_VALUES[current_color_idx]
        # Outer glow ring
        glow = tuple(max(0, c // 3) for c in col)
        cv2.circle(frame, (cx, cy), brush_size + 6, glow, 2, cv2.LINE_AA)
        # Brush preview dot
        cv2.circle(frame, (cx, cy), brush_size, col, -1, cv2.LINE_AA)
        # Inner highlight
        hi = tuple(min(255, c + 80) for c in col)
        cv2.circle(frame, (cx - brush_size//4, cy - brush_size//4),
                   max(2, brush_size//3), hi, -1, cv2.LINE_AA)
    elif gesture == "HOVER":
        cv2.circle(frame, (cx, cy), 18, (160, 150, 180), 1, cv2.LINE_AA)
        cv2.line(frame, (cx-22, cy), (cx+22, cy), (160, 150, 180), 1)
        cv2.line(frame, (cx, cy-22), (cx, cy+22), (160, 150, 180), 1)
        cv2.circle(frame, (cx, cy), 3, (160, 150, 180), -1)
    elif gesture == "FIST":
        cv2.circle(frame, (cx, cy), 12, (70, 65, 80), 1, cv2.LINE_AA)
    elif gesture == "UNDO":
        # Arrow arc suggestion
        cv2.putText(frame, "UNDO", (cx + 12, cy - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 200, 60), 2, cv2.LINE_AA)


def check_color_select(cx, cy):
    if cy > TOOLBAR_H:
        return None
    for i in range(len(COLORS)):
        x1 = SWATCH_X0 + i * (SWATCH_W + SWATCH_GAP)
        x2 = x1 + SWATCH_W
        if x1 <= cx <= x2:
            return i
    return None

def check_brush_size(cx, cy):
    bx = SWATCH_X0 + len(COLORS) * (SWATCH_W + SWATCH_GAP) + 18
    bar_w = 110
    if cy <= TOOLBAR_H and bx <= cx <= bx + bar_w:
        return max(2, min(40, int((cx - bx) / bar_w * 40)))
    return None

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

print("🎨  Air Drawing  —  redesigned UI")
print("   ☝  one finger  = DRAW")
print("   ✌  two fingers = HOVER")
print("   👍 thumb up    = UNDO")
print("   ✋ all fingers = CLEAR (hold 1.5 s)")
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
        sel = check_color_select(cx, cy)
        if sel is not None:
            current_color_idx = sel
            current_mode = MODE_ERASE if COLOR_NAMES[sel] == "Eraser" else MODE_DRAW
        bs = check_brush_size(cx, cy)
        if bs is not None:
            brush_size = bs

    if gesture == "CLEAR":
        if clear_start is None:
            clear_start = time.time()
        elif time.time() - clear_start > 1.5:
            undo_stack.append(canvas.copy())
            canvas[:] = 0
            clear_start = None
    else:
        clear_start = None

    if gesture == "UNDO" and gesture_last != "UNDO":
        if time.time() - undo_last_time > 0.5:
            if undo_stack:
                canvas = undo_stack.pop()
            undo_last_time = time.time()

    if gesture == "DRAW" and cy > TOOLBAR_H and cx > 0:
        smooth = get_smooth_point((cx, cy))
        if current_mode == MODE_ERASE:
            cv2.circle(canvas, smooth, brush_size * 3, (0, 0, 0), -1)
        else:
            draw_col = COLOR_VALUES[current_color_idx]
            if prev_point is not None and is_drawing:
                cv2.line(canvas, prev_point, smooth, draw_col, brush_size, cv2.LINE_AA)
            else:
                if len(undo_stack) < MAX_UNDO:
                    undo_stack.append(canvas.copy())
                cv2.circle(canvas, smooth, brush_size // 2, draw_col, -1)
        prev_point = smooth
        is_drawing = True
    else:
        prev_point = None
        is_drawing = False
        smooth_points.clear()

    gesture_last = gesture

    # ── Blend canvas ──
    canvas_gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(canvas_gray, 5, 255, cv2.THRESH_BINARY)
    mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    frame = np.where(mask_3ch == 255, canvas, frame)

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

    cv2.imshow(WINDOW_NAME, frame)

# Detect window close button
    if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
        break
          
    key = cv2.waitKey(1) & 0xFF

    if key in (ord('q'), 27):
        break
    elif key == ord('f') or key == ord('F'):
        # Toggle fullscreen
        is_fullscreen = not is_fullscreen
        if is_fullscreen:
            cv2.setWindowProperty(WINDOW_NAME,
                                  cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_FULLSCREEN)
        else:
            cv2.setWindowProperty(WINDOW_NAME,
                                  cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_NORMAL)
    elif key == ord('z'):
        if undo_stack:
            canvas = undo_stack.pop()
    elif key == ord('c'):
        undo_stack.append(canvas.copy())
        canvas[:] = 0
    elif key == ord('['):
        brush_size = max(2, brush_size - 2)
    elif key == ord(']'):
        brush_size = min(40, brush_size + 2)
    elif ord('1') <= key <= ord('9'):
        idx = key - ord('1')
        if idx < len(COLORS):
            current_color_idx = idx
            current_mode = MODE_ERASE if COLOR_NAMES[idx] == "Eraser" else MODE_DRAW

cap.release()
cv2.destroyAllWindows()
print("🎨  Air Drawing closed.")