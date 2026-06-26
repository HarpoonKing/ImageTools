#!/usr/bin/env python3
"""核心图片处理逻辑（无 GUI 依赖，可独立测试）。"""

from pathlib import Path
from dataclasses import dataclass, field

from PIL import Image

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff", ".tif"}
RESAMPLE = Image.LANCZOS


@dataclass
class ResizeOptions:
    mode: str                 # "limit" | "scale" | "fixed"
    # limit
    limit_dim: str = "width"  # "width" | "height" | "both"
    max_width: int = 1920
    max_height: int = 1080
    allow_enlarge: bool = False
    # scale
    scale_percent: float = 100.0
    # fixed
    fixed_width: int = 1024
    fixed_height: int = 1024
    pad_color: tuple = (0, 0, 0, 0)  # 透明
    # 通用
    out_format: str = "保持原格式"   # "保持原格式" | "PNG" | "JPEG" | "WEBP"
    jpeg_quality: int = 90


def calc_limit_size(w: int, h: int, opt: ResizeOptions) -> tuple[int, int]:
    """限制最大边长，等比计算目标尺寸。"""
    if opt.limit_dim == "width":
        ratio = opt.max_width / w
    elif opt.limit_dim == "height":
        ratio = opt.max_height / h
    else:  # both -> 取较小比例，保证完整放入限制框
        ratio = min(opt.max_width / w, opt.max_height / h)

    if ratio >= 1.0 and not opt.allow_enlarge:
        return w, h  # 不放大
    return max(1, round(w * ratio)), max(1, round(h * ratio))


def fit_with_padding(im: Image.Image, target_w: int, target_h: int,
                     pad_color: tuple) -> Image.Image:
    """等比缩放后置于固定画布中央，多余区域填充 pad_color（默认透明）。"""
    src = im.convert("RGBA")
    w, h = src.size
    ratio = min(target_w / w, target_h / h)
    new_w = max(1, round(w * ratio))
    new_h = max(1, round(h * ratio))
    resized = src.resize((new_w, new_h), RESAMPLE)

    canvas = Image.new("RGBA", (target_w, target_h), pad_color)
    offset = ((target_w - new_w) // 2, (target_h - new_h) // 2)
    canvas.paste(resized, offset, resized)
    return canvas


def process_image(src_path: Path, dst_path: Path, opt: ResizeOptions) -> None:
    """处理单张图片并保存。"""
    with Image.open(src_path) as im:
        w, h = im.size

        if opt.mode == "limit":
            new_w, new_h = calc_limit_size(w, h, opt)
            out = im.resize((new_w, new_h), RESAMPLE)

        elif opt.mode == "scale":
            factor = opt.scale_percent / 100.0
            new_w = max(1, round(w * factor))
            new_h = max(1, round(h * factor))
            out = im.resize((new_w, new_h), RESAMPLE)

        elif opt.mode == "fixed":
            out = fit_with_padding(im, opt.fixed_width, opt.fixed_height, opt.pad_color)

        else:
            raise ValueError(f"未知模式: {opt.mode}")

        _save(out, dst_path, opt)


def _save(im: Image.Image, dst_path: Path, opt: ResizeOptions) -> None:
    fmt = opt.out_format
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "JPEG":
        im = _flatten_alpha(im)
        im.save(dst_path, "JPEG", quality=opt.jpeg_quality)
    elif fmt == "PNG":
        im.save(dst_path, "PNG")
    elif fmt == "WEBP":
        im.save(dst_path, "WEBP", quality=opt.jpeg_quality)
    else:  # 保持原格式
        ext = dst_path.suffix.lower()
        if ext in {".jpg", ".jpeg"}:
            im = _flatten_alpha(im)
        im.save(dst_path)


def _flatten_alpha(im: Image.Image) -> Image.Image:
    """将带透明通道的图铺白底转 RGB（用于 JPEG 等不支持透明的格式）。"""
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        rgba = im.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    return im.convert("RGB")


def target_path(src: Path, in_root: Path, out_dir: Path,
                opt: ResizeOptions, suffix: str) -> Path:
    """根据源文件与输入根目录，计算保留子目录结构的输出路径。"""
    try:
        rel = src.relative_to(in_root)
    except ValueError:
        rel = Path(src.name)

    stem = rel.stem + suffix
    ext = rel.suffix
    if opt.out_format == "PNG":
        ext = ".png"
    elif opt.out_format == "JPEG":
        ext = ".jpg"
    elif opt.out_format == "WEBP":
        ext = ".webp"
    return out_dir / rel.parent / f"{stem}{ext}"
