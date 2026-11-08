#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cup-shop-illustration 的本地图片工具。

只做五件事，纯本地、不联网、不调用任何 AI 服务：
  prepare  预处理用户照片（EXIF 方向 / 转 sRGB / 去 alpha / 限制长边）+ 打印信息卡
  compose  把「真实原图」和「AI 插画」无裁切拼接成高清 PNG
  cleanwm  无痕抹掉右下角平台强制水印（用周围背景色羽化填充，不裁地台）
  trim     裁掉图片底部的平台水印（备用方案）
  sheet    多版插画拼成对比宫格

依赖：Pillow（WorkBuddy 托管 venv 已内置）
用法：python imgtool.py <子命令> --help
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps, ImageStat

# 控制台中文输出（Windows GBK 终端兜底）
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULT_BG = "#FFFFFF"


def load_image(path: str | Path) -> Image.Image:
    """读取图片并统一成 RGB；只做色彩空间/方向归一，绝不裁切或改动画面内容。"""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"找不到图片：{p}")
    img = Image.open(p)
    img = ImageOps.exif_transpose(img)  # 手机照片的旋转信息
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, rgba).convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")  # CMYK / L / 16bit 等
    return img


def parse_color(s: str) -> tuple[int, int, int]:
    s = (s or "").lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise ValueError(f"颜色格式应为 #RRGGBB，收到：{s}")
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def resize_to_height(img: Image.Image, h: int) -> Image.Image:
    if img.height == h:
        return img
    w = max(1, round(img.width * h / img.height))
    return img.resize((w, h), Image.LANCZOS)


def resize_to_width(img: Image.Image, w: int) -> Image.Image:
    if img.width == w:
        return img
    h = max(1, round(img.height * w / img.width))
    return img.resize((w, h), Image.LANCZOS)


def analyze(img: Image.Image) -> dict:
    w, h = img.size
    if h > w * 1.10:
        orient, layout = "portrait", "side"
    elif w > h * 1.10:
        orient, layout = "landscape", "stack"
    else:
        orient, layout = "square", "side"

    q = img.resize((64, 64)).quantize(colors=5, method=Image.Quantize.MEDIANCUT)
    palette = q.getpalette() or []
    counts = sorted(q.getcolors() or [], reverse=True)
    colors = []
    for cnt, idx in counts[:5]:
        rgb = tuple(palette[idx * 3 : idx * 3 + 3])
        colors.append(
            {"hex": "#%02X%02X%02X" % rgb, "share": round(cnt / 4096, 3)}
        )
    return {
        "width": w,
        "height": h,
        "ratio": round(w / h, 3),
        "orientation": orient,
        "layout": layout,
        "brightness": round(ImageStat.Stat(img.convert("L")).mean[0], 1),
        "dominant_colors": colors,
    }


