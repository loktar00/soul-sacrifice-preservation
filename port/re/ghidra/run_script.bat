@echo off
rem Re-run the export post-script on the already-analyzed project (no re-analysis).
set "ROOT=E:\soul sacrifice\port"
set "JAVA_HOME=%ROOT%\tools\jdk21"
set "USERPROFILE=%ROOT%\re\ghidra\home"
call "%ROOT%\tools\ghidra_12.1.3_PUBLIC\support\analyzeHeadless.bat" "%ROOT%\re\ghidra" SoulSacrifice -process eboot.elf -noanalysis -scriptPath "%ROOT%\re\ghidra\scripts" -postScript ExportSummary.java > "%ROOT%\re\ghidra\export.log" 2>&1 < nul
