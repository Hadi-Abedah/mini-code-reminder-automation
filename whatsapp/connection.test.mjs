import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { hasLinkedSession, trackAuthWrites, waitForConnection } from './connection.mjs';

function setup(overrides = {}) {
  const socket = { ev: new EventEmitter(), end() {} };
  const promise = waitForConnection({ makeSocket: () => socket, saveCreds: async () => {},
    pairing: false, showQr: () => assert.fail('No QR in scheduled runs'),
    loggedOutCode: 401, restartCode: 515, timeoutMs: 100, ...overrides });
  return { socket, promise };
}

test('expired session gives actionable pairing error', async () => {
  const { socket, promise } = setup();
  socket.ev.emit('connection.update', { connection: 'close', lastDisconnect: { error: { output: { statusCode: 401 } } } });
  await assert.rejects(promise, /pairing required/);
});

test('scheduled run never waits for QR pairing', async () => {
  const { socket, promise } = setup();
  socket.ev.emit('connection.update', { qr: 'qr-value' });
  await assert.rejects(promise, /pairing required/);
});

test('open connection saves updated credentials', async () => {
  let saved = 0;
  const { socket, promise } = setup({ saveCreds: async () => { saved++; } });
  socket.ev.emit('creds.update', {});
  socket.ev.emit('connection.update', { connection: 'open' });
  const connection = await promise;
  await connection.flushCredentials();
  assert.equal(saved, 2);
});

test('connection timeout exits clearly', async () => {
  const { promise } = setup({ timeoutMs: 5 });
  await assert.rejects(promise, /timed out/);
});

test('pairing handles required socket restart', async () => {
  const sockets = [];
  const { promise } = setup({
    pairing: true,
    makeSocket: () => { const socket = { ev: new EventEmitter(), end() {} }; sockets.push(socket); return socket; },
  });
  sockets[0].ev.emit('connection.update', { connection: 'close', lastDisconnect: { error: { output: { statusCode: 515 } } } });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(sockets.length, 2);
  sockets[1].ev.emit('connection.update', { connection: 'open' });
  assert.equal((await promise).socket, sockets[1]);
});


test('QR-linked identity is accepted even when registered is false', () => {
  assert.equal(hasLinkedSession({ registered: false, me: { id: '123:1@s.whatsapp.net' } }), true);
  assert.equal(hasLinkedSession({ registered: true }), false);
  assert.equal(hasLinkedSession({}), false);
});

test('connection does not report success before credentials reach disk', async () => {
  let release;
  const saving = new Promise(resolve => { release = resolve; });
  const { socket, promise } = setup({ saveCreds: () => saving });
  let connected = false;
  promise.then(() => { connected = true; });
  socket.ev.emit('connection.update', { connection: 'open' });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(connected, false);
  release();
  await promise;
  assert.equal(connected, true);
});

test('credential save failure cannot report pairing success', async () => {
  const { socket, promise } = setup({ saveCreds: async () => { throw new Error('disk full'); } });
  socket.ev.emit('connection.update', { connection: 'open' });
  await assert.rejects(promise, /disk full/);
});


test('shutdown waits for outstanding Signal-key writes', async () => {
  let release;
  const saving = new Promise(resolve => { release = resolve; });
  const state = { keys: { set: () => saving } };
  const writes = trackAuthWrites(state, async () => {});
  const write = state.keys.set({});
  let flushed = false;
  const flush = writes.flush().then(() => { flushed = true; });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(flushed, false);
  release();
  await Promise.all([write, flush]);
  assert.equal(flushed, true);
});

test('shutdown reports authentication write errors', async () => {
  const state = { keys: { set: async () => { throw new Error('write failed'); } } };
  const writes = trackAuthWrites(state, async () => {});
  await assert.rejects(state.keys.set({}), /write failed/);
  await assert.rejects(writes.flush(), /write failed/);
});
