@echo off
setlocal EnableDelayedExpansion

rem — поднимаем скрипт с правами администратора
net session >nul 2>&1 || (
  powershell -Command "Start-Process \"%~f0\" -Verb RunAs"
  exit /b
)

set "BIN=%~dp0bin"
set "LISTS=%~dp0lists"

@echo PATCHED_BY_GUI v1.5.3

pushd %BIN%
winws.exe ^
--wf-tcp=80,443 --wf-udp=443,50000-50100 ^
--filter-udp=443 --hostlist="%LISTS%\list-general.txt" --dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fake-quic="%BIN%\quic_initial_www_google_com.bin" --new ^
--filter-udp=50000-50100 --filter-l7=discord,stun --dpi-desync=fake --dpi-desync-repeats=6 --new ^
--filter-tcp=80 --hostlist="%LISTS%\list-general.txt" --dpi-desync=fake,split2 --dpi-desync-autottl=2 --dpi-desync-fooling=md5sig --new ^
--filter-tcp=443 --hostlist="%LISTS%\list-general.txt" --dpi-desync=fake,multidisorder --dpi-desync-split-pos=midsld --dpi-desync-repeats=8 --dpi-desync-fooling=md5sig,badseq --new ^
--filter-udp=443 --ipset="%LISTS%\ipset-all.txt" --dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fake-quic="%BIN%\quic_initial_www_google_com.bin" --new ^
--filter-tcp=80 --ipset="%LISTS%\ipset-all.txt" --dpi-desync=fake,split2 --dpi-desync-autottl=2 --dpi-desync-fooling=md5sig --new ^
--filter-tcp=443 --ipset="%LISTS%\ipset-all.txt" --dpi-desync=fake,multidisorder --dpi-desync-split-pos=midsld --dpi-desync-repeats=6 --dpi-desync-fooling=md5sig,badseq --new ^
--filter-udp=50000-50100 --ipset="%LISTS%\ipset-all.txt" --dpi-desync=fake --dpi-desync-autottl=2 --dpi-desync-repeats=10 --dpi-desync-any-protocol=1 --dpi-desync-fake-unknown-udp="%BIN%\quic_initial_www_google_com.bin" --dpi-desync-cutoff=n2
popd
