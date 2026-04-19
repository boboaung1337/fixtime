## Fixtime Install


```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```bash
wget https://raw.githubusercontent.com/boboaung1337/fixtime/refs/heads/main/fixtime.py && mv fixtime.py ~/.local/bin/fixtime.py && sudo chmod +x ~/.local/bin/fixtime.py
```



## Options

```bash
fixtime.py -h
```

## Basic Usage

```bash
fixtime.py -u tombwatcher.htb -i 10.10.10.10 --auto-ntpdate
```

```bash
fixtime.py -u tombwatcher.htb -i 10.10.10.10 --auto-ntpdate --force
```

```bash
fixtime.py -u dc.voleur.htb -i 192.168.1.10 --check-skew
```

```bash
fixtime.py -u dc.domain.com -i 10.0.0.5 --auto-domain --auto-ntpdate
```

```bash
fixtime.py -u target.local -i 192.168.0.100 --ntp-server time.google.com --auto-ntpdate
```
```


