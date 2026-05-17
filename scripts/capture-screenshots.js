const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const http = require('http');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');
const frontendDir = path.join(rootDir, 'frontend');
const outputDir = path.join(rootDir, 'docs', 'screenshots');
const baseUrl = process.env.E2E_BASE_URL || 'http://127.0.0.1:3000';
const useMocks = process.env.E2E_USE_MOCKS !== 'false';
const email = process.env.E2E_EMAIL;
const password = process.env.E2E_PASSWORD;

const demoDocs = [
  {
    id: 'demo-doc-1',
    userId: 'demo-user',
    originalFileName: 'SACH PHONG THUY UNG DUNG.pdf',
    fileName: 'demo-phong-thuy.pdf',
    fileType: 'application/pdf',
    status: 'completed',
    totalPages: 24,
    totalChunks: 86,
    errorMessage: null,
    createdAt: '2026-05-17T08:00:00Z',
    updatedAt: '2026-05-17T08:02:00Z',
  },
  {
    id: 'demo-doc-2',
    userId: 'demo-user',
    originalFileName: 'scan-contract.pdf',
    fileName: 'scan-contract.pdf',
    fileType: 'application/pdf',
    status: 'failed',
    totalPages: 8,
    totalChunks: 0,
    errorMessage: 'PDF scan/image-only: no text layer found; OCR is required.',
    createdAt: '2026-05-17T09:00:00Z',
    updatedAt: '2026-05-17T09:01:00Z',
  },
];

const chunkReports = {
  'demo-doc-1': {
    document_id: 'demo-doc-1',
    file_name: 'SACH PHONG THUY UNG DUNG.pdf',
    status: 'completed',
    total_pages: 24,
    extracted_text_length: 48216,
    total_chunks: 86,
    parser_used: 'pypdf',
    warning: null,
    error_message: null,
    chunks: [
      {
        chunk_id: 'chunk-001',
        chunk_index: 0,
        page_start: 1,
        page_end: 1,
        token_count: 188,
        preview: 'Phong thuy ung dung tap trung vao cach bo tri khong gian song, anh sang, gio va dong chay sinh hoat trong nha.',
      },
      {
        chunk_id: 'chunk-002',
        chunk_index: 1,
        page_start: 2,
        page_end: 2,
        token_count: 214,
        preview: 'Khi sap xep noi that, tai lieu uu tien su thong thoang, tinh can bang va viec giu cac loi di chinh gon gang.',
      },
    ],
  },
  'demo-doc-2': {
    document_id: 'demo-doc-2',
    file_name: 'scan-contract.pdf',
    status: 'failed',
    total_pages: 8,
    extracted_text_length: 0,
    total_chunks: 0,
    parser_used: 'pymupdf',
    warning: 'PDF scan/image-only: no text layer found; OCR is required.',
    error_message: 'PDF scan/image-only: no text layer found; OCR is required.',
    chunks: [],
  },
};

function requestOk(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      res.resume();
      resolve(res.statusCode && res.statusCode < 500);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(1500, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForServer(url, timeoutMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await requestOk(url)) return true;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

async function ensureFrontend() {
  if (await requestOk(baseUrl)) {
    console.log(`[screenshots] using running frontend at ${baseUrl}`);
    return null;
  }

  console.log('[screenshots] frontend is not running; starting Vite dev server');
  const command = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  const child = spawn(command, ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '3000'], {
    cwd: frontendDir,
    stdio: 'ignore',
    detached: process.platform !== 'win32',
    shell: process.platform === 'win32',
  });

  const ready = await waitForServer(baseUrl, 45000);
  if (!ready) {
    child.kill();
    throw new Error(`Frontend did not become ready at ${baseUrl}`);
  }
  return child;
}

async function installMockApi(context) {
  await context.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;
    const method = request.method();

    if (!pathname.startsWith('/api/')) {
      return route.continue();
    }

    const json = (payload, status = 200) =>
      route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify(payload),
      });

    if (pathname === '/api/auth/login' || pathname === '/api/auth/register') {
      return json({
        token: 'demo-token-for-screenshots',
        user: { id: 'demo-user', email: 'demo@example.com', fullName: 'Demo User' },
      });
    }

    if (pathname === '/api/dashboard') {
      return json({ totalDocuments: 2, totalChatSessions: 7, totalMessages: 31 });
    }

    if (pathname === '/api/documents' && method === 'GET') {
      return json(demoDocs);
    }

    if (pathname === '/api/documents/upload' && method === 'POST') {
      return json({ ...demoDocs[0], id: 'demo-doc-uploaded', totalPages: 12, totalChunks: 42 });
    }

    const chunkReportMatch = pathname.match(/^\/api\/documents\/([^/]+)\/chunk-report$/);
    if (chunkReportMatch) {
      return json(chunkReports[chunkReportMatch[1]] || chunkReports['demo-doc-1']);
    }

    if (pathname === '/api/chat/sessions' && method === 'POST') {
      return json({
        id: 'demo-session-1',
        userId: 'demo-user',
        documentId: 'demo-doc-1',
        title: 'Phong thuy Q&A',
        createdAt: '2026-05-17T10:00:00Z',
        updatedAt: '2026-05-17T10:00:00Z',
      });
    }

    if (pathname === '/api/chat/ask' && method === 'POST') {
      return json({
        user_message: {
          id: 'msg-user-1',
          role: 'user',
          content: 'Tai lieu noi ve phong thuy ung dung nhu the nao?',
        },
        assistant_message: {
          id: 'msg-assistant-1',
          role: 'assistant',
          content:
            'Tai lieu giai thich phong thuy ung dung qua viec bo tri khong gian song, anh sang, gio va loi di trong nha. Cau tra loi duoc tao tu cac chunk da truy xuat.',
          confidence: 0.82,
          sourcesJson: JSON.stringify(
            [
              {
                chunk_id: 'chunk-001',
                file_name: 'SACH PHONG THUY UNG DUNG.pdf',
                page_start: 1,
                page_end: 1,
                score: 0.86,
                support_level: 'strong',
              },
            ],
            null,
            2
          ),
          retrievalReportPath: 'demo/retrieval_report.json',
          answerReportPath: 'demo/answer_report.json',
        },
      });
    }

    if (pathname.includes('/api/debug/chat/')) {
      return json({
        message_id: 'msg-assistant-1',
        selected_chunks: ['chunk-001'],
        reason: 'Demo report for portfolio screenshot.',
      });
    }

    return json({ message: `No mock response for ${method} ${pathname}` }, 404);
  });
}

