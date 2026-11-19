"""本のリポジトリの中の場所.

スクリプトは本のリポジトリのルートで実行する（make はそうする）．
emend は本のリポジトリの common/ に submodule として置くので，スクリプトの場所からは
本のリポジトリを決めず，実行したディレクトリを本のリポジトリのルートとみなす．
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path.cwd()
ORIGINAL = ROOT / "tex/original"
REVISED = ROOT / "tex/revised"
CORRECTIONS = ROOT / "corrections"
# 最後に修正版へ取り込んだ忠実版の記録（check_original.py）
SYNC_STORE = ROOT / "tex/original-sync.json"


def require_root() -> None:
    if not ORIGINAL.is_dir():
        sys.exit(f"{ORIGINAL} がない．本のリポジトリのルートで実行する（make を使う）")
