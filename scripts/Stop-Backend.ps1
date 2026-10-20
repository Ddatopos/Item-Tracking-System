# 基于神经网络的物品示踪系统 V1.0
param([int]$Port = 5000)
$ErrorActionPreference = 'Stop'
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$Port/api/shutdown"
