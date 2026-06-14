# ✏ Air Drawing — Desktop App & Creative Suite

A hand-gesture interactive digital painting application with a high-fidelity macOS-style floating dock, multiple drawing tools, and a sidebar-navigated launcher dashboard.



## 🚀 Quick Start

```bash
# Step 1 — Install dependencies
pip install -r requirements.txt

# Step 2 — Launch the dashboard
python launcher.py
```

---

## 🎨 Core Features

1. **7 Art Tools**:
   - **Brush**: Standard freehand draw.
   - **Neon**: Glow line brush effect with a bright, soft core.
   - **Eraser**: Rub out canvas lines.
   - **Line / Rect / Circle**: Draw precise vector shapes interactively.
   - **Bucket**: Tap to flood-fill enclosed regions.
2. **Bezier Curve Smooth Strokes**: Real-time quadratic spline interpolation for organic, smooth hand-drawn lines.
3. **Pulsating Selection Glows**: Selected color spheres and active tool cards feature breathing halos (`sin(time.time() * 5)`).
4. **Solid Backgrounds & PiP**: Paint on dark (`#1c1414`) or light (`#faf4f4`) backdrops with an overlay webcam guidance feed in the corner.
5. **Artwork Exporting**: Crop and save clean PNG drawings instantly to the `output/` folder.
6. **Sidebar Navigation Dashboard Launcher**:
   - 🚀 **Control Center**: Waving hand canvas, app launch/stop CTA buttons, circular color preview, and log panel.
   - 🖐 **Gestures Guide**: A clean card directory for hand gestures.
   - ⌨ **Keyboard Keys**: An organized keyboard shortcuts registry.
   - 📂 **Saved Gallery**: A direct utility panel to open the local `output/` directory in Windows Explorer.

---

## 📁 Files

| File | What it is |
|------|-----------|
| `launcher.py` | Polish Tkinter Sidebar Dashboard GUI |
| `air_drawing.py` | CV/MediaPipe Interactive Engine |
| `requirements.txt` | Dependency requirements |
| `output/` | Directory where saved drawings are exported |

---

## 🖐 Hand Gestures

| Gesture | Action |
|---------|--------|
| ☝ Index finger | DRAW freehand / Drag shapes / FILL bucket |
| ✌ Two fingers | HOVER cursor (dwell 0.5s on toolbar buttons to click) |
| ✊ Fist | PAUSE cursor tracking |
| 👍 Thumb up | UNDO last stroke |
| 🖐 All 4 fingers (hold 1.5s) | CLEAR canvas |

---

## ⌨ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `[` / `]` | Adjust brush thickness down / up |
| `Z` / `Y` | Undo / Redo last stroke |
| `B` | Toggle Background Mode (Webcam ➔ Dark Solid ➔ Light Solid) |
| `S` | Save cropped drawing to `output/` |
| `T` | Cycle through drawing tools |
| `C` | Clear canvas drawing |
| `1`–`9` | Quick color swatch select |
| `F` | Toggle window fullscreen |
| `Q` / `ESC` | Quit application |
