function messageTime(message) {
  if (!message?.createdAt) return Number.POSITIVE_INFINITY;
  const time = new Date(message.createdAt).getTime();
  return Number.isFinite(time) ? time : Number.POSITIVE_INFINITY;
}

export function sortMessagesByCreatedAtAsc(messages) {
  return [...(messages || [])].sort((left, right) => messageTime(left) - messageTime(right));
}

export function appendPendingExchange(messages, { userPendingId, assistantPendingId, question, createdAt = new Date() }) {
  const userCreatedAt = createdAt.toISOString();
  const assistantCreatedAt = new Date(createdAt.getTime() + 1).toISOString();

  return [
    ...(messages || []),
    {
      id: userPendingId,
      role: 'user',
      content: question,
      loading: false,
      createdAt: userCreatedAt,
    },
    {
      id: assistantPendingId,
      role: 'assistant',
      content: 'Đang trả lời...',
      loading: true,
      createdAt: assistantCreatedAt,
    },
  ];
}

export function replacePendingExchange(messages, { userPendingId, assistantPendingId, userMessage, assistantMessage }) {
  return (messages || []).map((message) => {
    if (message.id === userPendingId) return userMessage;
    if (message.id === assistantPendingId) return assistantMessage;
    return message;
  });
}

export function removePendingExchange(messages, pendingIds) {
  const ids = new Set(pendingIds);
  return (messages || []).filter((message) => !ids.has(message.id));
}
