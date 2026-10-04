call "E:\soul sacrifice\port\build\env.bat"
echo BUILD_START %TIME%
cmake --build "E:\soul sacrifice\port\build\vita3k" --config Release
echo BUILD_END %TIME% rc=%ERRORLEVEL%
