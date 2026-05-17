import React from 'react';
import { useSearchParams } from 'react-router-dom';
import useDocuments from '../../documents/hooks/useDocuments';
import useChat from '../hooks/useChat';
import ChatBox from '../components/ChatBox';
import ChatSessionSidebar from '../components/ChatSessionSidebar';
import SourceChunkPanel from '../components/SourceChunkPanel';
import ErrorState from '../../../shared/components/ErrorState';
import LoadingSpinner from '../../../shared/components/LoadingSpinner';

export default function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedDocumentId = searchParams.get('docId') || '';
  const { documents, error: documentsError, loading } = useDocuments();
  const chat = useChat(selectedDocumentId);
  const selectedDocument = documents.find((document) => document.id === selectedDocumentId);

  function selectDocument(documentId) {
    setSearchParams(documentId ? { docId: documentId } : {});
    chat.newChat();
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner large />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)] animate-fade-in">
      <div className="flex items-center justify-between mb-4 shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Chat</h1>
          <p className="text-slate-500 mt-1">Ask questions about your documents</p>
        </div>
      </div>

      <ErrorState message={documentsError} />

      <div className="flex-1 flex flex-col lg:flex-row gap-4 min-h-0">
        <ChatSessionSidebar
          documents={documents}
          selectedDocumentId={selectedDocumentId}
          onSelectDocument={selectDocument}
          onNewChat={chat.newChat}
          hasChat={chat.sessionId || chat.messages.length > 0}
        />
        <ChatBox
          selectedDocument={selectedDocument}
          messages={chat.messages}
          sending={chat.sending}
          question={chat.question}
          setQuestion={chat.setQuestion}
          error={chat.error}
          onAsk={chat.ask}
          onClear={chat.newChat}
          onOpenReport={chat.openReport}
        />
      </div>

      <SourceChunkPanel report={chat.report} onClose={() => chat.setReport(null)} />
    </div>
  );
}
