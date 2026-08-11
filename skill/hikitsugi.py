#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
claude-code-hikitsugi — 前のチャットの生ログから「引き継ぎメモ」を再建する

Claude Code の会話ログ（~/.claude/projects/**/*.jsonl）をストリーミング解析し、
新しいチャットが続きから始められる handoff.md / digest.md を生成する。

- 標準ライブラリのみ。通信なし。完全ローカル処理。
- 秘密情報のマスキングは既定でON。マスキングは切り詰めより先に、抽出の境界で行う。
- 未知のイベントtype・壊れた行・辞書でないJSONは黙って読み飛ばす（形式変化に耐える）。
- タイムスタンプはUTCで記録されているため、表示・--since判定はローカル時刻に変換する。
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, date

# Windowsコンソールの文字化け対策
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DEFAULT_PROJECTS = os.path.join(os.path.expanduser("~"), ".claude", "projects")
DEFAULT_OUT_ROOT = os.path.join(os.path.expanduser("~"), ".claude", "hikitsugi-out")

# ---------------------------------------------------------------- マスキング

MASK_PATTERNS = [
    # BitLocker回復キー等の 6桁×8組
    (re.compile(r"\b\d{6}(?:-\d{6}){7}\b"), "[MASKED:recovery-key]"),
    # 各種APIキー・トークン
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"), "[MASKED:api-key]"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"), "[MASKED:github-token]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "[MASKED:github-token]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[MASKED:aws-key]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"), "[MASKED:slack-token]"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
     "[MASKED:jwt]"),
    # 「パスワード: xxxx」文脈は直後の最大3語まで隠す（空白入りの合言葉対策）
    (re.compile(r"(パスワード|password|passwd|pwd)(\s*[:：=]\s*)\S+(?:\s+\S+){0,2}",
                re.IGNORECASE),
     r"\1\2[MASKED]"),
]
EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]*@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b")


def mask_text(text):
    """秘密情報らしきものを [MASKED:*] に置換する。

    メールアドレスは先頭1文字とドメインを残す（完全匿名化ではない。READMEに明記）。
    既知のパターンしか捕まえられないため、出力の共有前には人間の目視確認が必要。
    """
    for pat, repl in MASK_PATTERNS:
        text = pat.sub(repl, text)
    text = EMAIL_RE.sub(lambda m: m.group(1) + "***@" + m.group(2), text)
    return text


def _identity(text):
    return text


# ---------------------------------------------------------------- 作業記録の検出

# 引き継ぎで要るのは事務処理の記録＝「何をしたか・何が起きたか・どう直したか」。
# AI側の発言に、その3種類が定型句として現れる。人との関係性・感情は対象にしない。
# 判定は上から順（先に当たったものを採用）。完了報告に「エラーを直した」等が
# 混ざることがあるため、成否の確定した「完了」を最優先で見る。
WORK_PATTERNS = [
    (re.compile(r"完了(し|です|しました)|完成(し|です|しました)|公開しました|保存しました"
                r"|作成しました|登録しました|記入しました|終わりました|できました"
                r"|プッシュ(済み|しました)|\bPASS\b"), "完了"),
    # 「トライ&エラー」等の慣用句は失敗報告ではないので除く
    (re.compile(r"失敗し|(?<!トライ&)(?<!トライアンド)エラー|できませんでした|うまくいか"
                r"|こけ(まし|て)|即死|見つかりませ|問題が(見つ|あり)|不具合"
                r"|落ちて(い)?ました"), "失敗"),
    (re.compile(r"修正し|直します|直しました|再実行|再起動|やり直|復元し"
                r"|対応しました|変更しました|入れ替え"), "対処"),
]


def detect_work(text):
    """AIの発言が作業報告なら、その種別（完了・失敗・対処）を返す。違えば None。"""
    if not text:
        return None
    for pat, label in WORK_PATTERNS:
        if pat.search(text):
            return label
    return None


# ---------------------------------------------------------------- 時刻

