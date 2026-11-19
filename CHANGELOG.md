# 変更の記録

本のリポジトリの側で対応が要る変更を書く．新しい順．

## Makefile で毎回 common/ をそろえる

- 本の `Makefile` の `common/` の取得を，`ifeq` で囲まずに毎回 `git submodule update --init` する形にする（README の見本）．pull で `common/` の指すコミットが進んだのに，手元の `common/` が古いままで，`git add -A` などで古いコミットを指したままコミットしてしまうのを防ぐ．
- CI の見本: `merge-base --is-ancestor` で，`HEAD` を `FETCH_HEAD`（取得した main）と比べ，失敗したときは理由を出す．禁止語のリストがないときも失敗にする．`.gitmodules` と禁止語のリストの変更でも動かす．

## emend に切り替えるとき

本のリポジトリにあったスクリプト・スタイルの仕組みの部分・規約と進め方を，ここにまとめた．切り替えるときに本の側ですること:

- `scripts/` を消し，`Makefile` を `include common/make/book.mk` にする．本ごとのターゲット（`make source` など）は本の `Makefile` に残す．
- `scripts/original-sync.json` を `tex/original-sync.json` に移す（中身は変えない）．
- `tex/latexmkrc` を `do '../common/tex/latexmkrc' or die "common/ を読めない（git submodule update --init）: $@$!\n";` にする（README の見本）．
- 本の sty から，版の切り替え・`\fixat`・`\fixskip`・`\recordchaptercounts`・印・索引・`\origpage`・`\bref`/`\beqref`・ltjsbook の付録の目次の補正を消して，`\RequirePackage{emend}` にする．
  - 索引の前置きの最初の文が違うなら `\renewcommand\fixindexlead{…}`，`\origpage` の色が違うなら `\definecolor{origpagecolor}{…}{…}`．
  - `\marginparwidth` などの余白の設定は本の sty に残す（emend は設定しない）．
- `make check` が，これまで検査していなかった本では新しく次を検査する: 取り下げた ID が修正版に残っていないこと．
- latexmk は `-halt-on-error` と `-synctex=1` を付けて動かす．監視する章ファイルは `tex/original/`，`tex/revised/`（それぞれ 1 段下のディレクトリまで），`tex/notation/`．
- 規約と進め方は `common/docs/` を見る．本ごとの事情は `docs/book.md` に書く．
- `.claude/settings.json`，CI，Dependabot，`.github/emend-denylist.txt` は README の「入れ方」に従う．
- 切り替えた後，手元では一度 `make clean` してからビルドする（前のビルドの aux に，本の sty の古いマクロ名が残っていて止まるため）．
