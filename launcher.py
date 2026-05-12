"""
Air Drawing — Desktop Launcher
Wraps the user's air_drawing.py with a polished GUI.
Run: python launcher.py
"""

import tkinter as tk
from tkinter import messagebox
import subprocess, sys, os, threading, time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT   = os.path.join(BASE_DIR, "air_drawing.py")
PYTHON   = sys.executable

# ── Exact colors from user's air_drawing.py ──────────────────────────────────
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
    ("Eraser", "#222233"),
]

GESTURES = [
    ("☝",  "Index finger",    "DRAW on canvas"),
    ("✌",  "Two fingers",     "HOVER / stop drawing"),
    ("✊",  "Fist",            "Pause pen"),
    ("👍", "Thumb up",        "UNDO last stroke"),
    ("🖐", "All 4 fingers",   "CLEAR canvas (hold 1.5s)"),
]

KEYS = [
    ("[  /  ]",  "Brush size ↓ ↑"),
    ("Z",        "Undo"),
    ("C",        "Clear canvas"),
    ("1 – 9",    "Quick color select"),
    ("Q / ESC",  "Quit"),
]

# ── Theme ─────────────────────────────────────────────────────────────────────
BG      = "#080810"
PANEL   = "#10101c"
CARD    = "#16162a"
ACCENT  = "#00e5ff"
ACCENT2 = "#ff4060"
TEXT    = "#dde8f0"
DIM     = "#556070"
GREEN   = "#00e090"
MONO    = ("Consolas", 10)
MONO_SM = ("Consolas",  8)
TITLE_F = ("Consolas", 20, "bold")
SUB_F   = ("Consolas",  9)


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Air Drawing")
        self.geometry("560x720")
        self.resizable(False, False)
        self.configure(bg=BG)
        self._proc    = None
        self._running = False
        self._anim_id = None
        self._dots    = 0
        self._build()
        self._check_deps()

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build(self):
        # ── Animated header ───────────────────────────────────────────────────
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=28, pady=(24, 0))

        self._canvas_anim = tk.Canvas(top, width=48, height=48,
                                       bg=BG, highlightthickness=0)
        self._canvas_anim.pack(side="left", padx=(0,14))
        self._draw_hand_icon()

        titl = tk.Frame(top, bg=BG)
        titl.pack(side="left")
        tk.Label(titl, text="AIR DRAWING", font=TITLE_F,
                 bg=BG, fg=ACCENT).pack(anchor="w")
        tk.Label(titl, text="hand-gesture canvas  ·  your code",
                 font=SUB_F, bg=BG, fg=DIM).pack(anchor="w")

        self._status_lbl = tk.Label(top, text="● IDLE",
                                     font=("Consolas", 9, "bold"),
                                     bg=BG, fg=DIM)
        self._status_lbl.pack(side="right", anchor="ne")

        # Accent line
        tk.Canvas(self, height=2, bg=ACCENT,
                  highlightthickness=0).pack(fill="x", padx=28, pady=12)

        # ── Palette preview ───────────────────────────────────────────────────
        self._section("COLOR PALETTE")
        pal = tk.Frame(self, bg=BG)
        pal.pack(padx=28, pady=(4,14), anchor="w")
        for name, hex_col in PALETTE:
            cell = tk.Frame(pal, bg=CARD, padx=2, pady=2)
            cell.pack(side="left", padx=2)
            swatch = tk.Frame(cell, bg=hex_col, width=38, height=34)
            swatch.pack()
            swatch.pack_propagate(False)
            if name == "Eraser":
                tk.Label(swatch, text="ER", bg=hex_col,
                         fg="#888", font=MONO_SM).place(relx=.5,rely=.5,anchor="c")
            lbl_fg = "#333" if name == "White" else TEXT
            tk.Label(cell, text=name[:3], bg=CARD,
                     fg=DIM, font=("Consolas",7)).pack()

        # ── Gestures ──────────────────────────────────────────────────────────
        self._section("GESTURES")
        gf = tk.Frame(self, bg=CARD, bd=0)
        gf.pack(fill="x", padx=28, pady=(4,14))
        for emoji, hand, action in GESTURES:
            row = tk.Frame(gf, bg=CARD)
            row.pack(fill="x", padx=12, pady=4)
            tk.Label(row, text=emoji, font=("Segoe UI Emoji",16),
                     bg=CARD, width=3).pack(side="left")
            tk.Label(row, text=hand, font=("Consolas",10,"bold"),
                     bg=CARD, fg=ACCENT, width=16, anchor="w").pack(side="left")
            tk.Label(row, text=action, font=MONO,
                     bg=CARD, fg=TEXT, anchor="w").pack(side="left")

        # ── Keyboard shortcuts ────────────────────────────────────────────────
        self._section("KEYBOARD SHORTCUTS")
        kf = tk.Frame(self, bg=CARD)
        kf.pack(fill="x", padx=28, pady=(4,14))
        for key, desc in KEYS:
            row = tk.Frame(kf, bg=CARD)
            row.pack(fill="x", padx=12, pady=3)
            key_lbl = tk.Label(row, text=key, font=("Consolas",10,"bold"),
                                bg="#1e1e30", fg=ACCENT2,
                                width=10, relief="flat", padx=4)
            key_lbl.pack(side="left", padx=(0,10))
            tk.Label(row, text=desc, font=MONO,
                     bg=CARD, fg=TEXT, anchor="w").pack(side="left")

        # ── Dep status ────────────────────────────────────────────────────────
        tk.Canvas(self, height=1, bg=DIM,
                  highlightthickness=0).pack(fill="x", padx=28, pady=8)

        self._dep_var = tk.StringVar(value="Checking dependencies…")
        tk.Label(self, textvariable=self._dep_var, font=MONO_SM,
                 bg=BG, fg=DIM, justify="left",
                 wraplength=500).pack(padx=28, anchor="w")

        # ── Log ───────────────────────────────────────────────────────────────
        self._log = tk.Text(self, height=4, bg=PANEL, fg=DIM,
                             font=("Consolas",8), bd=0,
                             state="disabled", wrap="word")
        self._log.pack(fill="x", padx=28, pady=(6,0))

        # ── Buttons ───────────────────────────────────────────────────────────
        bf = tk.Frame(self, bg=BG)
        bf.pack(pady=14)

        self._launch_btn = tk.Button(
            bf, text="▶  LAUNCH APP",
            font=("Consolas",12,"bold"),
            bg=ACCENT, fg="#000010",
            activebackground="#00b8cc",
            bd=0, padx=26, pady=10,
            cursor="hand2",
            command=self._launch)
        self._launch_btn.pack(side="left", padx=8)

        self._stop_btn = tk.Button(
            bf, text="■  STOP",
            font=("Consolas",12,"bold"),
            bg=CARD, fg=ACCENT2,
            activebackground="#1e1e30",
            bd=0, padx=26, pady=10,
            cursor="hand2",
            state="disabled",
            command=self._stop)
        self._stop_btn.pack(side="left", padx=8)

        self._log_write("Ready. Press ▶ LAUNCH APP to start your Air Drawing.\n")

    def _section(self, title):
        tk.Label(self, text=title, font=("Consolas",8,"bold"),
                 bg=BG, fg=DIM).pack(anchor="w", padx=28)

    # ── Animated hand icon ────────────────────────────────────────────────────
    def _draw_hand_icon(self):
        c = self._canvas_anim
        c.delete("all")
        # Palm
        c.create_rectangle(12,28,38,46, fill="#00e5ff", outline="")
        # Fingers (animated wave)
        t   = time.time() * 3
        tips = [
            (16, int(18 - 4*abs(__import__('math').sin(t+0.0)))),
            (22, int(10 - 4*abs(__import__('math').sin(t+0.4)))),
            (28, int( 8 - 4*abs(__import__('math').sin(t+0.8)))),
            (34, int(12 - 4*abs(__import__('math').sin(t+1.2)))),
        ]
        for fx, fy in tips:
            c.create_rectangle(fx-3, fy, fx+3, 30, fill="#00e5ff", outline="")
        # Thumb
        c.create_rectangle(4, 30, 14, 42, fill="#00e5ff", outline="")
        self._anim_id = self.after(50, self._draw_hand_icon)

    # ── Dep check ─────────────────────────────────────────────────────────────
    def _check_deps(self):
        def _check():
            missing = []
            for pkg, imp in [("opencv-python","cv2"),
                              ("mediapipe","mediapipe"),
                              ("numpy","numpy")]:
                try:
                    __import__(imp)
                except ImportError:
                    missing.append(pkg)
            if missing:
                msg = f"⚠  Missing: {', '.join(missing)}\n   pip install {' '.join(missing)}"
                col = ACCENT2
            else:
                msg = "✔  opencv-python  ✔  mediapipe  ✔  numpy  — all good!"
                col = GREEN
            self.after(0, lambda: (
                self._dep_var.set(msg),
                self.nametowidget(str(self._dep_var)).configure(fg=col)
                if False else None   # label update via StringVar
            ))
            # update label color directly
            for w in self.winfo_children():
                self._set_dep_color(w, col)
        threading.Thread(target=_check, daemon=True).start()

    def _set_dep_color(self, widget, col):
        try:
            if isinstance(widget, tk.Label) and \
               widget.cget("textvariable") == str(self._dep_var):
                widget.config(fg=col)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._set_dep_color(child, col)

    # ── Launch / Stop ─────────────────────────────────────────────────────────
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

    # ── Log helper ────────────────────────────────────────────────────────────
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
    app = Launcher()
    app.mainloop()