def to_local(ts):
    """UTCのISO文字列（...Z）をローカル時刻のdatetimeに変換。失敗はNone。"""
    if not isinstance(ts, str) or len(ts) < 10:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def fmt_day(dt):
    return dt.strftime("%Y-%m-%d") if dt else "????-??-??"


def fmt_hm(dt):
    return dt.strftime("%H:%M") if dt else "--:--"


# ---------------------------------------------------------------- ログ読み

def iter_events(path):
    """1行=1イベントのJSON辞書を順に返す。壊れた行・辞書でない行は黙って飛ばす。"""
    with open(path, encoding="utf-8", errors="replace") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                yield obj


_SYSTEM_HEADS = ("<system-reminder", "<local-command", "<command-name")


def _iter_content_items(message, item_type):
    """message.content から指定typeの項目を順に返す。"""
    if not isinstance(message, dict):
        return
    content = message.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == item_type:
                yield item


def _content_texts(message):
    """message.content から人間向けテキストを取り出す。

    システム由来ブロック（system-reminder等）は項目単位で除外する。
    こうすると、リマインダと本文が同居するメッセージでも本文だけが残る。
    """
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if isinstance(content, str):
        s = content.strip()
        if s and not s.lstrip().startswith(_SYSTEM_HEADS):
            return [content]
        return []
    texts = []
    for item in _iter_content_items(message, "text"):
        t = item.get("text") or ""
        if t.strip() and not t.lstrip().startswith(_SYSTEM_HEADS):
            texts.append(t)
    return texts


def _stringify(x, limit):
    if isinstance(x, str):
        s = x
    elif isinstance(x, list):
        parts = []
        for item in x:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
            else:
                parts.append(str(item))
        s = " ".join(parts)
    else:
        s = str(x)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def _title_of(event):
    return event.get("customTitle") or event.get("aiTitle")


# ---------------------------------------------------------------- セッション探索

def scan_sessions(projects_root, read_titles=True):
    """全プロジェクトの .jsonl を走査する。

    read_titles=False ならファイルの中身を読まない（IDだけで解決する高速パス用）。
    ※サブフォルダ（subagents/ 等）のログは対象外（README「制限」参照）。
    """
    sessions = []
    if not os.path.isdir(projects_root):
        return sessions
    for proj in sorted(os.listdir(projects_root)):
        proj_dir = os.path.join(projects_root, proj)
        if not os.path.isdir(proj_dir):
            continue
        for name in sorted(os.listdir(proj_dir)):
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(proj_dir, name)
            if not os.path.isfile(path):
                continue
            info = {
                "path": path,
                "project": proj,
                "session_id": name[:-6],
                "size_mb": round(os.path.getsize(path) / 1024 / 1024, 1),
                "mtime": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M"),
                "titles": [],
            }
            if read_titles:
                titles = []
                try:
                    with open(path, encoding="utf-8", errors="replace") as fp:
                        for line in fp:
                            # タイトルを含みうる行だけJSONパースする（高速化）
                            if '"customTitle"' not in line and '"aiTitle"' not in line:
                                continue
                            try:
                                d = json.loads(line)
                            except Exception:
                                continue
                            if not isinstance(d, dict):
                                continue
                            t = _title_of(d)
                            if t and t not in titles:
                                titles.append(t)
                except OSError:
                    continue
                info["titles"] = titles[-5:]
            sessions.append(info)
    return sessions


def find_sessions(sessions, query):
    """セッションを探す。一意なID前方一致が最優先。次にタイトル部分一致。"""
    q = query.lower()
    id_hits = [s for s in sessions if s["session_id"].lower().startswith(q)]
    if len(id_hits) == 1:
        return id_hits
    title_hits = []
    for s in sessions:
        if any(q in t.lower() for t in s["titles"]):
            title_hits.append(s)
    seen = set()
    merged = []
    for s in id_hits + title_hits:
        if s["path"] not in seen:
            seen.add(s["path"])
            merged.append(s)
    return merged


