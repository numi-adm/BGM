#define MyAppName "BGM"
#define MyAppVersion "1.0"
#define MyAppPublisher "NuNut"
#define MyAppExeName "bgm_player.exe"

[Setup]
; หมายเลข ID ของโปรแกรม (ห้ามซ้ำกับโปรแกรมอื่น)
AppId={{9F8A7C6B-5D4E-3F2A-1B0C-123456789ABC}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; กำหนดให้ไฟล์ Setup.exe ที่สร้างเสร็จแล้ว ไปอยู่ในโฟลเดอร์ Release
OutputDir=Release
OutputBaseFilename=BGMPlayer_Setup_v1.0
; รูปไอคอนของตัวติดตั้ง
SetupIconFile=icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
; ให้สิทธิ์ Users สามารถแก้ไขไฟล์ในโฟลเดอร์นี้ได้ (เพื่อให้โปรแกรมเซฟ settings.json ได้)
Name: "{app}"; Permissions: users-modify

[Files]
; ดึงไฟล์ .exe จากโฟลเดอร์ dist
Source: "{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; ดึงไฟล์ไอคอน
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion
; ดึงโฟลเดอร์ BGM พร้อมไฟล์เพลงข้างในทั้งหมด (ถ้ามี) ไปสร้างไว้ด้วย
Source: "BGM\*"; DestDir: "{app}\BGM"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; สร้าง Shortcut ใน Start Menu และหน้า Desktop (ใส่ \ เผื่อเว็บลบทิ้ง)
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
; ตั้งค่าให้เปิดโปรแกรมอัตโนมัติเมื่อติดตั้งเสร็จ
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent