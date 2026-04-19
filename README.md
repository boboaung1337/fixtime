# Fixtime Install

curl -LsSf https://astral.sh/uv/install.sh | sh

wget https://raw.githubusercontent.com/boboaung1337/fixtime/refs/heads/main/fixtime.py && mv fixtime.py ~/.local/bin/fixtime.py && sudo chmod +x ~/.local/bin/fixtime.py 

# OPTIONS

fixtime.py -h

# Basic usage with hostname and IP
fixtime.py -u tombwatcher.htb -i 10.10.10.10 --auto-ntpdate

# With force option
fixtime.py -u tombwatcher.htb -i 10.10.10.10 --auto-ntpdate --force

# Check skew only
fixtime.py -u dc.voleur.htb -i 192.168.1.10 --check-skew

# Auto domain detection with IP
fixtime.py -u dc.domain.com -i 10.0.0.5 --auto-domain --auto-ntpdate

# Use custom NTP server
fixtime.py -u target.local -i 192.168.0.100 --ntp-server time.google.com --auto-ntpdate
