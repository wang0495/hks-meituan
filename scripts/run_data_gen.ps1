$projectRoot = "C:\Users\wang\Desktop\hks美团"
$logFile = "$projectRoot\data_generation.log"

Remove-Item $logFile -ErrorAction SilentlyContinue

$job = Start-Job -Name "CityFlowDataGen" -ScriptBlock {
    param($root, $log)
    Set-Location $root
    $env:PYTHONPATH = $root
    python -m backend.tools.data_generator.main --task all --provider LongCatProvider --provider-args '{"api_key": "ak_2C232w6Wj58e9Pw8a86gd2id76U58"}' *>&1 | Out-File -FilePath $log -Encoding utf8
    $exitCode = $LASTEXITCODE
    "`n=== 进程退出码: $exitCode ===" | Out-File -FilePath $log -Encoding utf8 -Append
} -ArgumentList $projectRoot, $logFile

$sep = "=" * 60
Write-Host $sep
Write-Host "数据生成后台任务已启动"
Write-Host $sep
Write-Host ""
Write-Host "  任务名:    CityFlowDataGen"
Write-Host "  Task ID:   $($job.Id)"
Write-Host "  日志文件:  $logFile"
Write-Host ""
Write-Host "  查看日志:  Get-Content -Path '$logFile' -Tail 30 -Wait"
Write-Host "  检查状态:  Get-Job -Id $($job.Id)"
Write-Host "  停止任务:  Stop-Job -Id $($job.Id); Remove-Job -Id $($job.Id)"
Write-Host ""
