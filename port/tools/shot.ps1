param([string]$Out = "E:\soul sacrifice\port\notes\shot.png", [string]$Proc = "Vita3K")
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class W { [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
[DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
public struct RECT { public int L, T, R, B; } }
"@
[W]::SetProcessDPIAware() | Out-Null
$wins = Get-Process $Proc -ErrorAction Stop | Where-Object { $_.MainWindowHandle -ne 0 }
$i = 0
foreach ($p in $wins) {
  $r = New-Object W+RECT; [W]::GetWindowRect($p.MainWindowHandle, [ref]$r) | Out-Null
  $w = $r.R - $r.L; $h = $r.B - $r.T
  $bmp = New-Object System.Drawing.Bitmap $w, $h
  $g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc()
  [W]::PrintWindow($p.MainWindowHandle, $dc, 2) | Out-Null
  $g.ReleaseHdc($dc); $g.Dispose()
  $o = $Out -replace '\.png$', "_$i.png"; $bmp.Save($o); "$($p.MainWindowTitle) -> $o ($w x $h)"; $i++
}
