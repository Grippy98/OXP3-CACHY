param(
    [Parameter(Mandatory = $true)][string]$SourceDir,
    [Parameter(Mandatory = $true)][string]$ArtifactDir
)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path $SourceDir).Path
New-Item -ItemType Directory -Force $ArtifactDir | Out-Null
$artifact = (Resolve-Path $ArtifactDir).Path
$recipe = Split-Path -Parent $PSCommandPath
$pin = Get-Content (Join-Path $recipe 'source.json') -Raw | ConvertFrom-Json
$patch = Join-Path $recipe 'optiscaler-lifetime.patch'
if ((Get-FileHash $patch -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pin.patch_sha256) { throw 'Source patch hash mismatch.' }
if ((git -C $source rev-parse HEAD).Trim() -ne $pin.commit) { throw 'OptiScaler source commit mismatch.' }
if (git -C $source status --porcelain) { throw 'OptiScaler source must start clean.' }
$submodules = @(git -C $source submodule status --recursive)
if ($LASTEXITCODE -ne 0 -or ($submodules | Where-Object { $_ -match '^[-+U]' })) { throw 'Submodules must match the pinned commits.' }
git -C $source apply --check $patch
if ($LASTEXITCODE -ne 0) { throw 'Source patch does not apply.' }
git -C $source apply $patch
if ($LASTEXITCODE -ne 0) { throw 'Source patch application failed.' }
git -C $source diff --check
if ($LASTEXITCODE -ne 0) { throw 'Source patch whitespace check failed.' }

# Skip upstream packaging and its vendor-runtime copying. This artifact contains only this DLL and provenance.
# Generate the two normal resource headers ourselves so the runtime version identifies the experimental patch.
$project = Join-Path $source 'OptiScaler/OptiScaler.vcxproj'
[xml]$xml = Get-Content $project -Raw
$ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
$ns.AddNamespace('m', 'http://schemas.microsoft.com/developer/msbuild/2003')
foreach ($node in $xml.SelectNodes('//m:PreBuildEvent/m:Command | //m:PostBuildEvent/m:Command', $ns)) { $node.InnerText = '' }
$xml.Save($project)
$label = '273e8d44-oxp3-reuse-' + $pin.patch_sha256.Substring(0, 8)
[IO.File]::WriteAllText((Join-Path $source 'OptiScaler/resource_build_commit.h'), '#define VER_BUILD_COMMIT "' + $label + '"' + "`n", [Text.Encoding]::ASCII)
[IO.File]::WriteAllText((Join-Path $source 'OptiScaler/resource_build_date.h'), '#define VER_BUILD_DATE "OXP3 experimental"' + "`n", [Text.Encoding]::ASCII)

$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$msbuild = & $vswhere -latest -products '*' -requires Microsoft.Component.MSBuild -find 'MSBuild\**\Bin\MSBuild.exe' | Select-Object -First 1
if (-not $msbuild) { throw 'Visual Studio MSBuild was not found.' }
$vs = & $vswhere -latest -products '*' -format json | ConvertFrom-Json
& $msbuild (Join-Path $source 'OptiScaler.sln') /m:2 /p:Configuration=Release /p:Platform=x64 /verbosity:minimal
if ($LASTEXITCODE -ne 0) { throw "MSBuild failed: $LASTEXITCODE" }
$dll = Join-Path $source 'x64/Release/OptiScaler.dll'
if (-not (Test-Path $dll)) { throw 'Expected Release DLL is missing.' }
Copy-Item $dll (Join-Path $artifact 'OptiScaler.dll')
Copy-Item $patch (Join-Path $artifact 'source.patch')
Copy-Item (Join-Path $recipe 'README.md') (Join-Path $artifact 'SOURCE.md')
foreach ($name in @('LICENSE', 'LICENSE.txt', 'COPYING', 'AUTHORS')) {
    $file = Join-Path $source $name
    if (Test-Path $file) { Copy-Item $file (Join-Path $artifact $name) }
}
$record = [ordered]@{
    source_repository = $pin.repository
    source_commit = $pin.commit
    patch_sha256 = $pin.patch_sha256
    version_label = $label
    dll_sha256 = (Get-FileHash $dll -Algorithm SHA256).Hash.ToLowerInvariant()
    visual_studio_version = $vs.installationVersion
    msbuild_version = (& $msbuild -version -nologo | Select-Object -Last 1)
    submodules = $submodules
    build_support_changes = 'Only pre/post build commands disabled; version headers generated; runtime source changes are exactly source.patch.'
    runtime_status = 'Experimental artifact only. Not deployed or runtime-qualified by this build.'
    workflow_commit = $env:GITHUB_SHA
}
$record | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $artifact 'build-record.json') -Encoding utf8
Write-Output ('OptiScaler.dll SHA256 ' + $record.dll_sha256)
