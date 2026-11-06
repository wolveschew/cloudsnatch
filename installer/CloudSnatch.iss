#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif

[Setup]
AppId={{4F09DD22-2DC7-4DFB-8A96-ED1F0C27C486}
AppName=CloudSnatch
AppVersion={#AppVersion}
AppPublisher=wolveschew
DefaultDirName={localappdata}\Programs\CloudSnatch
DefaultGroupName=CloudSnatch
UninstallDisplayIcon={app}\CloudSnatch.exe
OutputDir=..\dist
OutputBaseFilename=CloudSnatchSetup
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

    TestPath := AddBackslash(WizardDirValue) + '.cloudsnatch-write-test';
    while FileExists(TestPath) do
      TestPath := TestPath + '-';
    if not SaveStringToFile(TestPath, 'SoundArchive write test', False) then
    begin
      MsgBox(
        'You do not have permission to install to the selected folder. Choose a folder you can modify, such as ' +
        ExpandConstant('{localappdata}\Programs\CloudSnatch') + '.',
        mbError, MB_OK);
      Result := False;
      Exit;
    end;
    DeleteFile(TestPath);
  end;
end;

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\CloudSnatch\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\MicrosoftEdgeWebView2Setup.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\CloudSnatch"; Filename: "{app}\CloudSnatch.exe"
Name: "{autodesktop}\CloudSnatch"; Filename: "{app}\CloudSnatch.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MicrosoftEdgeWebView2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft Edge WebView2 Runtime..."; Flags: waituntilterminated
Filename: "{app}\CloudSnatch.exe"; Description: "Launch CloudSnatch"; Flags: postinstall nowait skipifsilent
