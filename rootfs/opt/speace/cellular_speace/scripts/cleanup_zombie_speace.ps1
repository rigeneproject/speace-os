Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -gt (Get-Date).AddMinutes(-5) -and $_.Id -ne 5856 } | ForEach-Object {
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
    if ($cmd -like "*evolution_daemon*" -or $cmd -like "*start_evolution_daemon*") {
        Write-Host "Killing PID=$($_.Id) - $cmd"
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep 1
Write-Host "---REMAINING---"
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -gt (Get-Date).AddMinutes(-3) } | ForEach-Object {
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
    Write-Host "PID=$($_.Id) Cmd=$($cmd.Substring(0, [Math]::Min(100, $cmd.Length)))"
}
