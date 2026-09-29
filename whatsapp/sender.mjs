import makeWASocket, { DisconnectReason, useMultiFileAuthState } from '@whiskeysockets/baileys';
import pino from 'pino';
import qrcode from 'qrcode-terminal';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { dispatch, loadLedger, messageKey, validateMessages } from './core.mjs';
import { PAIRING_REQUIRED, hasLinkedSession, trackAuthWrites, waitForConnection } from './connection.mjs';

process.umask(0o077);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const stateDirectory = path.join(root, '.whatsapp');
const pairing = process.argv.includes('--pair');
const logger = pino({ level: 'silent' });
let connection;
let authWrites;

async function main() {
  let messages = [];
  let ledger;
  if (!pairing) {
    let input = '';
    for await (const chunk of process.stdin) input += chunk;
    messages = validateMessages(JSON.parse(input));
    ledger = await loadLedger(path.join(stateDirectory, 'sent.json'));
    if (!messages.some(m => !ledger.has(messageKey(m)))) {
      console.log('No new messages to send');
      return;
    }
  }
  await mkdir(stateDirectory, { recursive: true, mode: 0o700 });
  const { state, saveCreds } = await useMultiFileAuthState(path.join(stateDirectory, 'auth'));
  authWrites = trackAuthWrites(state, saveCreds);
  if (!pairing && !hasLinkedSession(state.creds)) throw new Error(PAIRING_REQUIRED);
  connection = await waitForConnection({
    makeSocket: () => makeWASocket({ auth: state, logger, markOnlineOnConnect: false,
                                    syncFullHistory: false, connectTimeoutMs: 45000,
                                    defaultQueryTimeoutMs: 30000 }),
    saveCreds: authWrites.saveCreds, pairing,
    showQr: qr => { console.log('WhatsApp → Linked devices → Link a device:'); qrcode.generate(qr, { small: true }); },
    loggedOutCode: DisconnectReason.loggedOut,
    restartCode: DisconnectReason.restartRequired,
    timeoutMs: pairing ? 180000 : 60000,
  });
  if (pairing) {
    await authWrites.flush();
    console.log('WhatsApp linked. Session saved locally.');
    return;
  }
  const results = await dispatch(messages, {
    ledger,
    send: (jid, content) => withTimeout(connection.socket.sendMessage(jid, content), 30000),
  });
  console.log(JSON.stringify(results));
  if (results.failed) process.exitCode = 1;
}

function withTimeout(promise, ms) {
  let timer;
  return Promise.race([promise, new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error('Send timed out; delivery is uncertain, inspect the group before retrying')), ms);
  })]).finally(() => clearTimeout(timer));
}

try { await main(); }
catch (error) { console.error(error.message); process.exitCode = 1; }
finally {
  if (connection) {
    try {
      await connection.socket.end(undefined);
      await connection.flushCredentials();
    }
    catch (error) { console.error(`Could not save WhatsApp session: ${error.message}`); process.exitCode = 1; }
  }
}

// Baileys can retain background handles after end(). This is a one-shot CLI:
// drain authentication writes and output before terminating those handles.
try { await authWrites?.flush(); }
catch (error) { console.error(`Could not save WhatsApp session: ${error.message}`); process.exitCode = 1; }
await Promise.all([process.stdout, process.stderr].map(stream => new Promise(resolve => stream.write('', resolve))));
process.exit(process.exitCode ?? 0);
