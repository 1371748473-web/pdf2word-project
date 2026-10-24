; PDF 转 Word 工具 — 精简版 Inno Setup 安装脚本（不含 CUDA，CPU 推理）
; 编译：ISCC.exe pdf2word-lite.iss
;
; 与 GPU 版（pdf2word.iss）的区别：
;   1. 包体积约 1.0 GB（vs GPU 版 3.4 GB）
;   2. 使用 CPU 推理（OCR 约 100s/页 vs GPU 版 18s/页）
;   3. 安装后可在程序内「工具 → 下载 GPU 加速支持」在线升级
;      从清华/阿里云 PyPI 镜像 + PaddlePaddle 官网下载，无需自建托管
;   4. AppId 不同，可与 GPU 版共存

#define MyAppName "PDF 工具箱（精简版）"
#define MyAppVersion "1.5"
#define MyAppPublisher "PDF2WordTool"
#define MyAppExeName "PDF工具箱.exe"

[Setup]
AppId={{8F1D2A64-3B7C-4E5A-9D21-6F3C9A1B0004}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\PDFToolboxLite
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
OutputDir=installer_out
OutputBaseFilename=PDFToolbox-Lite-Setup-{#MyAppVersion}
SetupIconFile=app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\PDFToolbox-Lite\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
