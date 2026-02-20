#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "beautifulsoup4>=4.14.3",
#     "dulwich>=0.25.0",
#     "impacket",
#     "minikerberos>=0.4.9",
#     "pituophis>=1.1",
#     "pyasn1>=0.4.8",
#     "pycryptodome>=3.9.0",
#     "pyftpdlib>=2.1.0",
#     "pysocks>=1.7.1",
#     "requests>=2.32.5",
#     "requests-pkcs12>=1.27",
#     "selenium>=4.39.0",
#     "tzlocal>=5.5",
# ]
# ///

# FixTime
# Author: x4c1s
# Date: 16/11/25
# License: WTFPL
# Improved by muzaffar1337 & Gemini

import requests
import subprocess
import argparse
import socket
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import concurrent.futures
import threading
import sys
import warnings
import os
import time as ttime
import re

# --- Corrected Imports for Warning Handling ---
try:
    # Required for SMB functionality
    from impacket.smbconnection import SMBConnection
except ImportError:
    print("[-] Required module 'impacket' not found. Install with: pip install impacket")
    sys.exit(1)

try:
    # Correct path for InsecureRequestWarning used by requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
except ImportError:
    # Fallback for older versions of requests/urllib3
    warnings.warn("Could not import InsecureRequestWarning from urllib3. Warning suppression may fail.", RuntimeWarning)
    # Define a dummy class to prevent the script from crashing immediately if the required class can't be imported
    class InsecureRequestWarning(Warning):
        pass

# Configuration
TIMEOUT = 3
MAX_WORKERS = 3
KERBEROS_MAX_SKEW = 300

# Lock for printing output
print_lock = threading.Lock()

