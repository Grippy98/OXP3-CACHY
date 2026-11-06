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
$tools = Get-Content (Join-Path $recipe 'tools.json') -Raw | ConvertFrom-Json
$patch = Join-Path $recipe 'renodx-gta-ui.patch'
if ((Get-FileHash $patch -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pin.patch_sha256) { throw 'Source patch hash mismatch.' }
if ((git -C $source rev-parse HEAD).Trim() -ne $pin.commit) { throw 'RenoDX source commit mismatch.' }
if (git -C $source status --porcelain) { throw 'RenoDX source must start clean.' }
$submodules = @(git -C $source submodule status --recursive)
if ($LASTEXITCODE -ne 0 -or ($submodules | Where-Object { $_ -match '^[-+U]' })) { throw 'Submodules must match their pinned commits.' }
if ((Get-Item $patch).Length -gt 0) {
    git -C $source apply --check $patch
    if ($LASTEXITCODE -ne 0) { throw 'Source patch does not apply.' }
    git -C $source apply $patch
    if ($LASTEXITCODE -ne 0) { throw 'Source patch application failed.' }
    git -C $source diff --check
    if ($LASTEXITCODE -ne 0) { throw 'Source patch whitespace check failed.' }
}
if ($pin.PSObject.Properties.Name -contains 'ui_packet_header_sha256') {
    $header = Join-Path $source 'src/games/gtav-enhanced/oxp3_ffx_ui_packet.h'
    if ((Get-FileHash $header -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pin.ui_packet_header_sha256) { throw 'UI packet ABI header mismatch.' }
}

# Match upstream's managed shader-tool versions, additionally verifying exact release archive hashes.
$bin = Join-Path $source 'bin'
$cache = if ($env:RUNNER_TEMP) { Join-Path $env:RUNNER_TEMP 'oxp3-renodx-shader-tools' } else { Join-Path ([IO.Path]::GetTempPath()) 'oxp3-renodx-shader-tools' }
New-Item -ItemType Directory -Force $bin, $cache | Out-Null
foreach ($name in @('dxc', 'slang', 'glslang')) {
    $tool = $tools.$name
    $archive = Join-Path $cache ($name + '.zip')
    Invoke-WebRequest -Uri $tool.url -OutFile $archive
    if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $tool.sha256) { throw "Shader tool hash mismatch: $name" }
    $expanded = Join-Path $cache $name
    New-Item -ItemType Directory -Force $expanded | Out-Null
    Expand-Archive -Path $archive -DestinationPath $expanded -Force
    if ($name -eq 'dxc') {
        Copy-Item (Join-Path $expanded 'bin/x64/*') $bin -Force
    } elseif ($name -eq 'slang') {
        Copy-Item (Join-Path $expanded 'bin/*') $bin -Recurse -Force
    } else {
        Copy-Item (Join-Path $expanded 'bin/glslang.exe') $bin -Force
    }
}

$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vsPath = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
if (-not $vsPath) { throw 'Visual Studio C++ tools were not found.' }
& (Join-Path $vsPath 'Common7/Tools/Launch-VsDevShell.ps1') -Arch amd64 -HostArch amd64 -SkipAutomaticLocation
$llvm = Join-Path $env:ProgramFiles 'LLVM/bin'
if (-not (Test-Path (Join-Path $llvm 'clang-cl.exe'))) { throw 'Runner LLVM clang-cl is missing.' }
$env:PATH = $llvm + ';' + $env:PATH
$env:PATH = $bin + ';' + $env:PATH
$compilerVersion = (& clang-cl --version) -join "`n"
if ($LASTEXITCODE -ne 0) { throw 'Clang version query failed.' }
$dxcVersion = (& (Join-Path $bin 'dxc.exe') --version) -join "`n"
if ($LASTEXITCODE -ne 0) { throw 'DXC version query failed.' }
$slangVersion = (& (Join-Path $bin 'slangc.exe') -version 2>&1) -join "`n"
if ($LASTEXITCODE -ne 0) { throw 'Slang version query failed.' }

# Keep upstream presets/CMake unchanged. Build only this addon and its embedded shaders.
Push-Location $source
try {
    cmake --preset clang-x64
    if ($LASTEXITCODE -ne 0) { throw 'RenoDX CMake configuration failed.' }
    cmake --build --preset clang-x64-release --target gtav-enhanced --parallel 2
    if ($LASTEXITCODE -ne 0) { throw 'GTA addon or shader build failed.' }
} finally { Pop-Location }
$addon = Join-Path $source 'build/Release/renodx-gtav-enhanced.addon64'
$shaderHeader = Join-Path $source 'build/gtav-enhanced.include/embed/swap_chain_proxy_pixel_shader.h'
if (-not (Test-Path $addon)) { throw 'Expected addon artifact is missing.' }
if (-not (Test-Path $shaderHeader)) { throw 'Expected regenerated proxy-shader header is missing.' }
Copy-Item $addon (Join-Path $artifact 'renodx-gtav-enhanced.addon64')
Copy-Item $patch (Join-Path $artifact 'source.patch')
Copy-Item (Join-Path $source 'LICENSE') (Join-Path $artifact 'LICENSE')
Copy-Item (Join-Path $recipe 'README.md') (Join-Path $artifact 'SOURCE.md')
Copy-Item (Join-Path $recipe 'tools.json') (Join-Path $artifact 'tools.json')
$record = [ordered]@{
    source_repository = $pin.repository
    source_commit = $pin.commit
    patch_sha256 = $pin.patch_sha256
    ui_packet_header_sha256 = $pin.ui_packet_header_sha256
    addon_sha256 = (Get-FileHash $addon -Algorithm SHA256).Hash.ToLowerInvariant()
    proxy_shader_header_sha256 = (Get-FileHash $shaderHeader -Algorithm SHA256).Hash.ToLowerInvariant()
    compiler = $compilerVersion
    dxc = $dxcVersion
    slang = $slangVersion
    tools = $tools
    submodules = $submodules
    configuration = 'Upstream clang-x64-release preset; gtav-enhanced target only; global build files unchanged.'
    runtime_status = 'Build artifact only; not installed or runtime-qualified by CI.'
    workflow_commit = $env:GITHUB_SHA
}
$record | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $artifact 'build-record.json') -Encoding utf8
Write-Output ('RenoDX GTA addon SHA256 ' + $record.addon_sha256)
