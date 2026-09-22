---
name: hikitsugi

description: >-
  ①いまのセッションの作業を新しいセッションへ引き継ぐ。
  ②作業の一覧を時間順に出して番号で選んでもらい、選ばれた分だけで引き継ぎ書を作り、新セッションに貼る2行を出す。
  ③圧縮の要約には頼らず、生ログといまの記憶から書く。
  ④「引き継ぎたい」「引き継ぎ書を作って」「新セッションに移りたい」で発火する。
---

# hikitsugi

最重要の手順を先頭に置く。圧縮後に戻るのは先頭 5,000 トークンだけのため。

## 目次

1. 全体の流れ（省略しない4手順）
2. 作業一覧の形（並べ方と番号の受け取り方）
3. 作業一覧のコマンド（生ログから時間順に抽出）
4. 引き継ぎ書の中身（この順に並べる6節）
5. 新セッションへの渡し方（貼る2行のひな形）
6. セッション情報の表（引き継ぎ書の末尾に付ける）
7. 引き継ぐ根拠（圧縮の要約に頼らない理由）
8. 禁止（やらないこと）

## 1. 全体の流れ（省略しない4手順）

1. このセッションの作業を時間順に並べた一覧を出し、引き継ぐものを番号で選んでもらう。
   番号が返るまで、ここで止まる。
2. 選ばれた番号の作業だけで引き継ぎ書を書き、作業フォルダの中に保存する。
   ファイル名は `<セッション名>_<yyyyMMdd_HHmm>_引き継ぎ書.md`。
3. 保存したパスと「新セッションに貼る2行」を、1つのコードブロックで見せる。
4. 検証のやり方を1行そえる。「新セッションで『引き継ぎ書の要点を3行で』と言わせ、読めたのを確かめてから旧を閉じる」。

`/compact` は使わない。打たせない。圧縮の要約には一切頼らない。
引き継ぎ書は、いまのコンテキストにある生きた記憶から自分で書く。

## 2. 作業一覧の形（並べ方と番号の受け取り方）

機械的に並べると、規則どおりの項目しか残らない。
どれを持っていくかは人の判断が要るので、選ぶ手続きを必ず挟む。

一覧はこの形で出す。番号・時間帯・作業名の3つだけ。

```
1  09-20 20:38〜21:10  退避30件をルールのフォルダへ戻した
2  09-20 21:10〜22:30  ルール47件の重複6組を検出
3  09-21 00:30        ルール設計書のHTMLをTODOに登録
4  09-21 09:40〜10:32  スキル「hikitsugi」を作成

番号で選んでください（全部なら「全部」）
```

書き方4点。

- 作業名は25字前後の具体名。「作業」「対応」「確認」のような一般語は使わない
- 時刻は生ログの実測値。1件だけの作業は開始時刻だけ書く
- 10行を超えたら、近い話題をまとめて10行以内にする
- 最後の1行「番号で選んでください（全部なら「全部」）」は必ず付ける

番号が返ったら、その作業だけを引き継ぎ書に書く。
選ばれなかった作業は、4節のどこにも書かない。

## 3. 作業一覧のコマンド（生ログから時間順に抽出）

生ログは次の場所にある。`<作業フォルダー>` はパス区切りをハイフンに置き換えた名前になる。

```
C:\Users\<ユーザー名>\.claude\projects\<作業フォルダー>\<セッションID>.jsonl
```

PowerShell で、自分の発言だけを時間順に取り出す。

```
$p = "C:\Users\<ユーザー名>\.claude\projects\<作業フォルダー>\<セッションID>.jsonl"
$sr = New-Object System.IO.StreamReader($p, [System.Text.Encoding]::UTF8)
while (($l = $sr.ReadLine()) -ne $null) {
  if ($l.Length -gt 200000) { continue }
  if ($l -notmatch '"type":"user"') { continue }
  try { $o = $l | ConvertFrom-Json } catch { continue }
  if ($o.type -ne 'user' -or -not $o.timestamp) { continue }
  $t = ([datetime]$o.timestamp).ToLocalTime()
  $c = $o.message.content
  $txt = if ($c -is [string]) { $c } else { ($c | Where-Object { $_.type -eq 'text' } | ForEach-Object { $_.text }) -join '' }
  if (-not $txt) { continue }
  if ($txt -match '^<(local-command|command-name|system-reminder)' -or $txt -match '^\[Request interrupted') { continue }
  if ($txt.Length -gt 40) { $txt = $txt.Substring(0,40) }
  "{0:MM-dd HH:mm}  {1}" -f $t, ($txt -replace "`r?`n"," ")
}
$sr.Close()
```

