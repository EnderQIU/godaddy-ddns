#!/usr/bin/env python3
#
# Update GoDaddy DNS "A/AAAA" Record.
#
# usage: godaddy_ddns.py [-h] [--version] [--ip IP] [--key KEY]
#                        [--secret SECRET] [--ttl TTL] [--force]
#                        hostname
#
# positional arguments:
#   hostname         DNS fully-qualified host name with an 'A/AAAA' record.  If the hostname consists of only a domain name
#                    (i.e., it contains only one period), the record for '@' is updated.
#
# optional arguments:
#   -h, --help       show this help message and exit
#   --version        show program's version number and exit
#   --ip IP          DNS Address (defaults to public WAN address from http://ipv4.icanhazip.com/)
#   --type {A,AAAA}  DNS resolve type. A for ipv4 (default), AAAA for ipv6.
#   --key KEY        GoDaddy production key
#   --secret SECRET  GoDaddy production secret
#   --ttl TTL        DNS TTL.
#   --force          force update of GoDaddy DNS record even if DNS query indicates that record is already correct
#
# GoDaddy customers can obtain values for the KEY and SECRET arguments by creating a production key at
# https://developer.godaddy.com/keys/.
#
# Note that command line arguments may be specified in a FILE, one to a line, by instead giving
# the argument "%FILE".  For security reasons, it is particularly recommended to supply the
# KEY and SECRET arguments in such a file, rather than directly on the command line:
#
# Create a file named, e.g., `godaddy-ddns.config` with the content:
#   MY.FULLY.QUALIFIED.HOSTNAME.COM
#   --key
#   MY-KEY-FROM-GODADDY
#   --secret
#   MY-SECRET-FROM-GODADDY
#
# Then just invoke `godaddy-ddns %godaddy-ddns.config`

prog='godaddy-ddns'
version='0.5'
author='Carl Edman (CarlEdman@gmail.com), EnderQIU (a34560824@gmail.com)'

import sys, json, argparse, socket

import requests

parser = argparse.ArgumentParser(description='Update GoDaddy DNS "A/AAAA" Record.', fromfile_prefix_chars='%', epilog= \
'''GoDaddy customers can obtain values for the KEY and SECRET arguments by creating a production key at
https://developer.godaddy.com/keys/.

Note that command line arguments may be specified in a FILE, one to a line, by instead giving
the argument "%FILE".  For security reasons, it is particularly recommended to supply the
KEY and SECRET arguments in such a file, rather than directly on the command line.''')

parser.add_argument('--version', action='version',
  version='{} {}'.format(prog, version))

parser.add_argument('hostname', type=str,
  help='DNS fully-qualified host name with an A or AAAA record.  If the hostname consists of only a domain name (i.e., it contains only one period), the record for @ is updated.')

parser.add_argument('--ip', type=str, default=None,
  help='DNS Address (defaults to public WAN address from https://icanhazip.com/)')

parser.add_argument('--type', type=str, default='A', choices=['A', 'AAAA'],
  help='DNS resolve type. A for ipv4 (default), AAAA for ipv6.')

parser.add_argument('--key', type=str, default='',
  help='GoDaddy production key')

parser.add_argument('--secret', type=str, default='',
  help='GoDaddy production secret')

parser.add_argument('--ttl', type=int, default=3600,
  help='DNS TTL.')

parser.add_argument('--force', type=bool, default=False,
  help='force update of GoDaddy DNS record even if DNS query indicates that record is already correct.')

args = parser.parse_args()

def main():
  hostnames = args.hostname.split('.')
  if len(hostnames)<2:
    msg = 'Hostname "{}" is not a fully-qualified host name of form "HOST.DOMAIN.TOP".'.format(args.hostname)
    raise Exception(msg)
  elif len(hostnames)<3:
    hostnames.insert(0,'@')


  if not args.ip:
    ip_lookup_url = 'https://ipv4.icanhazip.com/'
    if args.type == 'AAAA':
      ip_lookup_url = 'https://ipv6.icanhazip.com/'
    resp = requests.get(ip_lookup_url)
    if not resp.ok:
      msg = 'Unable to automatically obtain IP address from {}.'.format(ip_lookup_url)
      raise Exception(msg)
    else:
      args.ip = resp.text.strip()
      msg = 'Automatically obtained IP address "{}".'.format(args.ip)
      print(msg)
  
  ipslist = args.ip.split(",")
  for ipsiter in ipslist:
    try:
      if args.type == 'A':
        socket.inet_aton(ipsiter)
      elif args.type == 'AAAA':
        socket.inet_pton(socket.AF_INET6, ipsiter)
    except socket.error:
      msg = '"{}" is not a valid {} record.'.format(ipsiter, args.type)
      raise Exception(msg)


  if not args.force and len(ipslist)==1:
    try:
      if args.type == 'A':
        dnsaddr = socket.gethostbyname(args.hostname)
      elif args.type == 'AAAA':
        dnsaddr = socket.getaddrinfo(args.hostname, None, socket.AF_INET6)[0][4][0]
      if ipslist[0] == dnsaddr:
        msg = '"{}" already has IP address "{}".'.format(args.hostname, dnsaddr)
        raise Exception(msg)
    except socket.gaierror:  # [Errno -2] Name or service not known
      pass
    except Exception as e:
      print(e)
      return
             
  url = 'https://api.godaddy.com/v1/domains/{}/records/{}/{}'.format('.'.join(hostnames[1:]), args.type, hostnames[0])
  headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Authorization': 'sso-key {}:{}'.format(args.key,args.secret)
  }
  data = json.dumps([ { "data": ip, "ttl": args.ttl, "name": hostnames[0], "type": args.type } for ip in  ipslist])
  resp = requests.put(url, headers=headers, data=data)

  if resp.ok:
    print('IP address for "{}" set to "{}".'.format(args.hostname,args.ip))
    return

  if resp.status_code==400:
    msg = 'Unable to set IP address: GoDaddy API URL ({}) was malformed.'.format(resp.url)
  elif resp.status_code==401:
    if args.key and args.secret:
      msg = '''Unable to set IP address: --key or --secret option incorrect.
Correct values can be obtained from from https://developer.godaddy.com/keys/ and are ideally placed in a % file.'''
    else:
      msg = '''Unable to set IP address: --key or --secret option missing.
Correct values can be obtained from from https://developer.godaddy.com/keys/ and are ideally placed in a % file.'''
  elif resp.status_code==403:
    msg = '''Unable to set IP address: customer identified by --key and --secret options denied permission.
Correct values can be obtained from from https://developer.godaddy.com/keys/ and are ideally placed in a % file.'''
  elif resp.status_code==404:
    msg = 'Unable to set IP address: {} not found at GoDaddy.'.format(args.hostname)
  elif resp.status_code==422:
    msg = 'Unable to set IP address: "{}" has invalid domain or lacks A record.'.format(args.hostname)
  elif resp.status_code==429:
    msg = 'Unable to set IP address: too many requests to GoDaddy within brief period.'
  elif resp.status_code==503:
    msg = 'Unable to set IP address: "{}" is unavailable.'.format(args.hostname)
  else:
    msg = 'Unable to set IP address: GoDaddy API failure because "{}".'.format(resp.status_code)
  raise Exception(msg)


if __name__ == '__main__':
  main()
