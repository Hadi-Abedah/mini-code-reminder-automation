import { mkdir, open, readFile, rename } from 'node:fs/promises';
import path from 'node:path';

export function validateMessages(messages) {
  if (!Array.isArray(messages)) throw new Error('Expected a JSON array of messages');
  for (const m of messages) {
    if (!m || !['date', 'name', 'time', 'groupId', 'text'].every(k => typeof m[k] === 'string' && m[k].trim()) ||
        !/^\d{4}-\d{2}-\d{2}$/.test(m.date) || !/^\d+(?:-\d+)?@g\.us$/.test(m.groupId)) {
      throw new Error('Invalid reminder payload');
    }
  }
  return messages;
}

export const messageKey = m => JSON.stringify([m.date, m.name, m.time, m.groupId]);

export async function loadLedger(filename) {
  let records;
  try { records = JSON.parse(await readFile(filename, 'utf8')); }
  catch (error) {
    if (error.code !== 'ENOENT') throw error; // Never discard a corrupt send history.
    records = {};
  }
  if (!records || Array.isArray(records) || typeof records !== 'object') throw new Error('Invalid send history');
  return {
    has: key => Object.hasOwn(records, key),
    async record(key, messageId) {
      records[key] = { sentAt: new Date().toISOString(), messageId };
      await mkdir(path.dirname(filename), { recursive: true, mode: 0o700 });
      const temporary = `${filename}.tmp`;
      const file = await open(temporary, 'w', 0o600);
      try { await file.writeFile(JSON.stringify(records, null, 2)); await file.sync(); }
      finally { await file.close(); }
      await rename(temporary, filename);
    },
  };
}

export async function dispatch(messages, { send, ledger, log = console.log }) {
  const results = { sent: 0, skipped: 0, failed: 0 };
  for (const message of messages) {
    const key = messageKey(message);
    if (ledger.has(key)) {
      results.skipped++;
      log(`Already sent: ${message.name} → ${message.groupId}`);
      continue;
    }
    let response;
    try {
      response = await send(message.groupId, { text: message.text });
      if (!response?.key?.id) throw new Error('No message ID returned');
    } catch (error) {
      results.failed++;
      log(`Failed: ${message.name} → ${message.groupId}: ${error.message}`);
      continue;
    }
    // Stop on persistence failure: continuing could cause unrecorded duplicate sends.
    await ledger.record(key, response.key.id);
    results.sent++;
    log(`Sent: ${message.name} → ${message.groupId}`);
  }
  return results;
}
