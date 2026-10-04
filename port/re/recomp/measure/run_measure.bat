@echo off
rem Runs a measurement script read-only (-noanalysis -readOnly). Pass a COPY of the project dir to avoid
rem contending for the project lock with a running Ghidra. Set GHIDRA_HOME_DIR to keep settings elsewhere.
rem Usage: run_measure.bat [project dir, default the real project opened -readOnly] [script, default RecompMeasure.java]
set "ROOT=E:\soul sacrifice\port"
set "PROJ=%~1"
if "%PROJ%"=="" set "PROJ=%ROOT%\re\ghidra"
set "SCRIPT=%~2"
if "%SCRIPT%"=="" set "SCRIPT=RecompMeasure.java"
set "JAVA_HOME=%ROOT%\tools\jdk21"
if "%GHIDRA_HOME_DIR%"=="" set "GHIDRA_HOME_DIR=%ROOT%\re\ghidra\home"
set "USERPROFILE=%GHIDRA_HOME_DIR%"
call "%ROOT%\tools\ghidra_12.1.3_PUBLIC\support\analyzeHeadless.bat" "%PROJ%" SoulSacrifice -process eboot.elf -noanalysis -readOnly -scriptPath "%ROOT%\re\recomp\measure" -postScript %SCRIPT% > "%ROOT%\re\recomp\measure\out\%SCRIPT%.log" 2>&1 < nul
