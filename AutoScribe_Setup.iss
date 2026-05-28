; ================================================================
;  AutoScribe Installer — Inno Setup 6
;  Generado v3.1 — modelo gratuito e ilimitado
; ================================================================

#define AppName      "AutoScribe"
#define AppVersion   "1.0"
#define AppPublisher "Helix Scan"
#define AppExeName   "AutoScribe.exe"
#define AppIco       "Lg_HS.ico"
#define SourceDir    "C:\Users\heibe\OneDrive\Desktop\Heiber SENA\Heiber SENA\Helix Scan\AutoScribe"

[Setup]
AppId={{F3A2B1C4-9E5D-4F78-A123-BC456DE78901}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir={#SourceDir}\Installer_Output
OutputBaseFilename=AutoScribe_v1.0_Setup
SetupIconFile={#SourceDir}\assets\logos\{#AppIco}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\assets\logos\{#AppIco}
UninstallDisplayName={#AppName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon";  Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"
Name: "launchafter";  Description: "Ejecutar AutoScribe al finalizar la instalación"; GroupDescription: "Al terminar:"; Flags: unchecked

[Files]
; Ejecutable principal
Source: "{#SourceDir}\AutoScribe.exe";         DestDir: "{app}";               Flags: ignoreversion

; Archivos del core (embebidos en el .exe via Nuitka)
Source: "{#SourceDir}\AutoScribe_v1_0.pyc";    DestDir: "{app}";               Flags: ignoreversion
Source: "{#SourceDir}\python-embed.zip";        DestDir: "{app}";               Flags: ignoreversion
Source: "{#SourceDir}\Requirements.txt";        DestDir: "{app}";               Flags: ignoreversion

; Config inicial (solo si no existe ya)
Source: "{#SourceDir}\autoscribe_config.json";  DestDir: "{app}";               Flags: ignoreversion onlyifdoesntexist

; Módulos Python
Source: "{#SourceDir}\ui\*";                   DestDir: "{app}\ui";            Flags: ignoreversion recursesubdirs
Source: "{#SourceDir}\ocr\*";                  DestDir: "{app}\ocr";           Flags: ignoreversion recursesubdirs
Source: "{#SourceDir}\pipeline\*";             DestDir: "{app}\pipeline";      Flags: ignoreversion recursesubdirs
Source: "{#SourceDir}\translation\*";          DestDir: "{app}\translation";   Flags: ignoreversion recursesubdirs

; Assets
Source: "{#SourceDir}\assets\logos\*";         DestDir: "{app}\assets\logos";  Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "{#SourceDir}\assets\fondos\*";        DestDir: "{app}\assets\fondos"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\logos\{#AppIco}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\logos\{#AppIco}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Ejecutar {#AppName}"; \
  Flags: nowait postinstall skipifsilent; Tasks: launchafter

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
