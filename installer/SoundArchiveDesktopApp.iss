#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{4F09DD22-2DC7-4DFB-8A96-ED1F0C27C486}
AppName=SoundArchive Desktop App
AppVersion={#AppVersion}
AppPublisher=wolveschew
DefaultDirName={localappdata}\Programs\SoundArchive Desktop App
DefaultGroupName=SoundArchive Desktop App
UninstallDisplayIcon={app}\SoundArchiveDesktopApp.exe
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

[Code]
function NextButtonClick(CurPageID: Integer): Boolean;
var
  TestPath: string;
  TestHandle: Integer;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    if not ForceDirectories(WizardDirValue) then
    begin
      MsgBox(
        'The selected folder could not be created. Choose a folder you can access, such as your user Programs folder.',
        mbError, MB_OK);
      Result := False;
      Exit;
    end;

    TestPath := AddBackslash(WizardDirValue) + '.soundcloud-archive-write-test-' + IntToStr(GetTickCount);
    while FileExists(TestPath) do
      TestPath := TestPath + '-';
    TestHandle := FileCreate(TestPath);
    if TestHandle = -1 then
    begin
      MsgBox(
        'You do not have permission to install to the selected folder. Choose a folder you can modify, such as ' +
        ExpandConstant('{localappdata}\Programs\SoundArchive Desktop App') + '.',
        mbError, MB_OK);
      Result := False;
      Exit;
    end;
    FileClose(TestHandle);
    DeleteFile(TestPath);
  end;
end;

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\SoundArchiveDesktopApp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\MicrosoftEdgeWebView2Setup.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\SoundArchive Desktop App"; Filename: "{app}\SoundArchiveDesktopApp.exe"
Name: "{autodesktop}\SoundArchive Desktop App"; Filename: "{app}\SoundArchiveDesktopApp.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MicrosoftEdgeWebView2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft Edge WebView2 Runtime..."; Flags: waituntilterminated
Filename: "{app}\SoundArchiveDesktopApp.exe"; Description: "Launch SoundArchive Desktop App"; Flags: postinstall nowait skipifsilent
