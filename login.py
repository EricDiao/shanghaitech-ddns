#!/usr/bin/python3

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
        self.sessionID = None
        self.token = None

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
            logger.info('Auth Server returns %s',obj.status_code)
            response = obj.json()
            if response['success'] == True:
                logger.info("Auth Success...")
                self.ip = response[u'data'][u'ip']
                logger.info('IP: %s',self.ip)
                self.sessionID = response['data']['sessionId']
                self.token = response['token'][6:]
                self.status = True
            else:
                logger.info('Auth failed')
                self.status = False
        else:
            logger.info('Auth Server returns %s',obj.status_code)
            self.status = False

    def sync(self):
        url = 'https://controller.shanghaitech.edu.cn:8445/PortalServer/Webauth/webAuthAction!syncPortalAuthResult.action'
        data = {'clientIp': self.ip,
            'browserFlag': 'zh'}
        header = {'Accept': '*/*',
              'Content-Type': 'application/x-www-form-urlencoded',
              'JSESSIONID': getRandomString(32),
              'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36',
              'X-Requested-With': 'XMLHttpRequest',
              'X-XSRF-TOKEN': self.token,
              'Cookie': 'JSESSIONID='+self.sessionID+'; '+'XSRF_TOKEN='+self.token}
        for i in range(30):
            obj = requests.post(url, headers=header,data=data)
            if obj.status_code == requests.codes.ok:
                logger.info('Sync Server returns %s', obj.status_code)
                response = obj.json()
                status = response['data']['portalAuthStatus']
                if status == 0:
                    logger.info('Waiting...')
                elif status == 1:
                    logger.info('Connected.')
                    break
                elif status == 2:
                    logger.warning('Auth Failed!')
                    self.status = False
                    break
                else:
                    self.status = False
                    errorcode = response['data']['portalErrorCode']
                    if errorcode == 5:
                        logger.error('Exceed maximum device capacity!')
                    elif errorcode == 101:
                        logger.error('Passcode error!')
                    elif errorcode == 8000:
                        logger.warning('Radius relay auth failed, errorcode = %s', errorcode - 8000)
                    else:
                        logger.warning('Auth Failed!')
                        break
            else:
                logger.info('Sync Server returns %s',obj.status_code)
                self.status = False
            wait(3)

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
            logger.info('DDNS Server returns %s',obj.status_code)
            if obj.text == 'good ' + ip:
                logger.info('Updated, server returns %s',obj.text)
                self.status = True
            elif obj.text[0:5] == 'nochg':
                logger.info('Wont change, server returns %s',obj.text)
                self.status = True
            else:
                logger.warning('DDNS failed: '+obj.text)
                self.status = False
        else:
            logger.warning('DDNS Server failed...')
            self.status = False

def main(username,passwd,domain,key,interval):
    ip = None
    logger.warning('ShanghiaTech Wirless Network Auth')
    logger.warning('Using username: %s', username)
    if domain != None:
        logger.warning('Updating DNS for domain: %s',domain)
    logger.warning('Waiting time: %s s',interval)
    login = Loginer(username,passwd)
    update = DNSUpdater(domain,key)
    if domain != None:
        try:
            ip = socket.getaddrinfo(domain,None)[0][4][0]
            logger.info('Current IP for %s is %s',domain,ip)
        except:
            ip = None
            logger.warning('Failed to fetch IP for %s',domain)
    while True:
        if disconnected():
            login.login()
            login.sync()
            if login.status == True:
                if domain != None and ip != login.ip:
                    ip = login.ip
                    update.update(ip)
                elif ip != None:
                    logger.info('Dont need to update...')
                    update.status = True
            else:
                logger.warning('Login Failed, retrying for 3 times...')
                for i in range(3):
                    login.login()
                    login.sync()
                    if login.status == True:
                        break
                    wait(30)
                if login.status == False:
                    logger.error('Login failed, exit.')
                    exit(-1)
                elif ip != login.ip and domain != None:
                    ip = login.ip
                    update.update(ip)
            if domain != None:
                if update.status == False:
                    logger.error('Encountered error when updating DNS, exit.')
                    exit(-1)
        logger.debug('Sleep %s s...',interval)
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
    for ke in (username,passwd):
        if ke == None:
            exit(-1)

def disconnected(host="http://www.v2ex.com/generate_204"):
    r = requests.get(host)
    if r.status_code != 204:
        logger.warning('Disconnected %s',r.status_code)
        return True
    return False

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
    logger.setLevel(logging.INFO)
    argvparser()
    #if deamon == True:
    #    logger.warning('Running in background...')
    main(username,passwd,domain,key,interval)
