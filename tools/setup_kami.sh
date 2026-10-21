#!/usr/bin/env bash
# Kami 排版技能的运行依赖（容器重启后依赖与字体会丢，跑一次即可恢复）。
# 技能本体在 .claude/skills/kami（已入库）；字体约 38MB 不入库，从上游仓库取。
set -e
python3 -m pip install -q weasyprint pypdf pymupdf pygments python-pptx
python3 -m pip install -q --ignore-installed pillow   # 系统自带 PIL 与 /usr/local 的 python3 不兼容
FONT_DIR="$HOME/.local/share/fonts/kami"
if ! ls "$FONT_DIR"/TsangerJinKai02-W0*.ttf >/dev/null 2>&1; then
  TMP="$(mktemp -d)"
  git clone -q --depth 1 https://github.com/tw93/Kami "$TMP/kami"
  mkdir -p "$FONT_DIR" && cp "$TMP"/kami/assets/fonts/TsangerJinKai02-W0*.ttf "$FONT_DIR"/
  rm -rf "$TMP"; fc-cache -f >/dev/null 2>&1 || true
fi
python3 "$(dirname "$0")/../.claude/skills/kami/scripts/build.py" --doctor | grep -E 'OK: core|ERROR'
