import { useEffect, useState } from 'react';
import { askQuestion, createChatSession, getActiveChatSession, getChatMessages, getChatReport } from '../api/chatApi';
import { getErrorMessage } from '../../../shared/utils/errors';

const ACTIVE_DOCUMENT_KEY = 'activeDocumentId';
const ACTIVE_SESSION_KEY = 'activeChatSessionId';

export default function useChat(documentId) {
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(ACTIVE_SESSION_KEY));
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [report, setReport] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      if (!documentId) {
        setSessionId(null);
        setMessages([]);
        localStorage.removeItem(ACTIVE_DOCUMENT_KEY);
        localStorage.removeItem(ACTIVE_SESSION_KEY);
        return;
      }

      localStorage.setItem(ACTIVE_DOCUMENT_KEY, documentId);
      setLoadingMessages(true);
      setError('');

      try {
        const session = await getActiveChatSession(documentId);
        if (cancelled) return;
        setSessionId(session.id);
        localStorage.setItem(ACTIVE_SESSION_KEY, session.id);

        const restoredMessages = await getChatMessages(session.id);
        if (cancelled) return;
        setMessages(restoredMessages);
      } catch (err) {
        if (!cancelled) {
          setError(getErrorMessage(err, 'Failed to restore chat history.'));
          setSessionId(null);
          setMessages([]);
          localStorage.removeItem(ACTIVE_SESSION_KEY);
        }
      } finally {
        if (!cancelled) setLoadingMessages(false);
      }
    }

    restoreSession();
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  function newChat() {
    setSessionId(null);
    setMessages([]);
    setQuestion('');
    setError('');
    localStorage.removeItem(ACTIVE_SESSION_KEY);
  }

  async function ensureSession(text) {
    if (sessionId) return sessionId;
    const session = await createChatSession({ documentId, title: text.slice(0, 50) || 'Chat' });
    setSessionId(session.id);
    localStorage.setItem(ACTIVE_SESSION_KEY, session.id);
    return session.id;
  }

  async function ask(textOverride) {
    if (!documentId) {
      setError('Please select a document first.');
      return;
    }
    const text = (textOverride ?? question).trim();
    if (!text) return;

    setQuestion('');
    setError('');
    setSending(true);
    const optimisticId = `pending-${Date.now()}`;
    setMessages((current) => [...current, { id: optimisticId, role: 'user', content: text }]);

    try {
      const activeSessionId = await ensureSession(text);
      const response = await askQuestion({ sessionId: activeSessionId, documentId, question: text });
      setMessages((current) => [
        ...current.filter((message) => message.id !== optimisticId),
        response.user_message,
        response.assistant_message,
      ]);
    } catch (err) {
      setMessages((current) => current.filter((message) => message.id !== optimisticId));
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
    loadingMessages,
    report,
    setReport,
    ask,
    newChat,
    openReport,
  };
}
