@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
set "CMAKEDIR=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake"
set "PATH=%CMAKEDIR%\CMake\bin;%CMAKEDIR%\Ninja;%PATH%"
set "VCPKG_ROOT=E:\soul sacrifice\port\tools\vcpkg"
set "VCPKG_DEFAULT_BINARY_CACHE=E:\soul sacrifice\port\tools\vcpkg-binary-cache"
set "VCPKG_DISABLE_METRICS=1"
set "Qt6_ROOT=E:\soul sacrifice\port\tools\qt\6.11.0\msvc2022_64"
set "PATH=%VCPKG_ROOT%;%PATH%"
