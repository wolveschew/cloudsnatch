#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{4F09DD22-2DC7-4DFB-8A96-ED1F0C27C486}
AppName=SoundCloud Archive
AppVersion={#AppVersion}
AppPublisher=wolveschew
DefaultDirName={localappdata}\Programs\SoundCloud Archive
DefaultGroupName=SoundCloud Archive
UninstallDisplayIcon={app}\SoundCloudArchive.exe
OutputDir=..\dist
OutputBaseFilename=SoundCloudArchiveSetup
SetupIconFile=
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
Uninstallable=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\SoundCloudArchive.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\MicrosoftEdgeWebView2Setup.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\SoundCloud Archive"; Filename: "{app}\SoundCloudArchive.exe"
Name: "{autodesktop}\SoundCloud Archive"; Filename: "{app}\SoundCloudArchive.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MicrosoftEdgeWebView2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft Edge WebView2 Runtime..."; Flags: waituntilterminated
Filename: "{app}\SoundCloudArchive.exe"; Description: "Launch SoundCloud Archive"; Flags: postinstall nowait skipifsilent
