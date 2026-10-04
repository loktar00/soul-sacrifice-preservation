@echo off
rem Applies the vita-headers NID DB (re\ghidra\niddb, firmware 3.60) to the analyzed program, then re-exports.
set "ROOT=E:\soul sacrifice\port"
set "JAVA_HOME=%ROOT%\tools\jdk21"
set "USERPROFILE=%ROOT%\re\ghidra\home"
set "VLR_DATABASE_PATH=%ROOT%\re\ghidra\niddb"
call "%ROOT%\tools\ghidra_12.1.3_PUBLIC\support\analyzeHeadless.bat" "%ROOT%\re\ghidra" SoulSacrifice -process eboot.elf -noanalysis -scriptPath "%ROOT%\re\ghidra\scripts" -postScript ApplyNidDb.java -postScript ExportSummary.java > "%ROOT%\re\ghidra\nid.log" 2>&1 < nul
