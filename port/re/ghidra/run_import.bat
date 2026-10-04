@echo off
set "ROOT=E:\soul sacrifice\port"
set "JAVA_HOME=%ROOT%\tools\jdk21"
set "USERPROFILE=%ROOT%\re\ghidra\home"
call "%ROOT%\tools\ghidra_12.1.3_PUBLIC\support\analyzeHeadless.bat" "%ROOT%\re\ghidra" SoulSacrifice -import "%ROOT%\re\elf\eboot.elf" -overwrite > "%ROOT%\re\ghidra\import.log" 2>&1 < nul
