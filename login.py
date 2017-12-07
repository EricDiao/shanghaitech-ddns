import requests
import time
import json
import argparse
import sys
import random
import socket
import logging

def getRandomString(n = 32):
    _char = 'abcdefghijklmnopqrstuvwxyz0123456789'.upper()
    return ''.join((_char[random.randint(0, len(_char)-1)] for _ in range(n)))

def wait(sec):
    for i in range(sec):
        time.sleep(1)

class Loginer:

    def __init__(self,username,passwd):
        self.username = username
        self.passwd = passwd
        self.status = False
        self.ip = None

    def login(self):
        url = 'https://controller.shanghaitech.edu.cn:8445/PortalServer/Webauth/webAuthAction!login.action'
        data = {'userName': self.username,
            'password': self.passwd,
            'hasValidateCode': 'false',
            'validCode': '',
            'hasValidateNextUpdatePassword': 'true'}
        header = {'Accept': '*/*',
              'Content-Type': 'application/x-www-form-urlencoded',
              'JSESSIONID': getRandomString(32),
              'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36'}
        obj = requests.post(url, headers=header,data=data)
        if obj.status_code == requests.codes.ok:
            logger.debug('Auth Server returns %s',obj.status_code)
            response = obj.json()
            if response['success'] == True:
                logger.debug("Auth Success...")
                self.ip = response[u'data'][u'ip']
                logger.debug('IP: %s',self.ip)
                self.status = True
            else:
                logger.debug('Auth failed')
                self.status = False
        else:
            logger.debug('Auth Server returns %s',obj.status_code)
            self.status = False

class DNSUpdater:

    def __init__(self,domain,key):
        self.domain = domain
        self.key = key
        self.status = False

    def update(self,ip):
        if self.domain == None:
            return None
        url = 'https://dyn.dns.he.net/nic/update'
        payload = {"hostname": self.domain ,
                    "password":self.key,
                    "myip":ip}
        obj = requests.post(url, data=payload)
        if obj.status_code == requests.codes.ok:
            logger.debug('DDNS Server returns %s',obj.status_code)
            if obj.text == 'good ' + ip:
                logger.debug('Updated, server returns %s',obj.text)
                self.status = True
            elif obj.text[0:5] == 'nochg':
                logger.debug('Wont change, server returns %s',obj.text)
                self.status = True
            else:
                logger.warning('DDNS failed: '+obj.text)
                self.status = False
        else:
            logger.warning('DDNS Server failed...')
            self.status = False

def main(username,passwd,domain,key,interval):
    logger.warning('ShanghiaTech Wirless Network Auth')
    logger.warning('Using username: %s', username)
    if domain != None:
        logger.warning('Updating DNS for domain: %s',domain)
    login = Loginer(username,passwd)
    update = DNSUpdater(domain,key)
    try:
        ip = socket.getaddrinfo(domain,None)[0][4][0]
        logger.debug('Current ip for %s is %s',domain,ip)
    except:
        ip = None
    while True:
        login.login()
        if login.status == True:
            if ip != login.ip:
                ip = login.ip
                update.update(ip)
            else:
                update.status = True
        else:
            logger.warning('Login Failed, retrying for 3 times...')
            for i in range(3):
                login.login()
                if login.status == True:
                    break
                wait(30)
            if login.status == False:
                logger.error('Login failed, exit.')
                exit(-1)
            elif ip != login.ip:
                ip = login.ip
                update.update(ip)
        if update.status == False:
            logger.error('Encountered error when updating DNS, exit.')
            exit(-1)
        wait(interval)

def argvparser():
    global username, passwd, domain, key, deamon,interval
    deamon = False
    interval = 36000
    username = passwd = domain = key = None
    for i in range(len(sys.argv[1:])):
        argv = sys.argv[i+1]
        if argv == '-u':
            username = sys.argv[i+2]
        elif argv == '-p':
            passwd = sys.argv[i+2]
        elif argv == '-k':
            key = sys.argv[i+2]
        elif argv == '-d':
            domain = sys.argv[i+2]
        elif argv == '-i':
            interval = int(sys.argv[i+2])
        elif argv == '-D':
            deamon = True
    for ke in (username,passwd,domain,key):
        if ke == None:
            exit(-1)

if __name__ == '__main__':
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    hdlr = logging.FileHandler('login.log')
    hdlr.setFormatter(formatter)
    logger.addHandler(handler)
    logger.addHandler(hdlr)
    logger.setLevel(logging.DEBUG)
    argvparser()
    #if deamon == True:
    #    logger.warning('Running in background...')
    main(username,passwd,domain,key,interval)
