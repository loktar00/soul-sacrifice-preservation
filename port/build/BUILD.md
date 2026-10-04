# Vita3K self-build (M1.0)

Source: `port/src/Vita3K` @ a366df69 (same as prebuilt v0.2.1 4115). Follows CI job `windows-x64` in
`.github/workflows/c-cpp.yml`: preset `ci-windows-msvc` (Ninja Multi-Config, MSVC), Release,
vcpkg triplet `x64-windows-static-md`, Qt 6.11.0 `msvc2022_64` + qtmultimedia.

## Result
- Exe: `port/build/vita3k/bin/Release/Vita3K.exe` (32,743,424 bytes; DLLs/data/plugins sit beside it, Qt DLLs auto-deployed)
- Build: ~2.5 min compile (353 steps after a first failed pass), vcpkg deps ~7 min. Log: `port/build/vita3k-build.log`
- Toolchain: MSVC 14.41.34120 (VS 2022 Build Tools), CMake + Ninja bundled with Build Tools, Qt 6.11.0, vcpkg (HEAD clone, manifest baseline 77df67cf, openssl 3.6.1, curl 8.19.0).
- Boot test: `-w -A -r PCSA00152` with `tools/vita3k/config.yml` copied beside the exe. Log shows
  `Main executable efg (eboot.bin) loaded`, no CRITICAL. Screen: SELECT SEQUENCE MODULE debug menu (`m10_boot.png`).

## Portable installs (all under port/tools, no PATH/registry changes)
- `tools/vcpkg` (git clone of microsoft/vcpkg, bootstrapped), `tools/vcpkg-binary-cache`
- `tools/aqtvenv` (python venv with aqtinstall at the CI-pinned commit) and `tools/qt/6.11.0/msvc2022_64`

## Commands
```bat
:: 0. submodules (shallow ok)
cd "E:\soul sacrifice\port\src\Vita3K"
git submodule update --init --recursive --depth 1

:: 1. Qt (must use the CI-pinned aqt; stock aqtinstall 3.3.0 cannot find Qt 6.11 metadata)
python -m venv "E:\soul sacrifice\port\tools\aqtvenv"
tools\aqtvenv\Scripts\pip install "git+https://github.com/miurahr/aqtinstall.git@f383b3c7d9658e881bd8ce8810057393bd934ee1"
tools\aqtvenv\Scripts\aqt install-qt windows desktop 6.11.0 win64_msvc2022_64 -m qtmultimedia -O tools\qt

:: 2. vcpkg
git clone https://github.com/microsoft/vcpkg.git tools\vcpkg     (full history needed for builtin-baseline)
```
Then `port/build/env.bat` (vcvars64 + bundled cmake/ninja + VCPKG_ROOT + VCPKG_DEFAULT_BINARY_CACHE + Qt6_ROOT) and:
```bat
call "E:\soul sacrifice\port\build\env.bat"
cd /d "E:\soul sacrifice\port\tools\vcpkg" && bootstrap-vcpkg.bat -disableMetrics
cd /d "E:\soul sacrifice\port\src\Vita3K" && vcpkg install --triplet x64-windows-static-md
cmake --preset ci-windows-msvc -B "E:\soul sacrifice\port\build\vita3k" -DCMAKE_C_COMPILER_LAUNCHER= -DCMAKE_CXX_COMPILER_LAUNCHER=
cmake --build "E:\soul sacrifice\port\build\vita3k" --config Release
```
(wrappers: `step1.bat` = vcpkg, `step2.bat` = configure+build, `step3.bat` = rebuild; run via `cmd //c`.)
Run:
```
cd port\build\vita3k\bin\Release
copy ..\..\..\..\tools\vita3k\config.yml .
Vita3K.exe -w -A -r PCSA00152
```

## Gotchas
1. CI preset sets sccache as compiler launcher; sccache is not installed. Override with empty `-DCMAKE_*_COMPILER_LAUNCHER=` (above).
2. Qt 6.11 download layout changed; stock aqtinstall fails with "Failed to locate XML data". Use the CI-pinned aqt commit.
3. SOURCE PATCH required with MSVC 14.41: `vita3k/emuenv/include/emuenv/state.h` line ~148,
   `RendererPtr renderer{};` -> `RendererPtr renderer;`. Without it every TU that includes state.h fails
   with C2338 "can't delete an incomplete type" on `unique_ptr<renderer::State>` (older MSVC instantiates the deleter for the
   in-class initializer; CI's newer MSVC does not). Behaviour-neutral. This is the only source change (`git diff` in the repo).
4. Preset output dir is overridden with `-B` to `port/build/vita3k`; exe lands in `bin/Release` (Ninja Multi-Config).
5. Discord RPC logs a harmless `|E| discordrpc::init` error.
6. Screenshot caveat: `vpad.py shot` picks the first window titled PCSA00152. If the prebuilt emulator is also running the game it may capture that one; I captured by HWND of the built exe's PID instead.
7. Vita3K needs a sibling `config.yml` with `pref-path`; `-w` keeps it unmodified.
