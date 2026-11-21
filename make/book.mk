# make           忠実版と修正版の両方をビルドして pdf/ にコピーし，整合性チェックを行う
# make original  忠実版のみ
# make revised   修正版のみ
# make check     両版をビルドしたうえで，ラベル番号・修正 ID・参照などの整合性チェックと，
#                忠実版の変更が修正版に取り込まれていることの検査を行う（変更がなければビルドは数秒で終わる）
# make sync      忠実版（tex/original/）の変更を修正版（tex/revised/）に取り込む（3-way マージ）
# make clean     中間ファイルを削除
# make help      この説明を表示する
#
# TeX は Docker の中で動かす（common/scripts/tex．Docker がなければホストの TeX）．チェックはホストの python3 で動かす．

# 本の Makefile から include する（emend は本のリポジトリの common/ にある）:
#   include common/make/book.mk
# make help は，各 Makefile の先頭から最初の空行までのコメントを順に表示する．

EMEND ?= common
VERSIONS := original revised

.PHONY: all $(VERSIONS) check sync clean help

all: $(VERSIONS) check

# 新しく置いた章や記号のファイルにも気づくよう，latexmkrc がファイルの一覧を見ている．
$(VERSIONS):
	$(EMEND)/scripts/tex latexmk $@.tex
	mkdir -p pdf
	cp tex/build/$@.pdf pdf/$@.pdf

# チェックは aux と log を読むので，ビルドの後に動かす（make -j でも，単独の make check でも）
check: $(VERSIONS)
	python3 $(EMEND)/scripts/check.py
	python3 $(EMEND)/scripts/check_original.py

# 忠実版を直したとき，同じ直しを修正版に入れる（衝突した箇所は手で直す）
sync:
	python3 $(EMEND)/scripts/check_original.py --sync

clean:
	rm -rf tex/build

# 各 Makefile の先頭から最初の空行までのコメントを順に表示する（説明はそこにだけ書く）
help:
	@for f in $(MAKEFILE_LIST); do sed -n '/^[^#]/q; /^$$/q; s/^# \{0,1\}//p' $$f; echo; done