def format_session_row(s):
    t = " / ".join(s["titles"][-2:]) or "(無題)"
    return f"  {s['mtime']}  {s['size_mb']:6.1f}MB  {s['session_id'][:8]}  {t}"


# ---------------------------------------------------------------- 抽出

def extract(path, since=None, max_chars=240, masker=None):
    """ログから引き継ぎに必要な素材を抽出する。

    マスキングは切り詰めの前に全文へ適用する（切断面をまたぐ秘密の漏れを防ぐ）。
    since はローカル日付（date）で判定する。タイトル行は since の対象外。
    """
    m = masker or _identity
    data = {
        "timeline": [],       # (dt, "人"|"AI", text)
        "errors": [],         # (dt, snippet)
        "work": [],           # (dt, "完了"|"失敗"|"対処", text)
        "files_written": Counter(),
        "titles": [],
        "first_dt": None,
        "last_dt": None,
        "events": 0,
    }
    for ev in iter_events(path):
        data["events"] += 1
        etype = ev.get("type")

        # タイトルは期間フィルタより先に拾う（チャット名は期間に関係なく必要）
        if etype in ("custom-title", "ai-title"):
            t = _title_of(ev)
            if t and t not in data["titles"]:
                data["titles"].append(t)
            continue

        dt = to_local(ev.get("timestamp"))
        if dt:
            if data["first_dt"] is None:
                data["first_dt"] = dt
            data["last_dt"] = dt
        if since and dt and dt.date() < since:
            continue
        if ev.get("isSidechain"):
            continue

        msg = ev.get("message")
        if etype == "user":
            texts = _content_texts(msg)
            if texts:
                text = re.sub(r"\s+", " ", " ".join(texts)).strip()
                if text:
                    data["timeline"].append((dt, "人", m(text)[:max_chars]))
            for tr in _iter_content_items(msg, "tool_result"):
                if tr.get("is_error"):
                    data["errors"].append((dt, m(_stringify(tr.get("content"), 500))[:160]))
        elif etype == "assistant":
            texts = _content_texts(msg)
            if texts:
                text = re.sub(r"\s+", " ", " ".join(texts)).strip()
                if text:
                    full = m(text)
                    data["timeline"].append((dt, "AI", full[:max_chars]))
                    label = detect_work(full)
                    if label:
                        row = (dt, label, full[:160])
                        # 同じ報告の重複（連続する同一文）は1件に畳む
                        if not data["work"] or data["work"][-1][1:] != row[1:]:
                            data["work"].append(row)
            for tu in _iter_content_items(msg, "tool_use"):
                if tu.get("name") in ("Write", "Edit", "NotebookEdit"):
                    fp_ = (tu.get("input") or {}).get("file_path") or ""
                    if fp_:
                        data["files_written"][fp_] += 1
    return data


# ---------------------------------------------------------------- 出力

HANDOFF_INSTRUCTION = """\
## このファイルを読んでいるAI（新しいチャット）へ

これは前のチャットの生ログから機械抽出した引き継ぎ材料です。次の手順で引き継ぎを完了してください。

1. 下の各節と digest.md を読む（大きい場合は末尾＝直近から読む。「人」がユーザー、「AI」が前のClaude）
2. 次の7点に整理して、ユーザーに宣言する
   ①このチャットの目標 ②決まったこと（理由つき） ③未完了タスクと次の一手
   ④つまずき履歴（同じ失敗をしない） ⑤保留中の判断 ⑥固有名詞の辞書 ⑦読み取れなかった不明点
   ※①〜④の材料は「作業の記録」（完了／失敗／対処）の節を使う
3. 細部が必要になったら、下記の生ログをgrepで検索する（全部は読まない。大きすぎる）
4. [MASKED:...] は秘密情報の跡。**復元も推測もしない**
5. 材料に無いことを「決まっていた」と思い込まない。曖昧なら⑦で正直に言う

注意: サブエージェント（並行作業）の会話は別ファイルのため、この材料には含まれない。
"""


