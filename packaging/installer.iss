; Inno Setup: Windows installer. Build with: iscc packaging\installer.iss /DAppVersion=0.1.0
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
[Setup]
AppName=NameReforge
AppVersion={#AppVersion}
AppPublisher=Aurigalab
DefaultDirName={autopf}\NameReforge
DefaultGroupName=NameReforge
OutputDir=..\dist
LicenseFile=..\LICENSE
OutputBaseFilename=NameReforge-{#AppVersion}-windows-setup
SetupIconFile=..\src\nameforge\assets\icon.ico
UninstallDisplayIcon={app}\NameReforge.exe
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
[Files]
Source: "..\dist\NameReforge\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
[Icons]
Name: "{group}\NameReforge"; Filename: "{app}\NameReforge.exe"
Name: "{autodesktop}\NameReforge"; Filename: "{app}\NameReforge.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; Flags: unchecked
[Run]
Filename: "{app}\NameReforge.exe"; Description: "Launch NameReforge"; Flags: nowait postinstall skipifsilent
