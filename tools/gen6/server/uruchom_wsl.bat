@echo off
setlocal
rem ============================================================
rem  Gitara Sluchacz - serwer modelu gen 6 przez WSL (Windows)
rem  Pierwsze uruchomienie: kilka minut (pobranie repozytorium i instalacja).
rem  Potem startuje od razu. Zatrzymanie: Ctrl+C w tym oknie.
rem ============================================================
set REPO=https://github.com/NelexstarMain/Gutar
set BRANCH=ccr-2964b612-ep81z9
set PORT=8080
set TOKEN=gutar

where wsl >nul 2>nul
if errorlevel 1 (
  echo Nie znaleziono WSL. Zainstaluj: otworz PowerShell jako administrator i wpisz: wsl --install
  echo Potem uruchom ten plik ponownie.
  pause
  exit /b 1
)

set /p TOKEN=Haslo do serwera [Enter = gutar]: 
if "%TOKEN%"=="" set TOKEN=gutar

echo.
echo Uruchamiam w WSL. Strona otworzy sie sama za ok. 25 s, a przy pierwszym uruchomieniu dopiero po instalacji.
start "" /b cmd /c "timeout /t 25 /nobreak >nul & start http://localhost:%PORT%"

wsl bash -lc "set -e; command -v git >/dev/null || { echo Instaluje git; sudo apt-get update -qq && sudo apt-get install -y git; }; [ -d ~/Gutar/.git ] || git clone -b %BRANCH% %REPO% ~/Gutar; cd ~/Gutar; git fetch -q origin %BRANCH%; git checkout -q %BRANCH%; git pull -q origin %BRANCH%; GUTAR_TOKEN='%TOKEN%' PORT=%PORT% bash tools/gen6/server/uruchom.sh"

echo.
echo Serwer zatrzymany.
pause
