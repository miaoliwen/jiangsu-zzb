param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [string]$OutputDir,

    [ValidateSet('official', 'teacher', 'teacher-redline', 'review')]
    [string]$Variant,

    [string]$PandocPath,

    [string]$PythonPath = 'C:\Users\ROG\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
)

$ErrorActionPreference = 'Stop'

$scriptDirectory = Split-Path -Path $PSCommandPath -Parent
$pythonScript = Join-Path $scriptDirectory 'build_exam_paper.py'
$projectRoot = Split-Path -Path $scriptDirectory -Parent

function Resolve-PandocPath {
    param(
        [string]$ExplicitPath,
        [string]$RootPath
    )

    if ($ExplicitPath) {
        if (Test-Path -LiteralPath $ExplicitPath) {
            return $ExplicitPath
        }
        throw "Pandoc not found at explicit path: $ExplicitPath"
    }

    $bundledPandoc = Get-ChildItem -Path (Join-Path $RootPath 'tools\pandoc') -Filter 'pandoc.exe' -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
    if ($bundledPandoc) {
        return $bundledPandoc
    }

    return $null
}

$arguments = @($pythonScript, '--input', $InputPath)

if ($OutputDir) {
    $arguments += @('--output-dir', $OutputDir)
}

if ($Variant) {
    $arguments += @('--variant', $Variant)
}

$resolvedPandocPath = Resolve-PandocPath -ExplicitPath $PandocPath -RootPath $projectRoot
if ($resolvedPandocPath) {
    $arguments += @('--pandoc-path', $resolvedPandocPath)
}

& $PythonPath @arguments
