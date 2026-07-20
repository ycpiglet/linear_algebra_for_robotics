# 원격 개발 클라이언트 설정

Windows 또는 macOS에서 Tailscale과 OpenSSH를 통해 상시 가동 Linux 개발
호스트에 접속하는 설정입니다. 소스·빌드·Codex는 원격 호스트에서 실행되고 각
클라이언트는 화면과 입력만 담당합니다.

이 공개 저장소에는 실제 호스트명, 사용자명, 개인키 또는 자격증명을 넣지 않습니다.
아래 자리표시자는 자신의 환경 값으로 바꿉니다.

```text
REMOTE_HOST=devbox.example.ts.net
REMOTE_USER=developer
REMOTE_PROJECT=/home/developer/project
HOST_ALIAS=linear-dev
```

## 공통 준비

1. 원격 Linux 호스트와 클라이언트를 같은 Tailscale 계정 또는 허용된 tailnet에
   연결합니다.
2. 클라이언트마다 별도의 Ed25519 키를 만듭니다. 개인키를 장치 사이에 복사하지
   않습니다.
3. 최초 공개키 등록 동안에만 원격 호스트의 비밀번호 SSH 로그인을 허용합니다.
   모든 장치의 키 검증 후 다시 비활성화합니다.

최초 SSH 접속에서 호스트 키 확인 질문이 나오면 서버 관리자가 별도 경로로 알려준
지문과 일치할 때만 승인합니다. 다르면 `known_hosts`를 지우거나 무시하지 말고
접속을 중단합니다.

## Windows

