#!/usr/bin/env python3
"""TeX 化の整合性チェック（make check から呼ばれる）.

判定が一つに決まるものだけを検査する．どれかが NG なら make check が失敗する．

- 忠実版のラベル名の番号（thm:1.1.1 など）と，aux に書かれた実際の番号が一致する
  （修正版は番号を変えてよいので見ない）．
- ビルドのログに，未定義の参照，ラベルの重複，飛び先のないリンク，飛び先の重複がない．
- 修正版の \\bref，\\beqref が，修正版で消した（忠実版にだけある）ラベルを指していない．
  \\bref は未定義のラベルを黙ってラベル名の番号で表示するので，ログには出ない．
- 修正版の \\fixat{ID} と corrections/*.md の「### ID」が過不足なく対応する
  （取り下げた ID と「修正版には出ない」ID を考える）．忠実版に修正版の命令がない．
- 種類が「注記」の項目に「**直さなかった理由**」の欄がある．
- 忠実版の \\origpage の番号が，修正版にも過不足なくある．
- 補完・書き換えの印の置き場所と種類（common/scripts/marks.py）．
- make sync の衝突の印が修正版に残っていない．
- しおりの題名から記号が消えていない（hyperref の「Token not allowed in a PDF string」）．

aux と log を読むので，先に両版をビルドしておく（make check はそうする）．
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from book import CORRECTIONS, ORIGINAL, REVISED, ROOT, require_root

ORIGINAL_AUX = ROOT / "tex/build/original.aux"
REVISED_AUX = ROOT / "tex/build/revised.aux"
LOG_FILES = [ROOT / "tex/build/original.log", ROOT / "tex/build/revised.log"]
# ログの 1 行に収まる警告だけを見る（TeX はログを 79 文字で折り返すので，名前の途中で切れることはあるが検出はできる）
LOG_PROBLEM_RE = re.compile(
    r"LaTeX Warning: (?:Reference|Citation) .* undefined"
    r"|LaTeX Warning: There were undefined references"
    r"|LaTeX Warning: Label .* multiply defined"
    r"|LaTeX Warning: There were multiply-defined labels"  # 長いラベル名で上の行が折り返されたときのため
    r"|unreferenced destination"
    r"|duplicate destination"
)
LABEL_PREFIXES = ("thm", "eq", "fig", "sec", "ch", "app")

NEWLABEL_RE = re.compile(r"\\newlabel\{(?P<key>[a-z]+):(?P<num>[^}]+)\}\{\{(?P<val>[^}]*)\}")
BREF_RE = re.compile(r"\\b(?:eq)?ref\{(?P<key>[^}]+)\}")
FIX_RE = re.compile(r"\\fixat\{(?P<id>[^}]+)\}")
REVISED_ONLY_RE = re.compile(r"\\(?:fixat|fixskip|supplied|rewritten|addtag)\b|\\label\{rev:")
CONFLICT_RE = re.compile(r"^(?:<{7}|\|{7}|={7}|>{7})(?: |$)", re.MULTILINE)
MD_FIX_RE = re.compile(r"^###\s+(?P<id>[0-9A-Z]+-\d+)\b", re.MULTILINE)
# % から行末まで（\% は文字の %，\\% は改行の後のコメント）
COMMENT_RE = re.compile(r"(?<!\\)((?:\\\\)*)%.*$", re.MULTILINE)


def strip_comments(text: str) -> str:
    return COMMENT_RE.sub(r"\1", text)


def check_labels() -> list[str]:
    """忠実版のラベル名の番号と実際の番号が一致するか（修正版は番号を変えてよいので見ない）．"""
    if not ORIGINAL_AUX.exists():
        return ["忠実版の aux ファイルがない．先に make でビルドすること"]
    errors: list[str] = []
    for m in NEWLABEL_RE.finditer(ORIGINAL_AUX.read_text(encoding="utf-8")):
        if m["key"] not in LABEL_PREFIXES:
            continue
        val = m["val"].lstrip("{")  # \tag を使った式は {{{1.22}}} のように括弧が多い
        if m["num"] != val:
            errors.append(f"{ORIGINAL_AUX.name}: ラベル {m['key']}:{m['num']} の実際の番号が {val} になっている")
    return errors


def aux_labels(aux: Path) -> set[str]:
    return {f"{m['key']}:{m['num']}" for m in NEWLABEL_RE.finditer(aux.read_text(encoding="utf-8"))}


def check_deleted_refs() -> list[str]:
    """修正版の \\bref，\\beqref が，修正版で消した（忠実版にだけある）ラベルを指していないか．"""
    if not ORIGINAL_AUX.exists() or not REVISED_AUX.exists():
        return ["aux ファイルがそろっていない．先に make で両版をビルドすること"]
    deleted = aux_labels(ORIGINAL_AUX) - aux_labels(REVISED_AUX)
    errors: list[str] = []
    for tex in sorted(REVISED.rglob("*.tex")):
        text = strip_comments(tex.read_text(encoding="utf-8"))
        for m in BREF_RE.finditer(text):
            if m["key"] in deleted:
                line = text.count("\n", 0, m.start()) + 1
                errors.append(
                    f"{tex.relative_to(ROOT)}:{line}: {m['key']} は修正版で消えている"
                    "（\\bref はラベル名の番号を黙って表示するので，別の式や定理を指すことがある）．参照を直す"
                )
    return errors


def check_fix_ids() -> list[str]:
    errors: list[str] = []
    tex_ids: dict[str, set[str]] = {}
    for tex in sorted(REVISED.rglob("*.tex")):
        for m in FIX_RE.finditer(strip_comments(tex.read_text(encoding="utf-8"))):
            tex_ids.setdefault(m["id"], set()).add(str(tex.relative_to(REVISED)))
    for tex in sorted(ORIGINAL.rglob("*.tex")):
        text = strip_comments(tex.read_text(encoding="utf-8"))
        for m in REVISED_ONLY_RE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            errors.append(f"{tex.relative_to(ROOT)}:{line}: 忠実版に修正版の命令 {m.group(0)} がある")
    md_ids: dict[str, str] = {}
    withdrawn: set[str] = set()
    sections: dict[str, str] = {}
    for md in sorted(CORRECTIONS.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        for m in MD_FIX_RE.finditer(text):
            if m["id"] in md_ids:
                errors.append(f"{md.name}: 修正 ID {m['id']} が重複している")
            md_ids[m["id"]] = md.name
        for m in SECTION_RE.finditer(text):
            sections[m["id"]] = m.group(0)
            if WITHDRAWN_MARK in m.group(0):
                withdrawn.add(m["id"])
    for fid in sorted(set(tex_ids) - set(md_ids)):
        errors.append(f"修正 ID {fid}（{', '.join(sorted(tex_ids[fid]))}）の説明が corrections/ にない")
    # 後の修正で置き換えた範囲にあって修正版に出ない ID は，md の項目に「**修正版には出ない**」の欄を書き，
    # 置き換えた修正の ID を挙げる
    for fid in sorted(set(md_ids) - set(tex_ids) - withdrawn):
        note = re.search(rf"^- {re.escape(SUPERSEDED)}(?P<rest>.*)$", sections.get(fid, ""), re.MULTILINE)
        if note is None:
            errors.append(
                f"修正 ID {fid}（{md_ids[fid]}）が修正版のソースで使われていない"
                f"（後の修正の置き換えに含まれたなら，md の項目に「{SUPERSEDED} X-YY で置き換えた範囲にある」と書く）"
            )
        elif not any(ref in tex_ids for ref in ID_REF_RE.findall(note["rest"])):
            errors.append(f"修正 ID {fid}（{md_ids[fid]}）の「{SUPERSEDED}」の欄に，修正版にある置き換えの ID がない")
    for fid in sorted(set(md_ids) & set(tex_ids)):
        if SUPERSEDED in sections.get(fid, ""):
            errors.append(f"修正 ID {fid}（{md_ids[fid]}）は修正版にあるのに「{SUPERSEDED}」の欄がある")
    for fid in sorted(withdrawn & set(tex_ids)):
        errors.append(f"修正 ID {fid}（{md_ids[fid]}）は取り下げたのに修正版のソースに残っている")
    return errors


TABLE_ROW_RE = re.compile(r"^\|\s*(?P<id>[0-9A-Z]+-\d+)\s*\|[^|]*\|(?P<kind>[^|]*)\|", re.MULTILINE)
SECTION_RE = re.compile(r"^### (?P<id>[0-9A-Z]+-\d+)\b.*?(?=^### |^## |\Z)", re.MULTILINE | re.DOTALL)
WITHDRAWN_MARK = "**取り下げ**"
SUPERSEDED = "**修正版には出ない**:"
ID_REF_RE = re.compile(r"(?<![0-9A-Za-z.])[0-9A-Z]{1,3}-\d{2}(?![0-9])")


ORIGPAGE_RE = re.compile(r"\\origpage\{(\d+)\}")


def check_origpages() -> list[str]:
    """忠実版と修正版で，原書のページ境界の印（\\origpage）の番号が同じで，重複がないか．"""
    from check_original import load

    try:
        synced, _ = load()
    except SystemExit as e:  # 記録がない．ほかの検査の結果も出すため，ここで止めない
        return [str(e.code).removeprefix("NG: ")]
    errors: list[str] = []
    for orig_tex in sorted(ORIGINAL.rglob("*.tex")):
        rel = orig_tex.relative_to(ORIGINAL)
        rev_tex = REVISED / rel
        if not rev_tex.exists():
            if str(rel) in synced:
                errors.append(f"忠実版の tex/original/{rel} に対応する修正版の tex/revised/{rel} がない")
            continue  # まだ修正版に写していない新しい章（check_original.py が知らせる）
        orig = ORIGPAGE_RE.findall(strip_comments(orig_tex.read_text(encoding="utf-8")))
        rev = ORIGPAGE_RE.findall(strip_comments(rev_tex.read_text(encoding="utf-8")))
        missing = sorted(set(orig) - set(rev), key=int)
        extra = sorted(set(rev) - set(orig), key=int)
        dup = sorted({n for n in rev if rev.count(n) > 1}, key=int)
        for what, pages in (("がない", missing), ("が忠実版にないページを指している", extra), ("が重複している", dup)):
            if pages:
                listed = "，".join(f"p.{n}" for n in pages)
                errors.append(f"tex/revised/{rel}: 修正版の原書のページ境界の印（\\origpage）{what}: {listed}")
    return errors


def check_notes() -> list[str]:
    errors: list[str] = []
    for md in sorted(CORRECTIONS.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        kinds = {m["id"]: m["kind"] for m in TABLE_ROW_RE.finditer(text)}
        sections = {m["id"]: m.group(0) for m in SECTION_RE.finditer(text)}
        for fid, kind in kinds.items():
            if "注記" in kind and "**直さなかった理由**" not in sections.get(fid, ""):
                errors.append(f"{md.name}: 注記 {fid} に「**直さなかった理由**」の欄がない")
    return errors


PDF_STRING_WARNING_RE = re.compile(
    r"Package hyperref Warning: Token not allowed in a PDF string.*?\n"
    r"\(hyperref\)\s+removing `(?P<token>[^']*)' on input line (?P<line>\d+)"
)
HEADING_RE = re.compile(r"\\(?:chapter|section|subsection|subsubsection|paragraph)\*?[\[{]")


def check_pdf_strings() -> list[str]:
    """しおりの題名から消えた記号を，ログの行番号と見出しのある章ファイルで示す．"""
    chapter_lines = {
        str(tex.relative_to(ROOT / "tex")): tex.read_text(encoding="utf-8").splitlines()
        for tex in sorted(ORIGINAL.rglob("*.tex")) + sorted(REVISED.rglob("*.tex"))
    }
    found: dict[tuple[str, str], set[str]] = {}
    for log in LOG_FILES:
        if not log.exists():
            continue
        text = log.read_text(encoding="utf-8", errors="replace")
        for m in PDF_STRING_WARNING_RE.finditer(text):
            n = int(m["line"])
            # ログには行番号しか出ないので，その行に見出しがある章ファイルを候補として挙げる
            where = [
                f"{name}:{n}"
                for name, lines in chapter_lines.items()
                if n <= len(lines) and HEADING_RE.search(lines[n - 1])
            ]
            key = (", ".join(where) or f"{n} 行目（ファイル不明）", m["token"])
            found.setdefault(key, set()).add(log.stem)
    return [
        f"しおりの題名から `{token}` が消えている（{where}，{'・'.join(sorted(logs))}）．"
        f"\\texorpdfstring でしおり用の文字を指定する"
        for (where, token), logs in sorted(found.items())
    ]


def check_logs() -> list[str]:
    errors: list[str] = []
    for log in LOG_FILES:
        if not log.exists():
            continue
        seen: set[str] = set()
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            if LOG_PROBLEM_RE.search(line) and line not in seen:
                seen.add(line)
                errors.append(f"{log.name}: {line.strip()}")
    return errors


def check_conflicts() -> list[str]:
    errors: list[str] = []
    for tex in sorted(REVISED.rglob("*.tex")):
        text = tex.read_text(encoding="utf-8")
        for m in CONFLICT_RE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            errors.append(f"{tex.relative_to(ROOT)}:{line}: make sync の衝突の印が残っている")
    return errors


def check_marks() -> list[str]:
    from marks import check

    return check()


def main() -> int:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    require_root()
    # make sync の衝突の印が残っていると括弧の対応が崩れ，ほかの検査が止まるので，先に確かめる
    conflicts = check_conflicts()
    if conflicts:
        for e in conflicts:
            print(f"NG: {e}")
        return 1
    errors = (
        check_labels()
        + check_logs()
        + check_deleted_refs()
        + check_fix_ids()
        + check_notes()
        + check_origpages()
        + check_marks()
        + check_conflicts()
        + check_pdf_strings()
    )
    for e in errors:
        print(f"NG: {e}")
    if errors:
        return 1
    print("OK: ラベル番号・参照とリンク・消した参照先・修正 ID・注記の欄・原書のページ境界の印・補完と書き換えの印・衝突の残り・しおりの題名はすべて整合している")
    return 0


if __name__ == "__main__":
    sys.exit(main())
