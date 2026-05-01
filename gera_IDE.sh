#/bin/bash
set -x

if [ -z "$1" ]; then
    echo "Uso: ./gera_IDE.sh [nuitka | pyinstaller]"
    exit 1
fi

DIR="dist"
DIST="IDE_GCC_v0.5.0a"

if [ "$1" = "nuitka" ] 
then
	nuitka --onefile --enable-plugin=tk-inter IDE_GCC.py
    [ ! -d "$DIR" ]; mkdir "$DIR"
    mv IDE_GCC.bin "${DIR}/${DIST}n"
    cd "$DIR"
    zip "${DIST}n_Lin64.zip" "${DIST}n"
    
fi

if [ "$1" = "pyinstaller" ] 
then
	pyinstaller --onefile --paths '.' --hidden-import compiler_ast --hidden-import lexer --hidden-import preprocess --hidden-import parser --hidden-import semantic --hidden-import codegen --hidden-import optimizer --hidden-import formatter  IDE_GCC.py
    cd "$DIR"
    mv IDE_GCC "${DIST}p"
    zip "${DIST}p_Lin64.zip" "${DIST}p"
fi