# --- Argument Parsing ---
parser = argparse.ArgumentParser(
    description="Sync local time with remote Windows target for Kerberos authentication",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  %(prog)s -u dc.voleur.htb                    # Sync time with DC
  %(prog)s -i 10.10.10.10                      # Sync with IP only
  %(prog)s -u dc.domain.com -i 192.168.1.10    # Specify hostname and IP
  %(prog)s -i 10.10.10.10 --auto-ntpdate       # Run ntpdate automatically with IP only
  %(prog)s -i 192.168.1.10 --check-skew        # Check only with IP
  %(prog)s -i 10.10.0.5 --force                 # Force sync with IP only
  %(prog)s --restore-ntp                       # Restore NTP service
"""
)
parser.add_argument("-u", "--url", help="Target URL/IP (e.g., dc.domain.com or http://dc.domain.com)")
parser.add_argument("-i", "--ip", help="Target IP address (if different from DNS resolution or for IP-only mode)")
parser.add_argument("-d", "--domain", help="Domain name for NTP sync (e.g., domain.com)")
parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
parser.add_argument("--restore-ntp", action="store_true", help="Re-enable NTP and exit")
parser.add_argument("--check-skew", action="store_true", help="Check time difference without syncing")
parser.add_argument("--force", action="store_true", help="Force time sync even if within Kerberos tolerance")
parser.add_argument("--use-ntpdate", action="store_true", help="Use ntpdate for final precise sync")
parser.add_argument("--auto-domain", action="store_true", help="Auto-detect domain from hostname")
parser.add_argument("--skip-timezone", action="store_true", help="Don't set timezone to UTC")
parser.add_argument("--ntp-server", help="Custom NTP server (default: domain from target or time.google.com)")
parser.add_argument("--no-ntpdate-fallback", action="store_true", help="Don't use fallback NTP servers if primary fails")
parser.add_argument("--auto-ntpdate", action="store_true", 
                    help="Automatically run ntpdate command before script operations")
args = parser.parse_args()

# --- Helper Functions ---

def log(msg, force=False):
    if args.verbose or force:
        with print_lock:
            print(msg)

def extract_domain_from_hostname(hostname):
    """Extract domain from hostname (e.g., dc.domain.com -> domain.com)."""
    if not hostname:
        return None
    
    # Remove common prefixes
    hostname = str(hostname).lower()
    
    # Common DC/AD server prefixes to strip
    prefixes = ['dc.', 'ad.', 'adfs.', 'exchange.', 'mail.', 'owa.', 'www.', 'ns.', 'dns.', 'ntp.', 'time.']
    
    for prefix in prefixes:
        if hostname.startswith(prefix):
            hostname = hostname[len(prefix):]
            break
    
    # Split by dots and check if it looks like a domain
    parts = hostname.split('.')
    
    # If it looks like a domain (at least 2 parts after stripping prefix)
    if len(parts) >= 2:
        # Check if last part is a common TLD
        common_tlds = ['com', 'net', 'org', 'edu', 'gov', 'mil', 'io', 'htb', 'local', 'lan', 'corp']
        if parts[-1] in common_tlds:
            return hostname
        
        # Check if it has at least 2 parts and doesn't look like an IP
        if not re.match(r'^\d+\.\d+\.\d+\.\d+$', hostname):
            return '.'.join(parts[-2:]) if len(parts) >= 2 else hostname
    
    return None

def get_ntp_server(target_ip, target_hostname):
    """Determine the best NTP server to use."""
    # Priority: 1. User specified, 2. Auto-detected domain, 3. Fallback
    if args.ntp_server:
        return args.ntp_server
    
    if args.auto_domain or args.domain:
        domain = args.domain
        if not domain and args.auto_domain:
            domain = extract_domain_from_hostname(target_hostname)
        
        if domain:
            # Try domain first
            return domain
    
    # Fallback to target IP
    return target_ip

def get_local_time_info():
    try:
        local_now = datetime.now()
        utc_now = datetime.now(timezone.utc)
        
        try:
            result = subprocess.run(['timedatectl', 'status'], 
                                  capture_output=True, text=True, check=False)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                timezone_line = [l for l in lines if 'Time zone' in l]
                if timezone_line:
                    timezone_info = timezone_line[0].split(':')[1].strip()
                else:
                    timezone_info = "Unknown"
            else:
                timezone_info = "Unknown"
        except:
            timezone_info = "Unknown"
        
        offset = utc_now - local_now.replace(tzinfo=timezone.utc)
        offset_hours = offset.total_seconds() / 3600
        
        return {
            'local': local_now,
            'utc': utc_now,
            'timezone': timezone_info,
            'offset_hours': offset_hours
        }
    except Exception as e:
        log(f"[-] Failed to get local time info: {e}")
        return None

def restore_ntp():
    try:
        print("[*] Re-enabling NTP")
        result = subprocess.run(["sudo", "timedatectl", "set-ntp", "on"], 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if result.returncode == 0:
            print("[+] NTP restored successfully")
        else:
            print(f"[-] Failed to restore NTP: {result.stderr.strip()}")
    except Exception as e:
        print(f"[-] Failed to restore NTP: {e}")

def validate_url():
    """Validate and process URL/IP arguments."""
    # Handle IP-only mode
    if not args.url and args.ip:
        url = f"http://{args.ip}"
        hostname = args.ip
        target_ip = args.ip
        print(f"[*] Using IP-only mode with target: {target_ip}")
        return url, hostname, target_ip
    
    # Handle URL with or without IP override
    url = args.url
    if not url.startswith(('http://', 'https://')):
        url = f"http://{url}"
    
    parsed = urlparse(url)
    hostname = parsed.hostname or parsed.path.split(':')[0]
    
    if ':' in hostname:
        hostname = hostname.split(':')[0]
    
    # Use provided IP or resolve DNS
    if args.ip:
        target_ip = args.ip
        print(f"[*] Using provided IP: {target_ip}")
    else:
        try:
            target_ip = socket.gethostbyname(hostname)
            print(f"[*] Resolved IP: {target_ip}")
        except socket.gaierror:
            target_ip = hostname  # Might already be an IP
            print(f"[*] Using hostname as IP (DNS resolution failed): {target_ip}")
    
    return url, hostname, target_ip

def check_port(host, port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except socket.gaierror:
        log(f"[-] DNS resolution failed for {host}")
        return False
    except Exception as e:
        log(f"[-] Port check for {host}:{port} failed: {e}")
        return False

def set_timezone_utc():
    try:
        print("[*] Setting timezone to UTC")
        result = subprocess.run(['sudo', 'timedatectl', 'set-timezone', 'UTC'],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if result.returncode == 0:
            print("[+] Timezone set to UTC")
            return True
        else:
            print(f"[-] Failed to set timezone to UTC: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"[-] Failed to set timezone: {e}")
        return False

def run_ntpdate_sync(ntp_server):
    """Use ntpdate for precise time synchronization."""
    try:
        print(f"[*] Using ntpdate for precise sync with {ntp_server}")
        
        # Disable NTP first
        print("[*] Temporarily disabling NTP...")
        result = subprocess.run(['sudo', 'timedatectl', 'set-ntp', 'off'],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        
        # Run ntpdate
        print(f"[*] Running ntpdate {ntp_server}...")
        result = subprocess.run(['sudo', 'ntpdate', ntp_server],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        
        if result.returncode == 0:
            print(f"[✓] ntpdate sync successful with {ntp_server}")
            if result.stdout.strip():
                print(f"    Output: {result.stdout.strip()}")
            return True
        else:
            print(f"[-] ntpdate failed: {result.stderr.strip()}")
            
            # Try alternative ntp servers if not disabled
            if not args.no_ntpdate_fallback:
                fallback_servers = ['time.google.com', 'time.windows.com', 'pool.ntp.org']
                for server in fallback_servers:
                    print(f"[*] Trying fallback NTP server: {server}")
                    result = subprocess.run(['sudo', 'ntpdate', server],
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                    if result.returncode == 0:
                        print(f"[✓] ntpdate sync successful with {server}")
                        return True
            
            return False
    except Exception as e:
        print(f"[-] ntpdate failed: {e}")
        return False

def auto_ntpdate_sync(ntp_server):
    """Automatically run ntpdate command (disable NTP -> ntpdate -> re-enable NTP)."""
    try:
        print(f"\n[🔧] Running automatic ntpdate sync with {ntp_server}")
        print(f"    Command: sudo timedatectl set-ntp false | sudo ntpdate {ntp_server} | sudo timedatectl set-ntp true")
        
        # Step 1: Disable NTP
        print("[*] Disabling NTP...")
        result1 = subprocess.run(["sudo", "timedatectl", "set-ntp", "false"], 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        
        if result1.returncode != 0:
            print(f"[-] Failed to disable NTP: {result1.stderr.strip()}")
            return False
        
        # Step 2: Run ntpdate
        print(f"[*] Running ntpdate {ntp_server}...")
        result2 = subprocess.run(['sudo', 'ntpdate', ntp_server],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        
        if result2.returncode == 0:
            print(f"[✓] ntpdate sync successful with {ntp_server}")
            if result2.stdout.strip():
                print(f"    Output: {result2.stdout.strip()}")
        else:
            print(f"[-] ntpdate failed: {result2.stderr.strip()}")
            
            # Try fallback servers
            if not args.no_ntpdate_fallback:
                fallback_servers = ['time.google.com', 'time.windows.com', 'pool.ntp.org']
                for server in fallback_servers:
                    print(f"[*] Trying fallback NTP server: {server}")
                    result_fb = subprocess.run(['sudo', 'ntpdate', server],
                                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                    if result_fb.returncode == 0:
                        print(f"[✓] ntpdate sync successful with {server}")
                        result2 = result_fb
                        break
        
        # Step 3: Re-enable NTP
        print("[*] Re-enabling NTP...")
        result3 = subprocess.run(["sudo", "timedatectl", "set-ntp", "true"], 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        
        if result3.returncode != 0:
            print(f"[-] Failed to re-enable NTP: {result3.stderr.strip()}")
        
        # Return success if ntpdate was successful
        return result2.returncode == 0
        
    except Exception as e:
        print(f"[-] Auto ntpdate sync failed: {e}")
        return False

# --- Time Retrieval Functions ---

def get_time_winrm(url, host, ip=None):
    port = 5985
    target = ip if ip else host
    try:
        if not check_port(target, port):
            log(f"[-] Port {port} (WinRM) closed on {target}.")
            return None
        
        log(f"[*] Trying WinRM ({port}) on {target}")
        
        endpoints = ['/wsman', '/wsman/', '']
        
        for endpoint in endpoints:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", InsecureRequestWarning)
                    # Try with IP if provided
                    if ip:
                        r = requests.head(f"http://{ip}:{port}{endpoint}", 
                                        timeout=TIMEOUT, verify=False, allow_redirects=False)
                    else:
                        r = requests.head(f"{url}:{port}{endpoint}", 
                                        timeout=TIMEOUT, verify=False, allow_redirects=False)
                
                if 'Date' in r.headers:
                    date_str = r.headers['Date']
                    try:
                        remote_time = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %Z')
                        return (remote_time, f"WinRM (HTTP Date header) on {target}")
                    except ValueError:
                        try:
                            remote_time = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S GMT')
                            return (remote_time, f"WinRM (HTTP Date header) on {target}")
                        except:
                            continue
            except requests.exceptions.RequestException:
                continue
        
        log(f"[-] WinRM: No valid Date header from {target}")
    except Exception as e:
        log(f"[-] WinRM failed on {target}: {type(e).__name__} - {e}")
    return None

def get_time_smb(host, ip=None):
    port = 445
    target = ip if ip else host
    try:
        if not check_port(target, port):
            log(f"[-] Port {port} (SMB) closed on {target}.")
            return None
            
        log(f"[*] Trying SMB ({port}) on {target}")
        conn = SMBConnection(target, target, sess_port=port, timeout=TIMEOUT)
        server_time = conn.getSMBServer().get_server_time()
        conn.close()
        return (server_time, f"SMB on {target}")
    except Exception as e:
        log(f"[-] SMB failed on {target}: {type(e).__name__} - {e}")
    return None

def get_time_http(url, host, ip=None):
    """Try to get time from HTTP/HTTPS headers."""
    port = 80
    target = ip if ip else host
    try:
        log(f"[*] Trying HTTP ({port}) on {target}")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", InsecureRequestWarning)
            r = requests.head(url, timeout=TIMEOUT, verify=False, allow_redirects=False)
        
        if 'Date' in r.headers:
            date_str = r.headers['Date']
            try:
                remote_time = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %Z')
                return (remote_time, f"HTTP Date header on {target}")
            except ValueError:
                try:
                    remote_time = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S GMT')
                    return (remote_time, f"HTTP Date header on {target}")
                except:
                    pass
    except:
        pass
    
    # Try HTTPS on port 443
    port = 443
    try:
        log(f"[*] Trying HTTPS ({port}) on {target}")
        https_url = url.replace('http://', 'https://')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", InsecureRequestWarning)
            r = requests.head(https_url, timeout=TIMEOUT, verify=False, allow_redirects=False)
        
        if 'Date' in r.headers:
            date_str = r.headers['Date']
            try:
                remote_time = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %Z')
                return (remote_time, f"HTTPS Date header on {target}")
            except ValueError:
                try:
                    remote_time = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S GMT')
                    return (remote_time, f"HTTPS Date header on {target}")
                except:
                    pass
    except:
        pass
    
    return None

def get_remote_time_concurrent(url, host, ip=None):
    tasks = [
        (get_time_winrm, (url, host, ip)),
        (get_time_smb, (host, ip)),
        (get_time_http, (url, host, ip)),
    ]
    
    found_result = None
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_method = {
                executor.submit(func, *args): func.__name__ 
                for func, args in tasks
            }
            
            for future in concurrent.futures.as_completed(future_to_method):
                result = future.result()
                if result:
                    found_result = result
                    log(f"[+] Time found via {result[1]}")
                    for f in future_to_method.keys():
                        if not f.done():
                            f.cancel()
                    break
    
    except KeyboardInterrupt:
        log("\n[-] Interrupted by user")
        raise
    
    return found_result

def calculate_skew(local_time, remote_time):
    if local_time.tzinfo is None:
        local_time = local_time.replace(tzinfo=timezone.utc)
    if remote_time.tzinfo is None:
        remote_time = remote_time.replace(tzinfo=timezone.utc)
    
    skew = abs((remote_time - local_time).total_seconds())
    signed_skew = (remote_time - local_time).total_seconds()
    
    return {
        'absolute_seconds': skew,
        'signed_seconds': signed_skew,
        'within_kerberos_tolerance': skew <= KERBEROS_MAX_SKEW,
        'local_ahead': signed_skew < 0,
        'remote_ahead': signed_skew > 0
    }

def sync_time_manual(remote_time_tuple, ntp_server):
    """Manual time sync using date command."""
    if remote_time_tuple is None:
        return False
    
    remote_time_obj, method = remote_time_tuple
    
    try:
        if remote_time_obj.tzinfo is None:
            remote_time_obj = remote_time_obj.replace(tzinfo=timezone.utc)
        
        remote_utc = remote_time_obj.astimezone(timezone.utc)
        time_str = remote_utc.strftime('%Y-%m-%d %H:%M:%S')
        
        local_info = get_local_time_info()
        if local_info:
            print(f"\n[+] Time Information:")
            print(f"    Local time:    {local_info['local'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    Local UTC:     {local_info['utc'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    Remote time:   {remote_time_obj.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    Remote UTC:    {remote_utc.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    Source:        {method}")
            print(f"    Timezone:      {local_info['timezone']}")
        
        skew_info = calculate_skew(local_info['local'] if local_info else datetime.now(), remote_time_obj)
        print(f"\n[+] Time Difference: {abs(skew_info['signed_seconds']):.2f} seconds")
        
        if skew_info['signed_seconds'] > 0:
            print(f"    Remote is ahead by {skew_info['signed_seconds']:.2f} seconds")
        else:
            print(f"    Local is ahead by {abs(skew_info['signed_seconds']):.2f} seconds")
        
        if skew_info['within_kerberos_tolerance'] and not args.force:
            print(f"[✓] Within Kerberos tolerance ({KERBEROS_MAX_SKEW} seconds)")
            print("[*] No sync needed (use --force to override)")
            return True
        
        if not skew_info['within_kerberos_tolerance']:
            print(f"[!] Exceeds Kerberos tolerance ({KERBEROS_MAX_SKEW} seconds)")
        
        if args.check_skew:
            return True
        
        # Set timezone to UTC if not skipped
        if not args.skip_timezone:
            set_timezone_utc()
        
        # Disable NTP
        print("[*] Disabling NTP for manual time setting...")
        result = subprocess.run(["sudo", "timedatectl", "set-ntp", "off"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        
        # Set time using date command
        print(f"[*] Setting system time to {time_str} UTC...")
        result = subprocess.run(['sudo', 'date', '-u', '-s', time_str],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        
        if result.returncode == 0:
            print("[✓] Time synced successfully!")
            
            # Use ntpdate for final precise sync if requested
            if args.use_ntpdate and ntp_server:
                if run_ntpdate_sync(ntp_server):
                    print("[✓] Final ntpdate sync completed")
                else:
                    print("[-] ntpdate failed, but manual sync was successful")
            
            # Final verification
            ttime.sleep(1)
            new_local = datetime.now(timezone.utc)
            new_skew = calculate_skew(new_local, remote_time_obj)
            
            if new_skew['within_kerberos_tolerance']:
                print("[✓] Verification: Time is now within Kerberos tolerance")
            else:
                print(f"[!] Verification: Still {new_skew['absolute_seconds']:.2f}s difference")
            
            print("\n[*] IMPORTANT: Run with **--restore-ntp** when finished to re-enable automatic sync.")
            return True
        else:
            print(f"[-] Failed to set time: {result.stderr.strip()}")
            return False
            
    except Exception as e:
        print(f"[-] Sync failed: {type(e).__name__} - {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return False

# --- Main Execution ---

def main():
    try:
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    except:
        pass
    
    if args.restore_ntp:
        restore_ntp()
        return
    
    # Modified validation to allow IP-only mode
    if not args.url and not args.ip and not args.restore_ntp:
        parser.error("Either -u/--url or -i/--ip is required unless using --restore-ntp")
    
    if args.check_skew and not args.url and not args.ip:
        parser.error("Either -u/--url or -i/--ip is required with --check-skew")
    
    local_info = get_local_time_info()
    if local_info:
        print(f"[*] Local time: {local_info['local'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    Local UTC:  {local_info['utc'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    Timezone:   {local_info['timezone']}")
        print(f"[*] Kerberos max skew: {KERBEROS_MAX_SKEW} seconds ({KERBEROS_MAX_SKEW/60:.1f} minutes)")
    
    if args.url or args.ip:
        url, hostname, target_ip = validate_url()
        
        # Determine NTP server
        ntp_server = get_ntp_server(target_ip, hostname)
        
        print(f"\n[*] Target: {hostname}")
        print(f"[*] Target IP: {target_ip}")
        print(f"[*] NTP server: {ntp_server}")
        
        if args.auto_domain or args.domain:
            domain = args.domain or extract_domain_from_hostname(hostname)
            if domain:
                print(f"[*] Domain: {domain}")
        
        # Run auto ntpdate sync if requested
        if args.auto_ntpdate:
            print("\n" + "="*60)
            print("[🚀] Starting automatic ntpdate synchronization...")
            print("="*60)
            auto_ntpdate_sync(ntp_server)
            print("="*60)
            print("[✅] Auto ntpdate sync completed")
            print("="*60 + "\n")
            
            # Update local time info after sync
            local_info = get_local_time_info()
            if local_info:
                print(f"[*] Updated local time: {local_info['local'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            result = get_remote_time_concurrent(url, hostname, target_ip)
            
            if result:
                remote_time, method = result
                
                if args.check_skew:
                    skew_info = calculate_skew(
                        local_info['local'] if local_info else datetime.now(),
                        remote_time
                    )
                    
                    print(f"\n[+] Time Skew Analysis:")
                    print(f"    Remote time: {remote_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"    Source:      {method}")
                    print(f"    Difference:  {skew_info['absolute_seconds']:.2f} seconds")
                    
                    if skew_info['signed_seconds'] > 0:
                        print(f"    Remote is ahead by {skew_info['signed_seconds']:.2f} seconds")
                    else:
                        print(f"    Local is ahead by {abs(skew_info['signed_seconds']):.2f} seconds")
                    
                    if skew_info['within_kerberos_tolerance']:
                        print(f"[✓] Within Kerberos tolerance - Kerberos should work")
                    else:
                        print(f"[!] Exceeds Kerberos tolerance - Kerberos will fail")
                        if not args.auto_ntpdate:
                            print(f"[*] Suggested command: {sys.argv[0]} -i {target_ip} --auto-ntpdate")
                        print(f"[*] Or manually: sudo timedatectl set-ntp false && sudo ntpdate {ntp_server} && sudo timedatectl set-ntp true")
                else:
                    success = sync_time_manual(result, ntp_server)
                    if success:
                        print("\n[+] Next steps:")
                        print("    1. Test Kerberos authentication (e.g., nxc smb, getTGT.py, etc.)")
                        print(f"    2. Run '{sys.argv[0]} --restore-ntp' when done")
                        print(f"\n[*] Quick test: nxc smb {hostname} -u USER -p 'PASS' -k")
                    else:
                        print("\n[-] Time sync failed")
                        if ntp_server:
                            print(f"[*] Try auto ntpdate: {sys.argv[0]} -i {target_ip} --auto-ntpdate")
                            print(f"[*] Or manually: sudo timedatectl set-ntp false && sudo ntpdate {ntp_server} && sudo timedatectl set-ntp true")
            else:
                print("\n[-] Failed to fetch remote time from target")
                print(f"[*] Checked on {target_ip}: WinRM (5985), SMB (445), HTTP/HTTPS (80/443)")
                print("\n[*] Alternative methods:")
                print(f"    1. Use auto ntpdate: {sys.argv[0]} -i {target_ip} --auto-ntpdate")
                print(f"    2. Try manual sync: sudo date -u -s '$(curl -sI http://{target_ip} | grep Date | cut -d' ' -f2-)'")
                if not args.ntp_server:
                    print(f"    3. Run with --auto-domain: {sys.argv[0]} -u {hostname} -i {target_ip} --auto-domain --auto-ntpdate")
                
        except KeyboardInterrupt:
            print("\n[-] Operation cancelled")
            sys.exit(1)
        except Exception as e:
            print(f"\n[-] Error: {type(e).__name__} - {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            print(f"\n[*] You can try auto ntpdate:")
            print(f"    {sys.argv[0]} -i {target_ip} --auto-ntpdate")
            print(f"\n[*] Or manually:")
            print(f"    sudo timedatectl set-ntp false && sudo ntpdate {ntp_server} && sudo timedatectl set-ntp true")

if __name__ == "__main__":
    if os.geteuid() != 0 and not args.check_skew and not args.restore_ntp:
        print("[!] Warning: Root privileges required for time sync")
        print("[*] Run with sudo or as root")
        if not args.force:
            ttime.sleep(2)
    
    main()
