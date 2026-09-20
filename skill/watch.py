#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""見張り（UserPromptSubmit フック）：いまのチャットが重くなったら「引き継いでください」と知らせる。

発言のたびに自分の生ログを測り、基準を超えたときだけ 1 行の案内を会話に足す。
基準に届かないときは何も出さない。失敗しても黙って終わる（会話を止めない）。
同じ状態で何度も言わないよう、知らせた印を一時フォルダに残す。

登録（~/.claude/settings.json の hooks.UserPromptSubmit に1本足す）:
  {"hooks": [{"type": "command", "command": "python -X utf8 \"<このファイルの絶対パス>\"", "timeout": 15}]}
基準の変更: 環境変数 HIKITSUGI_MB（既定 15）・HIKITSUGI_COMPACTS（既定 1）
"""
import os, sys, io, json, glob, tempfile

PROJECTS = os.path.join(os.path.expanduser("~"), ".claude", "projects")
MB_LIMIT = float(os.environ.get("HIKITSUGI_MB", "15"))
COMPACT_LIMIT = int(os.environ.get("HIKITSUGI_COMPACTS", "1"))


def read_hook_input():
    """UserPromptSubmit フックの標準入力（JSON）を読む。読めなければ空の辞書。

    2026-09-20 修正: 以前は sys.stdin.read() の返り値を捨てていた。
    公式のフック入力には session_id と transcript_path が入っているので、そちらを優先する。
    """
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def find_own_log(hook_input=None, projects=None):
    """測る対象のログを決める。

    優先順位（2026-09-20 修正）:
      1. フック入力の transcript_path（確実。標準のホーム配下でなくてよい）
      2. フック入力の session_id から projects 以下を探す
      3. 互換: 環境変数 CLAUDE_CODE_SESSION_ID から探す
    どれも当たらなければ (None, セッションID or None) を返し、呼び出し側は無音で終わる。
    別セッションを指す環境変数があっても、フック入力があればそちらを使う。
    """
    hook_input = hook_input or {}
    root = projects or PROJECTS
    sid = hook_input.get("session_id") or None

    path = hook_input.get("transcript_path")
    if isinstance(path, str) and path and os.path.isfile(path):
        return path, sid or os.path.splitext(os.path.basename(path))[0]

    for candidate in (sid, os.environ.get("CLAUDE_CODE_SESSION_ID")):
        if not candidate:
            continue
        hits = glob.glob(os.path.join(root, "*", candidate + ".jsonl"))
        if hits:
            return hits[0], candidate
        sid = sid or candidate
    return None, sid


def measure(path):
    size_mb = os.path.getsize(path) / 1048576
    compacts, title = 0, ""
    with io.open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"isCompactSummary":true' in line or '"compact_boundary"' in line:
                compacts += 1
            elif '"custom-title"' in line:
                try:
                    title = json.loads(line).get("customTitle") or title
                except Exception:
                    pass
    return size_mb, compacts, title


def main():
    hook_input = read_hook_input()
    try:
        path, sid = find_own_log(hook_input)
        if not path or not sid:
            return 0
        size_mb, compacts, title = measure(path)
        over = compacts >= COMPACT_LIMIT or size_mb > MB_LIMIT
        if not over:
            return 0
        # 同じ状態（圧縮回数・MBの整数部）では1回だけ知らせる
        stamp = f"{compacts}-{int(size_mb)}"
        marker = os.path.join(tempfile.gettempdir(), f"hikitsugi_watch_{sid}.txt")
        try:
            if io.open(marker, encoding="utf-8").read().strip() == stamp:
                return 0
        except Exception:
            pass
        with io.open(marker, "w", encoding="utf-8") as f:
            f.write(stamp)
        why = []
        if compacts >= COMPACT_LIMIT:
            why.append(f"圧縮{compacts}回")
        if size_mb > MB_LIMIT:
            why.append(f"ログ{size_mb:.1f}MB")
        skill_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hikitsugi.py")
        msg = (f"【引き継ぎの案内】このチャット「{title or '(無名)'}」は重くなっています（{'・'.join(why)}）。"
               f"記憶が一部消えている可能性があります。次を行ってください：\n"
               f"1. 本人に「このチャットは重くなっているので引き継ぎメモを作ります」と1行で伝える\n"
               f"2. `python -X utf8 \"{skill_py}\" --session {sid[:8]} --brief --out \"<引き継ぎメモの置き場>/<日付>_<チャット名>_自動生成\"` を実行する\n"
               f"3. 出力された【引き継ぎ】の3行をそのままコードブロックで表示し、「新しいチャットを開いてこれを貼ってください」と伝える\n"
               f"（置き場はプロジェクトの決まりに従う。無ければ ~/.claude/hikitsugi-out/）")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                 "additionalContext": msg}}, ensure_ascii=False))
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
