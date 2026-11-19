#!/usr/bin/env python3
"""TeX 化の整合性チェック.

1. ラベルの番号チェック
   ラベルは「接頭辞:原書の番号」（例: thm:1.1.1, eq:1.12）で付ける規約なので，
   ビルド後の aux に書かれた実際の番号がラベル名の番号と一致するかを確かめる．
   一致しなければ，書き起こしで定理や式を取りこぼした／重複させた可能性がある．

2. 修正 ID のチェック
   修正版のソース（tex/revised/ の下の *.tex）の目印 \\fixat{ID} の ID と，
   corrections/*.md の見出し「### ID ...」が過不足なく対応しているかを確かめる．
   項目の中に「**取り下げ**」の欄がある ID は，修正版から外した補完の記録なので，
   逆に修正版のソースに残っていないことを確かめる．
   後の修正で置き換えた範囲にあって修正版に出ない ID は，md の項目の「**修正版には出ない**」の欄で
   置き換えた修正の ID を挙げていればよい．
   忠実版のソース（tex/original/）に \\fixat や \\supplied などの修正版の命令がないことも確かめる．

3. 注記のチェック（エラー）
   corrections/*.md の一覧で種類が「注記」の項目は，原書の誤りを直さずに注記にとどめたもの．
   その項目（### ID）に「**直さなかった理由**」の欄があるかを確かめる．

4. 原書のページ境界の印のチェック（エラー）
   \\origpage{n} は忠実版のソースにしかないと修正版の余白に出ない．
   各章で，忠実版のソースにある \\origpage の番号がすべて修正版のソースにもあるかを確かめる
   （書き換えた範囲の中にページ境界があるときは，修正版の対応する位置にも \\origpage を置く）．

5. メモに残った原書の誤りの検出（警告のみ．make check は失敗しない）
   「修正しなかった点・メモ」の項目のうち，「偽」「成り立たない」「不正確」「穴」「隙間」などと書いているのに
   どの修正 ID にも結びついていないものを列挙する．原書の誤りが PDF に出ずに
   md のメモだけに残っていないかを人が確かめるためのもの（common/docs/conventions.md「原書の誤りを見つけたとき」）．

6. 補完・書き換えの印のチェック（エラー）
   修正版で原書にない議論を囲む印（\\supplied，\\rewritten）が，common/scripts/marks.py の基準どおりの
   場所（\\fixat{ID} の直後）にあり，種類が ID の種類と合っているかを確かめる．

7. 参照とリンクのチェック（エラー）
   ビルドのログ（tex/build/*.log）に，未定義の参照，ラベルの重複，飛び先のないリンク
   （LuaTeX の ``unreferenced destination''），飛び先の重複の警告がないかを確かめる．
   これらの警告ではビルドは止まらず，長い出力に埋もれやすいので，ここでエラーにする．

8. 2 つの版の番号のチェック（エラー）
   忠実版と修正版の両方にあるラベルは，同じ番号でなければならない．また，両方にある章の終わりの
   カウンタの値（節・式・定理・脚注など．\\recordchaptercounts が aux に書く）も同じでなければならない．
   修正版で式や定理，脚注を消したり足したりして以降の番号がずれていないかを確かめる
   （直し方は common/docs/conventions.md の「番号」）．

9. マージの衝突の残りのチェック（エラー）
   make sync（忠実版の変更を修正版に取り込む）で衝突した箇所の印
   （<<<<<<<，=======，>>>>>>>）が修正版のソースに残っていないかを確かめる．

10. PDF のしおりのチェック（エラー）
   ビルドのログに hyperref の「Token not allowed in a PDF string」が出ていないかを確かめる．
   見出しに数式などを書くと，しおり（PDF のアウトライン）の題名からその部分が黙って消える．
   \\texorpdfstring{$\\varepsilon$}{ε} のようにしおり用の文字を指定して直す．

11. 忠実版と修正版の差分の検査（警告のみ．make check は失敗しない）
   修正版の変更に \\fixat がない箇所と，印（\\supplied，\\rewritten）の要りそうな補完・書き換えに
   印がない箇所を「要確認」として表示する（common/scripts/changes.py）．

make check から呼ばれる．aux と log を読むので，先に両版をビルドしておく（make check はそうする）．
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from book import CORRECTIONS, ORIGINAL, REVISED, ROOT, require_root

AUX_FILES = [ROOT / "tex/build/original.aux", ROOT / "tex/build/revised.aux"]
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
FIX_RE = re.compile(r"\\fixat\{(?P<id>[^}]+)\}")
REVISED_ONLY_RE = re.compile(r"\\(?:fixat|fixskip|supplied|rewritten)\b")
CONFLICT_RE = re.compile(r"^(?:<{7}|\|{7}|={7}|>{7})(?: |$)", re.MULTILINE)
MD_FIX_RE = re.compile(r"^###\s+(?P<id>[0-9A-Z]+-\d+)\b", re.MULTILINE)
# % から行末まで（\% は文字の %，\\% は改行の後のコメント）
COMMENT_RE = re.compile(r"(?<!\\)((?:\\\\)*)%.*$", re.MULTILINE)


def strip_comments(text: str) -> str:
    return COMMENT_RE.sub(r"\1", text)


def check_labels() -> list[str]:
    errors: list[str] = []
    found_any = False
    for aux in AUX_FILES:
        if not aux.exists():
            continue
        found_any = True
        for m in NEWLABEL_RE.finditer(aux.read_text(encoding="utf-8")):
            if m["key"] not in LABEL_PREFIXES:
                continue
            val = m["val"].lstrip("{")  # \tag を使った式は {{{1.22}}} のように括弧が多い
            if m["num"] != val:
                errors.append(
                    f"{aux.name}: ラベル {m['key']}:{m['num']} の実際の番号が {val} になっている"
                )
    if not found_any:
        errors.append("aux ファイルがない．先に make でビルドすること")
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
MEMO_HEAD = "## 修正しなかった点・メモ"
WITHDRAWN_MARK = "**取り下げ**"
SUPERSEDED = "**修正版には出ない**:"
# 原書の誤りを述べていそうな表現と，それを打ち消す表現
ERROR_WORDS_RE = re.compile(r"偽で|偽に|偽と|偽である|成り立たない|不正確|反例|穴|隙間|抜けて|欠けて|使えない|足りない")
NEGATED_RE = re.compile(r"誤りではない|誤りとまではいえない|不正確ではない")
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


def find_unfixed_errors_in_memos() -> list[str]:
    warnings: list[str] = []
    for md in sorted(CORRECTIONS.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        if MEMO_HEAD not in text:
            continue
        memo = text.split(MEMO_HEAD, 1)[1]
        for item in re.split(r"\n(?=- )", memo):
            item = item.strip()
            if not item.startswith("- "):
                continue
            if ERROR_WORDS_RE.search(item) and not ID_REF_RE.search(item) and not NEGATED_RE.search(item):
                head = re.sub(r"\s+", " ", item)[:70]
                warnings.append(f"{md.name}: {head}…")
    return warnings


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


def read_labels(aux: Path) -> dict[str, str]:
    return {f"{m['key']}:{m['num']}": m["val"].lstrip("{") for m in NEWLABEL_RE.finditer(aux.read_text(encoding="utf-8"))}


COUNTS_RE = re.compile(r"\\[a-z]+@counts\{(?P<name>[^}]+)\}\{(?P<vals>[^}]*)\}")


def read_counts(aux: Path) -> dict[str, str]:
    """章の終わりのカウンタの値（\\recordchaptercounts が aux に書いたもの）．"""
    return {m["name"]: " ".join(m["vals"].split()) for m in COUNTS_RE.finditer(aux.read_text(encoding="utf-8"))}


def check_numbering() -> list[str]:
    """忠実版と修正版に共通するラベルの番号と，両方にある章の終わりのカウンタの値が一致するか．"""
    if not all(aux.exists() for aux in AUX_FILES):
        return ["aux ファイルがそろっていない．先に make で両版をビルドすること"]
    orig, rev = (read_labels(aux) for aux in AUX_FILES)
    errors = [
        f"ラベル {key} の番号が忠実版では {orig[key]}，修正版では {rev[key]}（修正版で番号がずれている）"
        for key in sorted(set(orig) & set(rev))
        if orig[key] != rev[key]
    ]
    oc, rc = (read_counts(aux) for aux in AUX_FILES)
    if not oc:
        errors.append("aux に章の終わりのカウンタの値がない（main.tex の差し込み口が \\recordchaptercounts を呼んでいるか確かめる）")
    for name in sorted(set(oc) & set(rc)):
        if not (ORIGINAL / f"{name}.tex").exists() or not (REVISED / f"{name}.tex").exists():
            continue
        if oc[name] != rc[name]:
            a, b = dict(x.split("=") for x in oc[name].split()), dict(x.split("=") for x in rc[name].split())
            diff = "，".join(f"{k} が {a.get(k)} と {b.get(k)}" for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k))
            errors.append(
                f"{name}: 章の終わりの番号が忠実版と修正版で違う（{diff}）．"
                f"修正版で式・定理・脚注を足したり消したりしたなら \\tag や \\fixskip で揃える"
            )
    return errors


def check_conflicts() -> list[str]:
    errors: list[str] = []
    for tex in sorted(REVISED.rglob("*.tex")):
        text = tex.read_text(encoding="utf-8")
        for m in CONFLICT_RE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            errors.append(f"{tex.relative_to(ROOT)}:{line}: make sync の衝突の印が残っている")
    return errors


def change_warnings() -> list[str]:
    from changes import warnings

    return warnings()


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
        + check_numbering()
        + check_logs()
        + check_fix_ids()
        + check_notes()
        + check_origpages()
        + check_marks()
        + check_conflicts()
        + check_pdf_strings()
    )
    for w in find_unfixed_errors_in_memos():
        print(f"要確認: メモにだけ原書の誤りが書かれている可能性: {w}")
    for w in change_warnings():
        print(f"要確認: {w}")
    for e in errors:
        print(f"NG: {e}")
    if errors:
        return 1
    print("OK: ラベル番号・2 つの版の番号・参照とリンク・修正 ID・注記の欄・原書のページ境界の印・補完と書き換えの印・衝突の残り・しおりの題名はすべて整合している")
    return 0


if __name__ == "__main__":
    sys.exit(main())
