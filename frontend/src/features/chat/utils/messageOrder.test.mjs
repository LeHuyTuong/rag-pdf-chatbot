import test from 'node:test';
import assert from 'node:assert/strict';

import {
  appendPendingExchange,
  removePendingExchange,
  replacePendingExchange,
  sortMessagesByCreatedAtAsc,
} from './messageOrder.mjs';

test('sortMessagesByCreatedAtAsc copies and sorts without mutating the original array', () => {
  const original = [
    { id: 'newer', createdAt: '2026-05-20T03:00:00.000Z' },
    { id: 'older', createdAt: '2026-05-20T01:00:00.000Z' },
  ];

  const sorted = sortMessagesByCreatedAtAsc(original);

  assert.deepEqual(sorted.map((message) => message.id), ['older', 'newer']);
  assert.deepEqual(original.map((message) => message.id), ['newer', 'older']);
  assert.notEqual(sorted, original);
});

test('pending chat exchange is appended and replaced in place', () => {
  const initial = [{ id: 'assistant-old', role: 'assistant', content: 'Cũ' }];
  const pending = appendPendingExchange(initial, {
    userPendingId: 'pending-user',
    assistantPendingId: 'pending-assistant',
    question: 'Vì sao Việt Nam phải Đổi mới?',
    createdAt: new Date('2026-05-20T04:00:00.000Z'),
  });

  assert.deepEqual(pending.map((message) => message.id), ['assistant-old', 'pending-user', 'pending-assistant']);
  assert.equal(pending[2].role, 'assistant');
  assert.equal(pending[2].loading, true);

  const replaced = replacePendingExchange(pending, {
    userPendingId: 'pending-user',
    assistantPendingId: 'pending-assistant',
    userMessage: { id: 'user-db', role: 'user', content: 'Vì sao Việt Nam phải Đổi mới?' },
    assistantMessage: { id: 'assistant-db', role: 'assistant', content: 'Vì context cho thấy...' },
  });

  assert.deepEqual(replaced.map((message) => message.id), ['assistant-old', 'user-db', 'assistant-db']);
});

test('pending chat exchange rolls back both placeholder messages', () => {
  const messages = [
    { id: 'old' },
    { id: 'pending-user' },
    { id: 'pending-assistant' },
  ];

  const rolledBack = removePendingExchange(messages, ['pending-user', 'pending-assistant']);

  assert.deepEqual(rolledBack.map((message) => message.id), ['old']);
});
