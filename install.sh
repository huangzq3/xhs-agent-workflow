#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_SOURCE="$SCRIPT_DIR/skills"
PACKAGE_VERSION="$(tr -d '[:space:]' < "$SCRIPT_DIR/VERSION")"

EXPLICIT_TARGET=""
DRY_RUN=0
UPGRADE=0

usage() {
  echo "Usage:"
  echo "  bash install.sh --target PATH [--upgrade] [--dry-run]"
  echo ""
  echo "PATH must be an absolute Skills directory selected for the active Agent runtime."
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target)
      [ "$#" -ge 2 ] || { echo "ERROR: --target requires a value" >&2; exit 2; }
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
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[ -n "$EXPLICIT_TARGET" ] || {
  echo "ERROR: --target is required; the installer does not guess an Agent-specific directory" >&2
  usage >&2
  exit 2
}

case "$EXPLICIT_TARGET" in
  /*) SKILLS_TARGET="$EXPLICIT_TARGET" ;;
  *)
    echo "ERROR: --target must be an absolute path: $EXPLICIT_TARGET" >&2
    exit 2
    ;;
esac

for skill in xhs-workflow xhs-persona xhs-topic-report xhs-writer xhs-publish xhs-content-review xhs-iterate; do
  source_dir="$SKILLS_SOURCE/$skill"
  skill_file="$source_dir/SKILL.md"
  [ -f "$skill_file" ] || { echo "ERROR: missing $skill_file" >&2; exit 2; }
  [ "$(head -n 1 "$skill_file")" = "---" ] || { echo "ERROR: invalid frontmatter in $skill_file" >&2; exit 2; }
  grep -q '^name:' "$skill_file" || { echo "ERROR: missing name in $skill_file" >&2; exit 2; }
  grep -q '^description:' "$skill_file" || { echo "ERROR: missing description in $skill_file" >&2; exit 2; }
done

echo "XHS Workflow Pack $PACKAGE_VERSION"
echo "Source: $SKILLS_SOURCE"
echo "Target: $SKILLS_TARGET"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "Mode: dry-run"
fi

if [ "$DRY_RUN" -eq 0 ]; then
  mkdir -p "$SKILLS_TARGET"
fi

BACKUP_ROOT="$SKILLS_TARGET/.xhs-workflow-backups/$(date '+%Y%m%dT%H%M%S')"
INSTALLED=0
SKIPPED=0
BACKED_UP=0

for skill in xhs-workflow xhs-persona xhs-topic-report xhs-writer xhs-publish xhs-content-review xhs-iterate; do
  source_dir="$SKILLS_SOURCE/$skill"
  target_dir="$SKILLS_TARGET/$skill"

  if [ -d "$target_dir" ] && [ "$UPGRADE" -eq 0 ]; then
    echo "SKIP: $skill already exists; use --upgrade to back up and replace"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  if [ "$DRY_RUN" -eq 1 ]; then
    if [ -d "$target_dir" ]; then
      echo "PLAN: move $target_dir to $BACKUP_ROOT/$skill"
    fi
    echo "PLAN: install $source_dir to $target_dir"
    continue
  fi

  if [ -d "$target_dir" ]; then
    mkdir -p "$BACKUP_ROOT"
    mv "$target_dir" "$BACKUP_ROOT/$skill"
    echo "BACKUP: $target_dir -> $BACKUP_ROOT/$skill"
    BACKED_UP=$((BACKED_UP + 1))
  fi

  staging_dir="$(mktemp -d "$SKILLS_TARGET/.$skill.install.XXXXXX")"
  cp -R "$source_dir/." "$staging_dir/"
  if [ -d "$staging_dir/scripts" ]; then
    find "$staging_dir/scripts" -type f -name '*.py' -exec chmod u+x {} \;
  fi
  mv "$staging_dir" "$target_dir"
  [ -f "$target_dir/SKILL.md" ] || { echo "ERROR: install verification failed for $skill" >&2; exit 2; }
  echo "INSTALLED: $skill"
  INSTALLED=$((INSTALLED + 1))
done

echo "Result: installed=$INSTALLED skipped=$SKIPPED backups=$BACKED_UP"
if [ "$BACKED_UP" -gt 0 ]; then
  echo "Recoverable backups: $BACKUP_ROOT"
fi

if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
  python3 "$SKILLS_SOURCE/xhs-workflow/scripts/workflow_cli.py" --help >/dev/null
  python3 "$SKILLS_SOURCE/xhs-workflow/scripts/portfolio_cli.py" --help >/dev/null
  echo "OPTIONAL: Python helpers available"
else
  echo "OPTIONAL: Python 3.9+ unavailable; use the same JSON contracts through the active Agent's file capabilities"
fi

if command -v python3 >/dev/null 2>&1 && python3 -c 'import PIL' 2>/dev/null; then
  echo "OPTIONAL: Pillow available for local rendering and image verification"
else
  echo "OPTIONAL: Pillow missing; local text-card rendering and image finalization are unavailable"
fi

if command -v python3 >/dev/null 2>&1 && python3 -c 'import jsonschema' 2>/dev/null; then
  echo "OPTIONAL: jsonschema available"
else
  echo "OPTIONAL: jsonschema missing; use workflow_cli.py cross-field validation when Python is available"
fi

echo "Next: let the active Agent read xhs-workflow/SKILL.md and discover its runtime capabilities before G0"
