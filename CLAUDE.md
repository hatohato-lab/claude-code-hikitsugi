# CLAUDE.md — claude-code-hikitsugi

## このリポジトリの前提

- Claude Code のプラグイン。前のセッションの生ログから、Claude Code 自身が圧縮時に書いた要約（`"isCompactSummary":true` の行）を取り出して、新しいセッションに読ませる
- 要約を自分で作らない。生ログを解析して組み立てる方式は v2 で捨てた（理由は CHANGELOG.md）
- 依存は標準ライブラリのみ。通信しない。これを壊す変更はしない
- 形はプラグイン（`.claude-plugin/plugin.json`＋`marketplace.json`）。install スクリプトは作らない

## 確認コマンド（変更したら必ず回す）

```bash
python eval/oracle.py --selftest       # 機械判定26項目。全PASSが合格条件
claude plugin validate .               # プラグインの形式の検査
```

## 編集の約束

- 生ログの読み方は防御的に。壊れた行・辞書でない行は黙って飛ばす。落とさない
- 目印のキー（`isCompactSummary`・`compact_boundary`）が無いときは「要約がありません」と正直に出す。推測で補わない
- 実ログ・実出力をリポジトリにコミットしない（.gitignore 済み）
- `00_設計書/` は個人メモで公開対象外。公開用の説明は `docs/index.html`
- 図を直すときは `docs/plantuml/*.puml` を直して描き直す。SVG を手で書き換えない
