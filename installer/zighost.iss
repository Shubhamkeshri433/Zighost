; Inno Setup script. tools/build_windows.py passes the values from backend/brand.py as /D defines,
; so the name, version and publisher live in one place only.
#ifndef AppName
  #define AppName "Zighost"
#endif
#ifndef AppVersion
  #define AppVersion "0.1.0"
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

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppName}.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppName}.exe"; Description: "Open {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
const
  WebView2Id = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2Url = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';

var
  DownloadPage: TDownloadWizardPage;
  WebView2File: String;

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

{ Uninstall keeps servers and worlds unless the person says otherwise. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  dataDir: String;
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
  begin
    dataDir := ExpandConstant('{userappdata}\{#DataKey}');
    if DirExists(dataDir) then
      if MsgBox('Also delete your servers, worlds, backups and settings?' + #13#10 + #13#10 + dataDir + #13#10 + #13#10 +
                'Choose No to keep them (for example if you plan to install again).', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(dataDir, True, True, True);
  end;
end;
