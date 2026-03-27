#!/usr/bin/env python3
"""
EMIT Converter — GUI
Cross-platform (macOS + Windows)
Wraps emit_convert.py logic with a Tkinter interface.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext

# Ensure emit_convert is importable from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Colours & fonts
# ---------------------------------------------------------------------------

BG        = "#1e1e2e"
SURFACE   = "#2a2a3e"
ACCENT    = "#7c6af7"
ACCENT_HV = "#9b8fff"
TEXT      = "#e0e0f0"
SUBTEXT   = "#888aaa"
SUCCESS   = "#4ade80"
WARNING   = "#facc15"
ERROR     = "#f87171"
BORDER    = "#3a3a55"

FONT_BODY  = ("Helvetica", 12)
FONT_SMALL = ("Helvetica", 10)
FONT_MONO  = ("Courier", 10)
FONT_HEAD  = ("Helvetica", 18, "bold")
FONT_LABEL = ("Helvetica", 11)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def styled_button(parent, text, command, accent=True, **kw):
    bg = ACCENT if accent else SURFACE
    fg = "#ffffff" if accent else TEXT
    btn = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=fg, activebackground=ACCENT_HV, activeforeground="#fff",
        relief="flat", bd=0, padx=16, pady=8,
        font=FONT_BODY, cursor="hand2", **kw
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=ACCENT_HV if accent else BORDER))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    return btn


def labeled_row(parent, label_text, widget_factory, pady=6):
    row = tk.Frame(parent, bg=BG)
    row.pack(fill="x", pady=pady)
    tk.Label(row, text=label_text, bg=BG, fg=SUBTEXT, font=FONT_LABEL, width=14, anchor="w").pack(side="left")
    widget = widget_factory(row)
    widget.pack(side="left", fill="x", expand=True, padx=(8, 0))
    return widget


def entry_with_browse(parent, browse_fn, is_dir=False):
    frame = tk.Frame(parent, bg=BG)
    var = tk.StringVar()
    e = tk.Entry(frame, textvariable=var, bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=FONT_BODY, bd=0)
    e.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 6))
    btn = styled_button(frame, "Browse", browse_fn, accent=False)
    btn.pack(side="right")
    frame.var = var
    return frame


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

class EMITConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EMIT Converter")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(720, 600)

        self._input_files = []
        self._running = False

        self._build_ui()
        self._center_window(780, 680)

    def _center_window(self, w, h):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=ACCENT, pady=18)
        hdr.pack(fill="x")
        tk.Label(hdr, text="EMIT Converter", bg=ACCENT, fg="#fff", font=FONT_HEAD).pack()
        tk.Label(hdr, text=".nc  →  ENVI  |  GeoTIFF", bg=ACCENT, fg="#ddd", font=FONT_SMALL).pack()

        # Body
        body = tk.Frame(self, bg=BG, padx=28, pady=20)
        body.pack(fill="both", expand=True)

        # --- Input files ---
        tk.Label(body, text="Input Files", bg=BG, fg=TEXT, font=("Helvetica", 12, "bold")).pack(anchor="w")

        inp_frame = tk.Frame(body, bg=SURFACE, relief="flat", bd=0)
        inp_frame.pack(fill="x", pady=(4, 12))

        btn_row = tk.Frame(inp_frame, bg=SURFACE)
        btn_row.pack(fill="x", padx=10, pady=8)
        styled_button(btn_row, "Add Files", self._add_files, accent=True).pack(side="left", padx=(0, 8))
        styled_button(btn_row, "Add Folder", self._add_folder, accent=False).pack(side="left", padx=(0, 8))
        styled_button(btn_row, "Clear", self._clear_files, accent=False).pack(side="left")

        self._file_list_label = tk.Label(inp_frame, text="No files selected", bg=SURFACE,
                                          fg=SUBTEXT, font=FONT_SMALL, anchor="w", wraplength=660, justify="left")
        self._file_list_label.pack(fill="x", padx=10, pady=(0, 8))

        # --- Output directory ---
        tk.Label(body, text="Output Directory", bg=BG, fg=TEXT, font=("Helvetica", 12, "bold")).pack(anchor="w")
        out_frame = tk.Frame(body, bg=SURFACE, pady=8, padx=10)
        out_frame.pack(fill="x", pady=(4, 16))

        self._out_var = tk.StringVar()
        out_entry = tk.Entry(out_frame, textvariable=self._out_var, bg=SURFACE, fg=TEXT,
                             insertbackground=TEXT, relief="flat", font=FONT_BODY, bd=0)
        out_entry.pack(side="left", fill="x", expand=True, ipady=5)
        styled_button(out_frame, "Browse", self._browse_output, accent=False).pack(side="right")

        # --- Options ---
        tk.Label(body, text="Options", bg=BG, fg=TEXT, font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(4, 0))
        opts = tk.Frame(body, bg=BG)
        opts.pack(fill="x", pady=(4, 16))

        # Format
        fmt_frame = tk.Frame(opts, bg=BG)
        fmt_frame.pack(side="left", padx=(0, 24))
        tk.Label(fmt_frame, text="Format", bg=BG, fg=SUBTEXT, font=FONT_LABEL).pack(anchor="w")
        self._fmt_var = tk.StringVar(value="both")
        for val, lbl in [("both", "Both"), ("envi", "ENVI only"), ("geotiff", "GeoTIFF only")]:
            rb = tk.Radiobutton(fmt_frame, text=lbl, variable=self._fmt_var, value=val,
                                bg=BG, fg=TEXT, selectcolor=ACCENT, activebackground=BG,
                                activeforeground=TEXT, font=FONT_SMALL)
            rb.pack(anchor="w")

        # Interleave
        il_frame = tk.Frame(opts, bg=BG)
        il_frame.pack(side="left", padx=(0, 24))
        tk.Label(il_frame, text="ENVI Interleave", bg=BG, fg=SUBTEXT, font=FONT_LABEL).pack(anchor="w")
        self._il_var = tk.StringVar(value="BIL")
        for val in ["BIL", "BIP", "BSQ"]:
            rb = tk.Radiobutton(il_frame, text=val, variable=self._il_var, value=val,
                                bg=BG, fg=TEXT, selectcolor=ACCENT, activebackground=BG,
                                activeforeground=TEXT, font=FONT_SMALL)
            rb.pack(anchor="w")

        # Flags
        flag_frame = tk.Frame(opts, bg=BG)
        flag_frame.pack(side="left")
        tk.Label(flag_frame, text="Flags", bg=BG, fg=SUBTEXT, font=FONT_LABEL).pack(anchor="w")
        self._ortho_var = tk.BooleanVar(value=True)
        self._overwrite_var = tk.BooleanVar(value=False)
        tk.Checkbutton(flag_frame, text="Orthorectify (GLT)", variable=self._ortho_var,
                       bg=BG, fg=TEXT, selectcolor=ACCENT, activebackground=BG,
                       activeforeground=TEXT, font=FONT_SMALL).pack(anchor="w")
        tk.Checkbutton(flag_frame, text="Overwrite existing", variable=self._overwrite_var,
                       bg=BG, fg=TEXT, selectcolor=ACCENT, activebackground=BG,
                       activeforeground=TEXT, font=FONT_SMALL).pack(anchor="w")

        # --- Progress bar ---
        self._progress = ttk.Progressbar(body, mode="indeterminate", length=400)
        self._progress.pack(fill="x", pady=(0, 8))

        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("TProgressbar", troughcolor=SURFACE, background=ACCENT, thickness=6)

        # --- Run button ---
        self._run_btn = styled_button(body, "Convert", self._run, accent=True)
        self._run_btn.pack(fill="x", ipady=4, pady=(0, 12))

        # --- Log ---
        tk.Label(body, text="Log", bg=BG, fg=SUBTEXT, font=FONT_LABEL).pack(anchor="w")
        self._log = scrolledtext.ScrolledText(body, bg=SURFACE, fg=TEXT, font=FONT_MONO,
                                               relief="flat", bd=0, height=10,
                                               insertbackground=TEXT, state="disabled")
        self._log.pack(fill="both", expand=True)
        self._log.tag_config("ok",   foreground=SUCCESS)
        self._log.tag_config("warn", foreground=WARNING)
        self._log.tag_config("err",  foreground=ERROR)
        self._log.tag_config("info", foreground=SUBTEXT)

    # ------------------------------------------------------------------
    # File selection
    # ------------------------------------------------------------------

    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="Select EMIT .nc files",
            filetypes=[("NetCDF files", "*.nc"), ("All files", "*.*")]
        )
        for f in files:
            if f not in self._input_files:
                self._input_files.append(f)
        self._refresh_file_label()

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Select folder containing .nc files")
        if folder:
            found = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".nc")]
            for f in found:
                if f not in self._input_files:
                    self._input_files.append(f)
            self._refresh_file_label()

    def _clear_files(self):
        self._input_files = []
        self._refresh_file_label()

    def _refresh_file_label(self):
        n = len(self._input_files)
        if n == 0:
            self._file_list_label.config(text="No files selected", fg=SUBTEXT)
        elif n <= 3:
            names = "\n".join(os.path.basename(f) for f in self._input_files)
            self._file_list_label.config(text=names, fg=TEXT)
        else:
            names = ", ".join(os.path.basename(f) for f in self._input_files[:2])
            self._file_list_label.config(text=f"{names} … and {n - 2} more", fg=TEXT)

    def _browse_output(self):
        folder = filedialog.askdirectory(title="Select output directory")
        if folder:
            self._out_var.set(folder)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log_write(self, msg: str, tag: str = ""):
        self._log.config(state="normal")
        self._log.insert("end", msg + "\n", tag)
        self._log.see("end")
        self._log.config(state="disabled")

    def _log_info(self, msg):    self._log_write(f"[INFO]  {msg}", "info")
    def _log_ok(self, msg):      self._log_write(f"[OK]    {msg}", "ok")
    def _log_warn(self, msg):    self._log_write(f"[WARN]  {msg}", "warn")
    def _log_error(self, msg):   self._log_write(f"[ERROR] {msg}", "err")

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _run(self):
        if self._running:
            return

        if not self._input_files:
            self._log_error("No input files selected.")
            return

        out_dir = self._out_var.get().strip()
        if not out_dir:
            self._log_error("No output directory selected.")
            return

        self._running = True
        self._run_btn.config(state="disabled", text="Converting…")
        self._progress.start(12)

        thread = threading.Thread(target=self._convert_all, args=(out_dir,), daemon=True)
        thread.start()

    def _convert_all(self, out_dir: str):
        try:
            import emit_convert as ec
        except ImportError as e:
            self.after(0, self._log_error, f"Could not import emit_convert: {e}")
            self.after(0, self._finish)
            return

        fmt        = self._fmt_var.get()
        interleave = self._il_var.get()
        ortho      = self._ortho_var.get()
        overwrite  = self._overwrite_var.get()
        total      = len(self._input_files)

        for i, fp in enumerate(self._input_files, 1):
            name = os.path.basename(fp)
            self.after(0, self._log_info, f"({i}/{total}) Loading {name}")

            try:
                ds   = ec.emit_xarray(fp, ortho=ortho)
                stem = os.path.splitext(name)[0]

                if fmt in ("envi", "both"):
                    envi_dir = os.path.join(out_dir, "envi") if fmt == "both" else out_dir
                    ec.write_envi(ds, envi_dir, stem=stem, interleave=interleave, overwrite=overwrite)
                    self.after(0, self._log_ok, f"ENVI → {envi_dir}/{stem}.img")

                if fmt in ("geotiff", "both"):
                    tif_dir = os.path.join(out_dir, "geotiff") if fmt == "both" else out_dir
                    ec.write_geotiff(ds, tif_dir, stem=stem, overwrite=overwrite)
                    self.after(0, self._log_ok, f"GeoTIFF → {tif_dir}/{stem}.tif")

            except Exception as e:
                self.after(0, self._log_error, f"{name}: {e}")

        self.after(0, self._log_info, "─" * 48)
        self.after(0, self._log_ok,   f"Done — {total} file(s) processed.")
        self.after(0, self._finish)

    def _finish(self):
        self._progress.stop()
        self._run_btn.config(state="normal", text="Convert")
        self._running = False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = EMITConverterApp()
    app.mainloop()
