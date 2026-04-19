markdown
## Fixtime Install

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Download and install fixtime
wget https://raw.githubusercontent.com/boboaung1337/fixtime/refs/heads/main/fixtime.py && mv fixtime.py ~/.local/bin/fixtime.py && sudo chmod +x ~/.local/bin/fixtime.py
Options
bash
fixtime.py -h
Basic Usage
Standard synchronization with hostname and IP
bash
fixtime.py -u tombwatcher.htb -i 10.10.10.10 --auto-ntpdate
Force synchronization
bash
fixtime.py -u tombwatcher.htb -i 10.10.10.10 --auto-ntpdate --force
Check time skew only
bash
fixtime.py -u dc.voleur.htb -i 192.168.1.10 --check-skew
Auto domain detection with IP
bash
fixtime.py -u dc.domain.com -i 10.0.0.5 --auto-domain --auto-ntpdate
Use custom NTP server
bash
fixtime.py -u target.local -i 192.168.0.100 --ntp-server time.google.com --auto-ntpdate
