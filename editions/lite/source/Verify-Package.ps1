param([string]$PackageDirectory=$PSScriptRoot)
$ErrorActionPreference='Stop'
$root=(Resolve-Path -LiteralPath $PackageDirectory).Path
$manifest=Get-Content -LiteralPath (Join-Path $root 'package-manifest.json') -Raw | ConvertFrom-Json
$results=@()
foreach($item in $manifest.files){
 $path=[IO.Path]::GetFullPath((Join-Path $root $item.path))
 if(!$path.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Manifest contains an unsafe path'}
 if(!(Test-Path -LiteralPath $path)){throw "Missing package file: $($item.path)"}
 if((Get-Item -LiteralPath $path).Length -ne $item.size){throw "Size mismatch: $($item.path)"}
 if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.sha256){throw "SHA-256 mismatch: $($item.path)"}
 $results+=[pscustomobject]@{file=$item.path;integrity='PASS'}
}
$signature=Get-AuthenticodeSignature -LiteralPath (Join-Path $root 'YOEAILite.exe')
@{integrity='PASS';files=$results;signature=$signature.Status.ToString();releaseStatus=$manifest.releaseStatus}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $root 'verification-result.json') -Encoding UTF8
Write-Output "PASS: $($results.Count) files match. Signature: $($signature.Status). Release status: $($manifest.releaseStatus)."
Write-Output 'A manifest hash check is not a trusted signature and does not certify commercial release readiness.'