Windows OpenSSH Client와 [Tailscale for Windows](https://tailscale.com/download/windows)를
설치하고 Tailscale에 로그인합니다. 저장소 루트의 PowerShell에서 데스크톱과
노트북에 서로 다른 `Device` 값을 사용합니다.

```powershell
Get-Command ssh, ssh-keygen

.\remote-access\bootstrap-windows.ps1 `
  -Device desktop `
  -RemoteHostName REMOTE_HOST `
  -RemoteUser REMOTE_USER `
  -RemoteProject REMOTE_PROJECT
```

노트북에서는 `-Device laptop`으로 실행합니다. OpenSSH Client가 없다면 관리자
PowerShell에서 다음을 먼저 실행합니다.

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
```

passphrase 키를 데스크톱 앱에서 사용하려면 관리자 PowerShell에서 Windows
`ssh-agent`를 한 번 활성화한 뒤 일반 PowerShell에서 키를 추가합니다.

```powershell
Get-Service ssh-agent | Set-Service -StartupType Automatic
Start-Service ssh-agent
ssh-add "$HOME\.ssh\id_ed25519_linear_dev_desktop"
```

## macOS

macOS에는 OpenSSH가 기본 포함됩니다. [Tailscale for macOS](https://tailscale.com/download/mac)을
설치하고 Tailscale에 로그인한 뒤 실행합니다. Mac이 여러 대라면 `--device`를
`macbook`, `macmini`처럼 각각 다르게 지정합니다.

```bash
chmod +x remote-access/bootstrap-macos.sh

./remote-access/bootstrap-macos.sh \
  --device macbook \
  --host REMOTE_HOST \
  --user REMOTE_USER \
  --project REMOTE_PROJECT
```

스크립트는 키를 macOS Keychain과 `ssh-agent`에 추가하고 `UseKeychain`을 SSH
설정에 적용합니다.

## Codex/ChatGPT 데스크톱 앱

설정이 끝나면 먼저 터미널에서 확인합니다.

```bash
ssh linear-dev
```

그다음 데스크톱 앱의 **Settings > Connections > SSH**에서 `linear-dev`를
추가하고 `REMOTE_PROJECT` 폴더를 선택합니다. 앱은 `~/.ssh/config`의 구체적인
호스트 별칭을 읽으며, 원격 호스트의 로그인 셸에서 `codex` 명령을 실행합니다.

앱의 SSH 연결 메뉴가 아직 제공되지 않는 환경에서는 터미널과 `tmux`로 같은
작업을 이어갈 수 있습니다.

```bash
ssh -t linear-dev "cd REMOTE_PROJECT && tmux new-session -A -D -s codex-main"
```

## 여러 컴퓨터에서 번갈아 작업하기

모든 클라이언트가 같은 원격 프로젝트를 열기 때문에 미커밋 변경도 즉시 같은
상태로 보입니다. 별도의 Windows↔Mac 파일 동기화는 필요하지 않습니다. GitHub는
커밋·push된 이력의 백업과 협업 원격 저장소로 사용합니다.

두 Codex 세션이 동시에 같은 working tree를 수정하지 않도록 합니다. 동시 작업이
필요하면 세션마다 별도 브랜치와 `git worktree`를 사용합니다. `tmux`의 `-D`는
새 장치가 연결될 때 기존 터미널 클라이언트를 분리해 두 키보드가 같은 세션을 동시에
조작하지 않도록 합니다.

## 이후 새 장치를 추가할 때

키 기반 로그인만 허용하도록 서버를 잠근 뒤 새 장치를 추가한다면, 이미 인증된
장치에서 새 장치의 공개키만 등록할 수 있습니다. Mac에서는 먼저 위와 같은 인자에
`--prepare-only`를 추가해 로컬 키와 설정만 만듭니다.

```bash
./remote-access/bootstrap-macos.sh \
  --device macbook \
  --host REMOTE_HOST \
  --user REMOTE_USER \
  --project REMOTE_PROJECT \
  --prepare-only

cat ~/.ssh/id_ed25519_linear_dev_macbook.pub
```

출력된 한 줄짜리 `.pub` 내용만 이미 승인된 Windows/macOS 장치로 안전하게 옮깁니다.
승인된 Windows PowerShell에서는 공개키 한 줄을 클립보드에 넣고 다음과 같이 중복 없이
등록할 수 있습니다.

```powershell
Get-Clipboard | ssh linear-dev 'umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys; IFS= read -r key; key=$(printf %s "$key" | tr -d "\r"); case "$key" in ssh-ed25519\ *) ;; *) exit 64 ;; esac; if ! grep -qxF -- "$key" ~/.ssh/authorized_keys; then if [ -s ~/.ssh/authorized_keys ]; then printf "\n" >> ~/.ssh/authorized_keys; fi; printf "%s\n" "$key" >> ~/.ssh/authorized_keys; fi'
```

그다음 Mac에서 같은 bootstrap 명령을 `--skip-register`로 다시 실행하면 비밀번호
인증 없이 새 키만으로 검증합니다. 개인키는 어떤 장치로도 전송하지 않습니다.

필요하다면 이미 승인된 접속이나 서버 콘솔에서 비밀번호 SSH를 아주 잠시 다시
허용해 일반 bootstrap을 실행한 뒤 즉시 다시 끌 수도 있습니다.

## 보안 메모

- 스크립트는 기존 `~/.ssh/config`를 고유한 `.bak` 파일로 백업합니다.
- 공개키 등록은 비밀번호 인증만, 최종 검증은 방금 만든 키만 강제합니다.
- `.pub`만 공개키입니다. 확장자 없는 개인키와 passphrase는 공유하거나 저장소에
  커밋하지 않습니다.
- SSH 포트나 Codex app-server를 공용 인터넷에 직접 노출하지 말고 VPN 또는 mesh
  network 안에서 사용합니다.
- 장치를 분실했다면 Tailscale 관리 화면에서 해당 장치를 제거하고, 서버의
  `authorized_keys`에서도 그 장치 주석이 붙은 공개키를 삭제합니다.

공식 참고 자료:

- [Codex remote connections](https://learn.chatgpt.com/docs/remote-connections)
- [Tailscale Windows 설치](https://tailscale.com/docs/install/windows)
- [Tailscale macOS 설치](https://tailscale.com/docs/install/mac)
