#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_SOURCE="$SCRIPT_DIR/skills"
PACKAGE_VERSION="$(tr -d '[:space:]' < "$SCRIPT_DIR/VERSION")"

EXPLICIT_TARGET=""
DRY_RUN=0
UPGRADE=0

usage() {
  echo "用法："
  echo "  bash install.sh --target PATH [--upgrade] [--dry-run]"
  echo ""
  echo "PATH 必须是当前 Agent 实际使用的 Skills 绝对目录。"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target)
      [ "$#" -ge 2 ] || { echo "错误：--target 后必须提供目录" >&2; exit 2; }
      EXPLICIT_TARGET="$2"
      shift 2
      ;;
    --upgrade)
      UPGRADE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "错误：无法识别参数 $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[ -n "$EXPLICIT_TARGET" ] || {
  echo "错误：必须提供 --target；安装器不会猜测不同 Agent 的 Skills 目录" >&2
  usage >&2
  exit 2
}

case "$EXPLICIT_TARGET" in
  /*) SKILLS_TARGET="$EXPLICIT_TARGET" ;;
  *)
    echo "错误：--target 必须是绝对路径：$EXPLICIT_TARGET" >&2
    exit 2
    ;;
esac

for skill in xhs-workflow xhs-persona xhs-topic-report xhs-writer article-audit xhs-publish xhs-content-review xhs-iterate; do
  source_dir="$SKILLS_SOURCE/$skill"
  skill_file="$source_dir/SKILL.md"
  [ -f "$skill_file" ] || { echo "错误：缺少 $skill_file" >&2; exit 2; }
  [ "$(head -n 1 "$skill_file")" = "---" ] || { echo "错误：$skill_file 的头部格式不合法" >&2; exit 2; }
  grep -q '^name:' "$skill_file" || { echo "错误：$skill_file 缺少名称" >&2; exit 2; }
  grep -q '^description:' "$skill_file" || { echo "错误：$skill_file 缺少用途说明" >&2; exit 2; }
done

echo "小红书运营工作流 $PACKAGE_VERSION"
echo "来源目录：$SKILLS_SOURCE"
echo "目标目录：$SKILLS_TARGET"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "模式：仅预览，不写入文件"
fi

if [ "$DRY_RUN" -eq 0 ]; then
  mkdir -p "$SKILLS_TARGET"
fi

BACKUP_ROOT="$SKILLS_TARGET/.xhs-workflow-backups/$(date '+%Y%m%dT%H%M%S')"
INSTALLED=0
SKIPPED=0
BACKED_UP=0

for skill in xhs-workflow xhs-persona xhs-topic-report xhs-writer article-audit xhs-publish xhs-content-review xhs-iterate; do
  source_dir="$SKILLS_SOURCE/$skill"
  target_dir="$SKILLS_TARGET/$skill"

  if [ -d "$target_dir" ] && [ "$UPGRADE" -eq 0 ]; then
    echo "跳过：$skill 已存在；如需备份并替换，请使用 --upgrade"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  if [ "$DRY_RUN" -eq 1 ]; then
    if [ -d "$target_dir" ]; then
      echo "计划：把 $target_dir 移到备份目录 $BACKUP_ROOT/$skill"
    fi
    echo "计划：把 $source_dir 安装到 $target_dir"
    continue
  fi

  if [ -d "$target_dir" ]; then
    mkdir -p "$BACKUP_ROOT"
    mv "$target_dir" "$BACKUP_ROOT/$skill"
    echo "已备份：$target_dir -> $BACKUP_ROOT/$skill"
    BACKED_UP=$((BACKED_UP + 1))
  fi

  staging_dir="$(mktemp -d "$SKILLS_TARGET/.$skill.install.XXXXXX")"
  cp -R "$source_dir/." "$staging_dir/"
  if [ -d "$staging_dir/scripts" ]; then
    find "$staging_dir/scripts" -type f -name '*.py' -exec chmod u+x {} \;
  fi
  mv "$staging_dir" "$target_dir"
  [ -f "$target_dir/SKILL.md" ] || { echo "错误：$skill 安装后校验失败" >&2; exit 2; }
  echo "已安装：$skill"
  INSTALLED=$((INSTALLED + 1))
done

echo "结果：已安装=${INSTALLED}，已跳过=${SKIPPED}，已备份=${BACKED_UP}"
if [ "$BACKED_UP" -gt 0 ]; then
  echo "可恢复备份：$BACKUP_ROOT"
fi

if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
  python3 "$SKILLS_SOURCE/xhs-workflow/scripts/workflow_cli.py" --help >/dev/null
  python3 "$SKILLS_SOURCE/xhs-workflow/scripts/portfolio_cli.py" --help >/dev/null
  python3 "$SKILLS_SOURCE/article-audit/scripts/article_audit_cli.py" --help >/dev/null
  echo "可选能力：Python 辅助器可用"
else
  echo "可选能力：Python 3.9+ 不可用；改用当前 Agent 的文件能力维护相同机器契约"
fi

if command -v python3 >/dev/null 2>&1 && python3 -c 'import jsonschema' 2>/dev/null; then
  echo "可选能力：jsonschema 可用"
else
  echo "可选能力：未安装 jsonschema；Python 可用时仍可使用 workflow_cli.py 完成跨字段校验"
fi

echo "下一步：让当前 Agent 读取 xhs-workflow/SKILL.md，并在“启动与授权确认”前核对实际能力"