async function capture(page, fileName, routePath, waitText) {
  const target = `${baseUrl}${routePath}`;
  try {
    await page.goto(target, { waitUntil: 'networkidle', timeout: 30000 });
    if (waitText) {
      await page.getByText(waitText, { exact: false }).first().waitFor({ timeout: 10000 });
    }
    const outputPath = path.join(outputDir, fileName);
    await page.screenshot({ path: outputPath, fullPage: false });
    return outputPath;
  } catch (error) {
    console.warn(`[screenshots] warning: skipped ${routePath}: ${error.message}`);
    return null;
  }
}

async function authenticate(page) {
  if (useMocks) {
    await page.addInitScript(() => {
      localStorage.setItem('token', 'demo-token-for-screenshots');
      localStorage.setItem('user', JSON.stringify({ id: 'demo-user', email: 'demo@example.com', fullName: 'Demo User' }));
    });
    return true;
  }

  if (!email || !password) {
    console.warn('[screenshots] warning: E2E_EMAIL/E2E_PASSWORD are missing; auth-only screenshots will be skipped.');
    return false;
  }

  try {
    await page.goto(`${baseUrl}/login`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password').fill(password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL(/\/dashboard/, { timeout: 15000 });
    return true;
  } catch (error) {
    console.warn(`[screenshots] warning: login failed; auth-only screenshots will be skipped: ${error.message}`);
    return false;
  }
}

async function main() {
  fs.mkdirSync(outputDir, { recursive: true });
  const startedFrontend = await ensureFrontend();
  const browser = await chromium.launch({ headless: true });
  const created = [];

  try {
    const publicContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    if (useMocks) await installMockApi(publicContext);
    const loginPage = await publicContext.newPage();
    const loginShot = await capture(loginPage, '01-login.png', '/login', 'RAG Chatbot');
    if (loginShot) created.push(loginShot);
    await publicContext.close();

    const appContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    if (useMocks) await installMockApi(appContext);
    const page = await appContext.newPage();
    const authed = await authenticate(page);

    if (authed) {
      for (const item of [
        ['02-dashboard.png', '/dashboard', 'Dashboard'],
        ['03-upload-pdf.png', '/upload', 'Upload PDF'],
        ['04-document-list.png', '/docs', 'Documents'],
      ]) {
        const shot = await capture(page, item[0], item[1], item[2]);
        if (shot) created.push(shot);
      }

      await page.goto(`${baseUrl}/docs`, { waitUntil: 'networkidle', timeout: 30000 });
      try {
        await page.getByRole('button', { name: /chunk report/i }).first().click();
        await page.locator('h2').filter({ hasText: 'Chunk Report' }).first().waitFor({ timeout: 10000 });
        const shot = path.join(outputDir, '05-chunk-report.png');
        await page.screenshot({ path: shot, fullPage: false });
        created.push(shot);
      } catch (error) {
        console.warn(`[screenshots] warning: skipped chunk report: ${error.message}`);
      }

      await page.goto(`${baseUrl}/chat?docId=demo-doc-1`, { waitUntil: 'networkidle', timeout: 30000 });
      try {
        await page.getByPlaceholder(/type your question/i).fill('Tai lieu noi ve phong thuy ung dung nhu the nao?');
        await page.getByRole('button', { name: /send/i }).click();
        await page.getByText('View Sources').waitFor({ timeout: 10000 });
        await page.getByText('View Sources').click();
        const shot = path.join(outputDir, '06-chat-with-source.png');
        await page.screenshot({ path: shot, fullPage: false });
        created.push(shot);
      } catch (error) {
        console.warn(`[screenshots] warning: skipped chat with source: ${error.message}`);
      }

      await page.goto(`${baseUrl}/docs`, { waitUntil: 'networkidle', timeout: 30000 });
      try {
        await page.getByRole('button', { name: /chunk report/i }).nth(1).click();
        await page.getByText('OCR is required').waitFor({ timeout: 10000 });
        const shot = path.join(outputDir, '07-error-handling.png');
        await page.screenshot({ path: shot, fullPage: false });
        created.push(shot);
      } catch (error) {
        console.warn(`[screenshots] warning: skipped error handling: ${error.message}`);
      }
    }

    await appContext.close();
  } finally {
    await browser.close();
    if (startedFrontend) {
      if (process.platform === 'win32') startedFrontend.kill();
      else process.kill(-startedFrontend.pid);
    }
  }

  if (!created.length) {
    throw new Error('No screenshots were created. Check frontend startup and routes.');
  }

  console.log('[screenshots] created:');
  for (const file of created) {
    console.log(`- ${path.relative(rootDir, file).replaceAll(path.sep, '/')}`);
  }
}

main().catch((error) => {
  console.error(`[screenshots] failed: ${error.message}`);
  process.exit(1);
});
