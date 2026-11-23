# emend

本を LaTeX に書き起こし，**原書に忠実な版**（忠実版）と，**誤りを直して証明の簡略化や補完を入れた版**（修正版）の 2 つの PDF を作るための，共通の仕組み．忠実版（`tex/original/`）と修正版（`tex/revised/`）は別のソースで，修正版の直した箇所には目印 `\fixat{ID}` を置き，忠実版を後から直したときは `make sync` で修正版に取り込む．本ごとのリポジトリ（以下「本のリポジトリ」）に submodule として入れて使う．

| 中身 | 場所 |
|---|---|
| 版の切り替え，`\fixat`，`\fixskip`，足した式・定理類の番号（`\addtag`，`\newaddtheorem`），章の終わりのカウンタの記録，［補完］［書き換え］の印，原書のページ境界，参照 | `tex/emend.sty` |
| latexmk の共通の設定 | `tex/latexmkrc` |
| make のターゲット（`make`，`make check`，`make sync` など） | `make/book.mk` |
| TeX を Docker で動かす | `scripts/tex` |
| 整合性チェック（ラベル番号，参照とリンク，消した参照先，修正 ID，注記，原書のページ境界，しおり，印，衝突の残り） | `scripts/check.py` |
| 補完・書き換えの印の置き場所と種類の検査 | `scripts/marks.py` |
| 忠実版と修正版の差分の検査（目印のない変更，印のない補完．警告のみ） | `scripts/changes.py` |
| 忠実版の変更が修正版に取り込まれているかの検査と，その取り込み（`make sync`） | `scripts/check_original.py` |
| 2 つの PDF をページの画像で比べる | `scripts/pdfdiff.py` |
| 作業の手順（書き起こし，校正，原書の誤りの修正，証明の簡略化・補完，並列作業） | [docs/workflow.md](docs/workflow.md) |
| ソースと修正のまとめの書き方 | [docs/conventions.md](docs/conventions.md) |
| 作業の注意点と制約（レビュー担当の `reviewer` エージェントが読む） | [docs/review.md](docs/review.md) |
| `reviewer` エージェントの定義（本のリポジトリの `.claude/agents/` からリンクする） | `agents/reviewer.md` |
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
docs/book-review.md         本ごとの注意点と制約（あれば．reviewer だけが読む）
tex/
  latexmkrc                 do '../common/tex/latexmkrc' or die "common/ を読めない（git submodule update --init）: $@$!\n";
  <本>.sty                  hyperref，emend → 見た目
  notation.sty              記号のマクロ
  main.tex, original.tex, revised.tex
  original/                 各章の本文（忠実版）
  revised/                  各章の本文（修正版）
  original-sync.json        最後に修正版へ取り込んだときの忠実版の記録（各ファイルの blob ID．make sync が書く）
corrections/                修正のまとめ
.gitignore                  tex/build/，pdf/
.claude/settings.json       セッションの開始時に common/ を取得し，emend の CLAUDE.md を読み込まない
.claude/agents/reviewer.md  → ../../common/agents/reviewer.md（シンボリックリンク）
.github/workflows/build-pdf.yml
.github/dependabot.yml      common/ の更新を PR で知らせる
.github/emend-denylist.txt  common/ に入っていてはいけない語（題名，著者名，リポジトリ名など．1 行に 1 語，空行を入れない）
```

### 入れ方

```sh
git submodule add https://github.com/moshg/emend.git common
```

**Makefile**: 毎回 `common/` を，本のリポジトリが指しているコミットにそろえてから読み込む（まだなければ取得する．pull で `common/` の指すコミットが進んだのに，手元の `common/` が古いままで，古いコミットを指したままコミットしてしまうのを防ぐ）．本ごとのターゲット（原書の PDF の取得など）は `include` の後に書く（前に書くと `make` の既定のターゲットになる）．先頭のコメントは `make help` に出る．

```make
# 『…』TeX 化プロジェクト
# make source    原書の PDF を Release「source」から resources/ に取得する（gh が要る）

$(shell git submodule update --init >&2)
include common/make/book.mk
```

**本の sty**: hyperref と emend を読んでから見た目を書く（`example/tex/examplebook.sty` が見本）．`\origpage` と印の色（`origpagecolor`，`fixmarkcolor`）は，読んだ後で変えてよい．

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

**`.claude/agents/reviewer.md`**: レビュー担当のエージェント．emend の `agents/reviewer.md` へのシンボリックリンクにする（emend 自体では登録されないよう，emend では `.claude/` の外に置いている）．クラウドのセッションでは，SessionStart のフックが `common/` を取得した後に読み込まれる．

```sh
mkdir -p .claude/agents && ln -s ../../common/agents/reviewer.md .claude/agents/reviewer.md
```

**`.github/workflows/build-pdf.yml`**: 次を足す．

```yaml
on:
  push:
    paths: [..., "common", ".gitmodules", ".github/emend-denylist.txt"]   # common/ の指すコミットが変わったときも動かす
  pull_request:
    paths: [..., "common", ".gitmodules", ".github/emend-denylist.txt"]
...
      - uses: actions/checkout@v7
        with:
          submodules: true
      - name: common/ が emend の main に入っている
        run: |
          git -C common fetch --quiet --unshallow origin main || git -C common fetch --quiet origin main
          if ! git -C common merge-base --is-ancestor HEAD FETCH_HEAD; then
            echo "::error::common/ が emend の main にないコミットを指している"; exit 1
          fi
      - name: common/ に本の情報が入っていない
        run: |
          rc=0
          grep -rnIiF -f .github/emend-denylist.txt common/ || rc=$?
          if [ "$rc" -eq 0 ]; then echo "::error::common/ に本の情報がある"; exit 1; fi
          if [ "$rc" -ne 1 ]; then echo "::error::禁止語の検査ができなかった"; exit 1; fi
```

**`.github/dependabot.yml`**: `common/` の更新を PR で知らせる．`updates:` に次を足す．

```yaml
  - package-ecosystem: gitsubmodule
    directory: /
    schedule:
      interval: weekly
```

**`CLAUDE.md`**: 少なくとも次を書く．

- 作業の手順は `common/docs/workflow.md`，書き方は `common/docs/conventions.md`，本ごとの事情は `docs/book.md`．作業の注意点と制約は `common/docs/review.md` と `docs/book-review.md` にあり，`reviewer` エージェントが読む（作業する担当は読まない）．
- `common/` は emend の submodule で，この中のファイルは本のリポジトリでは編集しない．直すときは emend のブランチで直して PR を出し，マージされてから `common/` が指すコミットを更新する（Dependabot の PR でもよい）．
- emend には本の情報を入れない（emend の `CLAUDE.md`）．

## 共通部分を変えるとき

emend で作業ブランチを切って変え，`make -C example` が通ることを確かめて PR を出す（[CLAUDE.md](CLAUDE.md)）．main にマージすると，各本のリポジトリに Dependabot が `common/` の更新の PR を出し，その本の CI がその本で確かめる．本の側で対応が要る変更は [CHANGELOG.md](CHANGELOG.md) に書く．
