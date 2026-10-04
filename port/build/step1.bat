call "E:\soul sacrifice\port\build\env.bat"
cd /d "E:\soul sacrifice\port\tools\vcpkg" && call bootstrap-vcpkg.bat -disableMetrics || exit /b 1
cd /d "E:\soul sacrifice\port\src\Vita3K" && vcpkg install --triplet x64-windows-static-md
