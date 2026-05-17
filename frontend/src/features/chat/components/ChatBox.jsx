import React, { useEffect, useRef } from 'react';
import ChatInput from './ChatInput';
import ChatMessageList from './ChatMessageList';
import ErrorState from '../../../shared/components/ErrorState';

export default function ChatBox({ selectedDocument, messages, sending, question, setQuestion, error, onAsk, onClear, onOpenReport }) {
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  useEffect(() => {
    if (selectedDocument) {
      inputRef.current?.focus();
    }
  }, [selectedDocument?.id]);

  return (
    <section className="flex-1 flex flex-col bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden min-h-[30rem]">
      <ChatMessageList messages={messages} sending={sending} onOpenReport={onOpenReport}>
        {!selectedDocument && (
          <div className="flex flex-col items-center justify-center h-full min-h-80 text-center">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center mb-4 text-blue-500 font-semibold">
              Chat
            </div>
            <h3 className="text-lg font-semibold text-slate-600 mb-1">Start a Conversation</h3>
            <p className="text-sm text-slate-400 max-w-sm">Select a document to begin asking questions about its content.</p>
          </div>
        )}

        {selectedDocument && messages.length === 0 && !sending && (
          <div className="flex flex-col items-center justify-center h-full min-h-80 text-center">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-emerald-50 to-teal-50 flex items-center justify-center mb-4 text-emerald-600 font-semibold">
              Ask
            </div>
            <h3 className="text-lg font-semibold text-slate-600 mb-1">Ask about "{selectedDocument.originalFileName}"</h3>
            <p className="text-sm text-slate-400 max-w-sm">Type your question below and get answers based on retrieved chunks.</p>
          </div>
        )}

        <ErrorState message={error} />
        <div ref={messagesEndRef} />
      </ChatMessageList>

      <ChatInput
        inputRef={inputRef}
        value={question}
        setValue={setQuestion}
        disabled={!selectedDocument}
        sending={sending}
        onSubmit={onAsk}
        onClear={onClear}
      />
    </section>
  );
}
