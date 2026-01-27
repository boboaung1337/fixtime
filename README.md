# fixtime

# Basic usage with hostname and IP
sudo python3 fixTime.py -u tombwatcher.htb -i 10.10.10.10 --auto-ntpdate

# With force option
sudo python3 fixTime.py -u tombwatcher.htb -i 10.10.10.10 --auto-ntpdate --force

# Check skew only
sudo python3 fixTime.py -u dc.voleur.htb -i 192.168.1.10 --check-skew

# Auto domain detection with IP
sudo python3 fixTime.py -u dc.domain.com -i 10.0.0.5 --auto-domain --auto-ntpdate

# Use custom NTP server
sudo python3 fixTime.py -u target.local -i 192.168.0.100 --ntp-server time.google.com --auto-ntpdate

# Basic usage with auto ntpdate
sudo python3 fixTime.py -u dc.voleur.htb --auto-ntpdate

# Check skew after auto sync
sudo python3 fixTime.py -u tombwatcher.htb --auto-ntpdate --check-skew

# Force sync even if within tolerance
sudo python3 fixTime.py -u 10.10.10.10 --auto-ntpdate --force

# Use auto-domain detection with auto ntpdate
sudo python3 fixTime.py -u dc.domain.com --auto-domain --auto-ntpdate
