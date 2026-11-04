"""生成 PWA / iOS 图标 PNG。

为什么不用 cairosvg 直接把 icon.svg 光栅化：Windows 上配置 cairo 要额外 DLL，
为一张静态图标引一条 C 依赖不划算。这里用 Pillow 按同一套 1024 坐标系重画一遍，
坐标与 static/icon.svg 一一对应——要改色改形时两处一起改。

用法（依赖只有 Pillow，已在 requirements 里）：
    python scripts/make_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

BASE = 1024          # 设计基准坐标系，与 icon.svg 的 viewBox 一致
SS = 3               # 超采样倍数，最后 LANCZOS 缩下来当抗锯齿用

OUT = Path(__file__).resolve().parent.parent / "static"

# 与 index.html 的 --brand 同族
STOPS = [(0.0, (0x6D, 0x6E, 0xF4)), (0.55, (0x4F, 0x46, 0xE5)), (1.0, (0x3B, 0x31, 0xC4))]
BRAND = (0x4F, 0x46, 0xE5)
BRAND_INK = (0x43, 0x38, 0xCA)
WHITE = (0xFF, 0xFF, 0xFF)

# 卡片：右上折角，其余三角为 72 的圆角
CARD = (288, 224, 736, 800)
CARD_R = 72
FOLD = [(588, 224), (736, 372), (588, 372)]
FOLD_CUT = [(588, 224), (736, 224), (736, 372)]

BADGE = (800, 800, 150)


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


def _gradient_at(t: float) -> tuple[int, int, int]:
    for (p0, c0), (p1, c1) in zip(STOPS, STOPS[1:]):
        if t <= p1:
            return _lerp(c0, c1, (t - p0) / (p1 - p0))
    return STOPS[-1][1]


def gradient_bg(size: int) -> Image.Image:
    """对角渐变。先画 96x96 再放大：渐变本身没有高频信息，放大不会失真。"""
    small = 96
    img = Image.new("RGB", (small, small))
    px = img.load()
    span = 2 * (small - 1)
    for y in range(small):
        for x in range(small):
            px[x, y] = _gradient_at((x + y) / span)
    return img.resize((size, size), Image.BICUBIC)


def glow_layer(size: int) -> Image.Image:
    """左上角柔光，免得大面积紫渐变看着发闷。"""
    small = 96
    img = Image.new("L", (small, small), 0)
    px = img.load()
    cx, cy, r = 0.26 * small, 0.10 * small, 0.72 * small
    for y in range(small):
        for x in range(small):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / r
            px[x, y] = 0 if d >= 1 else round(66 * (1 - d) ** 2)
    return img.resize((size, size), Image.BICUBIC)


def _scaled(pts, s: float):
    return [(x * s, y * s) for x, y in pts]


def draw_content(size: int, s: float, origin: tuple[float, float] = (0.0, 0.0)) -> Image.Image:
    """透明底的内容层：卡片 + 折角 + 文字骨架 + 箭头徽章。

    单独成形是为了 maskable 版本能把内容缩进安全区再贴到底色上，
    否则直接缩放整张图会在边缘露出渐变接缝。
    """
    ox, oy = origin
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    card_mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(card_mask)
    box = [CARD[0] * s + ox, CARD[1] * s + oy, CARD[2] * s + ox, CARD[3] * s + oy]
    md.rounded_rectangle(box, radius=CARD_R * s, fill=255)
    # 右上折角区直接从 mask 里挖掉，斜边就成了卡片的轮廓
    md.polygon([(x * s + ox, y * s + oy) for x, y in FOLD_CUT], fill=0)

    # 卡片投影
    shadow_mask = card_mask.filter(ImageFilter.GaussianBlur(18 * s))
    shadow = Image.new("RGBA", (size, size), (0x1B, 0x16, 0x60, 0))
    shadow.putalpha(shadow_mask.point(lambda v: int(v * 0.28)))
    layer.alpha_composite(shadow, (0, int(14 * s)))

    layer.paste(Image.new("RGBA", (size, size), WHITE + (255,)), (0, 0), card_mask)

    # 折页：比纸面暗一档
    fold = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(fold).polygon([(x * s + ox, y * s + oy) for x, y in FOLD], fill=BRAND + (41,))
    layer.alpha_composite(fold)

    # 三行文字骨架，末行短一截
    bars = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bars)
    for y, w in ((404, 256), (498, 256), (592, 152)):
        bd.rounded_rectangle(
            [384 * s + ox, y * s + oy, (384 + w) * s + ox, (y + 28) * s + oy],
            radius=14 * s,
            fill=BRAND + (43,),
        )
    layer.alpha_composite(bars)

    # 徽章投影
    cx, cy, r = BADGE[0] * s + ox, BADGE[1] * s + oy, BADGE[2] * s
    badge_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(badge_mask).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    bshadow = Image.new("RGBA", (size, size), (0x1B, 0x16, 0x60, 0))
    bshadow.putalpha(badge_mask.filter(ImageFilter.GaussianBlur(12 * s)).point(lambda v: int(v * 0.30)))
    layer.alpha_composite(bshadow, (0, int(8 * s)))
    layer.paste(Image.new("RGBA", (size, size), WHITE + (255,)), (0, 0), badge_mask)

    # 箭头：竖线 + 两笔箭头，圆头
    arrow = ImageDraw.Draw(layer)
    width = round(34 * s)
    arrow.line([(cx, 862 * s + oy), (cx, 740 * s + oy)], fill=BRAND_INK + (255,), width=width, joint="curve")
    arrow.line(
        [(754 * s + ox, 786 * s + oy), (cx, 738 * s + oy), (848 * s + ox, 786 * s + oy)],
        fill=BRAND_INK + (255,),
        width=width,
        joint="curve",
    )
    # 补两个圆头，Pillow 的 line 端点默认是square
    for px_, py_ in ((cx, 862 * s + oy), (cx, 738 * s + oy), (754 * s + ox, 786 * s + oy), (848 * s + ox, 786 * s + oy)):
        arrow.ellipse([px_ - width / 2, py_ - width / 2, px_ + width / 2, py_ + width / 2], fill=BRAND_INK + (255,))

    return layer


def render(full: bool = True) -> Image.Image:
    size = BASE * SS
    if full:
        canvas = gradient_bg(size).convert("RGBA")
        glow = glow_layer(size)
        canvas.alpha_composite(Image.merge("RGBA", (Image.new("L", (size, size), 255),) * 3 + (glow,)))
        canvas.alpha_composite(draw_content(size, SS))
        return canvas
    # maskable：纯色底 + 内容缩到安全区，避免缩放整图时边缘出现接缝
    canvas = Image.new("RGBA", (size, size), BRAND + (255,))
    return canvas


def main() -> None:
    OUT.mkdir(exist_ok=True)

    master = render(True)
    for name, px in (
        ("icon-1024.png", 1024),
        ("icon-512.png", 512),
        ("icon-192.png", 192),
        ("apple-touch-icon.png", 180),   # iOS 主屏唯一认的尺寸系
    ):
        master.resize((px, px), Image.LANCZOS).convert("RGB").save(OUT / name, "PNG", optimize=True)
        print(f"  {name:<24} {px}x{px}")

    # maskable：安全区是中心直径 80% 的圆，内容整体缩到 0.75 再居中
    side = BASE * SS
    canvas = render(False)
    content = draw_content(side, SS * 0.75, origin=(side * 0.125, side * 0.135))
    canvas.alpha_composite(content)
    canvas.resize((512, 512), Image.LANCZOS).convert("RGB").save(OUT / "icon-maskable-512.png", "PNG", optimize=True)
    print(f"  {'icon-maskable-512.png':<24} 512x512")

    # 老浏览器标签页（还有一堆爬虫）只认 /favicon.ico
    master.convert("RGB").save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print(f"  {'favicon.ico':<24} 16/32/48/64")


if __name__ == "__main__":
    main()
