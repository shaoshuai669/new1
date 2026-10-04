# -*- coding: utf-8 -*-
"""
从「贵门·宋韵行者」单文件 HTML 中抽取 base64 内嵌图片，生成外链版「减肥版」。

- 逐个匹配  key : "data:image/<mime>;base64,<payload>"
- 解码写入  images/<key>.<ext>
- 原位回填  key : "./images/<key>.<ext>"
- 用 Pillow 对每张图重编码压缩，确保单张 <= 200KB
- 输出 减肥版.html（原文件不改动）
"""

import base64
import os
import io
import re
import sys

from PIL import Image

SRC = r"C:\Users\Mr\Desktop\贵门宋韵行者 (1).html"
OUT_DIR = r"C:\Users\Mr\Desktop\减肥版"
IMG_DIR = os.path.join(OUT_DIR, "images")
OUT_HTML = os.path.join(OUT_DIR, "减肥版.html")

TARGET_MAX_KB = 200  # 单张图片体积上限（链接需求）
FINAL_QUALITY = 75   # 经 PSNR 实测选定：≈无损且比原始字节更小

PATTERN = re.compile(
    r'([A-Za-z0-9_$]+)\s*:\s*"data:image/(jpeg|jpg|png|webp);base64,([^"]+)"'
)


def compress(src_path, dst_path, orig_len, max_kb=TARGET_MAX_KB, quality=FINAL_QUALITY):
    """固定 quality 重编码，取「重编码结果」与「原始字节」中更小的一份落盘。

    实测原图本身即 q≈75 编码，q75 重算 PSNR 48-65dB（≈无损）且体积略小；
    q82 以上体积反而超过原图，属负优化，故不采用。
    返回 (bytes, quality, size)。
    """
    limit = max_kb * 1024
    with open(src_path, "rb") as f:
        orig = f.read()
    with Image.open(io.BytesIO(orig)) as im:
        im = im.convert("RGB")
        size = im.size
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
        data = buf.getvalue()
    if len(data) >= len(orig) or len(data) > limit:
        data = orig  # 重编码没收益，保留原始字节
    with open(dst_path, "wb") as f:
        f.write(data)
    return len(data), quality, size


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    os.makedirs(IMG_DIR, exist_ok=True)

    with open(SRC, "r", encoding="utf-8") as f:
        html = f.read()
    print("源文件字符数: %d" % len(html))

    matches = list(PATTERN.finditer(html))
    print("命中内嵌图片: %d 张" % len(matches))
    if not matches:
        print("错误：未找到任何 base64 图片，请确认源文件")
        return 1

    # 先落盘原图
    plan = []
    for m in matches:
        key = m.group(1)
        ext = m.group(2).lower()
        if ext == "jpeg":
            ext = "jpg"
        name = "%s.%s" % (key, ext)
        raw = base64.b64decode(m.group(3))
        raw_path = os.path.join(IMG_DIR, name)
        with open(raw_path, "wb") as f:
            f.write(raw)
        plan.append((m, name, ext, raw_path, len(raw)))

    # 压缩
    print("\n%-16s %10s %10s %7s %-12s %s" % ("文件", "原始", "压缩后", "quality", "尺寸", "状态"))
    print("-" * 78)
    total_after = 0
    total_before = 0
    for m, name, ext, raw_path, raw_len in plan:
        final_path = os.path.join(IMG_DIR, name)
        new_len, q, size = compress(raw_path, final_path, raw_len)
        total_after += new_len
        total_before += raw_len
        saved = (1 - new_len / raw_len) * 100
        status = "OK" if new_len <= TARGET_MAX_KB * 1024 else "偏大"
        print(
            "%-16s %8.1fKB %8.1fKB %7d %-12s %s (-%.0f%%)"
            % (name, raw_len / 1024, new_len / 1024, q, "%dx%d" % size, status, saved)
        )
        if new_len > raw_len:
            print("    注: %s 保留原始字节（重编码无收益）" % name)

    # 回填路径（从后往前，避免偏移失效）
    new_html = html
    for m, name, ext, _raw_path, _raw_len in reversed(plan):
        replacement = '%s:"./images/%s"' % (m.group(1), name)
        new_html = new_html[: m.start()] + replacement + new_html[m.end() :]

    with open(OUT_HTML, "w", encoding="utf-8", newline="") as f:
        f.write(new_html)

    print("\n原始图片总重: %.1f KB" % (total_before / 1024))
    print("压缩后总重:   %.1f KB" % (total_after / 1024))
    print("HTML 体积:    %.1f KB -> %.1f KB" % (
        os.path.getsize(SRC) / 1024, os.path.getsize(OUT_HTML) / 1024))
    print("输出: %s" % OUT_HTML)

    leftover = list(re.finditer(r"data:image/([a-zA-Z0-9.+-]+);?", new_html))
    print("\n残留 data:image 次数: %d" % len(leftover))
    for m in leftover:
        i = m.start()
        print("  mime=%s  上文: ...%s" % (
            m.group(1), new_html[max(0, i - 60):i].replace("\n", " ")))

    missing = [
        n for _m, n, _e, _p, _l in plan
        if not os.path.exists(os.path.join(IMG_DIR, n))
    ]
    print("引用缺失文件: %s" % (missing or "无"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
