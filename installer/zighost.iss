; Inno Setup script. tools/build_windows.py passes the values from backend/brand.py as /D defines,
; so the name, version and publisher live in one place only.
#ifndef AppName
  #define AppName "Zighost"
#endif
#ifndef AppVersion
  #define AppVersion "0.1.1"
#endif
#ifndef Publisher
  #define Publisher "shubverser"
#endif
#ifndef Copyright
  #define Copyright "(c) 2026 Shubham Keshri"
#endif
#ifndef AppGuid
  #define AppGuid "{272662F5-A911-4EA9-BC1E-3977AC6C1356}"
#endif
#ifndef DataKey
  #define DataKey "zighost"
#endif

[Setup]
AppId={{#AppGuid}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#Publisher}
AppCopyright={#Copyright}
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppName}.exe
UninstallDisplayName={#AppName}
SetupIconFile=..\assets\brand\zighost.ico
OutputDir=..\dist-installer
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Installs for the current Windows user only: no administrator prompt, and the app can update itself later.
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; run.py holds this mutex while the app is open, so Setup asks to close it first.
AppMutex={#DataKey}-single-instance
CloseApplications=yes
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

; An update installs over the old copy. Delete the old program files first so nothing from the old version is left behind.
; Servers, worlds, backups and settings live in %APPDATA%\{#DataKey}, never in {app}, so they are not touched.
[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppName}.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppName}.exe"; Description: "Open {#AppName}"; Flags: nowait postinstall skipifsilent
; "Update now" inside the app runs this installer silently with /UPDATING=1 and expects the new version to open by itself.
Filename: "{app}\{#AppName}.exe"; Flags: nowait; Check: IsUpdating

[Code]
const
  WebView2Id = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2Url = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';

var
  DownloadPage: TDownloadWizardPage;
  WebView2File: String;

function IsUpdating: Boolean;
begin
  Result := ExpandConstant('{param:UPDATING|0}') = '1';
end;

function WebView2Installed: Boolean;
var
  v: String;
begin
  Result := False;
  if RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + WebView2Id, 'pv', v) then
    Result := (v <> '') and (v <> '0.0.0.0');
  if not Result then
    if RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\' + WebView2Id, 'pv', v) then
      Result := (v <> '') and (v <> '0.0.0.0');
end;

function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  Result := True;
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), @OnDownloadProgress);
end;

{ Windows 11 and most Windows 10 PCs already have WebView2. If it is missing, get Microsoft's small installer first.
  If that fails, the app still works: it opens in the normal browser instead of its own window. }
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and (not WebView2Installed) then
  begin
    DownloadPage.Clear;
    DownloadPage.Add(WebView2Url, 'MicrosoftEdgeWebview2Setup.exe', '');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
        WebView2File := ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe');
      except
        WebView2File := '';
        if not DownloadPage.AbortedByUser then
          SuppressibleMsgBox('The Microsoft WebView2 component could not be downloaded. {#AppName} will still work and open in your browser. You can install WebView2 later from Microsoft to get the app window.', mbInformation, MB_OK, IDOK);
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  rc: Integer;
begin
  if (CurStep = ssPostInstall) and (WebView2File <> '') and FileExists(WebView2File) then
    Exec(WebView2File, '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, rc);
end;

{ How many server folders are inside the data folder. }
function CountServers(const serversDir: String): Integer;
var
  rec: TFindRec;
begin
  Result := 0;
  if FindFirst(serversDir + '\*', rec) then
  begin
    try
      repeat
        if ((rec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0) and (rec.Name <> '.') and (rec.Name <> '..') then
          Result := Result + 1;
      until not FindNext(rec);
    finally
      FindClose(rec);
    end;
  end;
end;

{ Uninstall keeps servers, worlds and backups. Deleting them takes two deliberate steps: answer No to "keep", then type DELETE.
  A quiet (silent) uninstall never deletes them. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  dataDir, typed: String;
  n: Integer;
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
  begin
    dataDir := ExpandConstant('{userappdata}\{#DataKey}');
    if DirExists(dataDir) then
    begin
      n := CountServers(dataDir + '\servers');
      if MsgBox('Keep your servers, worlds, backups and settings?' + #13#10 + #13#10 +
                'You have ' + IntToStr(n) + ' server(s) in:' + #13#10 + dataDir + #13#10 + #13#10 +
                'Yes keeps everything (recommended). A new install finds it again.' + #13#10 +
                'No goes on to delete it for good.', mbConfirmation, MB_YESNO or MB_DEFBUTTON1) = IDNO then
      begin
        typed := '';
        if InputQuery('Delete everything for good?',
                      'This permanently deletes ' + IntToStr(n) + ' server(s), their worlds, backups and settings. It cannot be undone and nothing goes to the Recycle Bin.' + #13#10 +
                      'Type DELETE to confirm, or press Cancel to keep it all.', typed) and (typed = 'DELETE') then
          DelTree(dataDir, True, True, True)
        else
          MsgBox('Nothing was deleted. Your servers are still in:' + #13#10 + dataDir, mbInformation, MB_OK);
      end;
    end;
  end;
end;
