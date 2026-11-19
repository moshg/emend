# emend

本を LaTeX に書き起こし，**原書に忠実な版**（忠実版）と，**誤りを直して証明の簡略化や補完を入れた版**（修正版）の 2 つの PDF を作るための，共通の仕組み．忠実版（`tex/original/`）と修正版（`tex/revised/`）は別のソースで，修正版の直した箇所には目印 `\fixat{ID}` を置き，忠実版を後から直したときは `make sync` で修正版に取り込む．本ごとのリポジトリ（以下「本のリポジトリ」）に submodule として入れて使う．

| 中身 | 場所 |
|---|---|
| 版の切り替え，`\fixat`，`\fixskip`，章の終わりのカウンタの記録，［補完］［書き換え］の印，修正箇所の索引，原書のページ境界，参照 | `tex/emend.sty` |
| latexmk の共通の設定 | `tex/latexmkrc` |
| make のターゲット（`make`，`make check`，`make sync` など） | `make/book.mk` |
| TeX を Docker で動かす | `scripts/tex` |
| 整合性チェック（ラベル番号，2 つの版の番号，参照とリンク，修正 ID，注記，原書のページ境界，しおり，印，衝突の残り） | `scripts/check.py` |
| 補完・書き換えの印の置き場所と種類の検査 | `scripts/marks.py` |
| 忠実版と修正版の差分の検査（目印のない変更，印のない補完．警告のみ） | `scripts/changes.py` |
| 忠実版の変更が修正版に取り込まれているかの検査と，その取り込み（`make sync`） | `scripts/check_original.py` |
| 2 つの PDF をページの画像で比べる | `scripts/pdfdiff.py` |
| 書き起こしの規約 | [docs/conventions.md](docs/conventions.md) |
| 作業の進め方（並列作業，校正，証明の簡略化・補完，レビュー） | [docs/workflow.md](docs/workflow.md) |
| TeX の実行環境と TeX Live の更新 | [docs/texlive.md](docs/texlive.md) |
| 見本の本（架空の内容．CI でビルドして検査する） | `example/` |
| 本のリポジトリで対応が要る変更の記録 | [CHANGELOG.md](CHANGELOG.md) |

見た目（定理環境，見出し，箇条書き，`\term`，文献の `\bcite`，版面）と記号は，原書に合わせて本ごとに決めるので，本のリポジトリに置く．

## 本のリポジトリの構成

```
common/                     emend（submodule）
Makefile                    include common/make/book.mk ＋本ごとのターゲット
CLAUDE.md                   common/ の扱い，読む文書
docs/book.md                本ごとの事情（番号の付け方，環境，文献の表示，記号，担当と ID の表，具体例）
tex/
  latexmkrc                 do '../common/tex/latexmkrc' or die "common/ を読めない（git submodule update --init）: $@$!\n";
  <本>.sty                  hyperref → emend → 見た目
  notation.sty              記号のマクロ
  main.tex, original.tex, revised.tex
  original/                 各章の本文（忠実版）
  revised/                  各章の本文（修正版）
  original-sync.json        最後に修正版へ取り込んだ忠実版の記録（make sync が書く）
corrections/                修正のまとめ
.gitignore                  tex/build/，pdf/
.claude/settings.json       セッションの開始時に common/ を取得し，emend の CLAUDE.md を読み込まない
.github/workflows/build-pdf.yml
.github/dependabot.yml      common/ の更新を PR で知らせる
.github/emend-denylist.txt  common/ に入っていてはいけない語（題名，著者名，リポジトリ名など．1 行に 1 語，空行を入れない）
```

### 入れ方

```sh
git submodule add https://github.com/moshg/emend.git common
```

**Makefile**: `common/` がまだ取得されていなければ取得してから読み込む．本ごとのターゲット（原書の PDF の取得など）は `include` の後に書く（前に書くと `make` の既定のターゲットになる）．先頭のコメントは `make help` に出る．

```make
# 『…』TeX 化プロジェクト
# make source    原書の PDF を Release「source」から resources/ に取得する（gh が要る）

ifeq ($(wildcard common/make/book.mk),)
$(shell git submodule update --init >&2)
endif
include common/make/book.mk
```

**本の sty**: hyperref を（オプションを付けるならそれも）emend より先に読み，emend を読んでから見た目を書く（`example/tex/examplebook.sty` が見本）．索引の前置きの最初の文（`\fixindexlead`）と，`\origpage` と印の色（`origpagecolor`，`fixmarkcolor`）は，読んだ後で変えてよい．

**main.tex，original.tex，revised.tex**: `example/tex/` が見本．

**`.claude/settings.json`**: クラウドのセッションは起動時に submodule を取得しないので，セッションの開始時に取得する．また，本のセッションで `common/` のファイルを読んだときに emend の `CLAUDE.md`（emend で作業するときの決まり）が読み込まれないようにする．

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [{ "type": "command", "command": "git submodule update --init --quiet" }] }
    ]
  },
  "claudeMdExcludes": ["**/common/CLAUDE.md"]
}
```

**`.github/workflows/build-pdf.yml`**: 次を足す．

```yaml
on:
  push:
    paths: [..., "common"]        # common/ の参照の更新でも動かす
  pull_request:
    paths: [..., "common"]
...
      - uses: actions/checkout@v7
        with:
          submodules: true
      - name: common/ が emend の main に入っている
        run: |
          git -C common fetch --quiet --unshallow origin main || git -C common fetch --quiet origin main
          git -C common merge-base --is-ancestor HEAD origin/main
      - name: common/ に本の情報が入っていない
        run: |
          if grep -rnIiF -f .github/emend-denylist.txt common/; then
            echo "::error::common/ に本の情報がある"; exit 1
          fi
```

**`.github/dependabot.yml`**: `common/` の更新を PR で知らせる．`updates:` に次を足す．

```yaml
  - package-ecosystem: gitsubmodule
    directory: /
    schedule:
      interval: weekly
```

**`CLAUDE.md`**: 少なくとも次を書く．

- 規約は `common/docs/conventions.md`，進め方は `common/docs/workflow.md`，本ごとの事情は `docs/book.md`．
- `common/` は emend の submodule で，この中のファイルは本のリポジトリでは編集しない．直すときは emend のブランチで直して PR を出し，マージされてから `common/` の参照を更新する（Dependabot の PR でもよい）．
- emend には本の情報を入れない（emend の `CLAUDE.md`）．

## 共通部分を変えるとき

emend で作業ブランチを切って変え，`make -C example` が通ることを確かめて PR を出す（[CLAUDE.md](CLAUDE.md)）．main にマージすると，各本のリポジトリに Dependabot が `common/` の更新の PR を出し，その本の CI がその本で確かめる．本の側で対応が要る変更は [CHANGELOG.md](CHANGELOG.md) に書く．
