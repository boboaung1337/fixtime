# fixtime

# Basic usage with auto ntpdate
sudo python3 fixTime.py -u dc.voleur.htb --auto-ntpdate

# Check skew after auto sync
sudo python3 fixTime.py -u tombwatcher.htb --auto-ntpdate --check-skew

# Force sync even if within tolerance
sudo python3 fixTime.py -u 10.10.10.10 --auto-ntpdate --force

# Use auto-domain detection with auto ntpdate
sudo python3 fixTime.py -u dc.domain.com --auto-domain --auto-ntpdate
