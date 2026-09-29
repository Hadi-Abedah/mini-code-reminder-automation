export const PAIRING_REQUIRED = 'WhatsApp pairing required. Run npm run pair interactively.';

// Baileys resumes QR-linked sessions using creds.me, not the registered flag.
export const hasLinkedSession = creds => typeof creds?.me?.id === 'string' && creds.me.id.length > 0;

export function waitForConnection({ makeSocket, saveCreds, pairing, showQr, loggedOutCode,
                                    restartCode, timeoutMs = 60000 }) {
  return new Promise((resolve, reject) => {
    let socket;
    let settled = false;
    let saves = Promise.resolve();
    const timer = setTimeout(() => fail(new Error('WhatsApp connection timed out')), timeoutMs);
    function fail(error) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(error);
      socket?.end(error);
    }
    function start() {
      if (settled) return;
      try { socket = makeSocket(); } catch (error) { fail(error); return; }
      const current = socket;
      current.ev.on('creds.update', () => {
        saves = saves.then(saveCreds);
        saves.catch(error => { if (!settled) fail(error); });
      });
      current.ev.on('connection.update', update => {
        if (settled || current !== socket) return;
        if (update.qr) {
          if (!pairing) { fail(new Error(PAIRING_REQUIRED)); return; }
          showQr(update.qr);
        }
        if (update.connection === 'open') {
          // Persist the final login identity even if no creds.update was emitted.
          saves = saves.then(saveCreds);
          saves.then(() => {
            if (settled) return;
            settled = true;
            clearTimeout(timer);
            resolve({ socket: current, flushCredentials: () => saves });
          }, fail);
        } else if (update.connection === 'close') {
          const code = update.lastDisconnect?.error?.output?.statusCode;
          if (code === restartCode) {
            current.ev.removeAllListeners('connection.update');
            saves.then(start, fail);
          } else {
            fail(new Error(code === loggedOutCode ? PAIRING_REQUIRED : `WhatsApp disconnected (${code ?? 'unknown'})`));
          }
        }
      });
    }
    start();
  });
}


// Track both credential and Signal-key writes before the one-shot process exits.
export function trackAuthWrites(state, saveCreds) {
  const pending = new Set();
  let failure;
  function track(operation) {
    const promise = Promise.resolve().then(operation);
    pending.add(promise);
    promise.then(() => pending.delete(promise), error => {
      pending.delete(promise);
      failure = error;
    });
    return promise;
  }
  const setKeys = state.keys.set.bind(state.keys);
  state.keys.set = data => track(() => setKeys(data));
  return {
    saveCreds: () => track(saveCreds),
    async flush() {
      while (pending.size) await Promise.all([...pending]);
      if (failure) throw failure;
    },
  };
}
