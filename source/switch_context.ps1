param([Parameter(Mandatory=$true)][ValidateSet(4096,8192,16384)][int]$Context,[Parameter(Mandatory=$true)][string]$ProfilePath)
$ErrorActionPreference='Stop'
$engineRoot='C:\AI\llama.cpp'
$profile=Get-Content -LiteralPath $ProfilePath -Raw | ConvertFrom-Json
if(!$profile.externalBackend -or [int]$profile.apiPort -ne 8080){throw 'Context control is only enabled for the configured local engine on port 8080.'}
$selected=Get-Content -LiteralPath (Join-Path $engineRoot 'model-config.json') -Raw | ConvertFrom-Json
$state=Get-Content -LiteralPath (Join-Path $engineRoot 'server-state.json') -Raw | ConvertFrom-Json
if([IO.Path]::GetFullPath($selected.model) -ne [IO.Path]::GetFullPath($profile.model) -or [IO.Path]::GetFullPath($state.model) -ne [IO.Path]::GetFullPath($profile.model) -or [int]$state.port -ne 8080){throw 'The shared engine does not match this app configuration. No process was stopped.'}
if([IO.Path]::GetFullPath($profile.projector) -ne [IO.Path]::GetFullPath('C:\AI\Models\DeepSeekV4\mmproj-F32.gguf')){throw 'Vision projector does not match the existing launcher.'}
$process=Get-Process -Id $state.pid -ErrorAction Stop
if($process.Path -ne (Join-Path $engineRoot 'llama-server.exe') -or $process.StartTime.ToString('o') -ne $state.started){throw 'Engine identity changed; no process was stopped.'}
$props=Invoke-RestMethod 'http://127.0.0.1:8080/props' -TimeoutSec 5
$previous=[int]$props.default_generation_settings.n_ctx
if($previous -notin @(4096,8192,16384)){throw 'Cannot safely restore the current context.'}
$slots=Invoke-RestMethod 'http://127.0.0.1:8080/slots' -TimeoutSec 5
if(@($slots | Where-Object {$_.is_processing}).Count){throw 'The shared engine is generating a response. Wait until it finishes.'}
function Save-ProfileContext([int]$Value){$profile.context=$Value;$temp=$ProfilePath+'.context-tmp';[IO.File]::WriteAllText($temp,($profile|ConvertTo-Json -Depth 12),[Text.UTF8Encoding]::new($false));Move-Item -LiteralPath $temp -Destination $ProfilePath -Force}
function Stop-VerifiedEngine {
 $owned=Get-Content -LiteralPath (Join-Path $engineRoot 'server-state.json') -Raw | ConvertFrom-Json
 # A separate child handles Ctrl+C so the restart controller remains alive.
 & powershell.exe -NoProfile -File (Join-Path $engineRoot 'stop-deepseek.ps1')
 if(Get-Process -Id $owned.pid -ErrorAction SilentlyContinue){throw 'The engine did not stop gracefully. No process was forcibly killed.'}
}
if($previous -eq $Context){Save-ProfileContext $Context;Write-Output 'Context already active.';exit 0}
Stop-VerifiedEngine
try {
 & (Join-Path $engineRoot 'start-deepseek.ps1') -Context $Context
 $active=Invoke-RestMethod 'http://127.0.0.1:8080/props' -TimeoutSec 5
 if([int]$active.default_generation_settings.n_ctx -ne $Context){throw 'Backend reported a different context.'}
 Save-ProfileContext $Context
 Write-Output "Context updated to $Context."
} catch {
 $failure=$_.Exception.Message
 try {
  $running=Get-NetTCPConnection -State Listen -LocalPort 8080 -ErrorAction SilentlyContinue
  if($running){Stop-VerifiedEngine}
  & (Join-Path $engineRoot 'start-deepseek.ps1') -Context $previous
  Save-ProfileContext $previous
 } catch {throw "Context change failed: $failure. Automatic restore also failed: $($_.Exception.Message). Check C:\AI\Logs."}
 throw "Context change failed: $failure. Previous $previous-token context restored."
}
