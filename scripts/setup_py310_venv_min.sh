#!/usr/bin/env bash
set -euo pipefail

# =====================================================
# Minimal bootstrap: Python 3.10 + venv + pip install -r
# 用法：
#   bash setup_py310_venv_min.sh
#   bash setup_py310_venv_min.sh --python-version 3.10.13
#   bash setup_py310_venv_min.sh --venv .venv
#   bash setup_py310_venv_min.sh --requirements path/to/reqs.txt
#   FORCE_REINSTALL=true bash setup_py310_venv_min.sh
# 说明：
#   - 会在当前目录创建虚拟环境（默认 ./venv）
#   - 默认从 requirements.txt 安装依赖（可用 --requirements 指定）
# =====================================================

# -------- 默认参数 --------
PYTHON_VERSION="${PYTHON_VERSION:-3.10.14}"
VENV_DIR="${VENV_DIR:-venv}"
REQ_FILE="${REQUIREMENTS:-requirements.txt}"
FORCE_REINSTALL="${FORCE_REINSTALL:-false}"

# -------- 工具函数 --------
log()  { printf "\033[1;34m[INFO]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[WARN]\033[0m %s\n" "$*"; }
err()  { printf "\033[1;31m[ERROR]\033[0m %s\n" "$*"; }
need_cmd(){ command -v "$1" >/dev/null 2>&1 || { err "命令未找到：$1"; exit 1; }; }

# -------- 解析参数 --------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --python-version) PYTHON_VERSION="$2"; shift 2 ;;
    --venv|--venv-dir) VENV_DIR="$2"; shift 2 ;;
    --requirements) REQ_FILE="$2"; shift 2 ;;
    --force-reinstall) FORCE_REINSTALL=true; shift ;;
    -h|--help)
      sed -n '1,120p' "$0"; exit 0 ;;
    *)
      warn "忽略未知参数：$1"; shift ;;
  esac
done

# -------- 安装 Python 3.10 --------
have_python_310() {
  if command -v python3.10 >/dev/null 2>&1; then
    local v; v="$(python3.10 -V 2>&1 | awk '{print $2}')"
    [[ "$v" == "$PYTHON_VERSION" ]] && return 0 || return 2
  fi
  return 1
}

install_build_deps_debian() {
  if command -v apt >/dev/null 2>&1; then
    need_cmd sudo
    log "安装 Python 构建依赖（Debian/Ubuntu）..."
    sudo apt update
    sudo apt install -y \
      build-essential libssl-dev zlib1g-dev libbz2-dev \
      libreadline-dev libsqlite3-dev wget curl llvm \
      libncurses5-dev libncursesw5-dev xz-utils tk-dev \
      libffi-dev liblzma-dev libgdbm-dev libgdbm-compat-dev \
      uuid-dev
  else
    warn "未检测到 apt，跳过构建依赖安装（请确保已安装编译依赖）。"
  fi
}

build_and_install_python() {
  local ver="$1"
  log "下载并编译 Python $ver..."
  pushd /tmp >/dev/null
  wget -q "https://www.python.org/ftp/python/${ver}/Python-${ver}.tgz"
  tar -xf "Python-${ver}.tgz"
  cd "Python-${ver}"
  ./configure --enable-optimizations
  make -j"$(nproc)"
  log "以 altinstall 安装（不覆盖系统 python3）..."
  sudo make altinstall
  popd >/dev/null
  log "Python $ver 安装完成：$(python3.10 -V 2>/dev/null || echo '未检测到')"
}

ensure_python_310() {
  have_python_310
  case $? in
    0) log "已存在期望版本的 python3.10 ($PYTHON_VERSION)，跳过安装。";;
    2)
      if [[ "$FORCE_REINSTALL" == "true" ]]; then
        warn "检测到 python3.10 版本与期望不一致，将强制重装为 $PYTHON_VERSION。"
        install_build_deps_debian
        build_and_install_python "$PYTHON_VERSION"
      else
        warn "python3.10 已存在但版本与期望($PYTHON_VERSION)不一致。若需重装：设置 FORCE_REINSTALL=true。"
      fi
      ;;
    1)
      log "未检测到 python3.10，开始安装 $PYTHON_VERSION..."
      install_build_deps_debian
      build_and_install_python "$PYTHON_VERSION"
      ;;
  esac
}

# -------- 创建 venv 并装依赖 --------
create_venv() {
  local dir="$1"
  if [[ -d "$dir" ]]; then
    warn "虚拟环境目录已存在：$dir（跳过创建）"
  else
    log "创建虚拟环境：$dir"
    python3.10 -m venv "$dir"
  fi

  log "升级 pip / setuptools / wheel ..."
  "$dir/bin/pip" install -U pip setuptools wheel
}

install_requirements() {
  local dir="$1"
  if [[ -f "$REQ_FILE" ]]; then
    log "安装依赖：$REQ_FILE"
    "$dir/bin/pip" install -r "$REQ_FILE"
  else
    warn "未找到依赖文件：$REQ_FILE（跳过 pip install -r）"
  fi
}

# -------- 主流程 --------
main() {
  log "目标 Python 版本：$PYTHON_VERSION"
  ensure_python_310
  need_cmd python3.10
  python3.10 -V

  create_venv "$VENV_DIR"
  install_requirements "$VENV_DIR"

  log "完成 ✅  虚拟环境：$VENV_DIR"
  echo "激活：source $VENV_DIR/bin/activate    退出：deactivate"
}

main "$@"
