#!/usr/bin/env python3
"""2 つの PDF をページごとの画像で比べる.

両方の PDF を同じ解像度のグレースケール画像にし，ページごとにバイト単位で比べて，
違うページの番号を表示する．PDF のファイルそのものは作成日時などが毎回変わるので比べない．

使いどころ:
  - TeX Live のイメージを更新したとき（docs/texlive.md）
  - スタイルやスクリプトを変えて，版面が変わっていないことを確かめたいとき

画像にするのにホストの Ghostscript（gs）か Poppler（pdftoppm）を使う．どちらもなければ終了する．
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def render(pdf: Path, out: Path, dpi: int) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    if shutil.which("gs"):
        subprocess.run(
            ["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=pgmraw", f"-r{dpi}",
             f"-sOutputFile={out}/p%05d.pgm", str(pdf)],
            check=True,
        )
    elif shutil.which("pdftoppm"):
        subprocess.run(["pdftoppm", "-gray", "-r", str(dpi), str(pdf), str(out / "p")], check=True)
    else:
        sys.exit("gs も pdftoppm もない．どちらかを入れる（Ghostscript か Poppler）")
    return sorted(out.glob("p*.pgm"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("old", type=Path, help="比べる PDF（前）")
    parser.add_argument("new", type=Path, help="比べる PDF（後）")
    parser.add_argument("--dpi", type=int, default=100, help="画像の解像度（既定 100）")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        old = render(args.old, Path(tmp) / "old", args.dpi)
        new = render(args.new, Path(tmp) / "new", args.dpi)
        diff = [i + 1 for i, (a, b) in enumerate(zip(old, new)) if a.read_bytes() != b.read_bytes()]
    if len(old) != len(new):
        print(f"NG: ページ数が違う（{args.old}: {len(old)}，{args.new}: {len(new)}）")
    if diff:
        shown = "，".join(map(str, diff[:50])) + ("，…" if len(diff) > 50 else "")
        print(f"NG: {len(diff)} ページが違う: {shown}")
    if len(old) != len(new) or diff:
        return 1
    print(f"OK: 全 {len(old)} ページが同じ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
