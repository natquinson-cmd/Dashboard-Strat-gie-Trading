Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32Min {
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@
$p = Get-Process mshta -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "*KeepAlive*" }
if ($p) {
    [Win32Min]::ShowWindow($p.MainWindowHandle, 6) | Out-Null
}
