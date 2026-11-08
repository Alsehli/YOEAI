param([int]$Port=8086)
$ErrorActionPreference='Stop'
$results=@()
$health=Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 5
if($health.status -ne 'ok'){throw 'Lite engine is not ready'}
$results+=@{test='health';status='PASS'}
$body=@{model='alsehli-lite';messages=@(@{role='user';content='Reply with exactly LITE_OK'});temperature=0;max_tokens=32}|ConvertTo-Json -Depth 9
$r=Invoke-RestMethod "http://127.0.0.1:$Port/v1/chat/completions" -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 120
if($r.choices[0].message.content -notmatch 'LITE_OK'){throw 'Text test failed'}
$results+=@{test='text';status='PASS';response=$r}
$image=Join-Path $PSScriptRoot 'vision-test.png';$data=[Convert]::ToBase64String([IO.File]::ReadAllBytes($image))
$body=@{model='alsehli-lite';messages=@(@{role='user';content=@(@{type='text';text='Transcribe all printed text and describe the colored shape.'},@{type='image_url';image_url=@{url="data:image/png;base64,$data"}})});temperature=0;max_tokens=128}|ConvertTo-Json -Depth 10
$r=Invoke-RestMethod "http://127.0.0.1:$Port/v1/chat/completions" -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 180
if($r.choices[0].message.content -notmatch '7429'){throw 'Vision OCR test failed'}
$results+=@{test='vision';status='PASS';response=$r}
$results+=@{test='GPU_snapshot';status='OBSERVED';snapshot=(& nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader)}
$results|ConvertTo-Json -Depth 12|Set-Content -LiteralPath (Join-Path $PSScriptRoot 'second-PC-results.json') -Encoding UTF8
Write-Output 'PASS: Lite text and image requests. Continue manual/8 GB memory/offline/signing tests before sale.'
