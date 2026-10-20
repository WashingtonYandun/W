#ifndef BundleDir
  #error BundleDir must point to a verified Windows bundle
#endif
#ifndef WVersion
  #error WVersion must identify the packaged compiler
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif

[Setup]
AppId={{E7DFAD44-C0AF-447A-BD57-39A0498CA07A}
AppName=W Language
AppVersion={#WVersion}
AppPublisher=Washington Yandun
AppPublisherURL=https://github.com/WashingtonYandun/W
DefaultDirName={localappdata}\Programs\W Language
DefaultGroupName=W Language
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible and not arm64
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableDirPage=yes
DisableProgramGroupPage=yes
ChangesEnvironment=yes
Compression=lzma2/fast
SolidCompression=yes
OutputDir={#OutputDir}
OutputBaseFilename=w-{#WVersion}-windows-x64-setup
UninstallDisplayIcon={app}\w.exe
LicenseFile={#BundleDir}\LICENSE
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: english; MessagesFile: compiler:Default.isl
Name: spanish; MessagesFile: compiler:Languages\Spanish.isl

[CustomMessages]
english.AddToPath=Add W to my terminal PATH (recommended)
spanish.AddToPath=Agregar W al PATH de mi terminal (recomendado)
english.OpenTerminal=Open a terminal ready to use W
spanish.OpenTerminal=Abrir una terminal lista para usar W

[Tasks]
Name: addtopath; Description: {cm:AddToPath}

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\W Language"; Filename: "{cmd}"; Parameters: "/K """"{app}\open-terminal.cmd"""""; WorkingDir: "{userdocs}"
Name: "{group}\Uninstall W Language"; Filename: "{uninstallexe}"

[Run]
Filename: "{cmd}"; Parameters: "/K """"{app}\open-terminal.cmd"""""; WorkingDir: "{userdocs}"; Description: "{cm:OpenTerminal}"; Flags: postinstall nowait skipifsilent

[Messages]
english.FinishedLabel=W is installed with its own runtime and C compiler.%n%nUse the W Language shortcut or open a new terminal and run: w version%n%nNo Python, pip, virtual environment or Visual Studio setup is needed.
spanish.FinishedLabel=W incluye su propio runtime y compilador C.%n%nUsa el acceso directo W Language o abre una terminal nueva y ejecuta: w version%n%nNo necesitas instalar Python, pip, un entorno virtual ni Visual Studio.

[Code]
const
  InstallerKey = 'Software\WLanguage\Installer';

function NormalizeEntry(Value: String): String;
begin
  Value := Trim(Value);
  if (Length(Value) > 1) and (Value[1] = '"') and (Value[Length(Value)] = '"') then
    Value := Copy(Value, 2, Length(Value) - 2);
  while (Length(Value) > 3) and (Value[Length(Value)] = '\') do
    Delete(Value, Length(Value), 1);
  Result := Lowercase(Value);
end;

function FilterPath(Value, Entry: String; Remove: Boolean; var Found: Boolean): String;
var
  Item, Delimiter: String;
  Separator: Integer;
begin
  Result := '';
  Delimiter := '';
  Found := False;
  repeat
    Separator := Pos(';', Value);
    if Separator = 0 then begin
      Item := Value;
      Value := '';
    end else begin
      Item := Copy(Value, 1, Separator - 1);
      Delete(Value, 1, Separator);
    end;
    if NormalizeEntry(Item) = NormalizeEntry(Entry) then begin
      Found := True;
      if not Remove then begin
        Result := Result + Delimiter + Item;
        Delimiter := ';';
      end;
    end else begin
      Result := Result + Delimiter + Item;
      Delimiter := ';';
    end;
  until Separator = 0;
end;

procedure RemoveOwnedPath;
var
  Owned, Current, Updated: String;
  Found: Boolean;
begin
  if RegQueryStringValue(HKCU, InstallerKey, 'PathEntry', Owned) then begin
    if RegQueryStringValue(HKCU, 'Environment', 'Path', Current) then begin
      Updated := FilterPath(Current, Owned, True, Found);
      if Found and not RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Updated) then
        Log('Could not remove the owned W PATH entry.');
    end;
    RegDeleteValue(HKCU, InstallerKey, 'PathEntry');
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Current, Entry, Unused: String;
  Found: Boolean;
begin
  if CurStep = ssPostInstall then begin
    RemoveOwnedPath;
    if WizardIsTaskSelected('addtopath') then begin
      Entry := ExpandConstant('{app}');
      RegQueryStringValue(HKCU, 'Environment', 'Path', Current);
      Unused := FilterPath(Current, Entry, False, Found);
      if not Found then begin
        if Current <> '' then Current := Current + ';';
        if not RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Current + Entry) then
          RaiseException('Cannot update the user PATH.');
        if not RegWriteStringValue(HKCU, InstallerKey, 'PathEntry', Entry) then
          RaiseException('Cannot record the W PATH entry.');
      end;
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then RemoveOwnedPath;
end;
