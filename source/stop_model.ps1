param([int]$PidToStop,[string]$ExpectedExe,[long]$Created)
$ErrorActionPreference='Stop'
$engine=Get-Process -Id $PidToStop -ErrorAction SilentlyContinue
if(!$engine){exit 0}
if($engine.Path -ne $ExpectedExe -or $engine.StartTime.ToUniversalTime().ToFileTimeUtc() -ne $Created){throw 'Engine identity changed; nothing was stopped.'}
Add-Type @'
using System; using System.Runtime.InteropServices;
public class YoeModelConsole {
 [DllImport("kernel32.dll")] public static extern bool FreeConsole();
 [DllImport("kernel32.dll")] public static extern bool AttachConsole(uint pid);
 [DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr handler,bool add);
 [DllImport("kernel32.dll")] public static extern bool GenerateConsoleCtrlEvent(uint evt,uint group);
}
'@
[YoeModelConsole]::FreeConsole() | Out-Null
if(![YoeModelConsole]::AttachConsole($PidToStop)){throw 'Could not attach to the owned model console.'}
[YoeModelConsole]::SetConsoleCtrlHandler([IntPtr]::Zero,$true) | Out-Null
[YoeModelConsole]::GenerateConsoleCtrlEvent(0,0) | Out-Null
Start-Sleep -Milliseconds 500
[YoeModelConsole]::FreeConsole() | Out-Null
if(!$engine.WaitForExit(20000)){throw 'The owned model is still shutting down. No force termination was used.'}
