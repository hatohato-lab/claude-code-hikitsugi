#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""claude-code-hikitsugi の外部オラクル（機械判定eval）。

使い方:
    python eval/oracle.py --selftest

corpus のログをエンジンに食わせ、出力を検査して合否を機械判定する。
検査の柱は3つ：①秘密が漏れない ②壊れた入力で死なない ③引き継ぎ材料が正しく残る。
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ENGINE = os.path.join(REPO, "skill", "hikitsugi.py")
CORPUS = os.path.join(HERE, "corpus", "basic.jsonl")

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail and not ok else ""))


def run_engine(args):
    return subprocess.run(
        [sys.executable, ENGINE] + args,
        capture_output=True, text=True, encoding="utf-8", errors="replace")


def selftest():
    print("== claude-code-hikitsugi oracle ==")

    # ---- 0. マスキング関数の単体検査
    sys.path.insert(0, os.path.join(REPO, "skill"))
    import hikitsugi as hk
    unit = [
        "111111-222222-333333-444444-555555-666666-777777-888888",
        "sk-abcdefghijklmnop1234567890",
        "ghp_abcdefghij1234567890abcdefghij",
        "AKIAIOSFODNN7EXAMPLE",
        "xoxb-1234567890-abcdefghijk",
        "eyJabcdefghijklmnopqrstu.eyJabcdefghij.abcdefghijk",
    ]
    ok = all(u not in hk.mask_text("a " + u + " b") for u in unit)
    check("マスキング単体（キー・トークン6種が消える）", ok)
    pw = hk.mask_text("パスワード: open sesame now これは")
    check("パスワード文脈（空白入りでも最大3語隠す）", "open" not in pw and "sesame" not in pw)
    em = hk.mask_text("taro@example.com")
    check("メール（先頭1文字+ドメインだけ残る）", em == "t***@example.com")

    # ---- 1. corpus を一時プロジェクトに配置してエンジンを実行
    tmp = tempfile.mkdtemp(prefix="hikitsugi-oracle-")
    try:
        proj = os.path.join(tmp, "projects", "test-proj")
        os.makedirs(proj)
        shutil.copy(CORPUS, os.path.join(proj, "oracletest-sample.jsonl"))
        out_dir = os.path.join(tmp, "out")

        r = run_engine(["--projects", os.path.join(tmp, "projects"),
                        "--session", "oracletest", "--out", out_dir])
        check("実行が成功する（壊れた行・未知typeが混ざっても exit 0）", r.returncode == 0,
              r.stderr[:200])

        handoff = os.path.join(out_dir, "handoff.md")
        digest = os.path.join(out_dir, "digest.md")
        check("handoff.md と digest.md が生成される",
              os.path.isfile(handoff) and os.path.isfile(digest))
        H = open(handoff, encoding="utf-8").read() if os.path.isfile(handoff) else ""
        D = open(digest, encoding="utf-8").read() if os.path.isfile(digest) else ""
        both = H + D

        # ---- 2. 秘密が漏れない
        check("回復キー（通常位置）が生で残らない", "999999-888888" not in both)
        check("回復キー（切り詰め境界をまたぐ位置）が生で残らない", "111111-222222" not in both)
        check("マスク跡 [MASKED:recovery-key] が出力に残る", "[MASKED:recovery-key]" in both)
        check("パスワードの値が漏れない", "open sesame" not in both)
        check("メールが部分マスクされる", "t***@example.com" in both and "taro@example.com" not in both)

        # ---- 3. 引き継ぎ材料が正しく残る
        check("ユーザーの決定（理由つき）が残る", "SQLiteに決定" in D and "運用が軽い" in D)
        check("AI側の発言も残る（決定の理由の供給源）", "【AI】" in D and "SQLite採用" in D)
        check("system-reminderは項目単位で除外し、同居する本文は残す",
              "本文はこちらです" in D and "これはシステム通知" not in D)
        check("エラーが記録される", "Error: design.md not found" in H)

        # ---- 3-2. 作業の記録（何をしたか・何が起きたか・どう直したか）
        sec = ""
        if "## 作業の記録" in H and "## プログラムのエラー" in H:
            sec = H.split("## 作業の記録", 1)[1].split("## プログラムのエラー", 1)[0]
        check("作業記録：完了が種別つきで残る",
              "【完了】" in sec and "実装が完了しました" in sec)
        check("作業記録：失敗が種別つきで残る",
              "【失敗】" in sec and "即死していました" in sec)
        check("作業記録：対処が種別つきで残る",
              "【対処】" in sec and "再実行します" in sec)
        check("作業記録：ユーザーの発言は混入しない",
              "入らないはず" not in sec)
        check("書き込みファイルが記録される", "design.md" in H)
        check("チャット名（タイトル）が引き継がれる", "オラクル検証チャット" in H)
        check("生ログへのgrep導線がある", "grep -n" in H)

        # ---- 4. 検索・引数まわり
        r2 = run_engine(["--projects", os.path.join(tmp, "projects"), "--find", "オラクル"])
        check("チャット名でセッションを見つけられる（--find）",
              r2.returncode == 0 and "oraclete" in r2.stdout)
        r3 = run_engine(["--projects", os.path.join(tmp, "projects"),
                         "--session", "oracletest", "--out", out_dir,
                         "--since", "2026/08/01"])
        check("--since の形式誤りを拒否する", r3.returncode != 0)
        r4 = run_engine(["--projects", os.path.join(tmp, "projects"),
                         "--session", "oracletest", "--out", out_dir,
                         "--since", "2026-08-01"])
        H4 = open(handoff, encoding="utf-8").read()
        check("--since を付けてもチャット名は失われない",
              r4.returncode == 0 and "オラクル検証チャット" in H4)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok_all = all(ok for _, ok in RESULTS)
    n_ok = sum(1 for _, ok in RESULTS if ok)
    print(f"== 結果: {n_ok}/{len(RESULTS)} PASS ==")
    return 0 if ok_all else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    print("使い方: python eval/oracle.py --selftest")
    sys.exit(2)