def write_outputs(data, log_path, out_dir, do_mask=True, since=None):
    os.makedirs(out_dir, exist_ok=True)
    m = mask_text if do_mask else _identity

    # ---- digest.md（時系列の発言記録。人とAIを併記）
    digest_path = os.path.join(out_dir, "digest.md")
    with open(digest_path, "w", encoding="utf-8") as fp:
        fp.write("# ダイジェスト（発言の時系列記録）\n\n")
        fp.write("- 「人」= ユーザーの発言、「AI」= 前のClaudeの発言（どちらも冒頭のみ）\n")
        fp.write(f"- 元ログ: {log_path}\n")
        if since:
            fp.write(f"- 抽出対象: {since} 以降のみ（--since指定）\n")
        fp.write("\n")
        cur_day = None
        for dt, who, text in data["timeline"]:
            d = fmt_day(dt)
            if d != cur_day:
                fp.write(f"\n## {d}\n\n")
                cur_day = d
            fp.write(f"- {fmt_hm(dt)} 【{who}】{text}\n")

    # ---- handoff.md（引き継ぎの入口）
    human = [(dt, t) for dt, who, t in data["timeline"] if who == "人"]
    handoff_path = os.path.join(out_dir, "handoff.md")
    with open(handoff_path, "w", encoding="utf-8") as fp:
        fp.write("# 引き継ぎメモ（claude-code-hikitsugi が生成）\n\n")
        titles = " / ".join(data["titles"][-3:]) or "(タイトルなし)"
        fp.write(f"- チャット名: {m(titles)}\n")
        fp.write(f"- 期間: {fmt_day(data['first_dt'])} 〜 {fmt_day(data['last_dt'])}"
                 "（ローカル時刻）\n")
        fp.write(f"- 規模: イベント{data['events']:,}件"
                 f"（人の発言{len(human):,}件・AI発言"
                 f"{len(data['timeline']) - len(human):,}件）\n")
        fp.write(f"- マスキング: {'ON' if do_mask else 'OFF（注意）'}\n")
        if since:
            fp.write(f"- 抽出対象: {since} 以降のみ（--since指定。期間・イベント数は全体の値）\n")
        fp.write("\n")
        fp.write(HANDOFF_INSTRUCTION)
        fp.write("\n## 生ログ（無傷の全記録・grepで掘る）\n\n")
        fp.write(f"```\n{log_path}\n```\n\n")
        fp.write("検索例（PowerShell / bash）:\n\n")
        fp.write("```\ngrep -n \"探したい語\" \"" + log_path + "\" | head -20\n```\n\n")

        fp.write("## よく書き込んだファイル（作業の中心地・上位20）\n\n")
        top = data["files_written"].most_common(20)
        if top:
            for p, c in top:
                fp.write(f"- {c:3d}回  {m(p)}\n")
        else:
            fp.write("- （記録なし）\n")

        fp.write("\n## 作業の記録（何をしたか・何が起きたか・どう直したか・直近40件）\n\n")
        fp.write("種別は 完了／失敗／対処 の3つ。前のチャットの事務処理の流れはここで追える。\n\n")
        works = data.get("work", [])[-40:]
        if works:
            for dt, label, text in works:
                fp.write(f"- {fmt_day(dt)} {fmt_hm(dt)} 【{label}】{text}\n")
        else:
            fp.write("- （記録なし）\n")

        fp.write("\n## プログラムのエラー（参考・直近15件）\n\n")
        errs = data["errors"][-15:]
        if errs:
            for dt, snip in errs:
                fp.write(f"- {fmt_day(dt)} {fmt_hm(dt)}  {snip}\n")
        else:
            fp.write("- （記録なし）\n")

        fp.write("\n## 直近のユーザー発言（最後の40件・新しいほど下）\n\n")
        for dt, text in human[-40:]:
            fp.write(f"- {fmt_day(dt)} {fmt_hm(dt)}  {text}\n")

        fp.write("\n## 全発言のダイジェスト\n\n")
        fp.write(f"同じフォルダの digest.md（{len(data['timeline']):,}件）を参照。\n")

    return handoff_path, digest_path


