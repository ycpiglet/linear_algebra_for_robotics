[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateLength(1, 32)]
    [ValidatePattern("^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,30}[A-Za-z0-9])?$")]
    [string]$Device,

    [Parameter(Mandatory = $true)]
    [ValidateLength(1, 253)]
    [ValidatePattern("^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")]
    [string]$RemoteHostName,

    [Parameter(Mandatory = $true)]
    [ValidateLength(1, 32)]
    [ValidatePattern("^[A-Za-z_][A-Za-z0-9_-]{0,31}$")]
    [string]$RemoteUser,

    [Parameter(Mandatory = $true)]
    [ValidateScript({
        if (-not $_.StartsWith("/") -or $_ -match "['`r`n]") {
            throw "RemoteProject는 작은따옴표나 줄바꿈이 없는 Linux 절대 경로여야 합니다."
        }
        $true
    })]
    [string]$RemoteProject,

    [ValidateLength(1, 63)]
    [ValidatePattern("^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,61}[A-Za-z0-9])?$")]
    [string]$HostAlias = "linear-dev"
)

$ErrorActionPreference = "Stop"
$Device = $Device.ToLowerInvariant()
$RemoteHostName = $RemoteHostName.ToLowerInvariant()
$HostAlias = $HostAlias.ToLowerInvariant()

$Ssh = Get-Command ssh.exe -ErrorAction SilentlyContinue
$SshKeygen = Get-Command ssh-keygen.exe -ErrorAction SilentlyContinue
if (-not $Ssh -or -not $SshKeygen) {
    throw "Windows OpenSSH Client가 필요합니다. 관리자 PowerShell에서 Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0 을 실행하세요."
}

$TailscaleCommand = Get-Command tailscale.exe -ErrorAction SilentlyContinue
$TailscalePath = $null
if ($TailscaleCommand) {
    $TailscalePath = $TailscaleCommand.Source
} else {
    $InstalledTailscalePath = Join-Path $env:ProgramFiles "Tailscale\tailscale.exe"
    if (Test-Path $InstalledTailscalePath) {
        $TailscalePath = $InstalledTailscalePath
    }
}
if (-not $TailscalePath) {
    throw "Tailscale이 설치되지 않았습니다. https://tailscale.com/download/windows 에서 먼저 설치하세요."
}

Write-Host "Tailscale 연결 상태를 확인합니다..."
& $TailscalePath status
if ($LASTEXITCODE -ne 0) {
    throw "Tailscale에 로그인한 뒤 다시 실행하세요."
}

$SshDir = Join-Path $HOME ".ssh"
New-Item -ItemType Directory -Force -Path $SshDir | Out-Null

$KeyAlias = $HostAlias -replace '[^A-Za-z0-9_]', '_'
if ($HostAlias -ne "linear-dev") {
    $Sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $AliasHashBytes = $Sha256.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($HostAlias))
    } finally {
        $Sha256.Dispose()
    }
    $AliasHash = -join ($AliasHashBytes[0..5] | ForEach-Object { $_.ToString("x2") })
    $KeyAlias = "${KeyAlias}_$AliasHash"
}
$KeyName = "id_ed25519_${KeyAlias}_$Device"
$KeyPath = Join-Path $SshDir $KeyName
$PublicKeyPath = "$KeyPath.pub"

if (-not (Test-Path $KeyPath)) {
    Write-Host
    Write-Host "$Device 전용 SSH 키를 생성합니다."
    Write-Host "개인키 보호를 위해 passphrase 입력을 권장합니다."
    & $SshKeygen.Source -t ed25519 -a 64 -f $KeyPath -C "windows-$Device-to-$HostAlias"
    if ($LASTEXITCODE -ne 0) {
        throw "SSH 키 생성에 실패했습니다."
    }
} elseif (-not (Test-Path $PublicKeyPath)) {
    throw "개인키는 있지만 공개키가 없습니다: $PublicKeyPath"
} else {
    Write-Host "기존 $Device 전용 키를 재사용합니다: $KeyPath"
}

$DerivedPublicKey = (& $SshKeygen.Source -y -f $KeyPath)
if ($LASTEXITCODE -ne 0) {
    throw "개인키에서 공개키를 확인하지 못했습니다. SSH key passphrase를 확인하세요."
}
$DerivedKeyParts = $DerivedPublicKey.Trim() -split "\s+"
$StoredKeyParts = (Get-Content -Raw $PublicKeyPath).Trim() -split "\s+"
if (
    $DerivedKeyParts.Count -lt 2 -or
    $StoredKeyParts.Count -lt 2 -or
    $DerivedKeyParts[0] -ne $StoredKeyParts[0] -or
    $DerivedKeyParts[1] -ne $StoredKeyParts[1]
) {
    throw "개인키와 공개키가 서로 일치하지 않습니다: $KeyPath"
}

