@echo off
rem SPDX-FileCopyrightText: 2026 Philippe TRESSARD
rem SPDX-License-Identifier: AGPL-3.0-or-later
rem
rem deployer.cmd - lance deploiement/deployer.sh depuis PowerShell, l'invite de
rem commandes ou un double-clic, ou bash n'est pas dans le PATH. Memes options :
rem   .\deploiement\deployer.cmd
rem   .\deploiement\deployer.cmd --verifier
rem Git Bash est cherche (registre de Git for Windows, puis git dans le PATH),
rem jamais suppose a un chemin fixe. Fins de ligne CRLF : voir .gitattributes.
setlocal
set "BASH_EXE="
for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\GitForWindows" /v InstallPath 2^>nul ^| find "InstallPath"') do if exist "%%B\bin\bash.exe" set "BASH_EXE=%%B\bin\bash.exe"
if not defined BASH_EXE for /f "delims=" %%G in ('where git.exe 2^>nul') do if not defined BASH_EXE if exist "%%~dpG..\bin\bash.exe" set "BASH_EXE=%%~dpG..\bin\bash.exe"
if not defined BASH_EXE (
  echo Git Bash introuvable : installer Git for Windows, https://git-scm.com/download/win
  set "CODE=1"
) else (
  pushd "%~dp0.."
  "%BASH_EXE%" deploiement/deployer.sh %*
  call set "CODE=%%ERRORLEVEL%%"
  popd
)
rem Lance d'un double-clic (l'Explorateur ecrit cmd /c ""fichier" "), la fenetre
rem attend qu'on ait lu le resultat ; depuis une console, non.
echo(%CMDCMDLINE%| findstr /e /c:"\" \"" >nul && pause
exit /b %CODE%
