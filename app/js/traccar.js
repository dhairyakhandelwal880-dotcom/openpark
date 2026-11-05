// traccar.js — Express / Node router & WebSocket handler for Traccar protocol.
import express from 'express';
import { parseTraccar } from './traccar-parse.js';

export function createTraccarRouter({ broadcast, logger = console } = {}) {
  const router = express.Router();
  const keepRaw = (req, _res, buf) => { req.rawBody = buf.toString('utf8'); };

  // 1) Log every request (raw body included) once it finishes, even if body parsing fails.
  router.use('/api/traccar', (req, res, next) => {
    res.on('finish', () => {
      logger.log('[traccar]', JSON.stringify({
        t: new Date().toISOString(),
        method: req.method,
        url: req.originalUrl,
        ip: req.ip,
        contentType: req.headers['content-type'],
        ua: req.headers['user-agent'],
        raw: (req.rawBody ?? '').slice(0, 2000),
        status: res.statusCode,
      }));
    });
    next();
  });

  // 2) Accept form, JSON and text bodies (Traccar Client / forwarding use different ones).
  router.use('/api/traccar',
    express.urlencoded({ extended: false, verify: keepRaw }),
    express.json({ type: ['application/json', 'application/*+json'], verify: keepRaw }),
    express.text({ type: 'text/*', verify: keepRaw }),
  );

  const handle = (req, res) => {
    let body = req.body;
    if (typeof body === 'string') { try { body = JSON.parse(body); } catch { body = {}; } }
    const msg = parseTraccar(req.query, body);
    if (!msg) return res.status(400).send('bad position');
    broadcast?.(msg);
    res.status(200).send('OK'); // Traccar Client retries on non-2xx, so only 400 genuinely bad data
  };
  router.route('/api/traccar').get(handle).post(handle);

  // eslint-disable-next-line no-unused-vars
  router.use('/api/traccar', (err, _req, res, _next) => res.status(400).send('bad request'));
  return router;
}

export function attachWs(wss) {
  wss.on('connection', (ws) => {
    ws.on('message', (raw) => {
      let m;
      try { m = JSON.parse(raw.toString()); } catch { return; }
      if (m?.type === 'ping') ws.send(JSON.stringify({ type: 'pong', t: m.t }));
    });
  });
  return (msg) => {
    const s = JSON.stringify(msg);
    for (const c of wss.clients) if (c.readyState === 1) c.send(s);
  };
}
