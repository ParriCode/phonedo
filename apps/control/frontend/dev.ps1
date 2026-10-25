param(
    [ValidateSet('serve', 'build', 'test')]
    [string]$Command = 'serve'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$frontendToolRoot = Join-Path $repoRoot '.run/frontend-tools'
$savedEnvironment = @{}
foreach ($name in @('PATH', 'CARGO_HOME', 'RUSTUP_HOME', 'TRUNK_TOOLS_CACHE_DIR', 'CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER')) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

Push-Location $PSScriptRoot
try {
    # Usa las herramientas locales si están disponibles, sin cambiar Windows.
    if (Test-Path (Join-Path $frontendToolRoot 'cargo/bin/cargo.exe')) {
        $env:CARGO_HOME = Join-Path $frontendToolRoot 'cargo'
        $env:RUSTUP_HOME = Join-Path $frontendToolRoot 'rustup'
        $env:PATH = (Join-Path $frontendToolRoot 'cargo/bin') + ';' + (Join-Path $frontendToolRoot 'trunk') + ';' + $env:PATH
        $env:PATH = (Join-Path $frontendToolRoot 'wasm-bindgen') + ';' + $env:PATH
        $nativeTools = Join-Path (& rustc --print sysroot) 'lib/rustlib/x86_64-pc-windows-gnu/bin/self-contained'
        if (Test-Path $nativeTools) {
            $env:PATH = $nativeTools + ';' + $env:PATH
            $env:CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER = Join-Path $nativeTools 'x86_64-w64-mingw32-gcc.exe'
        }
        $llvmRoot = Join-Path $frontendToolRoot 'llvm-mingw'
        if (Test-Path $llvmRoot) {
            $llvmTools = Get-ChildItem -LiteralPath $llvmRoot -Directory | Select-Object -First 1
            if ($llvmTools) { $env:PATH = (Join-Path $llvmTools.FullName 'bin') + ';' + $env:PATH }
        }
        $env:TRUNK_TOOLS_CACHE_DIR = Join-Path $frontendToolRoot 'cache'
    }
    if ($Command -eq 'test') {
        if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) { throw 'Falta Rust. Consulta README.md.' }
        & cargo test --locked
    } else {
        if (-not (Get-Command trunk -ErrorAction SilentlyContinue)) { throw 'Falta Trunk. Consulta README.md.' }
        & trunk $Command
    }
    if ($LASTEXITCODE -ne 0) { throw "La operación terminó con código $LASTEXITCODE." }
} finally {
    Pop-Location
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
}
