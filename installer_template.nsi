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

Function VerifyLoaderDestination
    IfFileExists "$INSTDIR\spacehaven.jar" reject
    IfFileExists "$INSTDIR\spacehaven.exe" reject
    IfFileExists "$INSTDIR\savegames\*.*" reject
    Return
    reject:
        Abort
FunctionEnd

Function .onVerifyInstDir
    Call VerifyLoaderDestination
FunctionEnd

Section "Install"
    Call VerifyLoaderDestination
    SetDetailsPrint listonly
    SetOutPath "$INSTDIR"
    !include "FILE_LIST.nsh"
    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
    !include "UNINSTALL_FILE_LIST.nsh"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir "$INSTDIR"
SectionEnd
