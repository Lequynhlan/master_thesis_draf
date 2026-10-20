param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("midnight", "pre_market")]
    [string]$RunLabel
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ConfigPath = Join-Path $ProjectRoot "config\vertical_slice.yaml"
$LogDirectory = Join-Path $ProjectRoot "runs\daily_news"
$LogPath = Join-Path $LogDirectory ("{0}_{1}.log" -f $RunLabel, (Get-Date -Format "yyyyMMdd-HHmmss"))

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Không tìm thấy Python của môi trường project: $PythonPath"
}
if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Không tìm thấy cấu hình daily crawl: $ConfigPath"
}

New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
$TimeZone = Get-TimeZone
"Bắt đầu daily ingest: $(Get-Date -Format o)" | Out-File -FilePath $LogPath -Encoding utf8
"Múi giờ Windows: $($TimeZone.Id) ($($TimeZone.DisplayName)); UTC offset hiện tại: $((Get-Date).ToString('zzz'))" | Out-File -FilePath $LogPath -Append -Encoding utf8
"Nhãn lịch chạy: $RunLabel" | Out-File -FilePath $LogPath -Append -Encoding utf8

$RunId = Get-Date -Format "yyyyMMdd-HHmmss-fff"
$StdOutPath = Join-Path $LogDirectory ("{0}_{1}.stdout.tmp" -f $RunLabel, $RunId)
$StdErrPath = Join-Path $LogDirectory ("{0}_{1}.stderr.tmp" -f $RunLabel, $RunId)
$ExitCode = 1
try {
    # Tách stdout/stderr để cảnh báo Python không bị PowerShell coi là lỗi dừng script.
    # Task Scheduler sẽ nhận đúng mã thoát của Python và log vẫn ghi đủ kết quả.
    $PythonArguments = "-u -m wfkg crawl-daily --config `"$ConfigPath`""
    $PythonProcess = Start-Process -FilePath $PythonPath `
        -ArgumentList $PythonArguments `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden -Wait -PassThru `
        -RedirectStandardOutput $StdOutPath `
        -RedirectStandardError $StdErrPath
    $ExitCode = $PythonProcess.ExitCode

    foreach ($OutputPath in @($StdOutPath, $StdErrPath)) {
        if (Test-Path -LiteralPath $OutputPath) {
            Get-Content -LiteralPath $OutputPath -Raw | Out-File -FilePath $LogPath -Append -Encoding utf8
        }
    }
}
catch {
    $_ | Out-String | Out-File -FilePath $LogPath -Append -Encoding utf8
    $ExitCode = 1
}
finally {
    Remove-Item -LiteralPath $StdOutPath, $StdErrPath -Force -ErrorAction SilentlyContinue
}

"Kết thúc: $(Get-Date -Format o); mã thoát: $ExitCode" | Out-File -FilePath $LogPath -Append -Encoding utf8
exit $ExitCode
