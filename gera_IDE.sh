#!/usr/bin/env bash
set -euo pipefail
set -x

if [ $# -lt 1 ]; then
    echo "Uso: ./gera_IDE.sh [nuitka | pyinstaller]"
    exit 1
fi

MODE="$1"
DIR="dist"
DIST="IDE_GCC_v0.6.0_overlay_modes"
APP="IDE_GCC.py"

cd "$(dirname "$0")"
mkdir -p "$DIR"

COMMON_HIDDEN=(
  compiler_ast lexer preprocess parser semantic codegen optimizer formatter build_modes assembler_cariri_adv
)

if [ "$MODE" = "nuitka" ]; then
    python3 -m nuitka \
        --onefile \
        --enable-plugin=tk-inter \
        --include-package=pyparsing \
        "$APP"

    # Nuitka normalmente gera IDE_GCC.bin em Linux.
    if [ -f "IDE_GCC.bin" ]; then
        mv -f "IDE_GCC.bin" "${DIR}/${DIST}_nuitka"
    elif [ -f "IDE_GCC" ]; then
        mv -f "IDE_GCC" "${DIR}/${DIST}_nuitka"
    else
        echo "Executável do Nuitka não encontrado."
        exit 2
    fi
    chmod +x "${DIR}/${DIST}_nuitka"
    echo "OK: ${DIR}/${DIST}_nuitka"
    exit 0
fi

if [ "$MODE" = "pyinstaller" ]; then
    HIDDEN_ARGS=()
    for mod in "${COMMON_HIDDEN[@]}"; do
        HIDDEN_ARGS+=(--hidden-import "$mod")
    done

    pyinstaller \
        --clean \
        --onefile \
        --name "${DIST}_pyinstaller" \
        --paths "." \
        "${HIDDEN_ARGS[@]}" \
        "$APP"

    chmod +x "${DIR}/${DIST}_pyinstaller"
    echo "OK: ${DIR}/${DIST}_pyinstaller"
    exit 0
fi

echo "Modo inválido: $MODE"
echo "Uso: ./gera_IDE.sh [nuitka | pyinstaller]"
exit 1
