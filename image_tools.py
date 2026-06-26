#!/usr/bin/env python3
"""ImageTools - 批量图片调整桌面工具。

功能：
1. 限制最大宽度或高度，等比缩放
2. 按百分比等比放大 / 缩小
3. 固定尺寸，多余区域上下或左右透明留白
"""

import os
import sys
import json
import subprocess
import threading
import queue
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

from resize_core import (
    SUPPORTED_EXTS,
    ResizeOptions,
    process_image,
    target_path,
)

CONFIG_PATH = Path.home() / ".imagetools_config.json"


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class App(TkinterDnD.Tk if HAS_DND else tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ImageTools - 批量图片调整")
        self.geometry("760x780")
        self.minsize(700, 720)

        self.files: list[Path] = []
        self.in_root: Path | None = None
        self.msg_queue: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None

        self._setup_style()
        self._build_ui()
        self._apply_config(self._load_config())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_queue)

    # ---- 主题样式 ----
    def _setup_style(self):
        self.BG = "#f4f5f7"
        self.ACCENT = "#3b82f6"
        self.ACCENT_ACTIVE = "#2563eb"
        self.TEXT = "#1f2937"
        self.MUTED = "#6b7280"

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        base_font = ("Helvetica", 12)
        self.configure(bg=self.BG)
        style.configure(".", background=self.BG, foreground=self.TEXT, font=base_font)
        style.configure("TFrame", background=self.BG)
        style.configure("TLabel", background=self.BG, foreground=self.TEXT)
        style.configure("TCheckbutton", background=self.BG)
        style.configure("TRadiobutton", background=self.BG)
        style.configure("TLabelframe", background=self.BG, bordercolor="#d1d5db",
                        relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background=self.BG,
                        foreground=self.ACCENT, font=("Helvetica", 12, "bold"))
        style.configure("TButton", padding=6)
        style.map("TButton", background=[("active", "#e5e7eb")])
        style.configure("Accent.TButton", padding=8,
                        font=("Helvetica", 13, "bold"),
                        foreground="#ffffff", background=self.ACCENT)
        style.map("Accent.TButton",
                  background=[("active", self.ACCENT_ACTIVE), ("disabled", "#9ca3af")],
                  foreground=[("disabled", "#e5e7eb")])
        style.configure("Title.TLabel", font=("Helvetica", 18, "bold"), foreground=self.TEXT)
        style.configure("Hint.TLabel", font=("Helvetica", 10), foreground=self.MUTED)
        style.configure("Status.TLabel", background="#e5e7eb", foreground=self.MUTED,
                        font=("Helvetica", 10))
        style.configure("TProgressbar", background=self.ACCENT, troughcolor="#e5e7eb",
                        bordercolor="#e5e7eb", lightcolor=self.ACCENT, darkcolor=self.ACCENT)

    # ---- UI 构建 ----
    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}

        # 标题栏
        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(header, text="🖼  批量图片调整工具", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="限制尺寸 · 等比缩放 · 固定留白",
                  style="Hint.TLabel").pack(side="left", padx=12, pady=(10, 0))

        # 1. 输入文件
        frm_in = ttk.LabelFrame(self, text=" ① 选择图片 ")
        frm_in.pack(fill="both", **pad)
        bar = ttk.Frame(frm_in)
        bar.pack(fill="x", padx=6, pady=(8, 4))
        ttk.Button(bar, text="添加文件…", command=self._add_files).pack(side="left", padx=3)
        ttk.Button(bar, text="添加文件夹…", command=self._add_folder).pack(side="left", padx=3)
        ttk.Button(bar, text="移除所选", command=self._remove_selected).pack(side="left", padx=3)
        ttk.Button(bar, text="清空", command=self._clear_files).pack(side="left", padx=3)
        ttk.Button(bar, text="打开输入目录", command=self._open_in_root).pack(side="left", padx=3)
        self.lbl_count = ttk.Label(bar, text="已选 0 张", style="Hint.TLabel")
        self.lbl_count.pack(side="right", padx=6)

        list_wrap = ttk.Frame(frm_in)
        list_wrap.pack(fill="both", expand=True, padx=6, pady=(0, 8))
        self.file_list = tk.Listbox(
            list_wrap, height=5, activestyle="none", selectmode="extended",
            bg="#ffffff", fg=self.TEXT, highlightthickness=1,
            highlightbackground="#d1d5db", highlightcolor="#d1d5db",
            selectbackground=self.ACCENT, selectforeground="#ffffff", borderwidth=0)
        self.file_list.pack(side="left", fill="both", expand=True)
        sb_files = ttk.Scrollbar(list_wrap, command=self.file_list.yview)
        sb_files.pack(side="right", fill="y")
        self.file_list.config(yscrollcommand=sb_files.set)
        self.file_list.bind("<Double-Button-1>", lambda e: self._remove_selected())

        # 拖放支持
        if HAS_DND:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self._on_drop)

        # 2. 模式
        frm_mode = ttk.LabelFrame(self, text=" ② 处理模式 ")
        frm_mode.pack(fill="x", **pad)
        self.mode = tk.StringVar(value="limit")
        ttk.Radiobutton(frm_mode, text="限制最大尺寸（等比）", value="limit",
                        variable=self.mode, command=self._on_mode_change).grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Radiobutton(frm_mode, text="按比例缩放", value="scale",
                        variable=self.mode, command=self._on_mode_change).grid(row=0, column=1, sticky="w", padx=8, pady=6)
        ttk.Radiobutton(frm_mode, text="固定尺寸 + 留白", value="fixed",
                        variable=self.mode, command=self._on_mode_change).grid(row=0, column=2, sticky="w", padx=8, pady=6)

        # 参数容器
        self.frm_params = ttk.Frame(self)
        self.frm_params.pack(fill="x", **pad)
        self._build_limit_params()
        self._build_scale_params()
        self._build_fixed_params()

        # 3. 输出
        frm_out = ttk.LabelFrame(self, text=" ③ 输出设置 ")
        frm_out.pack(fill="x", **pad)

        ttk.Label(frm_out, text="输出目录：").grid(row=0, column=0, sticky="w", padx=8, pady=5)
        self.out_dir = tk.StringVar()
        ttk.Entry(frm_out, textvariable=self.out_dir).grid(row=0, column=1, columnspan=2, sticky="we", padx=6, pady=5)
        ttk.Button(frm_out, text="浏览…", command=self._choose_out).grid(row=0, column=3, padx=6, pady=5)
        ttk.Button(frm_out, text="打开", command=self._open_out_dir).grid(row=0, column=4, padx=(0, 8), pady=5)
        frm_out.columnconfigure(1, weight=1)

        ttk.Label(frm_out, text="输出格式：").grid(row=1, column=0, sticky="w", padx=8, pady=5)
        self.out_format = tk.StringVar(value="保持原格式")
        ttk.Combobox(frm_out, textvariable=self.out_format, state="readonly", width=14,
                     values=["保持原格式", "PNG", "JPEG", "WEBP"]).grid(row=1, column=1, sticky="w", padx=6, pady=5)

        ttk.Label(frm_out, text="文件名后缀：").grid(row=1, column=2, sticky="e", padx=6, pady=5)
        self.suffix = tk.StringVar(value="_resized")
        ttk.Entry(frm_out, textvariable=self.suffix, width=14).grid(row=1, column=3, columnspan=2, sticky="w", padx=6, pady=5)

        self.overwrite = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm_out, text="覆盖已存在文件", variable=self.overwrite).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 6))
        self.open_after = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm_out, text="完成后打开输出目录", variable=self.open_after).grid(
            row=2, column=2, columnspan=3, sticky="w", padx=6, pady=(0, 6))

        # 4. 执行
        frm_run = ttk.Frame(self)
        frm_run.pack(fill="x", **pad)
        self.btn_run = ttk.Button(frm_run, text="▶  开始处理", style="Accent.TButton", command=self._start)
        self.btn_run.pack(side="left", padx=6)
        self.progress = ttk.Progressbar(frm_run, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=8)
        self.lbl_percent = ttk.Label(frm_run, text="0%", style="Hint.TLabel", width=6)
        self.lbl_percent.pack(side="left", padx=(0, 6))

        # 日志
        frm_log = ttk.LabelFrame(self, text=" 日志 ")
        frm_log.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(frm_log, height=6, state="disabled", wrap="word",
                           bg="#ffffff", fg=self.TEXT, relief="flat",
                           highlightthickness=1, highlightbackground="#d1d5db",
                           font=("Menlo", 11))
        self.log.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        sb = ttk.Scrollbar(frm_log, command=self.log.yview)
        sb.pack(side="right", fill="y")
        self.log.config(yscrollcommand=sb.set)

        # 状态栏
        self.status = tk.StringVar(value="就绪")
        ttk.Label(self, textvariable=self.status, style="Status.TLabel",
                  anchor="w", padding=(10, 4)).pack(fill="x", side="bottom")

        self._on_mode_change()

    def _build_limit_params(self):
        f = ttk.Frame(self.frm_params)
        self.limit_frame = f
        ttk.Label(f, text="限制：").grid(row=0, column=0, padx=4, pady=4, sticky="w")
        self.limit_dim = tk.StringVar(value="width")
        ttk.Combobox(f, textvariable=self.limit_dim, state="readonly", width=10,
                     values=["width", "height", "both"]).grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(f, text="最大宽：").grid(row=0, column=2, padx=4)
        self.max_width = tk.IntVar(value=1920)
        ttk.Entry(f, textvariable=self.max_width, width=8).grid(row=0, column=3, padx=4)
        ttk.Label(f, text="最大高：").grid(row=0, column=4, padx=4)
        self.max_height = tk.IntVar(value=1080)
        ttk.Entry(f, textvariable=self.max_height, width=8).grid(row=0, column=5, padx=4)
        self.allow_enlarge = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="允许放大", variable=self.allow_enlarge).grid(row=0, column=6, padx=8)

    def _build_scale_params(self):
        f = ttk.Frame(self.frm_params)
        self.scale_frame = f
        ttk.Label(f, text="缩放比例(%)：").grid(row=0, column=0, padx=4, pady=4, sticky="w")
        self.scale_percent = tk.DoubleVar(value=50.0)
        ttk.Entry(f, textvariable=self.scale_percent, width=10).grid(row=0, column=1, padx=4)
        ttk.Label(f, text="（>100 放大，<100 缩小）").grid(row=0, column=2, padx=8)

    def _build_fixed_params(self):
        f = ttk.Frame(self.frm_params)
        self.fixed_frame = f
        ttk.Label(f, text="宽：").grid(row=0, column=0, padx=4, pady=4)
        self.fixed_width = tk.IntVar(value=1024)
        ttk.Entry(f, textvariable=self.fixed_width, width=8).grid(row=0, column=1, padx=4)
        ttk.Label(f, text="高：").grid(row=0, column=2, padx=4)
        self.fixed_height = tk.IntVar(value=1024)
        ttk.Entry(f, textvariable=self.fixed_height, width=8).grid(row=0, column=3, padx=4)
        ttk.Label(f, text="留白：").grid(row=0, column=4, padx=4)
        self.pad_mode = tk.StringVar(value="透明")
        ttk.Combobox(f, textvariable=self.pad_mode, state="readonly", width=10,
                     values=["透明", "白色", "黑色"]).grid(row=0, column=5, padx=4)

    def _on_mode_change(self):
        for fr in (self.limit_frame, self.scale_frame, self.fixed_frame):
            fr.pack_forget()
        m = self.mode.get()
        if m == "limit":
            self.limit_frame.pack(fill="x")
        elif m == "scale":
            self.scale_frame.pack(fill="x")
        else:
            self.fixed_frame.pack(fill="x")

    # ---- 拖放 ----
    def _on_drop(self, event):
        """处理从系统拖入的文件/文件夹。"""
        raw = event.data
        # tkdnd 在 macOS 上用花括号包裹含空格的路径
        paths: list[str] = []
        if '{' in raw:
            import re
            paths = re.findall(r'\{([^}]+)\}', raw)
            # 还有不含空格未被花括号包裹的部分
            remaining = re.sub(r'\{[^}]+\}', '', raw).strip()
            if remaining:
                paths.extend(remaining.split())
        else:
            paths = raw.split()

        added: list[Path] = []
        for p in paths:
            pp = Path(p)
            if pp.is_dir():
                found = [f for f in pp.rglob("*") if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS]
                added.extend(found)
                if self.in_root is None:
                    self.in_root = pp
            elif pp.is_file() and pp.suffix.lower() in SUPPORTED_EXTS:
                added.append(pp)
                if self.in_root is None:
                    self.in_root = pp.parent
        if added:
            self._extend_files(added)

    # ---- 文件选择 ----
    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="选择图片",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff *.tif"), ("所有文件", "*.*")],
        )
        added = [Path(p) for p in paths if Path(p).suffix.lower() in SUPPORTED_EXTS]
        self._extend_files(added)
        if added and self.in_root is None:
            self.in_root = added[0].parent

    def _add_folder(self):
        d = filedialog.askdirectory(title="选择文件夹（含子目录）")
        if not d:
            return
        root = Path(d)
        found = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]
        self.in_root = root
        self._extend_files(found)

    def _extend_files(self, items: list[Path]):
        existing = set(self.files)
        for p in items:
            if p not in existing:
                self.files.append(p)
                existing.add(p)
        self._refresh_file_list()

    def _refresh_file_list(self):
        self.file_list.delete(0, "end")
        for p in self.files:
            self.file_list.insert("end", p.name)
        self.lbl_count.config(text=f"已选 {len(self.files)} 张")
        self.status.set(f"已选 {len(self.files)} 张图片"
                        + (f" · 输入目录 {self.in_root}" if self.in_root else ""))

    def _remove_selected(self):
        sel = list(self.file_list.curselection())
        if not sel:
            return
        for idx in reversed(sel):
            del self.files[idx]
        self._refresh_file_list()

    def _clear_files(self):
        self.files.clear()
        self.in_root = None
        self._refresh_file_list()

    def _open_in_root(self):
        if not self.in_root or not self.in_root.exists():
            messagebox.showinfo("提示", "尚未确定输入目录，请先添加文件或文件夹。")
            return
        self._open_in_file_manager(self.in_root)

    @staticmethod
    def _open_in_file_manager(path: Path):
        """在系统文件管理器中打开目录（跨平台）。"""
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            elif sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("错误", f"无法打开目录：{e}")

    def _choose_out(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.out_dir.set(d)

    def _open_out_dir(self):
        out = self.out_dir.get().strip()
        if not out or not Path(out).exists():
            messagebox.showinfo("提示", "输出目录不存在，请先选择或先完成一次处理。")
            return
        self._open_in_file_manager(Path(out))

    # ---- 配置持久化 ----
    def _load_config(self) -> dict:
        try:
            return json.loads(CONFIG_PATH.read_text("utf-8"))
        except Exception:  # noqa: BLE001
            return {}

    def _apply_config(self, cfg: dict):
        if not cfg:
            return
        mapping = {
            "mode": self.mode, "limit_dim": self.limit_dim,
            "max_width": self.max_width, "max_height": self.max_height,
            "allow_enlarge": self.allow_enlarge, "scale_percent": self.scale_percent,
            "fixed_width": self.fixed_width, "fixed_height": self.fixed_height,
            "pad_mode": self.pad_mode, "out_format": self.out_format,
            "suffix": self.suffix, "out_dir": self.out_dir,
            "overwrite": self.overwrite, "open_after": self.open_after,
        }
        for key, var in mapping.items():
            if key in cfg:
                try:
                    var.set(cfg[key])
                except tk.TclError:
                    pass
        self._on_mode_change()

    def _save_config(self):
        cfg = {
            "mode": self.mode.get(), "limit_dim": self.limit_dim.get(),
            "max_width": int(self.max_width.get()), "max_height": int(self.max_height.get()),
            "allow_enlarge": bool(self.allow_enlarge.get()),
            "scale_percent": float(self.scale_percent.get()),
            "fixed_width": int(self.fixed_width.get()), "fixed_height": int(self.fixed_height.get()),
            "pad_mode": self.pad_mode.get(), "out_format": self.out_format.get(),
            "suffix": self.suffix.get(), "out_dir": self.out_dir.get(),
            "overwrite": bool(self.overwrite.get()), "open_after": bool(self.open_after.get()),
        }
        try:
            CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
        except Exception:  # noqa: BLE001
            pass

    def _on_close(self):
        try:
            self._save_config()
        finally:
            self.destroy()

    # ---- 执行 ----
    def _collect_options(self) -> ResizeOptions:
        pad_map = {"透明": (0, 0, 0, 0), "白色": (255, 255, 255, 255), "黑色": (0, 0, 0, 255)}
        return ResizeOptions(
            mode=self.mode.get(),
            limit_dim=self.limit_dim.get(),
            max_width=int(self.max_width.get()),
            max_height=int(self.max_height.get()),
            allow_enlarge=bool(self.allow_enlarge.get()),
            scale_percent=float(self.scale_percent.get()),
            fixed_width=int(self.fixed_width.get()),
            fixed_height=int(self.fixed_height.get()),
            pad_color=pad_map[self.pad_mode.get()],
            out_format=self.out_format.get(),
        )

    def _start(self):
        if self.worker and self.worker.is_alive():
            return
        if not self.files:
            messagebox.showwarning("提示", "请先添加要处理的图片。")
            return
        out = self.out_dir.get().strip()
        if not out:
            messagebox.showwarning("提示", "请选择输出目录。")
            return

        try:
            opt = self._collect_options()
        except (tk.TclError, ValueError):
            messagebox.showerror("错误", "参数填写有误，请检查数值输入。")
            return

        if opt.mode == "scale" and opt.scale_percent <= 0:
            messagebox.showerror("错误", "缩放比例必须大于 0。")
            return
        if opt.mode == "fixed" and (opt.fixed_width <= 0 or opt.fixed_height <= 0):
            messagebox.showerror("错误", "固定尺寸必须大于 0。")
            return

        out_dir = Path(out)
        in_root = self.in_root or (self.files[0].parent if self.files else Path("."))
        suffix = self.suffix.get()
        overwrite = bool(self.overwrite.get())

        self._save_config()
        self.btn_run.config(state="disabled")
        self.progress.config(maximum=len(self.files), value=0)
        self.lbl_percent.config(text="0%")
        self.status.set("正在处理…")
        self._log_clear()

        self.worker = threading.Thread(
            target=self._run_batch,
            args=(list(self.files), in_root, out_dir, opt, suffix, overwrite),
            daemon=True,
        )
        self.worker.start()

    def _run_batch(self, files, in_root, out_dir, opt, suffix, overwrite):
        ok = skipped = 0
        total = len(files)
        for i, src in enumerate(files, 1):
            try:
                dst = target_path(src, in_root, out_dir, opt, suffix)
                if not overwrite and dst.exists():
                    skipped += 1
                    self.msg_queue.put(("log", f"⏭ 跳过（已存在） {dst.name}"))
                else:
                    process_image(src, dst, opt)
                    ok += 1
                    self.msg_queue.put(("log", f"✓ {src.name} → {dst.name}"))
            except Exception as e:  # noqa: BLE001
                self.msg_queue.put(("log", f"✗ {src.name} 失败: {e}"))
            self.msg_queue.put(("progress", (i, total)))
        msg = f"完成：成功 {ok} / {total} 张"
        if skipped:
            msg += f"（跳过 {skipped}）"
        self.msg_queue.put(("done", (msg, str(out_dir))))

    # ---- 队列轮询（线程安全更新 UI） ----
    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "progress":
                    done, total = payload
                    self.progress.config(value=done)
                    pct = round(done / total * 100) if total else 0
                    self.lbl_percent.config(text=f"{pct}%")
                elif kind == "done":
                    msg, out_dir = payload
                    self._log(msg)
                    self.btn_run.config(state="normal")
                    self.status.set(msg)
                    if self.open_after.get() and Path(out_dir).exists():
                        self._open_in_file_manager(Path(out_dir))
                    messagebox.showinfo("完成", msg)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    # ---- 日志 ----
    def _log(self, text: str):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _log_clear(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
