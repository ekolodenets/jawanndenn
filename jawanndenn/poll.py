# Copyright (C) 2016 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import cPickle as pickle
import hashlib
import logging
import os

from threading import Lock

from jawanndenn.markup import safe_html


_MAX_POLLS = 100
_MAX_VOTERS_PER_POLL = 40

_KEY_OPTIONS = 'options'
_KEY_TITLE = 'title'

_PICKLE_PROTOCOL_VERSION = 2

_PICKLE_CONTENT_VERSION = 1
_PICKLE_POLL_VERSION = 1
_PICKLE_POLL_DATABASE_VERSION = 1


_log = logging.getLogger(__name__)


def _get_random_sha256():
    return hashlib.sha256(os.urandom(256 / 8)).hexdigest()


class _Poll(object):
    def __init__(self):
        self.config = []
        self.votes = []
        self._lock = Lock()
        self._version = _PICKLE_POLL_VERSION

    def __getstate__(self):
        d = self.__dict__.copy()
        del d['_lock']
        return d

    def __setstate__(self, d):
        self.__dict__.update(d)
        self._lock = Lock()

    @staticmethod
    def from_config(config):
        poll = _Poll()

        if _KEY_OPTIONS not in config \
                or _KEY_TITLE not in config:
            raise ValueError('Malformed configuration: %s' % config)

        poll.config = {
            _KEY_TITLE: safe_html(config[_KEY_TITLE]),
            _KEY_OPTIONS: map(safe_html, config[_KEY_OPTIONS]),
        }
        return poll

    @property
    def options(self):
        return self.config[_KEY_OPTIONS]

    def vote(self, person, votes):
        with self._lock:
            if len(self.votes) >= _MAX_VOTERS_PER_POLL:
                raise ValueError('Too many votes per poll')
            if len(votes) != len(self.options):
                raise ValueError('Malformed vote')
            self.votes.append((person, votes))


class PollDatabase(object):
    def __init__(self):
        self._db = {}
        self._db_lock = Lock()
        self._version = _PICKLE_POLL_DATABASE_VERSION

    def __getstate__(self):
        d = self.__dict__.copy()
        del d['_db_lock']
        return d

    def __setstate__(self, d):
        self.__dict__.update(d)
        self._db_lock = Lock()

    def add(self, config):
        poll = _Poll.from_config(config)
        poll_id = _get_random_sha256()

        with self._db_lock:
            if len(self._db) >= _MAX_POLLS:
                raise ValueError('Too many polls')
            if poll_id in self._db:
                raise ValueError('ID collision: %s' % poll_id)
            self._db[poll_id] = poll

        return poll_id

    def get(self, poll_id):
        with self._db_lock:
            return self._db[poll_id]

    def load(self, filename):
        with open(filename, 'rb') as f:
            d = pickle.load(f)

        if d['version'] != _PICKLE_CONTENT_VERSION:
            raise ValueError('Content version mismatch')

        self.__dict__.update(d['data'].__dict__)
        _log.info('%d polls loaded.' % len(self._db))

    def save(self, filename):
        d = {
            'version': _PICKLE_CONTENT_VERSION,
            'data': self,
        }
        with open(filename, 'w') as f:
            pickle.dump(d, f, _PICKLE_PROTOCOL_VERSION)
        _log.info('%d polls saved.' % len(self._db))