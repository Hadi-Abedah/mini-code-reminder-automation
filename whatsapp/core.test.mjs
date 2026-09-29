import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { dispatch, loadLedger, validateMessages } from './core.mjs';

const sample = { date: '2026-09-27', name: 'lesson', time: '8pm', groupId: '123@g.us', text: 'Reminder' };

test('successful sends survive reload and failed recipients can be retried', async () => {
  const directory = await mkdtemp(path.join(tmpdir(), 'reminders-'));
  try {
    const filename = path.join(directory, 'sent.json');
    const messages = [sample, { ...sample, groupId: '456@g.us' }];
    let calls = [];
    const first = await dispatch(messages, {
      ledger: await loadLedger(filename), log() {},
      send: async jid => { calls.push(jid); if (jid === '456@g.us') throw new Error('not allowed'); return { key: { id: 'success' } }; },
    });
    assert.deepEqual(first, { sent: 1, skipped: 0, failed: 1 });
    assert.deepEqual(calls, ['123@g.us', '456@g.us']);
    calls = [];
    const second = await dispatch(messages, {
      ledger: await loadLedger(filename), log() {},
      send: async jid => { calls.push(jid); return { key: { id: 'retry' } }; },
    });
    assert.deepEqual(second, { sent: 1, skipped: 1, failed: 0 });
    assert.deepEqual(calls, ['456@g.us']);
    assert.equal(Object.keys(JSON.parse(await readFile(filename))).length, 2);
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test('empty batch sends nothing', async () => {
  assert.deepEqual(await dispatch([], { send: () => assert.fail(), ledger: {}, log() {} }), { sent: 0, skipped: 0, failed: 0 });
});

test('history write failure stops the batch', async () => {
  let count = 0;
  await assert.rejects(dispatch([sample, sample], {
    send: async () => { count++; return { key: { id: 'sent' } }; },
    ledger: { has: () => false, record: async () => { throw new Error('disk full'); } }, log() {},
  }), /disk full/);
  assert.equal(count, 1);
});

test('corrupt history fails closed', async () => {
  const directory = await mkdtemp(path.join(tmpdir(), 'reminders-'));
  try {
    const filename = path.join(directory, 'sent.json');
    await writeFile(filename, 'not json');
    await assert.rejects(loadLedger(filename));
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test('payloads require group JIDs', () => {
  assert.deepEqual(validateMessages([sample]), [sample]);
  assert.throws(() => validateMessages([{ ...sample, groupId: '123@s.whatsapp.net' }]));
});
