# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_stevenblackhosts
# Purpose:     Check if a domain is malicious (malware or adware) according to
#              Steven Black Hosts block list.
#
# Author:      <bcoles@gmail.com>
#
# Created:     2021-08-30
# Copyright:   (c) bcoles 2021
# Licence:     GPL
# -------------------------------------------------------------------------------

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_stevenblack_hosts(SpiderFootPlugin):

    meta = {
        'name': "Steven Black Hosts",
        'summary': "Check if a domain is malicious (malware or adware) according to Steven Black Hosts list.",
        'flags': [],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'website': "https://github.com/StevenBlack/hosts",
            'model': "FREE_NOAUTH_UNLIMITED",
            'description': "Consolidating and extending hosts files (for malware and adware)"
            "from several well-curated sources."
        }
    }

    opts = {
        'checkaffiliates': True,
        'checkcohosts': True,
        'cacheperiod': 24
    }

    optdescs = {
        'checkaffiliates': "Apply checks to affiliates?",
        'checkcohosts': "Apply checks to sites found to be co-hosted on the target's IP?",
        'cacheperiod': "Hours to cache list data before re-fetching."
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.errorState = False

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return [
            "INTERNET_NAME",
            "AFFILIATE_INTERNET_NAME",
            "CO_HOSTED_SITE"
        ]

    # What events this module produces
    def producedEvents(self):
        return [
            "MALICIOUS_INTERNET_NAME",
            "MALICIOUS_AFFILIATE_INTERNET_NAME",
            "MALICIOUS_COHOST"
        ]

    def queryBlocklist(self, target):
        blocklist = self.retrieveBlocklist()

        if not blocklist:
            return False

        if target.lower() in blocklist:
            self.sf.debug(f"Host name {target} found in Steven Black Hosts block list.")
            return True

        return False

    def retrieveBlocklist(self):
        blocklist = self.sf.cacheGet('stevenblack_hosts', 24)

        if blocklist is not None:
            return self.parseBlocklist(blocklist)

        url = "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts"
        res = self.sf.fetchUrl(
            url,
            timeout=self.opts['_fetchtimeout'],
            useragent=self.opts['_useragent'],
        )

        if res['code'] != "200":
            self.sf.error(f"Unexpected HTTP response code {res['code']} from {url}")
            self.errorState = True
            return None

        if res['content'] is None:
            self.sf.error(f"Received no content from {url}")
            self.errorState = True
            return None

        self.sf.cachePut("stevenblack_hosts", res['content'])

        return self.parseBlocklist(res['content'])

    def parseBlocklist(self, blocklist):
        """Parse plaintext block list

        Args:
            blocklist (str): plaintext Steven Black Hosts block list

        Returns:
            list: list of blocked host names
        """
        hosts = list()

        if not blocklist:
            return hosts

        for line in blocklist.split('\n'):
            if not line:
                continue
            if line.startswith('#'):
                continue
            host = line.strip().split(" ")[1]
            # Note: Validation with sf.validHost() is too slow to use here
            # if not self.sf.validHost(host, self.opts['_internettlds']):
            #    continue
            if not host:
                continue
            hosts.append(host.lower())

        return hosts

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.sf.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventData in self.results:
            self.sf.debug(f"Skipping {eventData}, already checked.")
            return

        if self.errorState:
            return

        self.results[eventData] = True

        if eventName == "INTERNET_NAME":
            evtType = "MALICIOUS_INTERNET_NAME"
        elif eventName == 'AFFILIATE_INTERNET_NAME':
            if not self.opts.get('checkaffiliates', False):
                return
            evtType = 'MALICIOUS_AFFILIATE_INTERNET_NAME'
        elif eventName == 'CO_HOSTED_SITE':
            if not self.opts.get('checkcohosts', False):
                return
            evtType = 'MALICIOUS_COHOST'
        else:
            return

        self.sf.debug(f"Checking maliciousness of {eventData} ({eventName}) with Steven Black Hosts blocklist")

        if self.queryBlocklist(eventData):
            url = "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts"
            text = f"Steven Black Hosts Blocklist [{eventData}]\n<SFURL>{url}</SFURL>"
            evt = SpiderFootEvent(evtType, text, self.__name__, event)
            self.notifyListeners(evt)

# End of sfp_stevenblack_hosts class