# ---------------------------------------------------------------- CLI

def _parse_since(s):
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", s or ""):
        raise argparse.ArgumentTypeError("YYYY-MM-DD 形式で指定してください（例: 2026-08-01）")
    y, mo, d = map(int, s.split("-"))
    return date(y, mo, d)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="hikitsugi",
        description="Claude Code の会話ログから引き継ぎメモを生成する（完全ローカル・通信なし）")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="セッション一覧を表示")
    mode.add_argument("--find", metavar="NAME", help="チャット名でセッションを探す")
    mode.add_argument("--session", metavar="ID_OR_NAME", help="このセッションの引き継ぎメモを生成")
    ap.add_argument("--projects", default=DEFAULT_PROJECTS,
                    help="projectsフォルダ（既定: ~/.claude/projects）")
    ap.add_argument("--out", metavar="DIR",
                    help="出力先フォルダ（既定: ~/.claude/hikitsugi-out/<セッションID>/）")
    ap.add_argument("--since", metavar="YYYY-MM-DD", type=_parse_since,
                    help="この日付（ローカル時刻）以降だけを対象にする")
    ap.add_argument("--max-chars", type=int, default=240,
                    help="1発言あたりの最大文字数（既定240）")
    ap.add_argument("--no-mask", action="store_true",
                    help="マスキングを無効化（秘密情報が出力に残る。注意）")
    args = ap.parse_args(argv)

    if args.list or (not args.find and not args.session):
        sessions = scan_sessions(args.projects)
        print(f"セッション一覧（{args.projects}）")
        for s in sorted(sessions, key=lambda x: x["mtime"], reverse=True):
            print(format_session_row(s))
        if not sessions:
            print("  （見つかりません）")
        return 0

    if args.find:
        sessions = scan_sessions(args.projects)
        hits = find_sessions(sessions, args.find)
        print(f"「{args.find}」の候補: {len(hits)}件")
        for s in hits:
            print(format_session_row(s))
        if not hits:
            print("  見つかりません。--list で全セッションを確認してください。")
            return 1
        return 0

    # --session: まずIDだけの高速解決を試す（全ログ走査を避ける）
    light = scan_sessions(args.projects, read_titles=False)
    hits = [s for s in light if s["session_id"].lower().startswith(args.session.lower())]
    if len(hits) != 1:
        sessions = scan_sessions(args.projects)  # タイトルつきで再走査
        hits = find_sessions(sessions, args.session)
    if len(hits) == 0:
        print(f"エラー: 「{args.session}」に一致するセッションがありません。--list で確認してください。")
        return 1
    if len(hits) > 1:
        print(f"エラー: 候補が{len(hits)}件あります。セッションID（8桁で可）で指定し直してください。")
        for s in hits:
            print(format_session_row(s))
        return 1

    s = hits[0]
    out_dir = args.out or os.path.join(DEFAULT_OUT_ROOT, s["session_id"])
    do_mask = not args.no_mask
    print(f"解析中: {s['path']}（{s['size_mb']}MB）...")
    data = extract(s["path"], since=args.since, max_chars=args.max_chars,
                   masker=mask_text if do_mask else None)
    handoff, digest = write_outputs(data, s["path"], out_dir,
                                    do_mask=do_mask, since=args.since)
    human = sum(1 for _, who, _ in data["timeline"] if who == "人")
    print("完了:")
    print(f"  引き継ぎメモ: {handoff}")
    print(f"  ダイジェスト: {digest}")
    print(f"  人の発言 {human:,}件 / AI発言 {len(data['timeline']) - human:,}件 / "
          f"作業記録 {len(data['work']):,}件 / エラー記録 {len(data['errors']):,}件 / "
          f"書き込みファイル {len(data['files_written']):,}種")
    if args.no_mask:
        print("  ★警告: マスキング無効。出力に秘密情報が含まれ得ます。共有しないでください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