$ConfigPath = Join-Path $SshDir "config"
$BeginMarker = "# BEGIN CODEX SSH HOST $HostAlias"
$EndMarker = "# END CODEX SSH HOST $HostAlias"
$ConfigBlock = @"
$BeginMarker
Host $HostAlias
    HostName $RemoteHostName
    User $RemoteUser
    IdentityFile ~/.ssh/$KeyName
    IdentitiesOnly yes
    ForwardAgent no
    ServerAliveInterval 30
    ServerAliveCountMax 3
Host *
$EndMarker
"@

$ExistingConfig = ""
$HadExistingConfig = Test-Path $ConfigPath
if ($HadExistingConfig) {
    $ConfigItem = Get-Item -LiteralPath $ConfigPath
    if ($ConfigItem.PSIsContainer) {
        throw "SSH config 경로가 파일이 아닌 디렉터리입니다: $ConfigPath"
    }
    if (($ConfigItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "SSH config가 심볼릭 링크입니다. 자동 교체 대신 수동으로 설정하세요: $ConfigPath"
    }
    $ExistingConfig = [System.IO.File]::ReadAllText($ConfigPath)
}

$MarkerPattern = "(?ms)^" + [regex]::Escape($BeginMarker) + "\r?\n.*?^" + [regex]::Escape($EndMarker) + "\r?\n?"
$MarkerRegex = [regex]::new($MarkerPattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
$BeginMatches = [regex]::Matches($ExistingConfig, "(?im)^" + [regex]::Escape($BeginMarker) + "\r?$")
$EndMatches = [regex]::Matches($ExistingConfig, "(?im)^" + [regex]::Escape($EndMarker) + "\r?$")
$BeginCount = $BeginMatches.Count
$EndCount = $EndMatches.Count
if ($BeginCount -ne $EndCount -or $BeginCount -gt 1) {
    throw "관리되는 SSH config 마커가 손상되었거나 중복되었습니다: $ConfigPath"
}
if ($BeginCount -eq 1 -and $BeginMatches[0].Index -ge $EndMatches[0].Index) {
    throw "관리되는 SSH config 마커 순서가 잘못되었습니다: $ConfigPath"
}
$RemainingConfig = $MarkerRegex.Replace($ExistingConfig, "")
$RemainingConfig = $RemainingConfig.TrimStart("`r", "`n")

# OpenSSH client 설정은 먼저 얻은 값이 우선입니다. 관리 블록을 맨 앞에 두고
# Host * 로 범위를 초기화해 기존 전역 설정의 의미도 유지합니다.
$UpdatedConfig = "$ConfigBlock`r`n"
if ($RemainingConfig.Length -gt 0) {
    $UpdatedConfig += $RemainingConfig
    if (-not $UpdatedConfig.EndsWith("`n")) {
        $UpdatedConfig += "`r`n"
    }
}

$ConfigTempPath = "$ConfigPath.codex-tmp.$([guid]::NewGuid().ToString('N'))"
$ConfigBackupPath = "$ConfigPath.bak.$(Get-Date -Format 'yyyyMMdd-HHmmss-fff').$([guid]::NewGuid().ToString('N'))"
[System.IO.File]::WriteAllText($ConfigTempPath, $UpdatedConfig, [System.Text.UTF8Encoding]::new($false))
if ($HadExistingConfig) {
    Copy-Item -LiteralPath $ConfigPath -Destination $ConfigBackupPath
    Move-Item -LiteralPath $ConfigTempPath -Destination $ConfigPath -Force
    Write-Host "기존 SSH config 백업: $ConfigBackupPath"
} else {
    Move-Item -LiteralPath $ConfigTempPath -Destination $ConfigPath
}

function Restore-ManagedSshConfig {
    if ($HadExistingConfig) {
        Copy-Item -LiteralPath $ConfigBackupPath -Destination $ConfigPath -Force
    } else {
        Remove-Item -LiteralPath $ConfigPath -Force -ErrorAction SilentlyContinue
    }
}

$ResolvedConfig = & $Ssh.Source -G $HostAlias 2>$null
if ($LASTEXITCODE -ne 0) {
    Restore-ManagedSshConfig
    throw "SSH config 해석에 실패했습니다: $ConfigPath"
}
$ResolvedHostName = ($ResolvedConfig | Where-Object { $_ -match '^hostname\s+' } | Select-Object -First 1) -replace '^hostname\s+', ''
$ResolvedUser = ($ResolvedConfig | Where-Object { $_ -match '^user\s+' } | Select-Object -First 1) -replace '^user\s+', ''
$ResolvedIdentitiesOnly = ($ResolvedConfig | Where-Object { $_ -match '^identitiesonly\s+' } | Select-Object -First 1) -replace '^identitiesonly\s+', ''
$ResolvedIdentityFile = ($ResolvedConfig | Where-Object { $_ -match '^identityfile\s+' } | Select-Object -First 1) -replace '^identityfile\s+', ''
if (
    $ResolvedHostName -ne $RemoteHostName -or
    $ResolvedUser -ne $RemoteUser -or
    $ResolvedIdentitiesOnly -ne "yes" -or
    $ResolvedIdentityFile -notlike "*$KeyName"
) {
    Restore-ManagedSshConfig
    throw "적용된 SSH 설정이 예상과 다릅니다. 'ssh -G $HostAlias' 결과를 확인하세요."
}

$RegisterKeyCommand = @'
umask 077
mkdir -p ~/.ssh
touch ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
IFS= read -r key
key=$(printf %s "$key" | tr -d '\r')
case "$key" in ssh-ed25519\ *) ;; *) exit 64 ;; esac
if ! grep -qxF -- "$key" ~/.ssh/authorized_keys; then
    if [ -s ~/.ssh/authorized_keys ]; then printf '\n' >> ~/.ssh/authorized_keys; fi
    printf '%s\n' "$key" >> ~/.ssh/authorized_keys
