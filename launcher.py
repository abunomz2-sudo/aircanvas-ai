"""
Air Drawing — Desktop Launcher Dashboard
A premium sidebar-navigated utility suite to configure and run the gesture drawing app.
Run: python launcher.py
"""

import tkinter as tk
from tkinter import messagebox
import subprocess, sys, os, threading, time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT   = os.path.join(BASE_DIR, "air_drawing.py")
PYTHON   = sys.executable

# ── Colors matching the 9 canvas colors ──────────────────────────────────────
PALETTE = [
    ("Red",    "#FF3C00"),
    ("Orange", "#FF8C00"),
    ("Yellow", "#FFDC00"),
    ("Green",  "#32CD32"),
    ("Cyan",   "#00DCF0"),
    ("Blue",   "#0050FF"),
    ("Purple", "#B400C8"),
    ("Pink",   "#FF00B4"),
    ("White",  "#FFFFFF"),
]

GESTURES = [
    ("☝",  "Index finger",    "Draw freehand / Select / Fill"),
    ("✌",  "Two fingers",     "Hover cursor (Dwell to select)"),
    ("✊",  "Fist",            "Pause tracking cursor"),
    ("👍", "Thumb up",        "Undo last stroke"),
    ("🖐", "All 4 fingers",   "Clear canvas (hold 1.5s)"),
]

KEYS = [
    ("[ / ]",   "Adjust brush thickness down / up"),
    ("Z / Y",   "Undo / Redo drawing strokes"),
    ("B",       "Toggle Background (Webcam / Dark / Light)"),
    ("S",       "Save clean canvas crop to output/"),
    ("T",       "Cycle active drawing tools"),
    ("C",       "Clear active canvas drawing"),
    ("Q / ESC", "Quit drawing viewport"),
]

