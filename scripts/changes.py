#!/usr/bin/env python3
"""忠実版と修正版の差分の検査（警告のみ．make check は失敗しない）.

各ファイルについて，忠実版（tex/original/）と修正版（tex/revised/）を行単位で比べ，
変わった行のかたまり（間に残った行が GAP_ANY 行以下か，GAP 行以下でどれも空行・\\begin{…}・\\end{…}・
\\[・\\] などならひとまとめにする）ごとに次を調べる．

1. 目印のない変更
   修正版を ID なしで直した（誤植を黙って直した，忠実版の誤り（書き起こしや訳の誤り）を忠実版でなく修正版で直した）
   おそれのある変更を探す．\\supplied・\\rewritten の中の変更と，コメントの中身や，段落の区切りを
   変えない空白だけの変更は除く（空行を足したり消したりする変更は数える）．
   - かたまりの修正版の側に \\fixat が 1 つもない．
   - \\fixat のあるかたまりでも，文字単位で比べて，変わらない部分が ANCHOR_GAP 字以上続く所で
     変更を区切ったまとまりの前後 ANCHOR_GAP 字以内に \\fixat がない．
   長い書き換えの途中（原文がそのまま残った所の後）が引っかかったときは，そこにも同じ ID の
   \\fixat を置けばよい．目印から ANCHOR_GAP 字以内の変更は，その修正の一部とみなされる．

2. 印のない補完・書き換え
   かたまりの中の各文を，その文の終わりより前で最後の \\fixat の修正に割り当て，忠実版にない文
   （SENTENCE_END_RE で区切って数える．忠実版の文と SIMILAR 以上似ている文は，忠実版の文を直したものとみなして数えない）が
   1 文でもある修正を探す．その ID の種類が補完・注記・簡略化・書き換えなのに，\\supplied も
   \\rewritten もなければ（外側の印に覆われているものは除く）警告する．
   common/docs/conventions.md の「印」の基準で印を付けるか確かめる．

make check から呼ばれる．
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass

from book import ORIGINAL, REVISED, require_root
from marks import COMMENT_RE, MARK_RE, blank_comments, fix_kinds, group_end, mark_for_kind

GAP = 5  # 間に残った行がこれ以下で，どれも trivial ならまとめる
GAP_ANY = 2  # 間に残った行がこれ以下なら，中身によらずまとめる
ANCHOR_GAP = 80  # 変わらない部分がこの字数以上続く所で変更のまとまりを区切る．まとまりごとに目印が要る
SIMILAR = 0.6  # これ以上似ている文は，忠実版の文を直したものとみなす（新しい文に数えない）
# 文の終わり: 全角の「．」「。」と，空白・\・}・行末が続く欧文のピリオド（句読点が「, .」の本のため．
# 1.5 のような数の中のピリオドは区切らない）
SENTENCE_END_RE = re.compile(r"[．。]|\.(?=[\s\\}]|$)")
FIXAT_RE = re.compile(r"\\fixat\{(?P<id>[^}]+)\}")
# 文から除いて何も残らなければ，新しい文に数えない（目印，環境の始まりと終わり，括弧，空白）
BARE_RE = re.compile(r"\\fixat\{[^}]*\}|\\(?:begin|end)\{[^}]*\}(?:\[[^\]]*\])?|[{}\s．]")


@dataclass
class Block:
    name: str
    orig: tuple[int, int]  # 忠実版の行の範囲（0 始まり，終わりを含まない）
    rev: tuple[int, int]  # 修正版の行の範囲


TRIVIAL_RE = re.compile(r"\s*(?:\\(?:begin|end)\{[^}]*\}(?:\[[^\]]*\])?|\\\[|\\\]|%.*)?\s*")


def trivial(line: str) -> bool:
    """長い書き換えの途中にそのまま残りやすい行（空行，\\begin{…}，\\end{…}，\\[，\\]，コメント）か．"""
    return TRIVIAL_RE.fullmatch(line) is not None


def blocks(a: list[str], b: list[str], name: str) -> list[Block]:
    """変わった行のかたまり．間に残った行が GAP_ANY 行以下か，GAP 行以下でどれも trivial なら 1 つにまとめる．"""
    out: list[Block] = []
    cur: list[int] | None = None
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            mergeable = i2 - i1 <= GAP_ANY or (i2 - i1 <= GAP and all(trivial(x) for x in a[i1:i2]))
            if cur is not None and not mergeable:
                out.append(Block(name, (cur[0], cur[1]), (cur[2], cur[3])))
                cur = None
            elif cur is not None:
                cur[1], cur[3] = i2, j2
            continue
        if cur is None:
            cur = [i1, i2, j1, j2]
        else:
            cur[1], cur[3] = i2, j2
    if cur is not None:
        out.append(Block(name, (cur[0], cur[1]), (cur[2], cur[3])))
    return out


def normalize(lines: list[str]) -> str:
    """コメントの中身と，段落の区切りにならない空白の違いを消す（空行は \\par，行末の % は残す）．"""
    out = []
    for line in COMMENT_RE.sub(r"\1%", "\n".join(lines)).split("\n") if lines else []:
        line = line.strip()
        out.append(line if line else "\\par")
    return re.sub(r"\s+", " ", " ".join(out))


def comparable(text: str) -> str:
    """文字単位で比べるための形．コメントの中身を空白にし（% は残す），長さを保つ．"""
    return COMMENT_RE.sub(lambda m: m.group(1) + "%" + " " * (len(m.group(0)) - len(m.group(1)) - 1), text)


def unanchored_changes(o: str, r: str) -> list[int]:
    """r（修正版のかたまり）の中で，目印のない変更の位置．

    \\fixat を除いて文字単位で比べ，変わらない部分が ANCHOR_GAP 字以上続く所で区切った
    変更のまとまりのうち，前後 ANCHOR_GAP 字以内に \\fixat がないものの先頭の位置（r の中の文字位置）を返す．
    空白だけの違い（段落の区切りを足したり消したりするものを除く）は変更とみなさない．
    """
    oc = comparable(o)
    rfull = comparable(r)
    # \fixat を除いた文字列と，その各文字の r での位置，除いた目印の位置
    rc_chars: list[str] = []
    rpos: list[int] = []
    anchors: list[int] = []
    i = 0
    for m in FIXAT_RE.finditer(rfull):
        rc_chars.extend(rfull[i : m.start()])
        rpos.extend(range(i, m.start()))
        anchors.append(len(rc_chars))
        i = m.end()
    rc_chars.extend(rfull[i:])
    rpos.extend(range(i, len(rfull)))
    rpos.append(len(rfull))
    rc = "".join(rc_chars)
    found: list[int] = []
    first: int | None = None  # いまのまとまりの最初の変更の位置（rc の位置）
    last = 0  # いまのまとまりの最後の変更の終わり

    def close() -> None:
        if first is not None and not any(first - ANCHOR_GAP <= a <= last + ANCHOR_GAP for a in anchors):
            found.append(rpos[first])

    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, oc, rc, autojunk=False).get_opcodes():
        if tag == "equal":
            if j2 - j1 >= ANCHOR_GAP:
                close()
                first = None
            continue
        old, new = oc[i1:i2], rc[j1:j2]
        if not old.strip() and not new.strip() and old.count("\n") < 2 and new.count("\n") < 2:
            continue  # 空白だけの違い
        if first is None:
            first = j1
        last = j2
    close()
    return found


def sentences(text: str) -> list[str]:
    text = MARK_RE.sub("{", text)  # 印の命令名を消す（中身は残す）
    text = re.sub(r"\\fixat\{[^}]*\}|\\fixskip\{[^}]*\}\{[^}]*\}|\\origpage\{[^}]*\}", "", text)
    # 空白を除く前に文の終わりで区切る（欧文のピリオドは後ろの空白で見分ける）
    parts = SENTENCE_END_RE.split(blank_comments(text))
    return [s for s in (re.sub(r"\s+", "", p) for p in parts) if s]


def similar_in(s: str, old: list[str]) -> bool:
    """s が old のどれかと同じか，少し直しただけ（似ている度合いが SIMILAR 以上）か．"""
    if s in old:
        return True
    for t in old:
        sm = difflib.SequenceMatcher(None, s, t, autojunk=False)
        if sm.real_quick_ratio() >= SIMILAR and sm.quick_ratio() >= SIMILAR and sm.ratio() >= SIMILAR:
            return True
    return False


def marked_ranges(text: str) -> list[tuple[int, int]]:
    """印（\\supplied{…}，\\rewritten{…}）が覆う文字の範囲．"""
    return [(m.start(), group_end(text, m.end() - 1)) for m in MARK_RE.finditer(text)]


def check() -> tuple[list[str], list[str]]:
    kinds = fix_kinds()
    unmarked_changes: list[str] = []
    unmarked_supplements: list[str] = []
    for orig_tex in sorted(ORIGINAL.rglob("*.tex")):
        rel = orig_tex.relative_to(ORIGINAL)
        rev_tex = REVISED / rel
        if not rev_tex.exists():
            continue
        a = orig_tex.read_text(encoding="utf-8").split("\n")
        rev_text = rev_tex.read_text(encoding="utf-8")
        b = rev_text.split("\n")
        # 修正版の各行の先頭の文字位置（印に覆われているかを調べるため）
        starts = [0]
        for line in b:
            starts.append(starts[-1] + len(line) + 1)
        covered = marked_ranges(blank_comments(rev_text))
        for blk in blocks(a, b, str(rel)):
            o = "\n".join(a[blk.orig[0] : blk.orig[1]])
            r = "\n".join(b[blk.rev[0] : blk.rev[1]])
            where = f"tex/revised/{rel}:{blk.rev[0] + 1}（忠実版 {blk.orig[0] + 1} 行目）"
            if normalize(a[blk.orig[0] : blk.orig[1]]) == normalize(b[blk.rev[0] : blk.rev[1]]):
                continue  # コメントの中身や，段落の区切りを変えない空白だけの変更
            s0, e0 = starts[blk.rev[0]], starts[blk.rev[1]]
            ids = FIXAT_RE.findall(blank_comments(r))
            if any(cs <= s0 and e0 - 1 <= ce for cs, ce in covered):
                pass  # かたまり全体が印の中
            elif not ids:
                # 目印がなくても，変更がすべて印の中にあるなら（印の始まりの目印は前のかたまりにある）よい
                at_list = [s0 + pos for pos in unanchored_changes(o, r)]
                if all(any(cs <= at < ce for cs, ce in covered) for at in at_list):
                    continue
                head = re.sub(r"\s+", " ", r.strip())[:60]
                unmarked_changes.append(f"{where}: 変更に \\fixat がない: {head}…")
                continue
            else:
                for pos in unanchored_changes(o, r):
                    at = s0 + pos
                    if any(cs <= at < ce for cs, ce in covered):
                        continue
                    line = rev_text.count("\n", 0, at) + 1
                    ls = rev_text.rfind("\n", 0, at) + 1
                    head = re.sub(r"\s+", " ", rev_text[max(ls, at - 15) : at + 30])
                    unmarked_changes.append(
                        f"tex/revised/{rel}:{line}: 近くに \\fixat のない変更（前後 {ANCHOR_GAP} 字以内の変更にも目印がない）: …{head}…"
                    )
            # 修正ごとの範囲は分からないので，かたまりの各文を，その文の終わりより前で最後の \fixat の修正に数える
            old = sentences(o)
            old_text = "".join(old)
            body = blank_comments(rev_text)
            anchors = list(FIXAT_RE.finditer(body, s0, e0))
            new_count: dict[int, int] = {}
            pos = s0
            for end in [m.end() for m in SENTENCE_END_RE.finditer(body[s0:e0])] + [e0 - s0]:
                sent_start, sent_end = pos, s0 + end
                pos = sent_end
                owner = [k for k, m in enumerate(anchors) if m.start() < sent_end]
                if not owner:
                    continue
                # 印の外にある部分だけを見る（印の境目にまたがる文の，印の中の部分は数えない）
                outside = "".join(
                    ch for i, ch in enumerate(body[sent_start:sent_end], sent_start)
                    if not any(cs <= i < ce for cs, ce in covered)
                )
                if not BARE_RE.sub("", outside):
                    continue  # 印の中か，目印・環境・括弧だけ
                # 印の前後に残った原文の切れ端（文の途中で印が始まるときなど）は，忠実版の文章に含まれていれば新しい文に数えない
                if all(similar_in(x, old) or x in old_text for x in sentences(outside)):
                    continue
                new_count[owner[-1]] = new_count.get(owner[-1], 0) + 1
            for k, n in new_count.items():
                m = anchors[k]
                fid = m["id"]
                if not mark_for_kind(kinds.get(fid, "")):
                    continue
                if any(cs <= m.start() < ce for cs, ce in covered):
                    continue
                line = rev_text.count("\n", 0, m.start()) + 1
                unmarked_supplements.append(
                    f"tex/revised/{rel}:{line} {fid}（{kinds.get(fid)}）: 忠実版にない文が {n} 文あるのに"
                    f" \\supplied も \\rewritten もない"
                )
    return unmarked_changes, unmarked_supplements


def warnings() -> list[str]:
    changes, supplements = check()
    return [f"目印のない変更: {w}" for w in changes] + [f"印のない補完・書き換え: {w}" for w in supplements]


def main() -> int:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    require_root()
    ws = warnings()
    for w in ws:
        print(f"要確認: {w}")
    if not ws:
        print("OK: 修正版の変更にはすべて目印があり，補完・書き換えには印がある")
    return 0


if __name__ == "__main__":
    sys.exit(main())
