# Soul Sacrifice Delta eboot - Ghidra workspace

Everything is portable under `E:\soul sacrifice\port\`:

- JDK: `tools\jdk21` (Temurin 21.0.12.1)
- Ghidra: `tools\ghidra_12.1.3_PUBLIC` with VitaLoaderRedux 1.09 in `Ghidra\Extensions\VitaLoaderRedux`
- Project: `re\ghidra\SoulSacrifice.gpr` (program `eboot.elf`)

Ghidra's launch scripts force `user.home` to `%USERPROFILE%`, so every command
sets `USERPROFILE` to `re\ghidra\home` to keep settings out of the real profile.

## Open in the GUI (cmd.exe)

    set "JAVA_HOME=E:\soul sacrifice\port\tools\jdk21"
    set "USERPROFILE=E:\soul sacrifice\port\re\ghidra\home"
    "E:\soul sacrifice\port\tools\ghidra_12.1.3_PUBLIC\ghidraRun.bat"

Or just run `re\ghidra\gui.bat`. Then File > Open Project > `re\ghidra\SoulSacrifice.gpr`.
The extension is already installed; if Ghidra asks, enable it under File > Configure > Miscellaneous.

## Re-run import + full auto-analysis (headless, slow)

    re\ghidra\run_import.bat        (log: re\ghidra\import.log; uses -overwrite)

Equivalent command:

    set "JAVA_HOME=E:\soul sacrifice\port\tools\jdk21"
    set "USERPROFILE=E:\soul sacrifice\port\re\ghidra\home"
    "E:\soul sacrifice\port\tools\ghidra_12.1.3_PUBLIC\support\analyzeHeadless.bat" "E:\soul sacrifice\port\re\ghidra" SoulSacrifice -import "E:\soul sacrifice\port\re\elf\eboot.elf" -overwrite

## Re-run only the export script (imports.csv, summary.md)

    re\ghidra\run_script.bat        (log: re\ghidra\export.log)

Script: `re\ghidra\scripts\ExportSummary.java` (Java, since Ghidra 12 has no Jython).

## Gotchas

- Do not put `JAVA_TOOL_OPTIONS` with a path containing spaces: Ghidra's `java -version` probe fails and it reports an invalid JAVA_HOME.
- Run the .bat files with `cmd /c` and `< nul` (already in them); a failed launch waits on "Press any key" and keeps `import.log` locked.

## NID database

VitaLoaderRedux's builtin `BuiltinNIDDatabase.yaml` only covers kernel/TZS modules (0 of the eboot's userland imports resolved).
The project uses the vita-headers DB for firmware 3.60 (`db/360/*.yml`, 156 files, vitasdk/vita-headers master
e66ebe90b73d1fa4cce005a5b2072cec27322544) stored in `re\ghidra\niddb`. It was applied after the first analysis with:

    re\ghidra\run_nid.bat           (sets VLR_DATABASE_PATH, runs ApplyNidDb.java then ExportSummary.java; log nid.log)

For a fresh import, set `VLR_DATABASE_PATH=E:\soul sacrifice\port\re\ghidra\niddb` before `run_import.bat` and the
NID analyzer will use it during auto-analysis.
