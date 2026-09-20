#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生ログから、Claude Code が書いた最後の圧縮要約を取り出す。

  --list             セッション一覧
  --find NAME        名前かIDで探す
  --session X        X は名前の一部・IDの先頭・ログのパスのどれか。最後の要約を出す

要約が無ければ「要約がありません」と出して終了コード 2。
標準ライブラリだけ。通信しない。壊れた行は黙って飛ばす。
"""
import argparse, json, os, sys
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECTS = os.path.join(os.path.expanduser("~"), ".claude", "projects")
KEY = '"isCompactSummary":true'


def sessions(root):
    """projects 以下の .jsonl を、名前つきで返す。"""
    out = []
    if not os.path.isdir(root):
        return out
    for proj in sorted(os.listdir(root)):
        d = os.path.join(root, proj)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(d, name)
            titles = []
            try:
                with open(path, encoding="utf-8", errors="replace") as fp:
                    for line in fp:
                        if '"customTitle"' not in line and '"aiTitle"' not in line:
                            continue
                        try:
                            o = json.loads(line)
                        except Exception:
                            continue
                        t = o.get("customTitle") or o.get("aiTitle")
                        if t and t not in titles:
                            titles.append(t)
            except OSError:
                continue
            out.append({"path": path, "id": name[:-6], "titles": titles[-3:],
                        "mb": os.path.getsize(path) / 1048576,
                        "mtime": datetime.fromtimestamp(os.path.getmtime(path))})
    return out


def find(all_sessions, query):
    q = query.lower()
    hits = [s for s in all_sessions if s["id"].lower().startswith(q)]
    if len(hits) == 1:
        return hits
    return hits + [s for s in all_sessions
                   if s not in hits and any(q in t.lower() for t in s["titles"])]


def row(s):
    return f"  {s['mtime']:%Y-%m-%d %H:%M}  {s['mb']:6.1f}MB  {s['id'][:8]}  {' / '.join(s['titles'][-2:]) or '(無題)'}"


def last_summary(path):
    """最後の圧縮要約の (本文, 時刻, 圧縮回数) を返す。無ければ本文 None。"""
    text, ts, compacts = None, "", 0
    with open(path, encoding="utf-8", errors="replace") as fp:
        for line in fp:
            if '"compact_boundary"' in line:
                compacts += 1
            if KEY not in line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if not isinstance(o, dict) or not o.get("isCompactSummary"):
                continue
            c = (o.get("message") or {}).get("content")
            if isinstance(c, list):
                c = "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
            if isinstance(c, str) and c.strip():
                text, ts = c, o.get("timestamp", "")
    return text, ts, compacts


def local(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts or "不明"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="last_summary")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--find", metavar="NAME")
    g.add_argument("--session", metavar="NAME_ID_OR_PATH")
    ap.add_argument("--projects", default=PROJECTS)
    a = ap.parse_args(argv)

    if a.list or a.find:
        all_s = sessions(a.projects)
        hits = find(all_s, a.find) if a.find else sorted(all_s, key=lambda s: s["mtime"], reverse=True)
        print(f"候補 {len(hits)}件")
        for s in hits:
            print(row(s))
        return 0 if hits else 1

    if os.path.isfile(a.session):
        path = a.session
    else:
        hits = find(sessions(a.projects), a.session)
        if len(hits) != 1:
            print(f"候補が{len(hits)}件です。IDの先頭8桁で指定し直してください。")
            for s in hits:
                print(row(s))
            return 1
        path = hits[0]["path"]

    text, ts, compacts = last_summary(path)
    print(f"ログ: {path}")
    if not text:
        print("要約がありません。前のセッションで /compact を打ってから、もう一度実行してください。")
        return 2
    print(f"圧縮回数: {compacts}回 ／ この要約の時刻: {local(ts)}（この時刻より後の会話は入っていない）")
    print("----- ここから要約 -----")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
