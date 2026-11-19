; Inno Setup script for Pawn Engine. The GitHub build runs:  iscc /DAppVersion=1.2 installer\PawnEngine.iss
; (run build_exe.bat or tools\build_app.py first so dist\PawnEngine exists)
#ifndef AppVersion
  #define AppVersion "0.0"
#endif

[Setup]
AppId={{6B1D3E52-7A4C-4F0E-9C58-2D1A0B7E4F13}
AppName=Pawn Engine
AppVersion={#AppVersion}
AppPublisher=Pawn Engine
DefaultDirName={autopf}\Pawn Engine
DefaultGroupName=Pawn Engine
UninstallDisplayIcon={app}\PawnEngine.exe
SetupIconFile=..\assets\icon.ico
OutputDir=..\installer-output
OutputBaseFilename=PawnEngine-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; installs for just you (no admin needed) unless you choose "all users" in the first dialog
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Put a Pawn Engine shortcut on the Desktop"; GroupDescription: "Shortcuts:"
Name: "assoc"; Description: "Open Pawn Engine projects (project.pawnproj) by double-clicking them"; GroupDescription: "Files:"

[Files]
Source: "..\dist\PawnEngine\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Pawn Engine"; Filename: "{app}\PawnEngine.exe"
Name: "{group}\Uninstall Pawn Engine"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Pawn Engine"; Filename: "{app}\PawnEngine.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.pawnproj"; ValueType: string; ValueName: ""; ValueData: "PawnEngine.Project"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\PawnEngine.Project"; ValueType: string; ValueName: ""; ValueData: "Pawn Engine project"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\PawnEngine.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\PawnEngine.exe,0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\PawnEngine.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\PawnEngine.exe"" ""%1"""; Tasks: assoc

[Run]
Filename: "{app}\PawnEngine.exe"; Description: "Start Pawn Engine"; Flags: nowait postinstall skipifsilent
