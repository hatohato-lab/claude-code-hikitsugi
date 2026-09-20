# claude-code-hikitsugi（引き継ぎ）

**新しいセッションで「◯◯を継いで」と一言いうだけで、前のセッションの続きから始められる。**

*Say "take over ◯◯" in a new Claude Code session, and it resumes where the old one left off — from the summary Claude Code itself wrote.*

## しくみ（1行）

Claude Code は会話を圧縮するたびに、それまでの要約（見出し9つ・平均15,000字）を生ログに1行書いている。
このプラグインは、その最後の1行を取り出して新しいセッションに読ませるだけ。自分で要約は作らない。

図解と詳しい説明は [docs/index.html](docs/index.html)。

## 入れ方（1回だけ）

### VS Code

入力欄で `/` を押して **Manage plugins** を開き、**Marketplaces** に次を足す。

```
hatohato-lab/claude-code-hikitsugi
```

**Plugins** に hikitsugi が出るので **Install** を押す。これでスキルと見張りフックの両方が入る。

リンクから開くこともできる（VS Code が起動してインストール画面が出る）。

```
vscode://anthropic.claude-code/install-plugin?plugin=hikitsugi&marketplace=hatohato-lab/claude-code-hikitsugi
```

### ターミナル

```
/plugin marketplace add hatohato-lab/claude-code-hikitsugi
/plugin install hikitsugi@claude-code-hikitsugi
```

Python 3.8 以上が要る。追加パッケージは不要。設定ファイルの編集も不要。

## 使い方（毎回これだけ）

1. 古いセッションで `/compact` を打つ（要約がその時点まで進む）
2. 新しいセッションを開く
3. 一言。

```
仕事0920を継いで
```

Claude が前のセッションのログを探し、最後の要約を読んで、
「目標・決まったこと・残作業・止まっている場所・次の一手」を宣言して再開する。

要約が無いセッション（一度も圧縮されていない）を指定すると、
「前のセッションで `/compact` を打ってください」と返る。

## 見張り

発言のたびに自分のログを見て、圧縮が起きていたら1回だけ知らせる。

> 【引き継ぎの案内】このセッション「◯◯」は圧縮が1回起きています。区切りのよいところで /compact を打ち、新しいセッションで「◯◯を継いで」と言えば続きから始められます。

同じ状態では2度言わない。基準は圧縮回数だけで、ファイルの大きさは見ない（大きさと文脈の重さは一致しない）。

## 直接使う

```
python skills/hikitsugi/scripts/last_summary.py --list              セッション一覧
python skills/hikitsugi/scripts/last_summary.py --find "仕事"       名前で探す
python skills/hikitsugi/scripts/last_summary.py --session 2dafd4fb  最後の要約を出す
```

`--session` にはログファイルのパスをそのまま渡してもよい。

## 公式の機能との使い分け

| やりたいこと | 使うもの |
|---|---|
| 同じセッションをそのまま続ける | 公式 `claude --continue` / `--resume` |
| 同じセッションを軽くして続ける | 公式 `/compact` |
| **新しいセッションで続きから始める** | **本プラグイン**（公式の要約を、公式が扱わない「別セッション」へ渡す） |

## 制限

- 圧縮されたことのないセッションには要約が無い。`/compact` を1回打つ
- 要約は圧縮の時点で止まる。それ以降の会話は生ログにしか無い（出力に時刻を添えて注意する）
- サブエージェントの会話は別フォルダーにあり、要約に入らない
- 生ログの形式は Claude Code 内部のもので、版で変わり得る。目印のキーが無ければ「要約がありません」と正直に出す
- ログの保存期間は Claude Code の設定（既定30日・`cleanupPeriodDays`）に従う

## eval

```
python eval/oracle.py --selftest
```

作り物のログ2本で、取り出しと見張りを26項目で機械判定する。全PASSが合格条件。

## 変更履歴

[CHANGELOG.md](CHANGELOG.md)。v3（2026-09-20）で方式を作り直した。
それまでは生ログを言葉の一致で解析して要約を組み立てていたが、Claude Code 自身の要約のほうが上だった。

## License

MIT
