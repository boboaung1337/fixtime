## Fixtime Install

```bash
sudo su
```
```bash
wget https://github.com/boboaung1337/fixtime/raw/refs/heads/main/fixtime && sudo mv fixtime /usr/bin && sudo chmod +x /usr/bin/fixtime
```
## Options

```bash
fixtime -h
```

## Basic Usage

```bash
fixtime -u tombwatcher.htb -i 10.10.10.10 --auto-ntpdate
```

```bash
fixtime -u tombwatcher.htb -i 10.10.10.10 --auto-ntpdate --force
```

```bash
fixtime -u dc.voleur.htb -i 192.168.1.10 --check-skew
```

```bash
fixtime -u dc.domain.com -i 10.0.0.5 --auto-domain --auto-ntpdate
```

```bash
fixtime -u target.local -i 192.168.0.100 --ntp-server time.google.com --auto-ntpdate
```
```bash
fixtime --restore-ntp
```
