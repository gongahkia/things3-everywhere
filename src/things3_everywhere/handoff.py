"""Bounded process-local snapshots for human edits; no mutation dispatch."""

from copy import deepcopy
from secrets import token_urlsafe, token_hex
from hashlib import sha256
import re
from threading import RLock
from time import monotonic

from .adapter import parse_task
from .errors import BridgeError
from . import validation as v


class Handoffs:
    TTL = 900
    CAPACITY = 32
    TOMBSTONE_CAPACITY = 128
    FIELDS = ('title', 'notes', 'tags', 'deadline', 'status')

    def __init__(self, adapter, *, clock=monotonic):
        self.adapter = adapter
        self.clock = clock
        self._sessions = {}
        self.instance_id = token_hex(16)
        self._tombstones = {}
        self._lock = RLock()

    def _read(self, id):
        task = self.adapter.get_handoff_task(id)
        if task.id != id:
            raise BridgeError('INVALID_RESPONSE', 'Things returned a different task ID.')
        checked = parse_task([task.id, task.title, task.notes, task.status, task.tags, task.deadline])
        return {key: deepcopy(getattr(checked, key)) for key in self.FIELDS}

    def _retire(self, token, reason):
        self._sessions.pop(token, None)
        key = sha256(token.encode('ascii')).hexdigest()
        self._tombstones.pop(key, None)
        self._tombstones[key] = (reason, self.clock() + self.TTL)
        while len(self._tombstones) > self.TOMBSTONE_CAPACITY:
            del self._tombstones[next(iter(self._tombstones))]

    def _expire(self):
        now = self.clock()
        for key, (_, expires) in list(self._tombstones.items()):
            if now >= expires:
                del self._tombstones[key]
        for token, session in list(self._sessions.items()):
            if now >= session['expires']:
                self._retire(token, 'SESSION_EXPIRED')

    def _session(self, session_id):
        self._expire()
        if not isinstance(session_id, str) or not re.fullmatch(
                r'h1\.[0-9a-f]{32}\.[A-Za-z0-9_-]{32}', session_id):
            return None, 'SESSION_HANDLE_INVALID'
        if session_id.split('.')[1] != self.instance_id:
            # this identifies a namespace mismatch, not proof of prior issuance or restart.
            return None, 'SESSION_INSTANCE_MISMATCH'
        session = self._sessions.get(session_id)
        if session is not None:
            return session, None
        key = sha256(session_id.encode('ascii')).hexdigest()
        return None, self._tombstones.get(key, ('SESSION_UNKNOWN', None))[0]

    @staticmethod
    def _equal(before, after, key):
        return set(before[key]) == set(after[key]) if key == 'tags' else before[key] == after[key]

    @staticmethod
    def _result(outcome, reason=None, **details):
        return {'outcome': outcome, 'reason': reason, 'mutated': False, **details}

    @staticmethod
    def _failure(error):
        # Do not forward arbitrary adapter exception messages or error codes.
        code = error.code if isinstance(error, BridgeError) else 'INTERNAL_ERROR'
        allowed = {'NOT_FOUND', 'PERMISSION_DENIED', 'TIMEOUT', 'APP_UNAVAILABLE',
                   'INVALID_RESPONSE', 'ITEM_KIND_UNSUPPORTED', 'SCRIPT_FAILED'}
        return Handoffs._result('unavailable', code if code in allowed else 'READ_FAILED')

    def prepare(self, id, operation, value=None):
        id = v.task_id(id)
        mapping = {'rename': 'title', 'replace_notes': 'notes', 'change_deadline': 'deadline'}
        if operation == 'complete':
            if value is not None:
                v.invalid('Completion takes no replacement value.')
            field, value = 'status', 'completed'
        elif isinstance(operation, str) and operation in mapping:
            field = mapping[operation]
            value = v.fields({field: value})[field]
        else:
            v.invalid('Unsupported manual proposal operation.')
        with self._lock:
            self._expire()
            if len(self._sessions) >= self.CAPACITY:
                raise BridgeError('HANDOFF_LIMIT', 'Too many active handoffs; wait for expiration.')
            try:
                before = self._read(id)
            except Exception as error:
                return self._failure(error)
            token = 'h1.' + self.instance_id + '.' + token_urlsafe(24)
            self._sessions[token] = {'id': id, 'before': before, 'field': field,
                                     'value': value, 'expires': self.clock() + self.TTL,
                                     'reveal_attempted': False}
            return self._result('prepared', session_id=token, expires_in_seconds=self.TTL,
                                operation=operation, proposed={field: value},
                                already_matches=before[field] == value,
                                recurrence='unknown', automatic_execution=False)

    def reveal(self, session_id):
        with self._lock:
            session, reason = self._session(session_id)
            if session is None:
                return self._result('inconclusive', reason)
            if session['reveal_attempted']:
                return self._result('inconclusive', 'REVEAL_ALREADY_ATTEMPTED')
            session['reveal_attempted'] = True
            try:
                after = self._read(session['id'])
                if any(not self._equal(session['before'], after, key) for key in self.FIELDS):
                    self._retire(session_id, 'STATE_CHANGED_BEFORE_REVEAL')
                    return self._result('inconclusive', 'STATE_CHANGED_BEFORE_REVEAL')
                if self.clock() >= session['expires']:
                    self._retire(session_id, 'SESSION_EXPIRED')
                    return self._result('inconclusive', 'SESSION_EXPIRED')
                returned_id = self.adapter.reveal_task(session['id'])
                if returned_id != session['id']:
                    raise BridgeError('INVALID_RESPONSE', 'Reveal returned a different task ID.')
            except Exception as error:
                return self._failure(error)
            return self._result('revealed', 'MANUAL_EDIT_REQUIRED')

    def verify(self, session_id):
        with self._lock:
            session, reason = self._session(session_id)
            if session is None:
                return self._result('inconclusive', reason)
            # Consume on every verification attempt, including failed reads.
            self._retire(session_id, 'SESSION_CONSUMED')
            try:
                after = self._read(session['id'])
            except Exception as error:
                return self._failure(error)
            if self.clock() >= session['expires']:
                self._retire(session_id, 'SESSION_EXPIRED')
                return self._result('inconclusive', 'SESSION_EXPIRED')
            field = session['field']
            def equal(key):
                return self._equal(session['before'], after, key)
            changed = [key for key in self.FIELDS if not equal(key)]
            extra = [key for key in changed if key != field]
            matched = after[field] == session['value']
            outcome = 'verified' if matched and not extra else 'mismatched'
            reason = None
            if matched and session['before'][field] == session['value'] and not extra:
                outcome, reason = 'inconclusive', 'ALREADY_MATCHED_BEFORE'
            return self._result(outcome, reason, expected_change_observed=matched and field in changed,
                                changed_fields=changed, unexpected_fields=extra,
                                compared_fields=list(self.FIELDS))
