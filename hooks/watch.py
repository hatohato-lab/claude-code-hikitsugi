#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""見張り（UserPromptSubmit フック）。圧縮が起きたセッションで、1回だけ「引き継ぎどき」を知らせる。

基準は圧縮の回数だけ。ファイルの大きさは見ない（大きさと文脈の重さは一致しないため）。
同じ回数では2度言わない。失敗しても黙って終わる。
"""
import io, json, os, sys, tempfile


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
        path = data.get("transcript_path") or ""
        sid = data.get("session_id") or os.path.splitext(os.path.basename(path))[0]
        if not path or not os.path.isfile(path) or not sid:
            return 0
        compacts, title = 0, ""
        with io.open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if '"compact_boundary"' in line:
                    compacts += 1
                elif '"customTitle"' in line:
                    try:
                        title = json.loads(line).get("customTitle") or title
                    except Exception:
                        pass
        if compacts < 1:
            return 0
        marker = os.path.join(tempfile.gettempdir(), f"hikitsugi_watch_{sid}.txt")
        try:
            if io.open(marker, encoding="utf-8").read().strip() == str(compacts):
                return 0
        except Exception:
            pass
        with io.open(marker, "w", encoding="utf-8") as f:
            f.write(str(compacts))
        name = title or "(無名)"
        msg = (f"【引き継ぎの案内】このセッション「{name}」は圧縮が{compacts}回起きています。"
               f"要約から漏れた内容があります。ユーザーに1行で次を伝えてください：\n"
               f"区切りのよいところで /compact を打ち、新しいセッションで「{name}を継いで」と言えば続きから始められます。")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                 "additionalContext": msg}}, ensure_ascii=False))
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
