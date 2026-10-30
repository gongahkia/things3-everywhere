from copy import deepcopy
from dataclasses import replace
import json
import subprocess
import sys
import unittest
from unittest.mock import Mock

from things3_everywhere.adapter import ThingsAppleScriptAdapter
from things3_everywhere.errors import BridgeError
from things3_everywhere.handoff import Handoffs
from things3_everywhere.safety import WritePolicy
from things3_everywhere.service import ThingsService
from things3_everywhere.tools import dispatch
from things3_everywhere.transport import AppleScriptTransport, SCRIPT
from test_service import sample


class ManualAdapter:
    def __init__(self):
        self.tasks = {id: sample(id, recurrence='unknown') for id in ('synthetic-a', 'synthetic-b')}
        self.reads, self.shown = [], []
        self.failure = None

    def get_handoff_task(self, id):
        self.reads.append(id)
        if self.failure:
            raise self.failure
        if id not in self.tasks:
            raise BridgeError('NOT_FOUND', 'Missing synthetic task.')
        return deepcopy(self.tasks[id])

    def reveal_task(self, id):
        self.shown.append(id)
        return id

    def forbidden(self, *args, **kwargs):
        raise AssertionError('Mutation dispatch forbidden')

    create_task = update_task = complete_task = forbidden


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.adapter = ManualAdapter()
        self.service = ThingsService(self.adapter)
        self.now = 0
        self.service.handoffs.clock = lambda: self.now

    def prepare(self, operation='rename', value='New'):
        return self.service.prepare_manual_change('synthetic-a', operation, value)['session_id']

    def test_explicit_reveal_duplicate_titles_and_one_attempt(self):
        token = self.prepare()
        self.assertEqual(self.adapter.shown, [])
        self.assertEqual(self.service.reveal_manual_change(token)['outcome'], 'revealed')
        self.assertEqual(self.adapter.shown, ['synthetic-a'])
        self.assertEqual(self.service.reveal_manual_change(token)['outcome'], 'inconclusive')
        self.assertEqual(self.service.verify_manual_change(token)['outcome'], 'mismatched')
        self.assertEqual(self.adapter.tasks['synthetic-b'].title, 'Duplicate title')

    def test_all_operations_and_snapshot_consumption(self):
        for operation, field, value in [('rename', 'title', 'New'), ('replace_notes', 'notes', ''),
                                         ('change_deadline', 'deadline', '2032-02-29'),
                                         ('complete', 'status', 'completed')]:
            with self.subTest(operation=operation):
                token = self.prepare(operation, None if operation == 'complete' else value)
                self.adapter.tasks['synthetic-a'] = replace(self.adapter.tasks['synthetic-a'], **{field: value})
                result = self.service.verify_manual_change(token)
                self.assertEqual(result['outcome'], 'verified')
                self.assertEqual(result['changed_fields'], [field])
                self.assertEqual(self.service.verify_manual_change(token)['outcome'], 'inconclusive')

    def test_extra_changes_are_reported_without_personal_values(self):
        token = self.prepare()
        self.adapter.tasks['synthetic-a'] = replace(self.adapter.tasks['synthetic-a'], title='New', notes='PRIVATE_EXTRA')
        result = self.service.verify_manual_change(token)
        self.assertEqual(result['outcome'], 'mismatched')
        self.assertTrue(result['expected_change_observed'])
        self.assertEqual(result['unexpected_fields'], ['notes'])
        self.assertNotIn('PRIVATE_EXTRA', json.dumps(result))

    def test_noop_is_inconclusive(self):
        token = self.prepare(value='Duplicate title')
        self.assertEqual(self.service.verify_manual_change(token)['reason'], 'ALREADY_MATCHED_BEFORE')

    def test_expiration_restart_capacity_and_no_reconstruction(self):
        token = self.prepare()
        self.assertEqual(ThingsService(self.adapter).verify_manual_change(token)['outcome'], 'inconclusive')
        self.now = Handoffs.TTL
        self.assertEqual(self.service.reveal_manual_change(token)['reason'], 'SESSION_EXPIRED')
        self.assertEqual(self.service.handoffs._sessions, {})
        for _ in range(Handoffs.CAPACITY):
            self.prepare()
        with self.assertRaises(BridgeError) as caught:
            self.prepare()
        self.assertEqual(caught.exception.code, 'HANDOFF_LIMIT')

    def test_missing_logbook_id_and_read_failures_never_claim_success(self):
        for code in ('NOT_FOUND', 'TIMEOUT', 'PERMISSION_DENIED', 'ITEM_KIND_UNSUPPORTED', 'INVALID_RESPONSE'):
            self.adapter.failure = None
            token = self.prepare('complete', None)
            self.adapter.failure = BridgeError(code, 'PRIVATE_FAILURE')
            result = self.service.verify_manual_change(token)
            self.assertEqual(result['outcome'], 'unavailable')
            self.assertNotIn('PRIVATE_FAILURE', json.dumps(result))
        self.adapter.failure = None
        token = self.prepare()
        self.adapter.failure = RuntimeError('PRIVATE_FAILURE')
        self.assertNotIn('PRIVATE_FAILURE', json.dumps(self.service.verify_manual_change(token)))

    def test_mismatched_id_and_stale_reveal(self):
        token = self.prepare()
        self.adapter.tasks['synthetic-a'] = replace(self.adapter.tasks['synthetic-a'], id='synthetic-other')
        self.assertEqual(self.service.verify_manual_change(token)['reason'], 'INVALID_RESPONSE')
        self.adapter.tasks['synthetic-a'] = sample('synthetic-a')
        token = self.prepare()
        self.adapter.tasks['synthetic-a'] = replace(self.adapter.tasks['synthetic-a'], notes='Changed')
        self.assertEqual(self.service.reveal_manual_change(token)['reason'], 'STATE_CHANGED_BEFORE_REVEAL')
        self.assertEqual(self.adapter.shown, [])

    def test_reveal_failure_and_receipt_are_not_retried(self):
        for result in ('synthetic-other', BridgeError('TIMEOUT', 'PRIVATE_FAILURE')):
            token = self.prepare()
            self.adapter.reveal_task = Mock(side_effect=result if isinstance(result, Exception) else None,
                                            return_value=result)
            self.assertEqual(self.service.reveal_manual_change(token)['outcome'], 'unavailable')
            self.service.reveal_manual_change(token)
            self.adapter.reveal_task.assert_called_once()

    def test_validation_and_no_assertion_bypass(self):
        for args in ({'id': 'bad id', 'operation': 'rename', 'value': 'New'},
                     {'id': 'synthetic-a', 'operation': 'script', 'value': 'PRIVATE'},
                     {'id': 'synthetic-a', 'operation': 'complete', 'value': 'PRIVATE'},
                     {'id': 'synthetic-a', 'operation': 'rename', 'value': ' '},
                     {'id': 'synthetic-a', 'operation': 'change_deadline', 'value': '2031-02-29'},
                     {'id': 'synthetic-a', 'operation': 'rename', 'value': 'New', 'recurrence': 'none'}):
            result, failed = dispatch(self.service, 'things_prepare_manual_change', args)
            self.assertTrue(failed)
            self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertEqual(self.adapter.reads, [])

    def test_repeating_unknown_and_both_policies_are_manual_only(self):
        for enabled in (False, True):
            for recurrence in ('unknown', 'repeating', 'none'):
                self.service = ThingsService(self.adapter, WritePolicy(enabled))
                self.adapter.tasks['synthetic-a'] = sample('synthetic-a', recurrence=recurrence)
                token = self.prepare()
                self.assertEqual(self.service.reveal_manual_change(token)['outcome'], 'revealed')
                self.assertEqual(self.service.verify_manual_change(token)['outcome'], 'mismatched')
                live = ThingsAppleScriptAdapter(WritePolicy(enabled), transport=Mock())
                for operation in (lambda: live.update_task('synthetic-a', {'title': 'New'}, execution='execute'),
                                  lambda: live.complete_task('synthetic-a', execution='execute')):
                    with self.assertRaises(BridgeError) as caught:
                        operation()
                    self.assertEqual(caught.exception.code, 'RECURRENCE_UNSAFE' if enabled else 'READ_ONLY')
                live.transport.call.assert_not_called()

    def test_live_adapter_kind_checks_and_receipts(self):
        transport = Mock()
        adapter = ThingsAppleScriptAdapter(transport=transport)
        row = ['synthetic-a', 'Title', '', 'open', [], None]
        for kind in (None, 'project', 'unknown', 'selected to do'):
            transport.call.return_value = {'row': row, 'kind': kind}
            with self.assertRaises(BridgeError):
                adapter.get_handoff_task('synthetic-a')
        transport.call.return_value = {'row': row, 'kind': 'to do'}
        self.assertEqual(adapter.get_handoff_task('synthetic-a').id, 'synthetic-a')
        with self.assertRaises(BridgeError):
            adapter.get_handoff_task('synthetic-other')
        transport.call.return_value = {'id': 'synthetic-other', 'kind': 'to do'}
        with self.assertRaises(BridgeError):
            adapter.reveal_task('synthetic-a')
        transport.call.return_value = {'id': 'synthetic-a', 'kind': 'to do'}
        self.assertEqual(adapter.reveal_task('synthetic-a'), 'synthetic-a')

    @unittest.skipUnless(sys.platform == 'darwin', 'AppleScript guard test requires macOS')
    def test_applescript_kind_guard_without_things(self):
        # execute the production guard with class identifiers, without an app clause.
        helpers = SCRIPT.read_text().split('on taskRow(t)')[0]
        cases = [
            ('ordinary', '«class tstk»', 1, 0),
            ('ordinary reported as selected', '«class tslt»', 1, 0),
            ('project', '«class tspt»', 1, 7104),
            ('project wrapped as selected', '«class tslt»', 0, 7104),
            ('missing collection member', '«class tstk»', 0, 7104),
            ('ambiguous collection membership', '«class tslt»', 2, 7104),
            ('area', '«class tsaa»', 1, 7104),
            ('list', '«class tsls»', 1, 7104),
            ('unknown class', '«class zzzz»', 1, 7104),
            ('unavailable class', 'missing value', 1, 7104),
            ('class name text is not a class identifier', '"selected to do"', 1, 7104),
        ]
        probes = ', '.join('{' + kind + ', ' + str(count) + '}' for _, kind, count, _ in cases)
        script = helpers + '''
on run
    set outcomes to {}
    repeat with probe in {''' + probes + '''}
        try
            my requireHandoffKind(item 1 of probe, item 2 of probe)
            set end of outcomes to 0
        on error number errorNumber
            set end of outcomes to errorNumber
        end try
    end repeat
    return my jsonText(outcomes)
end run
'''
        result = subprocess.run(['/usr/bin/osascript', '-e', script], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, 'Synthetic AppleScript kind guard failed')
        outcomes = json.loads(result.stdout)
        self.assertEqual(len(outcomes), len(cases))
        for (label, _, _, expected), outcome in zip(cases, outcomes):
            with self.subTest(kind=label):
                self.assertEqual(outcome, expected)

    def test_preparation_reads_only_and_preserves_tasks_for_all_kind_outcomes(self):
        row = ['synthetic-a', 'Title', 'Original notes', 'open', [], None]
        for label, response, expected in (
            ('ordinary', {'ok': True, 'kind': 'to do', 'id': 'synthetic-a', 'row': row}, None),
            ('project', {'ok': False, 'error_number': 7104, 'write_started': False}, 'ITEM_KIND_UNSUPPORTED'),
            ('missing ID', {'ok': False, 'error_number': -1728, 'write_started': False}, 'NOT_FOUND'),
            ('unsupported type', {'ok': True, 'kind': 'unknown', 'row': row}, 'ITEM_KIND_UNSUPPORTED'),
        ):
            with self.subTest(kind=label):
                before = deepcopy(response)
                run = Mock(return_value=subprocess.CompletedProcess([], 0, json.dumps(response).encode(), b''))
                transport = AppleScriptTransport(run=run, preflight=lambda: None)
                adapter = ThingsAppleScriptAdapter(transport=transport)
                service = ThingsService(adapter)
                result = service.prepare_manual_change('synthetic-a', 'rename', 'New')
                self.assertFalse(result['mutated'])
                self.assertEqual(result['outcome'], 'unavailable' if expected else 'prepared')
                self.assertEqual(result['reason'], expected)
                self.assertEqual(len(service.handoffs._sessions), 0 if expected else 1)
                self.assertEqual(response, before)
                run.assert_called_once()
                args, kwargs = run.call_args
                self.assertEqual(args[0], ['/usr/bin/osascript', str(SCRIPT)])
                self.assertEqual(json.loads(kwargs['input']), {'operation': 'inspect_task', 'id': 'synthetic-a'})
                self.assertEqual(kwargs['env']['THINGS_ALLOW_WRITES'], 'false')

    def test_prepare_errors_and_summary_redaction(self):
        from things3_everywhere.cli import summarize
        self.adapter.failure = BridgeError('NOT_FOUND', 'PRIVATE_FAILURE')
        result, failed = dispatch(self.service, 'things_prepare_manual_change',
                                 {'id': 'synthetic-a', 'operation': 'rename', 'value': 'New'})
        self.assertEqual(result['outcome'], 'unavailable')
        self.assertNotIn('PRIVATE_FAILURE', json.dumps(result))
        self.assertEqual(self.service.handoffs._sessions, {})
        self.adapter.failure = None
        result = self.service.prepare_manual_change('synthetic-a', 'replace_notes', 'PRIVATE_PROPOSAL')
        summary = json.dumps(summarize(result))
        self.assertNotIn('PRIVATE_PROPOSAL', summary)
        self.assertNotIn(result['session_id'], summary)
        self.assertNotIn('Original notes', json.dumps(result))

    def test_deadline_passes_during_read(self):
        token = self.prepare()
        original = self.adapter.get_handoff_task
        def slow_read(id):
            self.now = Handoffs.TTL
            return original(id)
        self.adapter.get_handoff_task = slow_read
        self.assertEqual(self.service.verify_manual_change(token)['outcome'], 'inconclusive')
        self.now = 0
        self.adapter.get_handoff_task = original
        token = self.prepare()
        self.adapter.get_handoff_task = slow_read
        self.assertEqual(self.service.reveal_manual_change(token)['outcome'], 'inconclusive')
        self.assertEqual(self.adapter.shown, [])

    def test_fixed_transport_reveal_and_inspect(self):
        for operation in ('show_task', 'inspect_task'):
            run = Mock(return_value=subprocess.CompletedProcess([], 0, b'{"ok":true}', b''))
            transport = AppleScriptTransport(run=run, preflight=lambda: None)
            transport.call(operation, {'id': 'synthetic-a'})
            args, kwargs = run.call_args
            self.assertEqual(args[0], ['/usr/bin/osascript', str(SCRIPT)])
            self.assertEqual(json.loads(kwargs['input']), {'id': 'synthetic-a', 'operation': operation})
            self.assertEqual(kwargs['env']['THINGS_ALLOW_WRITES'], 'false')
            run.assert_called_once()
            for number, code in ((7104, 'ITEM_KIND_UNSUPPORTED'), (-1728, 'NOT_FOUND'), (7105, 'INVALID_RESPONSE'),
                                 (-1743, 'PERMISSION_DENIED'), (-1712, 'TIMEOUT')):
                run.return_value = subprocess.CompletedProcess([], 0,
                    json.dumps({'ok': False, 'error_number': number, 'write_started': False}).encode(), b'')
                with self.assertRaises(BridgeError) as caught:
                    transport.call(operation, {'id': 'synthetic-a'})
                self.assertEqual(caught.exception.code, code)

    def test_handle_diagnostics_and_bounded_private_tombstones(self):
        h = self.service.handoffs
        token = self.prepare()
        self.assertEqual(ThingsService(self.adapter).verify_manual_change(token)['reason'], 'SESSION_INSTANCE_MISMATCH')
        unknown = 'h1.' + h.instance_id + '.' + 'x' * 32
        self.assertEqual(h.verify(unknown)['reason'], 'SESSION_UNKNOWN')
        for bad in ('legacy-token', '', None, 'h1.' + 'x' * 200):
            self.assertEqual(h.verify(bad)['reason'], 'SESSION_HANDLE_INVALID')
        h.verify(token)
        self.assertEqual(h.verify(token)['reason'], 'SESSION_CONSUMED')
        for _ in range(h.TOMBSTONE_CAPACITY + 1):
            h.verify(self.prepare())
        self.assertEqual(len(h._tombstones), h.TOMBSTONE_CAPACITY)
        self.assertEqual(h.verify(token)['reason'], 'SESSION_UNKNOWN')
        encoded = json.dumps(h._tombstones)
        for private in ('synthetic-a', 'Original notes', 'Duplicate title', token):
            self.assertNotIn(private, encoded)
        self.now += h.TTL
        h.verify(unknown)
        self.assertEqual(h._tombstones, {})

    def test_expiration_is_deterministic_and_never_reads(self):
        token = self.prepare()
        self.now = Handoffs.TTL
        reads = list(self.adapter.reads)
        for call in (self.service.reveal_manual_change, self.service.verify_manual_change):
            self.assertEqual(call(token)['reason'], 'SESSION_EXPIRED')
        self.assertEqual(self.adapter.reads, reads)
        self.assertEqual(self.adapter.shown, [])

    def test_capacity_does_not_evict_active_session(self):
        tokens = [self.prepare() for _ in range(Handoffs.CAPACITY)]
        with self.assertRaises(BridgeError):
            self.prepare()
        self.assertEqual(set(self.service.handoffs._sessions), set(tokens))
        self.assertEqual(self.service.verify_manual_change(tokens[0])['outcome'], 'mismatched')
        self.prepare()

    def test_tag_order_is_ignored_before_reveal_and_verify(self):
        self.adapter.tasks['synthetic-a'] = replace(self.adapter.tasks['synthetic-a'], tags=['A', 'B'])
        token = self.prepare()
        self.adapter.tasks['synthetic-a'].tags.reverse()
        self.assertEqual(self.service.reveal_manual_change(token)['outcome'], 'revealed')
        self.adapter.tasks['synthetic-a'] = replace(self.adapter.tasks['synthetic-a'], title='New')
        self.assertEqual(self.service.verify_manual_change(token)['changed_fields'], ['title'])

    def test_notes_exact_replacement_clearing_and_unchanged(self):
        for value in ('First line\n雪 🐢\nLast line', '', 'Original notes'):
            with self.subTest(value=value):
                self.adapter.tasks['synthetic-a'] = sample('synthetic-a')
                token = self.prepare('replace_notes', value)
                self.adapter.tasks['synthetic-a'] = replace(self.adapter.tasks['synthetic-a'], notes=value)
                result = self.service.verify_manual_change(token)
                self.assertEqual(result['outcome'], 'inconclusive' if value == 'Original notes' else 'verified')
        token = self.prepare('replace_notes', 'a\nb')
        self.adapter.tasks['synthetic-a'] = replace(self.adapter.tasks['synthetic-a'], notes='a\r\nb')
        self.assertEqual(self.service.verify_manual_change(token)['outcome'], 'mismatched')

    def test_deadline_add_change_noop_and_invalid_values(self):
        for old, new in ((None, '2032-02-29'), ('2032-02-29', '2033-01-01'), ('2033-01-01', '2033-01-01')):
            self.adapter.tasks['synthetic-a'] = replace(self.adapter.tasks['synthetic-a'], deadline=old)
            token = self.prepare('change_deadline', new)
            self.adapter.tasks['synthetic-a'] = replace(self.adapter.tasks['synthetic-a'], deadline=new)
            self.assertEqual(self.service.verify_manual_change(token)['outcome'], 'inconclusive' if old == new else 'verified')
        for value in (None, '', '2031-02-29', '2032-2-29', '2032-02-29T00:00:00Z'):
            with self.assertRaises(BridgeError):
                self.prepare('change_deadline', value)

    def test_same_target_sessions_independent_and_repeated_verification_serialized(self):
        from concurrent.futures import ThreadPoolExecutor
        one, two = self.prepare(), self.prepare('replace_notes', 'Notes')
        self.adapter.tasks['synthetic-a'] = replace(self.adapter.tasks['synthetic-a'], title='New')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.service.verify_manual_change, [one, one]))
        self.assertEqual(sorted(r['outcome'] for r in results), ['inconclusive', 'verified'])
        self.assertIn('SESSION_CONSUMED', [r['reason'] for r in results])
        result = self.service.verify_manual_change(two)
        self.assertEqual(result['outcome'], 'mismatched')
        self.assertEqual(result['unexpected_fields'], ['title'])

    def test_status_changes_missing_and_malformed_reads(self):
        token = self.prepare()
        self.adapter.tasks['synthetic-a'] = replace(self.adapter.tasks['synthetic-a'], status='completed')
        self.assertEqual(self.service.verify_manual_change(token)['unexpected_fields'], ['status'])
        token = self.prepare('complete', None)
        del self.adapter.tasks['synthetic-a']
        self.assertEqual(self.service.verify_manual_change(token)['reason'], 'NOT_FOUND')
        self.assertEqual(self.service.verify_manual_change(token)['reason'], 'SESSION_CONSUMED')
        self.adapter.tasks['synthetic-a'] = sample('synthetic-a')
        token = self.prepare()
        self.adapter.tasks['synthetic-a'] = replace(self.adapter.tasks['synthetic-a'], tags='malformed')
        self.assertEqual(self.service.verify_manual_change(token)['reason'], 'INVALID_RESPONSE')

    @unittest.skipUnless(sys.platform == 'darwin', 'AppleScript date test requires macOS')
    def test_deadline_calendar_roundtrip_across_timezones_and_midnight(self):
        import os
        helpers = SCRIPT.read_text().split('on taskRow(t)')[0]
        script = helpers + '''
set d to my calendarDate("2032-02-29")
set time of d to 0
set firstDate to my dateText(d)
set time of d to 86399
return my jsonText({firstDate, my dateText(d), my dateText(missing value)})
'''
        for zone in ('UTC', 'Pacific/Kiritimati', 'America/Los_Angeles'):
            result = subprocess.run(['/usr/bin/osascript', '-e', script], env={**os.environ, 'TZ': zone}, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout), ['2032-02-29', '2032-02-29', None])
