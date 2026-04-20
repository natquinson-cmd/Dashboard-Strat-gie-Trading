Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
}
"@
$TOPMOST = [IntPtr]::new(-1)
$SWP_NOMOVE = 0x0002
$SWP_NOSIZE = 0x0001
$p = Get-Process mshta -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "*KeepAlive*" }
if ($p) {
    [Win32]::SetWindowPos($p.MainWindowHandle, $TOPMOST, 0, 0, 0, 0, $SWP_NOMOVE -bor $SWP_NOSIZE) | Out-Null
}
