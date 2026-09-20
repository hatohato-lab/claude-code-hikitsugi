#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""claude-code-hikitsugi v3 の機械判定（外部オラクル）。

  python eval/oracle.py --selftest

作り物のログ（eval/corpus/）を食わせ、取り出しスクリプトと見張りフックの出力を判定する。
全PASSが合格条件。実ログは使わない。
"""
import json, os, shutil, subprocess, sys, tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "eval", "corpus")
SCRIPT = os.path.join(ROOT, "skills", "hikitsugi", "scripts", "last_summary.py")
WATCH = os.path.join(ROOT, "hooks", "watch.py")
PY = [sys.executable, "-X", "utf8"]
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))


def run(args, stdin=""):
    r = subprocess.run(args, input=stdin.encode("utf-8"), capture_output=True)
    return r.returncode, r.stdout.decode("utf-8", "replace")


def selftest():
    with_s = os.path.join(CORPUS, "with_summary.jsonl")
    no_s = os.path.join(CORPUS, "no_summary.jsonl")

    # ---- 構成ファイル
    for rel in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "hooks/hooks.json"):
        p = os.path.join(ROOT, *rel.split("/"))
        try:
            json.load(open(p, encoding="utf-8"))
            check(f"{rel} が JSON として読める", True)
        except Exception as e:
            check(f"{rel} が JSON として読める", False, str(e))
    mp = json.load(open(os.path.join(ROOT, ".claude-plugin", "marketplace.json"), encoding="utf-8"))
    check("marketplace.json の plugin の source が ./ を指す",
          mp["plugins"][0].get("source") == "./")
    hk = json.load(open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8"))
    cmd = hk["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    check("hooks.json が watch.py を CLAUDE_PLUGIN_ROOT 経由で呼ぶ",
          "watch.py" in cmd and "${CLAUDE_PLUGIN_ROOT}" in cmd)
    skill = open(os.path.join(ROOT, "skills", "hikitsugi", "SKILL.md"), encoding="utf-8").read()
    check("SKILL.md に name: hikitsugi がある", "name: hikitsugi" in skill)
    check("SKILL.md が last_summary.py を案内している", "last_summary.py" in skill)
    check("SKILL.md が /compact を促す文を持つ", "/compact" in skill)

    # ---- 取り出しスクリプト：要約あり
    code, out = run(PY + [SCRIPT, "--session", with_s])
    check("要約ありのログで終了コード0", code == 0, f"code={code}")
    check("最後の要約を採る（新しい印がある）", "NEW-SUMMARY-MARKER" in out)
    check("古い要約は採らない", "OLD-SUMMARY-MARKER" not in out)
    check("圧縮回数を数える（2回）", "圧縮回数: 2回" in out)
    check("要約の時刻と「後の会話は入っていない」の注意が出る", "後の会話は入っていない" in out)
    check("壊れた行・辞書でない行が混ざっても落ちない", "Pending Tasks" in out)
    check("要約の後の発言は要約に混ざらない", "要約のあとの発言" not in out)

    # ---- 取り出しスクリプト：要約なし
    code, out = run(PY + [SCRIPT, "--session", no_s])
    check("要約なしのログで終了コード2", code == 2, f"code={code}")
    check("要約なしのとき /compact を促す", "/compact" in out)

    # ---- --find / --list（作り物の projects フォルダで）
    tmp = tempfile.mkdtemp(prefix="hikitsugi_oracle_")
    try:
        proj = os.path.join(tmp, "proj-a")
        os.makedirs(proj)
        shutil.copy2(with_s, os.path.join(proj, "aaaa1111-0000-0000-0000-000000000001.jsonl"))
        shutil.copy2(no_s, os.path.join(proj, "bbbb2222-0000-0000-0000-000000000002.jsonl"))
        code, out = run(PY + [SCRIPT, "--find", "オラクル", "--projects", tmp])
        check("--find が名前でセッションを見つける", code == 0 and "aaaa1111" in out and "bbbb2222" not in out)
        code, out = run(PY + [SCRIPT, "--session", "bbbb2222", "--projects", tmp])
        check("--session がIDの先頭で解決する", "bbbb2222" in out)
        code, out = run(PY + [SCRIPT, "--list", "--projects", tmp])
        check("--list が2件を出す", "候補 2件" in out)

        # ---- 見張りフック
        marker = os.path.join(tempfile.gettempdir(), "hikitsugi_watch_oracletest-with.txt")
        if os.path.exists(marker):
            os.remove(marker)
        hook_in = json.dumps({"session_id": "oracletest-with", "transcript_path": with_s})
        code, out = run(PY + [WATCH], hook_in)
        check("見張り：圧縮ありで案内を出す", code == 0 and "additionalContext" in out and "圧縮が2回" in out)
        check("見張り：案内にセッション名が入る", "オラクル検証セッション" in out)
        code, out = run(PY + [WATCH], hook_in)
        check("見張り：同じ状態では2度出さない", code == 0 and out.strip() == "")
        hook_in2 = json.dumps({"session_id": "oracletest-none", "transcript_path": no_s})
        code, out = run(PY + [WATCH], hook_in2)
        check("見張り：圧縮なしでは無音", code == 0 and out.strip() == "")
        code, out = run(PY + [WATCH], "this is not json")
        check("見張り：壊れた入力でも落ちない・無音", code == 0 and out.strip() == "")
        code, out = run(PY + [WATCH], json.dumps({"session_id": "x", "transcript_path": "/no/such/file"}))
        check("見張り：ログが無くても落ちない・無音", code == 0 and out.strip() == "")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            os.remove(os.path.join(tempfile.gettempdir(), "hikitsugi_watch_oracletest-with.txt"))
        except OSError:
            pass

    passed = sum(RESULTS)
    print(f"\n{passed}/{len(RESULTS)} PASS")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    print("使い方: python eval/oracle.py --selftest")
    sys.exit(2)
