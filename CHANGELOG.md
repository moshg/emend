# 変更の記録

本のリポジトリの側で対応が要る変更を書く．新しい順．

## 修正版の番号を詰め，原書の番号を余白に出す

規約の既定を，修正版の番号を修正版の並びのとおりに振る形にした（`docs/conventions.md` の「番号」）．定理類や式を消したり，移したり，足したりすると，後の番号は原書とずれる．ラベルは原書の番号のまま残す．修正版で番号が原書と違う定理類には，見出しの余白に「原 補題 4.34」と原書の番号が自動で出る（`\label{thm:…}` のラベル名の番号と実際の番号を比べる）．

- 番号を原書と同じに保つ本は，`docs/book.md` にそう書く．`\fixskip`，`\addtag`，`\newaddtheorem` はこれまでどおり使える．番号がそろっていれば余白には何も出ない．`\fixskip` の付け忘れなどで番号がずれている所があれば，余白に「原 …」が出るので気づける．
- 番号を詰める本は，`\fixskip` を消し，足した定理類と式を普通の環境にする．新しく足すもののラベルは `rev:修正 ID`（`rev:1-09`）にする．すでにある `rev:1.20a` のようなラベルは，そのままでよい（ラベルは名前なので番号と合っていなくてよい）．
- 種類を変えた（補題を系にしたなど）定理類には，`\label` の前に `\origname{補題}` と原書の種類を書く．書かないと修正版の種類の名前が出る．
- 余白の表示は `\origthmmark{種類}{番号}` が出す．本の sty で `\renewcommand` して見た目を変えたり，`\renewcommand\origthmmark[2]{}` で出さないようにしたりできる．`\marginparwidth` が狭いと折り返すので，本の sty で見直す．
- emend は，修正版で `\label`（hyperref などが定め直した後のもの）と，amsthm の定理環境の始まり（`\@thm`）を包むようになった．`\label` に任意引数を付けるパッケージ（cleveref など）を使っている本では，包み方が合わないことがある．amsthm を使わない本では，余白に種類の名前が出ず番号だけになる．
- md では，原書の定理や式を原書の番号で呼び，足したものは修正 ID で呼ぶ（`docs/conventions.md` の「修正のまとめ」）．
- `\newaddtheorem` に，番号のカウンタを指定する省略できる第 1 引数を足した（`\newaddtheorem[definition]{addlemma}{補題}`）．省略すると `theorem` で，これまでと同じ．定理類が `theorem` 以外のカウンタを共有していて，本の sty に同じ仕組みを作っていた本は，これに替えられる．
- `docs/workflow.md` の「証明の簡略化・補完」の 1 に，構成の組み替え（移す，まとめる，役目のなくなった補題を消す），主張を強める書き換え，定義の後の説明と例を足した．`docs/review.md` は，証明の途中にだけ現れる陽な評価が弱まる置き換えを，証明が明らかに短くなるときに認め，「使わない」の類の断りで済ませた並びを差し戻すようにした．本の `docs/book.md` やその他の文書が古い基準に触れていれば直す．

## 推測で判定する「要確認」をなくす

`make check` は「要確認」（目印のない変更，印のない補完・書き換え，メモにだけ残った原書の誤り）を出さなくなった．これらはレビュー担当が差分を見て確かめる．`scripts/changes.py` もなくなった．

- 本のリポジトリの文書が「要確認」や `changes.py` に触れていれば消す．`changes.py` を呼んでいれば外す．
- 原文が 80 字以上残った所より後の変更にも `\fixat` を置く決まりはなくなった．置いてある `\fixat` は残してよい．

## `\recordchaptercounts` をなくす

章の終わりのカウンタを aux に書く `\recordchaptercounts` は，番号を原書と一致させる検査をやめてから何にも使っていなかったので，なくした．

- main.tex の章を読み込む行（`\bookchapter` など）から `\recordchaptercounts{…}` を消す（命令がなくなったので，残すとビルドが止まる）．
- 手元では一度 `make clean` してからビルドする（前のビルドの aux に `\emend@counts` の行が残っていて止まるため）．

## 修正箇所の索引を PDF に出さない

修正版の巻末の修正箇所の索引をやめた．`\fixat{ID}` は PDF に何も出さない目印になり，修正の内容と理由は `corrections/*.md` だけで見る．本文の［補完］［書き換え］の印はこれまでどおり出る．

