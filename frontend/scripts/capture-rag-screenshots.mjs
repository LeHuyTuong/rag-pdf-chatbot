import { spawn } from 'node:child_process';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

const FRONTEND_URL = process.env.FRONTEND_URL || 'http://127.0.0.1:5174';
const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8080';
const DEMO_EMAIL = process.env.DEMO_EMAIL;
const DEMO_PASSWORD = process.env.DEMO_PASSWORD || 'password';
const DEMO_DOCUMENT_ID = process.env.DEMO_DOCUMENT_ID || '';
const OUTPUT_DIR = process.env.SCREENSHOT_DIR || path.resolve('docs/screenshots');
const CHROME_PATH = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const DEBUG_PORT = Number(process.env.CHROME_DEBUG_PORT || 9333);
const VIEWPORT_WIDTH = Number(process.env.SCREENSHOT_WIDTH || 1440);
const VIEWPORT_HEIGHT = Number(process.env.SCREENSHOT_HEIGHT || 1600);

if (!DEMO_EMAIL) {
  throw new Error('DEMO_EMAIL is required. Use an account that already has a completed history document.');
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function summarizeEvalJsonl(filePath, label) {
  const text = await readFile(filePath, 'utf8');
  const rows = text
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
  const count = (predicate) => rows.filter(predicate).length;
  const verdicts = new Map();
  for (const row of rows) {
    verdicts.set(row.verdict, (verdicts.get(row.verdict) || 0) + 1);
  }
  const sourceRows = count((row) => (row.sources || []).length > 0);
  const avgLatency = rows.reduce((sum, row) => sum + Number(row.latency_ms || 0), 0) / Math.max(rows.length, 1);
  return [
    `Run: ${label}`,
    `Total questions: ${rows.length}`,
    `PASS: ${verdicts.get('PASS') || 0}`,
    `WARNING: ${verdicts.get('WARNING') || 0}`,
    `FAIL: ${verdicts.get('FAIL') || 0}`,
    `PASS_TRAP_REFUSAL: ${verdicts.get('PASS_TRAP_REFUSAL') || 0}`,
    `WARNING_REFUSAL_WEAK: ${verdicts.get('WARNING_REFUSAL_WEAK') || 0}`,
    `FAIL_HALLUCINATION_RISK: ${verdicts.get('FAIL_HALLUCINATION_RISK') || 0}`,
    `ERROR: ${verdicts.get('ERROR') || 0}`,
    `Source coverage: ${((sourceRows / Math.max(rows.length, 1)) * 100).toFixed(2)}%`,
    `Source mapping issue count: ${count((row) => row.checks?.source_mapping_issue)}`,
    `Vietnamese diacritics pass rate: ${((count((row) => row.checks?.vietnamese_diacritics_ok) / Math.max(rows.length, 1)) * 100).toFixed(2)}%`,
    `Hallucination risk count: ${count((row) => row.checks?.hallucination_risk)}`,
    `Average latency: ${avgLatency.toFixed(1)} ms`,
  ].join('\n');
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${options?.method || 'GET'} ${url} failed: ${response.status} ${body}`);
  }
  return response.json();
}

async function waitForEndpoint(url, timeoutMs = 30000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return response;
    } catch {
      // Keep polling until Chrome opens the debugging endpoint.
    }
    await sleep(250);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

function encodeForJs(value) {
  return JSON.stringify(value).replace(/</g, '\\u003c');
}

async function createCdpClient(wsUrl) {
  const ws = new WebSocket(wsUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true });
    ws.addEventListener('error', reject, { once: true });
  });

  let nextId = 1;
  const callbacks = new Map();
  const eventWaiters = new Map();

  ws.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (message.id && callbacks.has(message.id)) {
      const { resolve, reject } = callbacks.get(message.id);
      callbacks.delete(message.id);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolve(message.result || {});
      return;
    }

    if (message.method && eventWaiters.has(message.method)) {
      const waiters = eventWaiters.get(message.method);
      eventWaiters.delete(message.method);
      for (const resolve of waiters) resolve(message.params || {});
    }
  });

  function send(method, params = {}) {
    const id = nextId++;
    ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      callbacks.set(id, { resolve, reject });
    });
  }

  function waitForEvent(method, timeoutMs = 30000) {
    return new Promise((resolve, reject) => {
      const waiters = eventWaiters.get(method) || [];
      waiters.push(resolve);
      eventWaiters.set(method, waiters);
      setTimeout(() => reject(new Error(`Timed out waiting for CDP event ${method}`)), timeoutMs);
    });
  }

  return { send, waitForEvent, close: () => ws.close() };
}

async function main() {
  await mkdir(OUTPUT_DIR, { recursive: true });

  const auth = await fetchJson(`${BACKEND_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: DEMO_EMAIL, password: DEMO_PASSWORD }),
  });
  const user = auth.user || { email: DEMO_EMAIL, fullName: 'Pre GraphDB Browser' };
  const documents = await fetchJson(`${BACKEND_URL}/api/documents`, {
    headers: { Authorization: `Bearer ${auth.token}` },
  });
  const document = DEMO_DOCUMENT_ID
    ? documents.find((item) => item.id === DEMO_DOCUMENT_ID)
    : documents.find((item) => item.status === 'completed') || documents[0];

  if (!document) {
    throw new Error(`No document found for ${DEMO_EMAIL}`);
  }
  console.log(`Using document ${document.id} (${document.totalChunks || 0} chunks)`);

  const chromeProfile = await mkdtemp(path.join(tmpdir(), 'rag-chatbot-chrome-'));
  const chrome = spawn(CHROME_PATH, [
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    '--hide-scrollbars',
    `--remote-debugging-port=${DEBUG_PORT}`,
    `--user-data-dir=${chromeProfile}`,
    `--window-size=${VIEWPORT_WIDTH},${VIEWPORT_HEIGHT}`,
    'about:blank',
  ], { stdio: 'ignore' });

  let client;
  try {
    await waitForEndpoint(`http://127.0.0.1:${DEBUG_PORT}/json/version`);
    const target = await fetchJson(`http://127.0.0.1:${DEBUG_PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' });
    client = await createCdpClient(target.webSocketDebuggerUrl);
    await client.send('Page.enable');
    await client.send('Runtime.enable');
    await client.send('Emulation.setDeviceMetricsOverride', {
      width: VIEWPORT_WIDTH,
      height: VIEWPORT_HEIGHT,
      deviceScaleFactor: 1,
      mobile: false,
    });

    async function evaluate(expression, timeoutMs = 30000) {
      const result = await client.send('Runtime.evaluate', {
        expression,
        awaitPromise: true,
        returnByValue: true,
        userGesture: true,
        timeout: timeoutMs,
      });
      if (result.exceptionDetails) {
        throw new Error(JSON.stringify(result.exceptionDetails));
      }
      return result.result?.value;
    }

    async function navigate(url) {
      const loaded = client.waitForEvent('Page.loadEventFired', 60000);
      await client.send('Page.navigate', { url });
      await loaded;
    }

    async function waitForExpression(expression, timeoutMs = 120000) {
      const started = Date.now();
      while (Date.now() - started < timeoutMs) {
        const value = await evaluate(expression);
        if (value) return value;
        await sleep(500);
      }
      const bodyText = await evaluate('document.body ? document.body.innerText.slice(0, 2000) : ""').catch(() => '');
      throw new Error(`Timed out waiting for expression: ${expression}\nPage text:\n${bodyText}`);
    }

    async function screenshot(fileName) {
      await evaluate(`
        (() => {
          const messages = document.querySelectorAll('.message-bubble-user, .message-bubble-assistant');
          const last = messages[messages.length - 1];
          if (last) last.scrollIntoView({ block: 'end' });
        })()
      `);
      await sleep(500);
      const data = await client.send('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: false });
      await writeFile(path.join(OUTPUT_DIR, fileName), Buffer.from(data.data, 'base64'));
    }

    async function ask(question, expectedAssistantCount) {
      await evaluate(`
        (() => {
          const textarea = document.querySelector('textarea');
          if (!textarea) throw new Error('Chat textarea not found');
          textarea.focus();
        })()
      `);
      await client.send('Input.insertText', { text: question });
      await sleep(200);
      await client.send('Input.dispatchKeyEvent', {
        type: 'keyDown',
        key: 'Enter',
        code: 'Enter',
        windowsVirtualKeyCode: 13,
        nativeVirtualKeyCode: 13,
      });
      await client.send('Input.dispatchKeyEvent', {
        type: 'keyUp',
        key: 'Enter',
        code: 'Enter',
        windowsVirtualKeyCode: 13,
        nativeVirtualKeyCode: 13,
      });
      await waitForExpression(`
        (() => {
          const assistants = Array.from(document.querySelectorAll('.message-bubble-assistant'));
          if (assistants.length < ${expectedAssistantCount}) return false;
          const last = assistants[assistants.length - 1].textContent || '';
          return !last.includes('Dang') && !last.includes('Đang') && !last.includes('Äang') && last.length > 40;
        })()
      `, 150000);
    }

    await client.send('Page.addScriptToEvaluateOnNewDocument', { source: `
      (() => {
        localStorage.setItem('token', ${encodeForJs(auth.token)});
        localStorage.setItem('user', ${encodeForJs(JSON.stringify(user))});
        localStorage.setItem('activeDocumentId', ${encodeForJs(document.id)});
        localStorage.removeItem('activeChatSessionId');
      })()
    ` });
    await navigate(`${FRONTEND_URL}/chat?docId=${document.id}`);
    await waitForExpression('!!document.querySelector("textarea") && !document.querySelector("textarea").disabled', 60000);
    await evaluate(`
      (() => {
        const newButton = Array.from(document.querySelectorAll('button')).find((button) => button.textContent.trim() === 'New');
        if (newButton) newButton.click();
      })()
    `);
    await sleep(500);

    console.log('Asking chat-order question 1/3');
    await ask('Đinh Bộ Lĩnh là ai?', 1);
    console.log('Asking chat-order question 2/3');
    await ask('Trần Hưng Đạo là ai?', 2);
    console.log('Asking chat-order question 3/3');
    await ask('Lý Thường Kiệt là ai?', 3);
    await screenshot('01-chat-order.png');
    console.log('Captured 01-chat-order.png');

    console.log('Asking reasoning/citation question');
    await ask('Vì sao Việt Nam phải tiến hành công cuộc Đổi mới từ năm 1986?', 4);
    await screenshot('02-rag-reasoning-citation.png');
    console.log('Captured 02-rag-reasoning-citation.png');

    console.log('Asking controlled-refusal question');
    await ask('Đinh Bộ Lĩnh là ai và dưới trướng ông có những tướng nào?', 5);
    await screenshot('03-controlled-refusal.png');
    console.log('Captured 03-controlled-refusal.png');

    const summary = [
      await summarizeEvalJsonl(path.resolve('rag-api/storage/eval/rag_eval_history_pre-graphdb-quick.jsonl'), 'pre-graphdb-quick'),
      await summarizeEvalJsonl(path.resolve('rag-api/storage/eval/rag_eval_history_pre-graphdb-trap.jsonl'), 'pre-graphdb-trap'),
    ].join('\n\n---\n\n');
    await navigate(`data:text/html;charset=utf-8,${encodeURIComponent(`
      <!doctype html>
      <title>Pre-GraphDB Evaluation Report</title>
      <style>
        body { margin: 0; padding: 32px; font-family: Consolas, monospace; background: #f8fafc; color: #0f172a; }
        h1 { font: 700 24px system-ui, sans-serif; margin: 0 0 20px; }
        pre { white-space: pre-wrap; background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 24px; line-height: 1.45; font-size: 14px; }
      </style>
      <h1>Pre-GraphDB Targeted RAG Evaluation</h1>
      <pre>${summary.replace(/[&<>]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[char]))}</pre>
    `)}`);
    await screenshot('04-evaluation-report.png');
    console.log('Captured 04-evaluation-report.png');
  } finally {
    client?.close();
    chrome.kill();
    await sleep(1000);
    await rm(chromeProfile, { recursive: true, force: true }).catch((error) => {
      console.warn(`Could not remove temporary Chrome profile: ${error.message}`);
    });
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
