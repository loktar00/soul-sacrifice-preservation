call "E:\soul sacrifice\port\build\env.bat"
cd /d "E:\soul sacrifice\port\src\Vita3K"
cmake --preset ci-windows-msvc -B "E:\soul sacrifice\port\build\vita3k" -DCMAKE_C_COMPILER_LAUNCHER= -DCMAKE_CXX_COMPILER_LAUNCHER= || exit /b 1
echo BUILD_START %TIME%
cmake --build "E:\soul sacrifice\port\build\vita3k" --config Release
echo BUILD_END %TIME% rc=%ERRORLEVEL%