出た時刻を、話題の切れ目でまとめて1行にする。
圧縮より前の発言もここに出る。要約に無くても、生ログには残っているため。

## 4. 引き継ぎ書の中身（この順に並べる6節）

1. 作業名と現在地 …… 何の作業で、どこまで終わったか。3行以内
2. 決定と理由 …… 決定1件につき「決定＋なぜ」を1行ずつ。理由は書かない限り消える
3. 未承認・保留 …… 承認や判断を待っているものの一覧。勝手に進めない印
4. 成果物 …… 絶対パスを1件1行で
5. 次の一手 …… 新セッションが最初にやること。1〜3件
6. 再取得コマンド …… 消えたデータを取り直すコマンド。一時フォルダの結果は消えるので、要るものは本文か作業フォルダへ写してから書く

## 5. 新セッションへの渡し方（貼る2行のひな形）

```
<保存した引き継ぎ書の絶対パス>
を読んで、要点を3行で言ってから「次の一手」の1から続きを始めて
```

## 6. セッション情報の表（引き継ぎ書の末尾に付ける）

自分のセッションIDは、一時フォルダのパスに入っている。

```
...\Temp\claude\<作業フォルダー>\<セッションID>\scratchpad
```

見つからなければ、推測せずに1行で聞く。

```
$id = "<自分のセッションID>"
$p  = "C:\Users\<ユーザー名>\.claude\projects\<作業フォルダー>\$id.jsonl"
$f  = Get-Item $p
$sr = New-Object System.IO.StreamReader($p, [System.Text.Encoding]::UTF8)
$name=""; $first=""; $last=""; $compacts=0; $n=0; $model=""
while (($l = $sr.ReadLine()) -ne $null) {
  $n++
  if ($l -match '"customTitle":"([^"]+)"') { $name = $Matches[1] }
  if ($l -match '"subtype":"compact_boundary"') { $compacts++ }
  if ($l -match '"model":"(claude-[^"]+)"') { $model = $Matches[1] }
  if ($l -match '"timestamp":"([^"]+)"') { if (-not $first) { $first = $Matches[1] }; $last = $Matches[1] }
}
$sr.Close()
"名前          $name"
"セッションID  $id"
"稼働          " + ([datetime]$first).ToLocalTime().ToString("MM-dd HH:mm") + "〜" + ([datetime]$last).ToLocalTime().ToString("MM-dd HH:mm")
"圧縮回数      $compacts 回"
"ログ          {0:N1} MB / {1:N0} 行   {2}" -f ($f.Length/1MB), $n, $model
```

## 7. 引き継ぐ根拠（圧縮の要約に頼らない理由）

| 症状 | 圧縮で起きていること | 出典 |
|---|---|---|
| 存在しないパスを言う | 圧縮直後に読み直すファイルは5件だけ。5,000トークン超は中身なしのパスだけ戻る | 1 |
| 決めたことを蒸し返す | 圧縮前の思考は引き継がれない。判断の理由だけが消える | 2 |
| ルールを守らない | paths 付きルールと下位フォルダの CLAUDE.md は要約で消える。ルート直下は残る | 1, 3 |
| 全体に精度が落ちる | 会話が長いほど品質が落ちると公式が明言 | 2, 4 |

```
1  https://code.claude.com/docs/en/context-window#what-survives-compaction
2  https://platform.claude.com/docs/en/build-with-claude/compaction
3  https://code.claude.com/docs/en/memory
4  https://www.trychroma.com/research/context-rot
```

「圧縮N回で引き継ぐ」という公式のしきい値は無い。
目安は「圧縮0回かつ占有70%未満なら続投」。これは運用上の目安で、公式の数値ではない。

## 8. 禁止（やらないこと）

- `/compact` を提案しない。打たせない
- 一覧を出さずに引き継ぎ書を書き始めない。番号が返る前に保存しない
- 他のセッションの生ログを開かない
- 要るデータを一時フォルダに置いたままにしない
- 要約に無いことを「決まっていた」と言わない
- 取れなかった項目は「不明」と書く。推測で埋めない