# ── Minimalist Premium Theme Colors ───────────────────────────────────────────
BG_SIDEBAR = "#08080c"
BG_CONTENT = "#0c0d15"
BG         = "#0c0d15"
PANEL      = "#10111f"
CARD       = "#141525"
ACCENT     = "#00e5ff"
ACCENT2    = "#ff4060"
TEXT       = "#dde8f0"
DIM        = "#556070"
GREEN      = "#00e090"


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Air Drawing Dashboard")
        self.geometry("820x480")
        self.resizable(False, False)
        self.configure(bg=BG)
        
        self._proc    = None
        self._running = False
        self._anim_id = None
        self._dots    = 0
        
        self._pages   = {}
        self._menu_btns = {}
        
        self._build_sidebar()
        self._build_content_area()
        
        self.show_page("control")
        self._check_deps()

    # ── Sidebar Navigation ───────────────────────────────────────────────────
    def _build_sidebar(self):
        self._sidebar = tk.Frame(self, bg=BG_SIDEBAR, width=210)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        
        # Brand Header
        brand_frame = tk.Frame(self._sidebar, bg=BG_SIDEBAR)
        brand_frame.pack(fill="x", padx=16, pady=(24, 20))
        
        tk.Label(brand_frame, text="✏  AIR DRAW", font=("Segoe UI Semibold", 16),
                 bg=BG_SIDEBAR, fg=ACCENT, anchor="w").pack(fill="x")
        tk.Label(brand_frame, text="Creative Gesture Suite", font=("Segoe UI", 8),
                 bg=BG_SIDEBAR, fg=DIM, anchor="w").pack(fill="x")
                 
        # Navigation Menu Buttons
        menu_frame = tk.Frame(self._sidebar, bg=BG_SIDEBAR)
        menu_frame.pack(fill="x", padx=10, pady=10)
        
        MENU_ITEMS = [
            ("control", "🚀  Control Center"),
            ("gestures", "🖐  Gestures Guide"),
            ("keys", "⌨  Keyboard Keys"),
            ("gallery", "📂  Saved Gallery")
        ]
        
        for page_id, label in MENU_ITEMS:
            btn = tk.Button(
                menu_frame, text=label, font=("Segoe UI Semibold", 10),
                bg=BG_SIDEBAR, fg="#8890a5", activebackground="#131424",
                activeforeground=ACCENT, bd=0, padx=12, pady=8, anchor="w",
                cursor="hand2", command=lambda p=page_id: self.show_page(p)
            )
            btn.pack(fill="x", pady=2)
            self._menu_btns[page_id] = btn
            
        # Footer Dependencies Check
        footer = tk.Frame(self._sidebar, bg=BG_SIDEBAR)
        footer.pack(side="bottom", fill="x", padx=16, pady=20)
        
        self._dep_var = tk.StringVar(value="Checking system...")
        self._dep_lbl = tk.Label(footer, textvariable=self._dep_var, font=("Segoe UI", 8),
                                 bg=BG_SIDEBAR, fg=DIM, justify="left", wraplength=170)
        self._dep_lbl.pack(fill="x", anchor="w")

    # ── Content Area & Switching ─────────────────────────────────────────────
    def _build_content_area(self):
        self._content_area = tk.Frame(self, bg=BG_CONTENT)
        self._content_area.pack(side="right", fill="both", expand=True)
        
        # Initialize page frames
        self._pages["control"] = self._create_control_page()
        self._pages["gestures"] = self._create_gestures_page()
        self._pages["keys"] = self._create_keys_page()
        self._pages["gallery"] = self._create_gallery_page()

    def show_page(self, page_id):
        # Hide all page frames
        for frame in self._pages.values():
            frame.pack_forget()
            
        # Reset button highlights
        for pid, btn in self._menu_btns.items():
            if pid == page_id:
                btn.config(bg="#121320", fg=ACCENT)
            else:
                btn.config(bg=BG_SIDEBAR, fg="#8890a5")
                
        # Show page
        self._pages[page_id].pack(fill="both", expand=True, padx=24, pady=24)

    # ── 1. Page: Control Center ──────────────────────────────────────────────
    def _create_control_page(self):
        frame = tk.Frame(self._content_area, bg=BG_CONTENT)
        
        header = tk.Frame(frame, bg=BG_CONTENT)
        header.pack(fill="x", pady=(0, 10))
        
        self._canvas_anim = tk.Canvas(header, width=44, height=44, bg=BG_CONTENT, highlightthickness=0)
        self._canvas_anim.pack(side="left", padx=(0, 12))
        self._draw_hand_icon()
        
        titl = tk.Frame(header, bg=BG_CONTENT)
        titl.pack(side="left")
        tk.Label(titl, text="CONTROL CENTER", font=("Segoe UI Semibold", 18), bg=BG_CONTENT, fg=ACCENT).pack(anchor="w")
        tk.Label(titl, text="Launch the engine & configure canvas palette", font=("Segoe UI", 9), bg=BG_CONTENT, fg=DIM).pack(anchor="w")
        
        self._status_lbl = tk.Label(header, text="● IDLE", font=("Segoe UI Semibold", 10), bg=BG_CONTENT, fg=DIM)
        self._status_lbl.pack(side="right", anchor="n", pady=10)
        
        tk.Canvas(frame, height=1, bg=CARD, highlightthickness=0).pack(fill="x", pady=(0, 12))
        
        # Palette Preview Circular
        palette_section = tk.Frame(frame, bg=BG_CONTENT)
        palette_section.pack(fill="x", pady=(0, 10))
        
        tk.Label(palette_section, text="PALETTE PREVIEW", font=("Segoe UI Semibold", 8), bg=BG_CONTENT, fg=DIM).pack(anchor="w")
        
        palette_canvas = tk.Canvas(palette_section, width=500, height=36, bg=BG_CONTENT, highlightthickness=0)
        palette_canvas.pack(pady=(4, 8), anchor="w")
        
        for i, (name, hex_col) in enumerate(PALETTE):
            cx = 16 + i * 40
            cy = 18
            r = 11
            palette_canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=hex_col, outline="")
            palette_canvas.create_oval(cx - r + 3, cy - r + 3, cx - r + 8, cy - r + 8, fill="#ffffff", outline="")
            palette_canvas.create_text(cx, 33, text=name[:3], fill=DIM, font=("Segoe UI Semibold", 7))
            
        # Action CTA Buttons
        bf = tk.Frame(frame, bg=BG_CONTENT)
        bf.pack(pady=10, anchor="w")
        
        self._launch_btn = tk.Button(
            bf, text="▶  LAUNCH CREATIVE APP",
            font=("Segoe UI Semibold", 10),
            bg=ACCENT, fg="#000010",
            activebackground="#00b8cc",
            bd=0, padx=22, pady=10,
            cursor="hand2",
            command=self._launch)
        self._launch_btn.pack(side="left", padx=(0, 12))

        self._stop_btn = tk.Button(
            bf, text="■  STOP ENGINE",
            font=("Segoe UI Semibold", 10),
            bg=CARD, fg=ACCENT2,
            activebackground="#1e1e30",
            bd=0, padx=22, pady=10,
            cursor="hand2",
            state="disabled",
            command=self._stop)
        self._stop_btn.pack(side="left")
        
        # Log terminal
        tk.Label(frame, text="CONSOLE OUTPUT", font=("Segoe UI Semibold", 8), bg=BG_CONTENT, fg=DIM).pack(anchor="w", pady=(8, 2))
        self._log = tk.Text(frame, height=8, bg=PANEL, fg=DIM, font=("Consolas", 8), bd=0, state="disabled", wrap="word")
        self._log.pack(fill="x")
        
        return frame

    # ── 2. Page: Gestures Guide ──────────────────────────────────────────────
    def _create_gestures_page(self):
        frame = tk.Frame(self._content_area, bg=BG_CONTENT)
        
        tk.Label(frame, text="GESTURES DIRECTORY", font=("Segoe UI Semibold", 18), bg=BG_CONTENT, fg=ACCENT).pack(anchor="w", pady=(0, 2))
        tk.Label(frame, text="Interactive hand pose triggers in the viewport", font=("Segoe UI", 9), bg=BG_CONTENT, fg=DIM).pack(anchor="w", pady=(0, 15))
        
        tk.Canvas(frame, height=1, bg=CARD, highlightthickness=0).pack(fill="x", pady=(0, 12))
        
        gf = tk.Frame(frame, bg=BG_CONTENT)
        gf.pack(fill="both", expand=True)
        
        for emoji, hand, action in GESTURES:
            card = tk.Frame(gf, bg=CARD, padx=16, pady=10)
            card.pack(fill="x", pady=4)
            
            tk.Label(card, text=emoji, font=("Segoe UI Emoji", 14), bg=CARD, width=3).pack(side="left")
            tk.Label(card, text=hand, font=("Segoe UI Semibold", 11), bg=CARD, fg=ACCENT, width=16, anchor="w").pack(side="left", padx=8)
            tk.Label(card, text=action, font=("Segoe UI", 10), bg=CARD, fg=TEXT, anchor="w").pack(side="left")
            
        return frame

    # ── 3. Page: Keyboard Registry ───────────────────────────────────────────
    def _create_keys_page(self):
        frame = tk.Frame(self._content_area, bg=BG_CONTENT)
        
        tk.Label(frame, text="KEYBOARD REGISTRY", font=("Segoe UI Semibold", 18), bg=BG_CONTENT, fg=ACCENT).pack(anchor="w", pady=(0, 2))
        tk.Label(frame, text="System hotkeys and quick canvas settings", font=("Segoe UI", 9), bg=BG_CONTENT, fg=DIM).pack(anchor="w", pady=(0, 15))
        
        tk.Canvas(frame, height=1, bg=CARD, highlightthickness=0).pack(fill="x", pady=(0, 12))
        
        kf = tk.Frame(frame, bg=BG_CONTENT)
        kf.pack(fill="both", expand=True)
        
        for key, desc in KEYS:
            row = tk.Frame(kf, bg=CARD, padx=16, pady=8)
            row.pack(fill="x", pady=3)
            
            key_lbl = tk.Label(row, text=key, font=("Segoe UI Semibold", 10), bg="#1c1d30", fg=ACCENT2, relief="flat", padx=10, pady=2)
            key_lbl.pack(side="left", padx=(0, 16))
            tk.Label(row, text=desc, font=("Segoe UI", 10), bg=CARD, fg=TEXT, anchor="w").pack(side="left")
            
        return frame

    # ── 4. Page: Saved Gallery Explorer ──────────────────────────────────────
    def _create_gallery_page(self):
        frame = tk.Frame(self._content_area, bg=BG_CONTENT)
        
        tk.Label(frame, text="ART GALLERY EXPLORER", font=("Segoe UI Semibold", 18), bg=BG_CONTENT, fg=ACCENT).pack(anchor="w", pady=(0, 2))
        tk.Label(frame, text="Access and view your saved canvas paintings", font=("Segoe UI", 9), bg=BG_CONTENT, fg=DIM).pack(anchor="w", pady=(0, 15))
        
        tk.Canvas(frame, height=1, bg=CARD, highlightthickness=0).pack(fill="x", pady=(0, 12))
        
        gallery_panel = tk.Frame(frame, bg=CARD, padx=24, pady=24)
        gallery_panel.pack(fill="both", expand=True, pady=10)
        
        tk.Label(gallery_panel, text="📂  EXPLORE SAVED PAINTINGS", font=("Segoe UI Semibold", 14), bg=CARD, fg=TEXT).pack(anchor="w", pady=(0, 8))
        tk.Label(gallery_panel, text="Whenever you press 'S' or click 'Save' in the active canvas viewport, the system saves a clean cropped copy of your drawing directly inside the local output/ folder.", font=("Segoe UI", 10), bg=CARD, fg=DIM, justify="left", wraplength=480).pack(anchor="w", pady=(0, 24))
        
        explore_btn = tk.Button(
            gallery_panel, text="OPEN GALLERY FOLDER", font=("Segoe UI Semibold", 11),
            bg=ACCENT, fg="#000010", activebackground="#00b8cc", bd=0, padx=24, pady=12,
            cursor="hand2", command=self._open_gallery
        )
        explore_btn.pack(anchor="w")
        
        return frame

    def _open_gallery(self):
        output_path = os.path.abspath("output")
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        if sys.platform == "win32":
            os.startfile(output_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", output_path])
        else:
            subprocess.Popen(["xdg-open", output_path])

    # ── Animated hand icon (Smooth anti-aliased vector lines) ─────────────────
    def _draw_hand_icon(self):
        c = self._canvas_anim
        c.delete("all")
        
        t = time.time() * 4.0
        
        # Palm base
        c.create_line(22, 28, 22, 40, fill="#00e5ff", width=14, capstyle="round")
        c.create_line(28, 28, 28, 40, fill="#00e5ff", width=14, capstyle="round")
        
        # Thumb
        c.create_line(15, 34, 9, 32, fill="#00e5ff", width=5, capstyle="round")
        
        # 4 Waving Fingers
        f_y1 = [
            int(18 - 5 * abs(math.sin(t))),
            int(10 - 5 * abs(math.sin(t + 0.4))),
            int(8 - 5 * abs(math.sin(t + 0.8))),
            int(13 - 5 * abs(math.sin(t + 1.2)))
        ]
        
        c.create_line(16, f_y1[0], 16, 28, fill="#00e5ff", width=5, capstyle="round")
        c.create_line(22, f_y1[1], 22, 28, fill="#00e5ff", width=5, capstyle="round")
        c.create_line(28, f_y1[2], 28, 28, fill="#00e5ff", width=5, capstyle="round")
        c.create_line(34, f_y1[3], 34, 28, fill="#00e5ff", width=5, capstyle="round")
        
        self._anim_id = self.after(35, self._draw_hand_icon)

    # ── Dependency Checklist ───────────────────────────────────────────────────
    def _check_deps(self):
        def _check():
            missing = []
            for pkg, imp in [("opencv-python", "cv2"),
                              ("mediapipe", "mediapipe"),
                              ("numpy", "numpy")]:
                try:
                    __import__(imp)
                except ImportError:
                    missing.append(pkg)
            if missing:
                msg = f"⚠  Missing: {', '.join(missing)}\n   pip install {' '.join(missing)}"
                col = ACCENT2
            else:
                msg = "✔ opencv-python  ✔ mediapipe  ✔ numpy  - all good!"
                col = GREEN
            self.after(0, lambda: (
                self._dep_var.set(msg),
                self._dep_lbl.configure(fg=col)
            ))
        threading.Thread(target=_check, daemon=True).start()

    # ── Launch / Stop Processes ──────────────────────────────────────────────
    def _launch(self):
        if self._running:
            return
        if not os.path.exists(SCRIPT):
            messagebox.showerror("Missing file",
                f"air_drawing.py not found:\n{SCRIPT}")
            return
        self._running = True
        self._status_lbl.config(text="● RUNNING", fg=GREEN)
        self._launch_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._log_write("Launching air_drawing.py…\n")
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            self._proc = subprocess.Popen(
                [PYTHON, SCRIPT],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, cwd=BASE_DIR,
            )
            for line in self._proc.stdout:
                self._log_write(line)
            self._proc.wait()
        except Exception as e:
            self._log_write(f"Error: {e}\n")
        finally:
            self._running = False
            self.after(0, self._on_stopped)

    def _stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            self._log_write("Stopped by user.\n")

    def _on_stopped(self):
        self._status_lbl.config(text="● IDLE", fg=DIM)
        self._launch_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        self._log_write("Process ended.\n")

    # ── Log Writer ───────────────────────────────────────────────────────────
    def _log_write(self, text):
        def _w():
            self._log.config(state="normal")
            self._log.insert("end", text)
            self._log.see("end")
            self._log.config(state="disabled")
        self.after(0, _w)

    def destroy(self):
        if self._anim_id:
            self.after_cancel(self._anim_id)
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        super().destroy()


if __name__ == "__main__":
    import math
    app = Launcher()
    app.mainloop()
