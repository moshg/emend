#!/usr/bin/env python3
"""修正版の本文で，原書にない議論を囲む印（\\supplied と \\rewritten）の検査.

印を付ける基準（common/docs/conventions.md の「印」と common/docs/review.md の「どの作業にも当てはまること」）:
  - 修正 ID の一覧の種類に「簡略化」か「書き換え」を含む修正は \\rewritten（［書き換え］…［書き換えここまで］），
    そうでなく「補完」か「注記」を含む修正は \\supplied（［補完］…［補完ここまで］）で囲む．
  - 長さによらず，その種類の修正はすべて囲む（印の付け忘れは common/scripts/changes.py が警告する）．
  - 印の中にさらに印は付けない（外側の印が覆う）．
  - 印は，その修正の目印 \\fixat{ID} の直後に置く．修正が 1 つの証明環境だけのときは，
    \\fixat{ID}\\begin{proof} の直後に置く（\\fixat{ID}\\begin{proof}\\supplied{…}\\end{proof}）．
    印の ID（巻末の索引の「（補完）」「（書き換え）」）は直前の \\fixat から決まる．

ここでは，印が目印の直後にあること，印の種類が ID の種類と合うこと，印が入れ子になっていないことを確かめる．
make check から呼ばれる．
"""
from __future__ import annotations

import argparse
import re
import sys

from book import CORRECTIONS, REVISED, ROOT, require_root

# % から行末まで（\% は文字の %，\\% は改行の後のコメント）．group(1) は % の前の \\ の並び
COMMENT_RE = re.compile(r"(?<!\\)((?:\\\\)*)%.*$", re.MULTILINE)
TABLE_ROW_RE = re.compile(r"^\|\s*(?P<id>[0-9A-Z]+-\d+)\s*\|[^|]*\|(?P<kind>[^|]*)\|", re.MULTILINE)
MARK_RE = re.compile(r"\\(supplied|rewritten)\{")
# 印の直前に来てよいもの: \fixat{ID}，空白，\begin{proof}[…]
BEFORE_MARK_RE = re.compile(r"\\fixat\{(?P<id>[^}]+)\}\s*(?:\\begin\{proof\}(?:\[[^\]]*\])?\s*)?$")


def fix_kinds() -> dict[str, str]:
    kinds: dict[str, str] = {}
    for md in sorted(CORRECTIONS.glob("*.md")):
        for m in TABLE_ROW_RE.finditer(md.read_text(encoding="utf-8")):
            kinds[m["id"]] = m["kind"].strip()
    return kinds


def mark_for_kind(kind: str) -> str | None:
    if "簡略化" in kind or "書き換え" in kind:
        return "rewritten"
    if "補完" in kind or "注記" in kind:
        return "supplied"
    return None


def group_end(text: str, i: int) -> int:
    """text[i] の { に対応する } の次の位置．"""
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    raise ValueError("閉じ括弧がない")


def blank_comments(text: str) -> str:
    """コメントを同じ長さの空白にする（位置と行番号を保つ）．"""
    return COMMENT_RE.sub(lambda m: m.group(1) + " " * (len(m.group(0)) - len(m.group(1))), text)


def check() -> list[str]:
    kinds = fix_kinds()
    errors: list[str] = []
    for tex in sorted(REVISED.rglob("*.tex")):
        text = blank_comments(tex.read_text(encoding="utf-8"))
        open_until = -1  # いま中にいる印の終わり
        for m in MARK_RE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            where = f"{tex.relative_to(ROOT)}:{line}"
            mark = m[1]
            end = group_end(text, m.end() - 1)
            if m.start() < open_until:
                errors.append(f"{where}: \\{mark} が外側の印の中にある（外側の印が覆うので要らない）")
                continue
            open_until = end
            b = BEFORE_MARK_RE.search(text, 0, m.start())
            if b is None:
                errors.append(
                    f"{where}: \\{mark} の直前に \\fixat{{ID}} がない（\\fixat{{ID}} か \\fixat{{ID}}\\begin{{proof}} の直後に置く）"
                )
                continue
            fid = b["id"]
            want = mark_for_kind(kinds.get(fid, ""))
            if want is None:
                errors.append(f"{where}: {fid} の種類（{kinds.get(fid, '一覧にない')}）には印を付けない")
            elif want != mark:
                errors.append(f"{where}: {fid} は \\{mark} ではなく \\{want} で囲む（種類が {kinds.get(fid)}）")
    return errors


def main() -> int:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    require_root()
    errors = check()
    for e in errors:
        print(f"NG: {e}")
    if not errors:
        print("OK: 補完・書き換えの印は基準どおり")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