# ---------------------------------------------------------------- prepare
def cmd_prepare(args: argparse.Namespace) -> None:
    src = Path(args.image)
    img = load_image(src)
    if max(img.size) > args.max_side:
        img.thumbnail((args.max_side, args.max_side), Image.LANCZOS)

    out = Path(args.out) if args.out else src.with_name(src.stem + "_clean.jpg")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() in (".jpg", ".jpeg"):
        img.save(out, "JPEG", quality=95, subsampling=0, optimize=True)
    else:
        img.save(out, "PNG", optimize=True)

    info = analyze(img)
    info["source"] = str(src)
    info["clean"] = str(out)
    info["note"] = "clean 图仅做格式/方向归一与等比缩小，画面内容与原图一致"
    print(json.dumps(info, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- compose
def cmd_compose(args: argparse.Namespace) -> None:
    photo = load_image(args.photo)  # 必须是用户上传的真实原图
    art = load_image(args.art)  # AI 生成的完整独立插画
    bg = parse_color(args.bg)

    layout = args.layout
    if layout == "auto":
        layout = analyze(photo)["layout"]

    gap, pad = args.gap, args.pad
    if layout == "side":
        # 以插画原始高度为基准：插画一个像素都不缩放，标题与地台保持最清晰
        h = art.height
        photo_r = resize_to_height(photo, h)
        art_r = art
        canvas_w = pad * 2 + photo_r.width + gap + art_r.width
        canvas_h = pad * 2 + h
        canvas = Image.new("RGB", (canvas_w, canvas_h), bg)
        canvas.paste(photo_r, (pad, pad))
        canvas.paste(art_r, (pad + photo_r.width + gap, pad))
    else:
        w = art.width
        photo_r = resize_to_width(photo, w)
        art_r = art
        canvas_w = pad * 2 + w
        canvas_h = pad * 2 + photo_r.height + gap + art_r.height
        canvas = Image.new("RGB", (canvas_w, canvas_h), bg)
        canvas.paste(photo_r, (pad, pad))
        canvas.paste(art_r, (pad, pad + photo_r.height + gap))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "PNG", optimize=True)

    print(
        json.dumps(
            {
                "compare": str(out),
                "layout": "左右拼接（原图左 / 插画右）" if layout == "side" else "上下拼接（原图上 / 插画下）",
                "size": list(canvas.size),
                "photo_source": str(args.photo),
                "photo_scaled": list(photo_r.size),
                "art_untouched": list(art.size),
                "gap": gap,
                "pad": pad,
                "bg": args.bg,
                "note": "两图均等比缩放，未裁切、未拉伸、未改动内容",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


# ---------------------------------------------------------------- trim
def cmd_trim(args: argparse.Namespace) -> None:
    src = Path(args.image)
    img = load_image(src)
    w, h = img.size
    cut = max(1, round(h * args.bottom))
    cropped = img.crop((0, 0, w, h - cut))

    if args.mode == "stretch":
        result = cropped.resize((w, h), Image.LANCZOS)
    elif args.mode == "pad":
        result = Image.new("RGB", (w, h), parse_color(args.bg))
        result.paste(cropped, (0, 0))
    else:
        result = cropped

    out = Path(args.out) if args.out else src.with_name(src.stem + "_trim.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    result.save(out, "PNG", optimize=True)
    print(json.dumps({"trimmed": str(out), "mode": args.mode,
                      "cut_px": cut, "size": list(result.size)},
                     ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- cleanwm
def cmd_cleanwm(args: argparse.Namespace) -> None:
    """抹掉右下角平台水印：取水印框上方条带的背景主色，羽化覆盖。

    只在纯色背景区工作，不裁切画面、不动地台。若地台/植物伸进了默认框，
    用 --box 把框缩小，或用 --color 指定填充色。
    """
    src = Path(args.image)
    img = load_image(src)
    w, h = img.size

    if args.box:
        parts = [float(v) for v in args.box.split(",")]
        if len(parts) != 4:
            raise ValueError("--box 需要四个 0–1 比例值：x0,y0,x1,y1")
        x0, y0, x1, y1 = parts
    else:
        x0, y0, x1, y1 = args.x0, args.y0, 1.0, 1.0  # 实测默认 0.86/0.925 可完整覆盖两行水印
    bx0, by0 = max(0, round(x0 * w)), max(0, round(y0 * h))
    bx1, by1 = min(w, round(x1 * w)), min(h, round(y1 * h))
    bw, bh = bx1 - bx0, by1 - by0
    if bw <= 0 or bh <= 0:
        raise ValueError("水印框尺寸不合法")

    if args.color:
        fill = parse_color(args.color)
    else:
        # 采样框正上方一条窄带的众数色，避开水印本身
        sy0, sy1 = max(0, by0 - round(0.045 * h)), max(1, by0 - round(0.012 * h))
        strip = img.crop((bx0, sy0, bx1, sy1))
        q = strip.resize((64, 8)).quantize(colors=4, method=Image.Quantize.MEDIANCUT)
        pal = q.getpalette() or []
        counts = sorted(q.getcolors() or [], reverse=True)
        # 取最亮的那个主色：纯色背景通常比叶片/描边亮
        candidates = [tuple(pal[i * 3 : i * 3 + 3]) for _, i in counts[:4]]
        fill = max(candidates, key=lambda c: sum(c))  # type: ignore[arg-type]

    region = img.crop((bx0, by0, bx1, by1))
    if args.mode == "selective":
        # 只把「偏白」的水印像素拉向背景色。深色叶片、地台、描边完全不动；
        # 贴着画布边缘的字也能清干净（整块填充会误抹飘叶，实测踩过坑）。
        span = 50.0
        out = []
        raw = region.tobytes()  # RGB 字节流，跨 Pillow 版本稳定
        for i in range(0, len(raw), 3):
            r, g, b = raw[i], raw[i + 1], raw[i + 2]
            a = (min(r, g, b) - args.threshold) / span
            a = max(0.0, min(1.0, a)) ** 0.5
            out.append(
                (
                    int(r + (fill[0] - r) * a),
                    int(g + (fill[1] - g) * a),
                    int(b + (fill[2] - b) * a),
                )
            )
        cleaned = Image.new("RGB", region.size)
        cleaned.putdata(out)
    else:
        overlay = Image.new("RGB", (bw, bh), fill)
        feather = max(1, args.feather)
        # 贴画布边界的一侧不羽化，否则贴边文字会残留半截。
        px = []
        for y in range(bh):
            for x in range(bw):
                a = 1.0
                if bx0 > 0:
                    a = min(a, x / feather)
                if by0 > 0:
                    a = min(a, y / feather)
                if bx1 < w:
                    a = min(a, (bw - 1 - x) / feather)
                if by1 < h:
                    a = min(a, (bh - 1 - y) / feather)
                px.append(int(255 * max(0.0, min(1.0, a))))
        mask = Image.new("L", (bw, bh))
        mask.putdata(px)
        cleaned = Image.composite(overlay, region, mask)

    img.paste(cleaned, (bx0, by0))

    out = Path(args.out) if args.out else src.with_name(src.stem + "_cleanwm.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    print(
        json.dumps(
            {
                "cleanwm": str(out),
                "box_px": [bx0, by0, bx1, by1],
                "fill": "#%02X%02X%02X" % fill,
                "mode": args.mode,
                "feather": args.feather,
                "size": list(img.size),
                "note": "未裁切画面；selective 模式只处理偏白像素，深色装饰不受影响",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


# ---------------------------------------------------------------- sheet
def cmd_sheet(args: argparse.Namespace) -> None:
    imgs = [load_image(p) for p in args.images]
    thumb_h = args.thumb_h
    thumbs = [resize_to_height(im, thumb_h) for im in imgs]
    cols = min(args.cols, len(thumbs))
    rows = (len(thumbs) + cols - 1) // cols
    cell_w = max(t.width for t in thumbs)
    gap = args.gap
    canvas = Image.new(
        "RGB",
        (cols * cell_w + (cols + 1) * gap, rows * thumb_h + (rows + 1) * gap),
        parse_color(args.bg),
    )
    for i, t in enumerate(thumbs):
        x = gap + (i % cols) * (cell_w + gap) + (cell_w - t.width) // 2
        y = gap + (i // cols) * (thumb_h + gap)
        canvas.paste(t, (x, y))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "PNG", optimize=True)
    print(json.dumps({"sheet": str(out), "count": len(imgs),
                      "size": list(canvas.size)}, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="饮品照片 → 等轴测杯子门店插画 · 本地图片工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prepare", help="预处理照片并打印信息卡")
    p.add_argument("image", help="用户上传的原始照片路径")
    p.add_argument("--out", help="输出路径，默认 <原名>_clean.jpg")
    p.add_argument("--max-side", type=int, default=2048, help="长边上限，默认 2048")
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("compose", help="真实原图 + 插画 无裁切拼接")
    p.add_argument("--photo", required=True, help="用户上传的原始照片（真实，不可替换）")
    p.add_argument("--art", required=True, help="AI 生成的完整独立插画 PNG")
    p.add_argument("--out", required=True, help="输出对比图 PNG")
    p.add_argument("--layout", choices=["auto", "side", "stack"], default="auto",
                    help="auto=按原图方向；side=左右；stack=上下")
    p.add_argument("--gap", type=int, default=24, help="两图之间白色间隔，默认 24px")
    p.add_argument("--pad", type=int, default=24, help="画布外边距，默认 24px")
    p.add_argument("--bg", default=DEFAULT_BG, help="背景色 #RRGGBB，默认白色")
    p.set_defaults(func=cmd_compose)

    p = sub.add_parser("trim", help="裁掉底部平台水印")
    p.add_argument("image")
    p.add_argument("--out")
    p.add_argument("--bottom", type=float, default=0.06, help="裁掉底部比例，默认 0.06")
    p.add_argument("--mode", choices=["crop", "pad", "stretch"], default="crop")
    p.add_argument("--bg", default=DEFAULT_BG)
    p.set_defaults(func=cmd_trim)

    p = sub.add_parser("cleanwm", help="无痕抹掉右下角平台水印（推荐）")
    p.add_argument("image")
    p.add_argument("--out")
    p.add_argument("--box", help="水印框比例 x0,y0,x1,y1，默认 0.86,0.925,1,1")
    p.add_argument("--x0", type=float, default=0.86)
    p.add_argument("--y0", type=float, default=0.925)
    p.add_argument("--color", help="强制填充色 #RRGGBB，默认自动取上方背景主色")
    p.add_argument("--mode", choices=["selective", "fill"], default="selective",
                   help="selective=只抹白色水印像素（默认，不伤叶片）；fill=整块填充")
    p.add_argument("--threshold", type=int, default=160,
                   help="判定「偏白」的最小通道阈值，默认 160（实测能去掉水印抗锯齿淡影）；背景复杂时调高到 190–210")
    p.add_argument("--feather", type=int, default=12, help="fill 模式的边缘羽化像素，默认 12")
    p.set_defaults(func=cmd_cleanwm)

    p = sub.add_parser("sheet", help="多版插画拼对比宫格")
    p.add_argument("images", nargs="+")
    p.add_argument("--out", required=True)
    p.add_argument("--cols", type=int, default=2)
    p.add_argument("--thumb-h", type=int, default=640)
    p.add_argument("--gap", type=int, default=16)
    p.add_argument("--bg", default=DEFAULT_BG)
    p.set_defaults(func=cmd_sheet)

    return ap


def main() -> int:
    args = build_parser().parse_args()
    try:
        args.func(args)
    except Exception as exc:  # 明确报错，不静默失败
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
