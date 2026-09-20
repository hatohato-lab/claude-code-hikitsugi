# claude-code-hikitsugi（引き継ぎ）

長くなった Claude Code のセッションを、新しいセッションで続きから始める。

*Hand a long Claude Code session over to a fresh one.*

## 入れ方（1回だけ）

入力欄で `/` を押して **Manage plugins** を開き、**Marketplaces** に次を足して **Install**。

```
hatohato-lab/claude-code-hikitsugi
```

## 使い方（3つ）

1. 古いセッションで `/compact` を打つ
2. 続けて `/hikitsugi:next` を打つ。2行が出るのでコピーする
3. 新しいセッションを開いて、その2行を貼る

出てくる2行はこの形。

```
このログの "isCompactSummary":true を含む最後の行を読んで、続きから始めて
C:\Users\<ユーザー名>\.claude\projects\<作業フォルダー>\<セッションID>.jsonl
```

## なぜ2行なのか

Claude Code は会話を圧縮するたびに、それまでの要約を生ログに1行書いている。
引き継ぎとは、その1行を新しいセッションに読ませることに尽きる。

Claude は自分のセッション名を見られない。名前で呼んでも届かない。
届くのは生ログのパスだけ。それが2行目。

## License

MIT
