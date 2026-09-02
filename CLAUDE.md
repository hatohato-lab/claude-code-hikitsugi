# CLAUDE.md — claude-code-hikitsugi

## このリポジトリの前提

- Claude Code の会話ログ（.jsonl）から引き継ぎメモを再建するツール。
- 形態は**スキル型**（`skill/SKILL.md`＋`skill/hikitsugi.py`）。
  理由：本ツールは「新しいチャット本体」が一言で発動する必要があり、サブエージェントでは会話の主導権を持てないため。
- 依存は標準ライブラリのみ。通信しない。これを壊す変更はしない。

## 確認コマンド（変更したら必ず回す）

```bash
python eval/oracle.py --selftest      # 機械判定24項目。全PASSが合格条件
python skill/hikitsugi.py --list      # 実環境での目視スモーク
```

## 編集の約束

- マスキングは「抽出の境界で・切り詰めより先に」適用する。この順序を崩さない
- ログのパースは防御的に（未知type・非辞書JSONは黙って飛ばす）。クラッシュさせない
- 実ログ・実出力をリポジトリにコミットしない（.gitignore 済み）
- `00_設計書/` は個人メモのため公開対象外。公開用の設計は `design/design.md`