fi
'@
$EmptySshConfigPath = Join-Path $env:TEMP "codex-ssh-empty-$([guid]::NewGuid().ToString('N')).conf"
[System.IO.File]::WriteAllText($EmptySshConfigPath, "", [System.Text.Encoding]::ASCII)
try {
    & $Ssh.Source `
        -F $EmptySshConfigPath `
        -i $KeyPath `
        -o IdentityAgent=none `
        -o IdentitiesOnly=yes `
        -o PreferredAuthentications=publickey `
        -o PasswordAuthentication=no `
        -o KbdInteractiveAuthentication=no `
        "$RemoteUser@$RemoteHostName" `
        "true"
    if ($LASTEXITCODE -eq 0) {
        Write-Host
        Write-Host "이 키가 이미 등록되어 있어 비밀번호 등록을 건너뜁니다."
    } else {
        Write-Host
        Write-Host "공개키를 원격 호스트에 등록합니다."
        Write-Host "처음 한 번은 원격 Linux 사용자 암호를 입력해야 합니다."
        Get-Content -Raw $PublicKeyPath |
            & $Ssh.Source `
                -F $EmptySshConfigPath `
                -o PreferredAuthentications=password `
                -o PasswordAuthentication=yes `
                -o PubkeyAuthentication=no `
                -o KbdInteractiveAuthentication=no `
                -o IdentitiesOnly=yes `
                "$RemoteUser@$RemoteHostName" `
                $RegisterKeyCommand
        if ($LASTEXITCODE -ne 0) {
            throw "공개키 등록에 실패했습니다. 원격 호스트에서 임시 비밀번호 로그인이 허용되어 있는지 확인하세요."
        }
    }

    $SshAgent = Get-Service ssh-agent -ErrorAction SilentlyContinue
    if ($SshAgent -and $SshAgent.Status -eq "Running") {
        Write-Host
        Write-Host "Windows ssh-agent에 키를 추가합니다."
        & ssh-add.exe $KeyPath
        if ($LASTEXITCODE -ne 0) {
            throw "Windows ssh-agent에 키를 추가하지 못했습니다."
        }
    } else {
        Write-Warning "Windows ssh-agent가 실행 중이 아닙니다. passphrase 키를 Codex 앱에서 쓰려면 아래 안내대로 활성화하세요."
    }

    Write-Host
    Write-Host "방금 만든 키만 사용해 SSH와 원격 Codex 실행을 검증합니다..."
    & $Ssh.Source `
        -F $EmptySshConfigPath `
        -i $KeyPath `
        -o IdentityAgent=none `
        -o IdentitiesOnly=yes `
        -o PreferredAuthentications=publickey `
        -o PasswordAuthentication=no `
        -o KbdInteractiveAuthentication=no `
        "$RemoteUser@$RemoteHostName" `
        "codex --version && cd '$RemoteProject' && git status --short --branch"
    if ($LASTEXITCODE -ne 0) {
        throw "새 키를 사용한 원격 접속 검증에 실패했습니다."
    }
} finally {
    Remove-Item -LiteralPath $EmptySshConfigPath -Force -ErrorAction SilentlyContinue
}

Write-Host
Write-Host "설정 완료: $Device -> $HostAlias"
Write-Host "데스크톱 앱에서는 Settings > Connections에서 '$HostAlias'를 추가하세요."
Write-Host "원격 프로젝트: $RemoteProject"
Write-Host
Write-Host "passphrase를 매번 묻는다면 관리자 PowerShell에서 다음을 한 번 실행하세요:"
Write-Host "  Get-Service ssh-agent | Set-Service -StartupType Automatic"
Write-Host "  Start-Service ssh-agent"
Write-Host "그 다음 일반 PowerShell에서:"
Write-Host "  ssh-add `"$KeyPath`""
