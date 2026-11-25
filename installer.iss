[Setup]
AppId=BlackoutTracker
AppName=BlackoutTracker
AppVersion=0.5.0
AppPublisherURL=https://github.com/akoval29/BlackoutTracker
AppUpdatesURL=https://github.com/akoval29/BlackoutTracker
DefaultDirName={localappdata}\Programs\BlackoutTracker
DefaultGroupName=BlackoutTracker
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=dist
OutputBaseFilename=BlackoutTracker-0.5-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\BlackoutTracker.exe
CloseApplications=yes
DisableDirPage=no
UsePreviousAppDir=no
Uninstallable=not IsPortable
CreateUninstallRegKey=not IsPortable

[Languages]
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"

[Files]
Source: "dist\BlackoutTracker\*"; DestDir: "{app}"; Excludes: "portable.flag,data\*"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\BlackoutTracker"; Filename: "{app}\BlackoutTracker.exe"; Check: not IsPortable
Name: "{userdesktop}\BlackoutTracker"; Filename: "{app}\BlackoutTracker.exe"; Check: not IsPortable

[Run]
Filename: "{app}\BlackoutTracker.exe"; Description: "Запустити BlackoutTracker"; Flags: nowait postinstall skipifsilent

[Code]
var
  QueuePage: TInputOptionWizardPage;
  ModePage: TInputOptionWizardPage;
  ProjectPage: TOutputMsgWizardPage;

function IsPortable: Boolean;
begin
  Result := ModePage.SelectedValueIndex = 1;
end;

procedure InitializeWizard;
var
  I, J: Integer;
begin
  ProjectPage := CreateOutputMsgPage(wpWelcome, 'Про BlackoutTracker',
    'Проєкт з відкритим вихідним кодом',
    'BlackoutTracker — це проєкт з відкритим вихідним кодом.' + #13#10 + #13#10 +
    'Останню версію програми можна завантажити на сторінці проєкту:' + #13#10 +
    'https://github.com/akoval29/BlackoutTracker' + #13#10 + #13#10 +
    'Там також доступний вихідний код проєкту.');
  ModePage := CreateInputOptionPage(ProjectPage.ID,
    'Як використовувати BlackoutTracker?', 'Оберіть звичайне встановлення або portable.',
    'Звичайне: ярлики та видалення через Windows, налаштування у профілі користувача.' + #13#10 + #13#10 +
    'Portable: програма, налаштування й кеш в одній папці. Її можна переносити або зберігати на флешці. Без ярликів і запису у списку програм Windows.' + #13#10 + #13#10 +
    'В обох випадках Python та Qt вже включено.', True, False);
  ModePage.Add('Звичайне встановлення');
  ModePage.Add('Portable — переносна версія');
  ModePage.SelectedValueIndex := 0;
  QueuePage := CreateInputOptionPage(wpSelectDir,
    'Оберіть чергу відключень',
    'Київська область — ДТЕК Київські регіональні електромережі',
    'Для нового встановлення типово обрано 6.1. При оновленні наявні налаштування зберігаються; змінити їх можна у застосунку.', True, False);
  for I := 1 to 6 do
    for J := 1 to 2 do
      QueuePage.Add(IntToStr(I) + '.' + IntToStr(J));
  QueuePage.SelectedValueIndex := 10;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = ModePage.ID then
  begin
    if IsPortable then
      WizardForm.DirEdit.Text := ExpandConstant('{src}\BlackoutTracker')
    else
      WizardForm.DirEdit.Text := ExpandConstant('{localappdata}\Programs\BlackoutTracker');
  end;
  if CurPageID = wpSelectDir then
  begin
    if (IsPortable and FileExists(ExpandConstant('{app}\unins000.exe'))) or
       ((not IsPortable) and FileExists(ExpandConstant('{app}\portable.flag'))) then
    begin
      MsgBox('У цій папці вже є інша версія. Оберіть окрему папку для цього режиму.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  SettingsPath, Group: String;
  Index: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    Index := QueuePage.SelectedValueIndex;
    Group := IntToStr((Index div 2) + 1) + '.' + IntToStr((Index mod 2) + 1);
    if IsPortable then
    begin
      SettingsPath := ExpandConstant('{app}\data');
      if not SaveStringToFile(ExpandConstant('{app}\portable.flag'), 'portable', False) then
        RaiseException('Не вдалося активувати portable-режим.');
    end
    else
      SettingsPath := ExpandConstant('{localappdata}\BlackoutTracker');
    ForceDirectories(SettingsPath);
    if not FileExists(SettingsPath + '\settings.json') then
    if not SaveStringToFile(SettingsPath + '\settings.json', '{"group":"' + Group + '"}', False) then
      MsgBox('Не вдалося зберегти чергу. Оберіть її під час першого запуску.', mbInformation, MB_OK);
  end;
end;
