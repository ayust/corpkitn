from collections import defaultdict
import logging
import re

from kitnirc.modular import Module


_log = logging.getLogger(__name__)


class NickToAccountModule(Module):
    """A KitnIRC module which provides nick->account translation.

    It listens for the NICK_TO_ACCOUNT event, and eventually generates
    a new event based on either cached info or a NickServ response.
    """

    def __init__(self, *args, **kwargs):
        super(NickToAccountModule, self).__init__(*args, **kwargs)
        self.cached_accounts = {}
        self.pending_requests = defaultdict(list)
        self.nickserv = "NickServ@services.foonetic.net"

    @Module.handle("NICK_TO_ACCOUNT")
    def account_request(self, client, nick, next_event, args):
        self.pending_requests[nick].append((next_event, args))

        account = self.cached_accounts.get(nick.lower())
        if account:
            self.dispatch(nick, account)
        else:
            client.msg(self.nickserv, "ACC %s *" % nick)

    @Module.handle("NOTICE")
    def notice(self, client, actor, recipient, message):
        if recipient != self.controller.client.user:
            return
        if actor != self.nickserv:
            return
        m = re.match(r"(\S+) -> (\S+) ACC (\d)", message)
        if not m:
            return
        nick, account, access = m.groups()
        account = account.lower()
        if access == '3':
            _log.debug("Nick %s is logged in as %s", nick, account)
            self.cached_accounts[nick.lower()] = account
            self.dispatch(nick, account)
        else:
            _log.debug("Nick %s is not logged in", nick)
            self.dispatch(nick, None)

    @Module.handle("QUIT")
    def nickquit(self, client, actor, message):
        self.cached_accounts.pop(actor.nick.lower(), None)

    @Module.handle("PART")
    def nickpart(self, client, actor, channel, message):
        self.cached_accounts.pop(actor.nick.lower(), None)

    @Module.handle("KICK")
    def nickkick(self, client, actor, target, channel, message):
        self.cached_accounts.pop(target.nick.lower(), None)

    @Module.handle("NICK")
    def renick(self, client, oldnick, newnick):
        oldacct = self.cached_accounts.pop(oldnick.lower(), None)
        if oldacct is not None:
            self.cached_accounts[newnick.lower()] = oldacct

    def dispatch(self, nick, account):
        requests = self.pending_requests.pop(nick, [])
        for next_event, args in requests:
            self.controller.client.dispatch_event(
                next_event, nick, account, args)


module = NickToAccountModule

# vim: set ts=4 sts=4 sw=4 et:
