@echo off

set DIR=dist
set DIST=IDE_GCC_v0.5.0a

:: Verifica qual argumento foi passado
if /I "%~1"=="nuitka" goto build_nuitka
if /I "%~1"=="pyinstaller" goto build_pyinstaller

:: Se não passar argumento ou for inválido
echo Uso: gera_IDE.bat [nuitka ^| pyinstaller]
goto fim

:: ======================================================================
:: BUILD COM NUITKA
:: ======================================================================
:build_nuitka
echo Construindo com Nuitka...
nuitka --onefile --include-data-dir=./stdlib=stdlib --enable-plugin=tk-inter IDE_GCC.py

if not exist "%DIR%" mkdir "%DIR%"

:: O Nuitka gera o .exe na raiz. Movemos para a pasta dist e renomeamos.
move /Y IDE_GCC.exe "%DIR%\%DIST%n.exe"

cd "%DIR%"
echo Compactando arquivo...
:: Usa o Python nativo para criar o ZIP de forma compatível com qualquer Windows
python -m zipfile -c "%DIST%n.zip" "%DIST%n.exe"
cd ..
echo Build finalizado!
goto fim


:: ======================================================================
:: BUILD COM PYINSTALLER
:: ======================================================================
:build_pyinstaller
echo Construindo com PyInstaller...
:: IMPORTANTE: No Windows, o separador do --add-data eh o ponto-e-virgula (;)
pyinstaller --onefile --paths "." --hidden-import compiler_ast --hidden-import lexer --hidden-import preprocess --hidden-import parser --hidden-import semantic --hidden-import codegen --hidden-import optimizer --hidden-import formatter --add-data "stdlib;stdlib" IDE_GCC.py

if not exist "%DIR%" mkdir "%DIR%"
cd "%DIR%"

:: O PyInstaller ja joga o executavel dentro da pasta dist. Apenas renomeamos.
move /Y IDE_GCC.exe "%DIST%p.exe"

echo Compactando arquivo...
:: Usa o Python nativo para criar o ZIP
python -m zipfile -c "%DIST%p.zip" "%DIST%p.exe"
cd ..
echo Build finalizado!
goto fim

:fim