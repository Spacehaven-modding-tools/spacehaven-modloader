@echo off
SETLOCAL
rmdir /S /Q .\dist  2> NIL
python ./version.py  > ./version.txt
SET /p ML_VERSION=<version.txt
SET ML_FILENAME=spacehaven-modloader-%ML_VERSION%.windows
ECHO Mod Loader Version is "%ML_VERSION%"

python -m PyInstaller --noconsole modloader.spec
move .\dist\spacehaven-modloader .\dist\%ML_FILENAME%

ECHO.
IF EXIST "%ProgramFiles%\7-Zip\7z.exe" (
  ECHO Compressing with 7-Zip...
  "%ProgramFiles%\7-Zip\7z.exe" a -mx9 ".\dist\%ML_FILENAME%.7z"  ".\dist\%ML_FILENAME%"
) ELSE (
  ECHO 7-Zip not found.  Creating zip with Windows 10 'tar'...
  tar -f .\dist\%ML_FILENAME%.zip -c .\dist\%ML_FILENAME%
)
ECHO.
ECHO Created Files for Distribution:
dir /B .\dist\*.zip .\dist\*.7z
ECHO.