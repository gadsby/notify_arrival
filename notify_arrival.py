#!/usr/bin/env python3

import re
import json
import time
import shlex
import argparse
import subprocess
import pandas as pd

def parse_args():
    parser = argparse.ArgumentParser(description='Notify when someone connects to network.')
    parser.add_argument('-n', '--name_file', required=True, type=str, help='JSON file containing MAC address and name key value pairs.')
    parser.add_argument('-d', '--delay', default=10, type=int, help='Delay between arp lookups. Longer means less responsive.')
    parser.add_argument('-i', '--ipv4_address', required=True, type=str, help='IPv4 address with \'x\' in place of range.')
    return parser.parse_args()

def mac_lookup(ip, ip_dict):
    """ Takes a series or ip and returns the mac address on that ip, or 'None'
        Can be used in an apply on a dataframe"""
    if isinstance(ip, pd.core.series.Series):
        ip = ip['ip_address']
    try:
        return ip_dict[ip]
    except KeyError:
        return 'None'

def name_lookup_init(series, name_file):
    """ Loads name lookup table from file, then attempts to connect mac addresses to a name """
    name_dict = load_name_lookup(name_file)
    return name_lookup(series['mac_address'], name_dict)

def name_lookup(mac, name_dict):
    try:
        return name_dict[mac.lower()]
    except KeyError:
        return 'Not Found'

def load_name_lookup(name_file):
    """Opening file every time allows for hot updating"""
    try:
        with open(name_file, 'r') as f_in:
            name_dict = json.loads(f_in.read())
    except IOError:
        subprocess.call(shlex.split('terminal-notifier -message "Configuration file could ' + 
            'not be found. Program will now close." -title "Error!"'))
        subprocess.call(shlex.split('say -v Daniel "My configuration file is missing! Goodbye."'))
        exit()
    except json.decoder.JSONDecodeError:
        subprocess.call(shlex.split('terminal-notifier -message "Improper configuration ' +
            'file formatting has forced program to close." -title "Error!"'))
        subprocess.call(shlex.split('say -v Daniel "My configuration file is badly formatted! Goodbye."'))
        exit()

    name_dict = {key.lower(): name_dict[key] for key in name_dict.keys()}
    return name_dict

def clean_ip_mac_dict(ip_mac_dict):
    for key in ip_mac_dict.keys():
        mac_address = ip_mac_dict[key]
        tokenize = mac_address.split(':')
        add_zeroes = ['0'*(2-len(token))+token for token in tokenize]
        mac_address = ':'.join(add_zeroes)
        ip_mac_dict[key] = mac_address
    return ip_mac_dict

def check_arp(ipv4_address_with_mask):
    arp_output = subprocess.check_output(shlex.split('arp -a')).decode()
    arp_lines = arp_output.split('\n')
    
    ip_mac_dict = {}
    mac_re = '(([0-9A-Fa-f]{1,2}:){5}([0-9A-Fa-f]{1,2}))'
    ip_re = ipv4_address_with_mask.replace('x', '\d{1,3}')
    total_re = re.compile('.*\((' + ip_re + ')\).* ' + mac_re + ' .*')

    for line in arp_lines:
        match = total_re.search(line)
        if match is not None:
            ip_mac_dict[match.group(1)] = match.group(2)
                        
    return clean_ip_mac_dict(ip_mac_dict)

def update_row(series, name_dict, ip_dict, names_now):
    new_mac = mac_lookup(series['ip_address'], ip_dict)
    new_name = name_lookup(new_mac, name_dict)
    if new_name not in names_now:
        notify_arrival(new_name)
    series['mac_address'] = new_mac
    series['name'] = new_name
    return series

def notify_arrival(name):
    subprocess.call(shlex.split('say -v Daniel "Someone is here"'))
    subprocess.call(shlex.split('terminal-notifier -message "It\'s {}" -title "Someone\'s Here!"'.format(name)))


if __name__ == "__main__":

    args = parse_args()

    name_file = args.name_file
    ipv4_address_with_mask = args.ipv4_address
    DELAY=args.delay

    ip_list = [ipv4_address_with_mask.replace('x', str(i)) for i in range(255)]
    ip_dict = check_arp(ipv4_address_with_mask)

    df = pd.DataFrame(ip_list, columns=['ip_address'])
    df['mac_address'] = df.apply(lambda series: mac_lookup(series, ip_dict), axis=1)
    df['name'] = df.apply(lambda series: name_lookup_init(series, name_file), axis=1)

    time.sleep(DELAY)


    while True:

        name_dict = load_name_lookup(name_file)
        ip_dict = check_arp(ipv4_address_with_mask)
        names_now = set(df.name)

        df.apply(lambda series: update_row(series, name_dict, ip_dict, names_now), axis=1)

        time.sleep(DELAY)
