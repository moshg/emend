#!/usr/bin/env python3
"""忠実版の変更を修正版に取り込んだかの検査と，その取り込み（3-way マージ）.

忠実版（tex/original/）と修正版（tex/revised/）は別のソースである．忠実版を直したとき
（書き起こしや訳の誤りが後から見つかったときなど）は，同じ直しを修正版にも入れなければならない．
そのため，最後に修正版へ取り込んだときの忠実版の各ファイルの git の blob ID を
tex/original-sync.json の "synced" に記録しておく．取り込みで衝突し，まだ解いていない
ファイルは "unresolved" に挙げる．

オプションなし（make check）:
  - 忠実版のファイルが記録と違えば NG（取り込み忘れか，意図しない変更）．
  - "unresolved" にあるファイルは NG（衝突を解いてから make sync を実行し直す）．
  - 記録になく，修正版もまだない忠実版のファイル（書き起こし中の新しい章）は NG にせず，知らせるだけにする．
  - 記録にあるのに忠実版から消えたファイルは NG．

--sync（make sync）:
  1. 先にすべての前提（記録した忠実版の中身が git にあるか，修正版のファイルがあるか）を確かめ，
     1 つでも満たさなければ何も変えずに止まる．
  2. 記録と違う忠実版のファイルについて，記録した中身から今の忠実版への変更を
     git merge-file で修正版の同じファイルに取り込む．新しい忠実版のファイルは修正版にそのまま写す．
     ファイルごとに記録を更新する（途中で止まっても，取り込んだファイルを二度取り込まない）．
  3. 衝突したファイルは <<<<<<< … >>>>>>> を残し，"unresolved" に挙げる．手で直してから
     make sync を実行し直すと，印が残っていないことを確かめて "unresolved" から外す．
     衝突をやり直したいときは，修正版のファイルを戻すだけでなく original-sync.json も戻す
     （戻さないと，忠実版の直しが修正版に入らないまま取り込み済みになる）．

記録がなく，修正版のファイルもまだない新しい本では，記録を空とみなす（最初の make sync で作る）．
修正版があるのに記録がなければ NG にする（git から戻す）．

ブランチをまとめるときに original-sync.json が衝突したら，make sync をやり直さず，
両方のブランチの行をすべて残し，両方にあるファイルの行は，そのファイルを変えた側の値を取る
（git hash-object tex/original/<名前> と一致する）．

記録した忠実版の中身は git から取り出すので，その中身が一度はコミットされているか，
--sync が git hash-object -w で書いた object が手元に残っている必要がある．
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from book import ORIGINAL, REVISED, ROOT, SYNC_STORE as STORE, require_root

CONFLICT_RE = re.compile(r"^(?:<{7}|\|{7}|={7}|>{7})(?: |$)", re.MULTILINE)


def blob_id(path: Path) -> str:
    """git に入れたときの blob ID（git hash-object．改行の変換などのフィルタも git と同じに扱う）．"""
    r = git("hash-object", str(path))
    if r.returncode == 0:
        return r.stdout.decode().strip()
    # git がないとき（フィルタは考えない）
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def current() -> dict[str, str]:
    return {p.name: blob_id(p) for p in sorted(ORIGINAL.glob("*.tex"))}


def load() -> tuple[dict[str, str], list[str]]:
    if not STORE.exists():
        if not any(REVISED.glob("*.tex")):
            return {}, []  # 新しい本: 最初の make sync で記録を作る
        sys.exit(f"NG: 修正版があるのに {STORE.relative_to(ROOT)} がない（git から戻す）")
    data = json.loads(STORE.read_text(encoding="utf-8"))
    return dict(data["synced"]), list(data.get("unresolved", []))


def save(synced: dict[str, str], unresolved: list[str]) -> None:
    data = {"synced": dict(sorted(synced.items())), "unresolved": sorted(set(unresolved))}
    STORE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def changed(synced: dict[str, str], now: dict[str, str]) -> list[str]:
    return [name for name in sorted(set(now) | set(synced)) if now.get(name) != synced.get(name)]


def is_new(name: str, synced: dict[str, str]) -> bool:
    """記録になく，修正版もまだない忠実版のファイル（書き起こし中の新しい章）．"""
    return name not in synced and not (REVISED / name).exists()


def has_conflicts(path: Path) -> bool:
    return path.exists() and CONFLICT_RE.search(path.read_text(encoding="utf-8")) is not None


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=False, capture_output=True)


def sync(synced: dict[str, str], unresolved: list[str], now: dict[str, str]) -> int:
    # 衝突を解いたファイルを "unresolved" から外す
    for name in list(unresolved):
        if has_conflicts(REVISED / name):
            print(f"NG: tex/revised/{name} に衝突の印が残っている．直してから make sync")
        else:
            unresolved.remove(name)
            print(f"衝突を解いたものとして記録した: tex/revised/{name}")
    todo = changed(synced, now)
    # 何かを変える前に，すべての前提を確かめる
    problems = []
    for name in todo:
        if name not in now:
            problems.append(f"tex/original/{name} が消えた．修正版の扱いを手で決め，記録から外す")
        elif name in synced:
            if git("cat-file", "-e", synced[name]).returncode != 0:
                problems.append(f"記録した忠実版の中身 {synced[name]}（tex/original/{name}）が git にない．取り込みは手で行い，記録を直す")
            if not (REVISED / name).exists():
                problems.append(f"tex/revised/{name} がない")
            if name in unresolved:
                problems.append(f"tex/revised/{name} の前の衝突をまだ解いていない")
    if problems:
        for p in problems:
            print(f"NG: {p}")
        print("何も変えずに止めた")
        save(synced, unresolved)
        return 1
    for name in todo:
        orig, rev = ORIGINAL / name, REVISED / name
        if name not in synced:
            if rev.exists():
                print(f"新しい忠実版のファイル tex/original/{name}: 修正版 tex/revised/{name} はもうあるので，そのまま記録する")
            else:
                rev.parent.mkdir(parents=True, exist_ok=True)
                rev.write_bytes(orig.read_bytes())
                print(f"新しい忠実版のファイル tex/original/{name} を tex/revised/{name} に写した")
        else:
            base = git("cat-file", "blob", synced[name])
            with tempfile.NamedTemporaryFile("wb", suffix=".tex") as f:
                f.write(base.stdout)
                f.flush()
                r = git("merge-file", "-L", "修正版", "-L", "前の忠実版", "-L", "今の忠実版", str(rev), f.name, str(orig))
            if r.returncode < 0 or r.returncode > 127:
                print(f"NG: git merge-file が失敗した: {r.stderr.decode()}")
                save(synced, unresolved)
                return 1
            if r.returncode:
                unresolved.append(name)
                print(f"衝突 {r.returncode} か所: tex/revised/{name} の <<<<<<< … >>>>>>> を手で直し，make sync を実行し直す")
            else:
                print(f"取り込んだ: tex/original/{name} → tex/revised/{name}")
        # 次に取り込むときの基準として，今の忠実版の中身を git の object に書いておく
        w = git("hash-object", "-w", str(orig))
        if w.returncode != 0 or w.stdout.decode().strip() != now[name]:
            print(f"NG: tex/original/{name} を git の object に書けなかった: {w.stderr.decode()}")
            save(synced, unresolved)
            return 1
        synced[name] = now[name]
        save(synced, unresolved)
    save(synced, unresolved)
    return 1 if unresolved else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sync", action="store_true", help="忠実版の変更を修正版に取り込み，記録を更新する（make sync）")
    args = parser.parse_args()
    require_root()
    now = current()
    synced, unresolved = load()
    if args.sync:
        return sync(synced, unresolved, now)
    bad = False
    for name in changed(synced, now):
        if name not in now:
            print(f"NG: 記録にある忠実版 tex/original/{name} がない（消したなら，修正版の扱いを決めて記録から外す）")
            bad = True
        elif is_new(name, synced):
            print(f"未同期: 新しい忠実版 tex/original/{name}（校正が済んだら make sync で修正版に写す）")
        else:
            print(f"NG: 忠実版 tex/original/{name} が，最後に修正版へ取り込んだときから変わっている"
                  f"（意図した変更なら make sync で修正版に取り込む）")
            bad = True
    for name in unresolved:
        print(f"NG: tex/revised/{name} の make sync の衝突をまだ解いていない（直してから make sync）")
        bad = True
    if bad:
        return 1
    print(f"OK: 忠実版の変更はすべて修正版に取り込まれている（{len(synced)} ファイル）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
