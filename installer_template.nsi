!define APPNAME "spacehaven-modloader"
!define VERSION "{{VERSION}}"
!define OUTPUT_FILE "dist/${APPNAME}-${VERSION}-setup.exe"

Name "Space Haven Mod Loader"
Caption "Space Haven Mod Loader"

SetCompressor lzma
OutFile "${OUTPUT_FILE}"

InstallDir "$LOCALAPPDATA\Programs\${APPNAME}"
RequestExecutionLevel user

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Var CurrentFile

Function .onInstFile
    DetailPrint 'Deploying: "$INSTDIR\$CurrentFile"'
FunctionEnd

Section "Install"
    SetDetailsPrint listonly
    SetOutPath "$INSTDIR"
    !include "FILE_LIST.nsh"
    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
    RMDir /r "$INSTDIR"
SectionEnd
