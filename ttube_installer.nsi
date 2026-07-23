; TTube Windows Installer Script (NSIS)
; Bundles the standalone ttube.exe — no Python installation required.
; Requirements: NSIS 3.x   https://nsis.sourceforge.io/
; Build:        makensis ttube_installer.nsi

!include "MUI2.nsh"
!include "x64.nsh"

; ── Product metadata ───────────────────────────────────────────────────────────
!define PRODUCT_NAME      "TTube"
!define PRODUCT_VERSION   "3.1.3"
!define PRODUCT_PUBLISHER "ImperialGoldenWolf"
!define PRODUCT_WEB_SITE  "https://github.com/ImperialGoldenWolf/TTube"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\ttube.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"

; ── Installer settings ─────────────────────────────────────────────────────────
Name              "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile           "TTube-${PRODUCT_VERSION}-Setup.exe"
InstallDir        "$LOCALAPPDATA\TTube"
InstallDirRegKey  HKCU "${PRODUCT_DIR_REGKEY}" ""
RequestExecutionLevel user   ; no UAC prompt needed — installs to %LOCALAPPDATA%
ShowInstDetails   show
ShowUnInstDetails show

; ── Icon ───────────────────────────────────────────────────────────────────────
!define MUI_ICON    "installer.ico"
!define MUI_UNICON  "installer.ico"

; ── MUI Pages ─────────────────────────────────────────────────────────────────
!define MUI_WELCOMEPAGE_TITLE    "Welcome to TTube Setup"
!define MUI_WELCOMEPAGE_TEXT     "TTube is a lightning-fast Terminal UI for streaming YouTube audio — no downloads, no clutter, just music.$\r$\n$\r$\nThis installer requires no Python. The standalone application will be installed to your AppData folder.$\r$\n$\r$\nClick Next to continue."

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE    "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN          "$INSTDIR\ttube.exe"
!define MUI_FINISHPAGE_RUN_TEXT     "Launch TTube now"
!define MUI_FINISHPAGE_LINK         "Visit project on GitHub"
!define MUI_FINISHPAGE_LINK_LOCATION "${PRODUCT_WEB_SITE}"
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ── Install Section ────────────────────────────────────────────────────────────
Section "TTube Application" SEC01
  SetOutPath "$INSTDIR"

  ; Standalone executable (built by PyInstaller — no Python needed)
  File "dist\ttube.exe"

  ; Documentation
  File "README.md"
  File "CHANGELOG.md"
  File "LICENSE"
  File "GETTING_STARTED.md"
  File "QUICK_REFERENCE.md"

  ; ── Shortcuts ────────────────────────────────────────────────────────────────
  ; Start Menu
  CreateDirectory "$SMPROGRAMS\TTube"
  CreateShortCut  "$SMPROGRAMS\TTube\TTube.lnk"       "$INSTDIR\ttube.exe" "" "$INSTDIR\ttube.exe" 0
  CreateShortCut  "$SMPROGRAMS\TTube\Uninstall TTube.lnk" "$INSTDIR\uninst.exe"

  ; Desktop
  CreateShortCut  "$DESKTOP\TTube.lnk" "$INSTDIR\ttube.exe" "" "$INSTDIR\ttube.exe" 0

  ; ── Registry ─────────────────────────────────────────────────────────────────
  WriteRegStr HKCU "${PRODUCT_DIR_REGKEY}"     ""               "$INSTDIR\ttube.exe"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}"     "DisplayName"    "${PRODUCT_NAME}"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}"     "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}"     "Publisher"      "${PRODUCT_PUBLISHER}"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}"     "URLInfoAbout"   "${PRODUCT_WEB_SITE}"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}"     "UninstallString" "$INSTDIR\uninst.exe"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}"     "DisplayIcon"    "$INSTDIR\ttube.exe"
  WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}"   "NoModify"       1
  WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}"   "NoRepair"       1

  ; Write uninstaller
  WriteUninstaller "$INSTDIR\uninst.exe"
SectionEnd

; ── Uninstall Section ──────────────────────────────────────────────────────────
Section "Uninstall"
  ; Remove shortcuts
  RMDir /r "$SMPROGRAMS\TTube"
  Delete    "$DESKTOP\TTube.lnk"

  ; Remove files
  Delete "$INSTDIR\ttube.exe"
  Delete "$INSTDIR\uninst.exe"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\CHANGELOG.md"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\GETTING_STARTED.md"
  Delete "$INSTDIR\QUICK_REFERENCE.md"
  RMDir  "$INSTDIR"

  ; Clean registry
  DeleteRegKey HKCU "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKCU "${PRODUCT_DIR_REGKEY}"

  MessageBox MB_ICONINFORMATION|MB_OK "TTube has been uninstalled."
SectionEnd
