# CLAUDE.md — claude-code-hikitsugi

## このリポジトリの前提

- Claude Code のプラグイン。中身は `skills/hikitsugi/SKILL.md` 1枚だけ
- Python もスクリプトも使わない。通信もしない
- 圧縮の要約には頼らない。いまのセッションの記憶と生ログから引き継ぎ書を書く

## 確認コマンド

```
claude plugin validate .
```

## 編集の約束

- 実ログ・実出力をコミットしない
- 個人のパス・氏名・会社名を書かない。例は `<ユーザー名>` のような伏せ字にする
- 機能を足すときも、まず SKILL.md に書く。ファイルを増やすのは最後の手段
