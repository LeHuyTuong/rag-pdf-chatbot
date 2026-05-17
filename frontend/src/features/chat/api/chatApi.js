import httpClient from '../../../shared/api/httpClient';

export async function createChatSession(payload) {
  const response = await httpClient.post('/api/chat/sessions', payload);
  return response.data;
}

export async function askQuestion(payload) {
  const response = await httpClient.post('/api/chat/ask', payload);
  return response.data;
}

export async function getChatReport(messageId, type) {
  const response = await httpClient.get(`/api/debug/chat/${messageId}/${type}-report`);
  return response.data;
}
