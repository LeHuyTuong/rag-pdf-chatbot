import { useState } from 'react';
import { askQuestion, createChatSession, getChatReport } from '../api/chatApi';
import { getErrorMessage } from '../../../shared/utils/errors';

export default function useChat(documentId) {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const [report, setReport] = useState(null);

  function newChat() {
    setSessionId(null);
    setMessages([]);
    setQuestion('');
    setError('');
  }

  async function ask() {
    if (!documentId) {
      setError('Please select a document first.');
      return;
    }
    if (!question.trim()) return;

    const text = question;
    setQuestion('');
    setError('');
    setSending(true);
    setMessages((current) => [...current, { role: 'user', content: text }]);

    try {
      let activeSessionId = sessionId;
      if (!activeSessionId) {
        const session = await createChatSession({ documentId, title: text.slice(0, 50) || 'Chat' });
        activeSessionId = session.id;
        setSessionId(activeSessionId);
      }

      const response = await askQuestion({ sessionId: activeSessionId, documentId, question: text });
      setMessages((current) => [...current, response.assistant_message]);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to send question.'));
    } finally {
      setSending(false);
    }
  }

  async function openReport(messageId, type) {
    try {
      const data = await getChatReport(messageId, type);
      setReport({ title: `${type === 'retrieval' ? 'Retrieval' : 'Answer'} Report`, data });
      setError('');
    } catch (err) {
      setError(getErrorMessage(err, `Failed to load ${type} report.`));
    }
  }

  return {
    sessionId,
    messages,
    question,
    setQuestion,
    error,
    setError,
    sending,
    report,
    setReport,
    ask,
    newChat,
    openReport,
  };
}
