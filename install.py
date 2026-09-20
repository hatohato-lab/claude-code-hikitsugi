#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""claude-code-hikitsugi インストーラ。

skill/ の中身（SKILL.md と hikitsugi.py）を ~/.claude/skills/hikitsugi/ にコピーするだけ。
設定ファイルの編集はしない。アンインストールはそのフォルダを消すだけ。
"""
import os
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skill")
    dst = os.path.join(os.path.expanduser("~"), ".claude", "skills", "hikitsugi")
    if not os.path.isdir(src):
        print("エラー: skill フォルダが見つかりません。リポジトリ直下で実行してください。")
        return 1
    # 2026-09-20 修正: SKILL.md が案内する watch.py（見張りフック）が入っていなかったため追加。
    # 説明どおり install.py だけで導入したとき、watch.py が無くて見張りを登録できなかった。
    required = ("SKILL.md", "hikitsugi.py", "watch.py")
    missing = [n for n in required if not os.path.isfile(os.path.join(src, n))]
    if missing:
        print("エラー: 必要なファイルが見つかりません:", ", ".join(missing))
        print("リポジトリを取得し直してください。")
        return 1
    os.makedirs(dst, exist_ok=True)
    copied = []
    for name in required:
        shutil.copy2(os.path.join(src, name), os.path.join(dst, name))
        copied.append(name)
    print("インストール完了:", dst)
    print("コピーしたファイル:", ", ".join(copied))
    print()
    print("使い方: 新しいチャットを開いて、一言。")
    print('  「◯◯のチャットを継いで」')
    print()
    print("アンインストール: 上のフォルダを削除するだけ。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
