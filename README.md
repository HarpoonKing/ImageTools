# ImageTools · 批量图片调整工具

一个基于 Python + Tkinter + Pillow 的桌面工具，支持批量调整图片尺寸。

## 功能

1. **限制最大尺寸（等比）** — 限制宽度、高度或两者的最大值，等比缩放；可选是否允许放大。
2. **按比例缩放** — 按百分比等比放大（>100%）或缩小（<100%）。
3. **固定尺寸 + 留白** — 缩放并居中放入固定画布，多余区域可填充透明 / 白色 / 黑色。

其它特性：
- 支持单张/多张添加，或整个文件夹（含子目录，保留目录结构）。
- 输出格式可选：保持原格式 / PNG / JPEG / WEBP（JPEG 自动给透明区域铺白底）。
- 可自定义输出文件名后缀。
- 后台线程处理 + 进度条 + 日志，界面不卡顿。

支持格式：PNG, JPG/JPEG, BMP, GIF, WEBP, TIFF。

## 运行

```bash
./run.sh
```

首次运行会自动创建虚拟环境并安装依赖（Pillow）。

### 手动运行

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python image_tools.py
```

> 注意：需要带 Tkinter 的 Python。macOS Homebrew 用户如缺少 Tk，可执行
> `brew install python-tk@3.13`。

## 文件说明

- `image_tools.py` — Tkinter 图形界面。
- `resize_core.py` — 核心图片处理逻辑（无 GUI 依赖，可单独调用）。
- `requirements.txt` — 依赖列表。
- `run.sh` — 一键启动脚本。