- main.tex から `\printfixindex` を消す（命令がなくなったので，残すとビルドが止まる）．
- 本の sty から `\renewcommand\fixindexlead{…}` を消す（同じく止まる）．
- 索引の前置きにあった文（`\fixindexlead` の文，修正の内容と理由が `corrections/` にあること，［補完］［書き換え］の印の意味）も PDF に出なくなる．修正版であることや印の意味を PDF に書いておきたいなら，本のまえがきなどに書く．
- emend は hyperref を読まなくなった．本の sty で hyperref を読んでいなければ，必ず読む（README の本の sty の形）．読まないとビルドは通るが，リンクとしおりがなくなり，`make check` のリンクとしおりの検査も働かない．hyperref を emend より先に読むという決まりはなくなった．
- emend は enumitem も読まなくなった．本（sty でも章のファイルでも）で enumitem の命令やオプション（`\setlist`，`\begin{enumerate}[label=…]` など）を使っているなら，本の sty で読む．使っていなくても，enumitem を読むと `description` のラベルの後の空きが変わるので，前と同じレイアウトにしたいなら本の sty で読む．
- `docs/book.md` に索引のことが書いてあれば消す．
- 手元では一度 `make clean` してからビルドする（前のビルドの aux に，なくなったマクロの行が残っていて止まるため）．
- `\fixat` が本文に何も置かなくなったので，修正版のレイアウトが `\fixat` の周りでわずかに変わる（和文の字間，改行や改ページの位置）．`common/` の更新の前後で修正版の PDF を比べると，その差が出る．本の sty で enumitem を読まないなら，`description` のレイアウトも両方の版で変わる．

## 補完・書き換えの印を長さによらず付ける

これまでは原文にない文が 3 文以上ある修正だけを印（`\supplied`，`\rewritten`）で囲んでいた．これからは，種類に「補完」「注記」「簡略化」「書き換え」を含む修正を，1〜2 文のものや括弧書きの注記も含めてすべて囲む．

- 印のない短い補完・書き換え・注記に印を付ける（`\fixat{ID}\supplied{（注：……）}` のように文の中でも使える）．
- `make check` は，忠実版にない文が 1 文でもあって印のない修正を「要確認」として表示するようになった（警告で，失敗にはしない）．忠実版の文を少し直しただけの文は数えないので，文の中に括弧書きを足しただけの修正などは表示されないことがある．

## 手順と注意点の文書を分け，レビュー担当のエージェントを置く

`common/docs/` を，作業する担当が読む `workflow.md`（手順）・`conventions.md`（書き方）と，`reviewer` エージェントが読む `review.md`（注意点と制約）に分けた．校正，レビュー，最終検証は `reviewer` に頼む．

- `.claude/agents/reviewer.md` を `common/agents/reviewer.md` へのシンボリックリンクにし，`CLAUDE.md` の読む文書を直す（どちらも README の「入れ方」）．
- `CLAUDE.md` や `docs/book.md` が古い節の名前（`conventions.md` の「原書の誤りを見つけたとき」「新しい章を追加する手順」，`workflow.md` の「対象」「書き方」「レビュー」など）を引いていれば直す．
- レビューの観点を依頼文に書き並べる雛形などがあれば消す（観点は `review.md` にあり，依頼文には種類と範囲だけを書く）．
- `docs/book.md` は作業する担当も読む．本ごとの注意点や制約（避ける書き方，判断の基準など）を書いているなら，`docs/book-review.md` に移す（`reviewer` だけが読む）．

## 修正版の番号を原書と一致させる規約と検査をやめる

- `docs/book.md` に，修正版の番号を原書と一致させる決まりや「2 つの版の番号」の検査のことが書いてあれば消す．`\fixskip` はそのまま使える．`\recordchaptercounts` は main.tex から呼んだままでよい（いまは何にも使わない）．
- `rev:` ラベルの番号は検査しなくなった．
- 修正版で消した式・定理を `\bref`，`\beqref` で参照していると，`make check` が NG にするようになった．NG になったら参照を直す．

## 修正版で初等的な性質を番号で引かない

- 修正版で補った文で初等的な性質を番号で引いている所は，言葉に直す（規約の「参照」）．

## 修正版で足した式・定理類の番号を「原書の番号＋アルファベット」にする

- 修正版の `\tag{…$'$}\label{rev:…}` を `\addtag\label{rev:…}` にし，ラベル名を実際の番号にする（この変更の時点では `make check` が「ラベル rev:1.20p の実際の番号が 1.20a」のように教えた．いまは検査しない）．番号は直前に出ている原書の式に付くので，数字が変わることがある．参照と `corrections/*.md` も直す．
- 番号付きの定理類を足したいときは，本の sty で `\newaddtheorem{addlemma}{補題}` などを定義し，`docs/book.md` に書く．
- `docs/book.md` にプライムの番号の書き方が残っていれば直す．

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
- latexmk は `-halt-on-error` と `-synctex=1` を付けて動かす．監視する章ファイルは `tex/original/`，`tex/revised/`（それぞれ 1 階層下のディレクトリまで），`tex/notation/`．
- 規約と進め方は `common/docs/` を見る．本ごとの事情は `docs/book.md` に書く．
- `.claude/settings.json`，CI，Dependabot，`.github/emend-denylist.txt` は README の「入れ方」に従う．
- 切り替えた後，手元では一度 `make clean` してからビルドする（前のビルドの aux に，本の sty の古いマクロ名が残っていて止まるため）．
