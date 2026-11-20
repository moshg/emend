# TeX の実行環境

## ビルドの仕組み

LuaLaTeX（`ltjsbook`）を Docker で動かす．TeX をホストに入れる必要はない（ホストに要るのは Docker，`make`，`python3`，`git`）．`make` は本のリポジトリのルートで `common/scripts/tex latexmk …` を実行し，`common/scripts/tex` が本のリポジトリを含む作業ツリーをコンテナにマウントして，その中の `tex/` で latexmk を動かす．`tex/latexmkrc` が読む `common/tex/latexmkrc` が，`common/tex/`（`emend.sty` のある場所）を TeX の探索パスに足す．

- TeX は TeX Live 2026（[Island of TeX](https://gitlab.com/islandoftex/images/texlive) のイメージ `registry.gitlab.com/islandoftex/images/texlive` の full）で，`scripts/tex` でタグとダイジェストを固定している．手元でも GitHub Actions でも同じ TeX が動く．最初の `make` でイメージ（約 2.8GB，展開後は約 9GB）が自動で取得される．
- フォントのキャッシュを `tex/build/texmf-cache/` に残しているので，変更のないときの `make` はすぐ終わる．章のファイルを新しく置いたときは，`latexmkrc` がファイルの一覧の変化に気づいてビルドし直す．
- コンテナは呼び出したユーザーで動くので，Linux でも `tex/build/` は root の持ち物にならない．rootless の Docker や Podman では，コンテナから `tex/` に書き込めないことがある．
- Docker が使えないとき（`TEX_LOCAL=1` を付けたとき，または Docker のデーモンに接続できないとき）は，ホストの TeX で実行する．その TeX には LuaLaTeX と luatexja が要る．バージョンが固定のものと違うと，版面が CI の PDF と少し変わることがある．

### Podman

Docker の代わりに Podman でもよい（`scripts/tex` は `docker` コマンドを呼ぶので，`podman-docker` を入れるなどして `docker` で Podman が動くようにしておく）．ただし Podman では Ctrl-C で止めても LuaLaTeX が最後まで動き続け，`make` が戻ったあとも `tex/build/` に書き込むことがある（`scripts/tex` の `--init` が Docker では tini だが，Podman の init はプロセスグループに中断を伝えないため）．中断したら LuaLaTeX が終わるのを待つか，`docker ps` で見つけたコンテナを `docker stop` してから `make` し直す．

## TeX Live の更新

Island of TeX は TeX Live のイメージを毎週，日付つきのタグ（`TL2026-2026-11-01-full` など）で出している．更新するときは次のようにする．

1. 新しいタグのダイジェストを `docker buildx imagetools inspect registry.gitlab.com/islandoftex/images/texlive:<タグ>` の `Digest` で調べる（Podman の環境では `skopeo inspect --no-tags --format '{{.Digest}}' docker://registry.gitlab.com/islandoftex/images/texlive:<タグ>` で同じ値が得られる）．
2. emend の `scripts/tex` の `image=` のタグとダイジェストを書き換える．
3. 見本の本（`example/`）と，各本で，更新の前と後に `make` した `pdf/*.pdf` を `common/scripts/pdfdiff.py 前.pdf 後.pdf` で見比べる．TeX Live のバージョンが変わると版面が変わることがある．
4. 違いが出たら，意図しない違いでないかを画像で確かめる．本ごとの sty で補う必要があるなら，emend の `CHANGELOG.md` にそう書く．
