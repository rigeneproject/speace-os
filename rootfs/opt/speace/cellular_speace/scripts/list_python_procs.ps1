$ErrorActionPreference = 'SilentlyContinue'
Get-Process python -ErrorAction SilentlyContinue |
  Where-Object { $_.StartTime -gt (Get-Date).AddMinutes(-30) } |
  ForEach-Object {
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
    $short = if ($cmd.Length -gt 140) { $cmd.Substring(0, 140) + '...' } else { $cmd }
    [PSCustomObject]@{
      Id           = $_.Id
      PPId         = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").ParentProcessId
      Started      = $_.StartTime.ToString('HH:mm:ss')
      CmdLine      = $short
    }
  } | Format-Table -AutoSize -Wrap
