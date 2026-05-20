import React from 'react';
import ChatMessageItem from './ChatMessageItem';
import TypingIndicator from './TypingIndicator';

export default function ChatMessageList({ messages, sending, onOpenReport, onSuggestedQuestion, debugMode = false, children }) {
  const visibleMessages = messages || [];
  const hasLoadingMessage = visibleMessages.some((message) => message.loading);

  return (
    <div className="flex-1 overflow-y-auto p-4 lg:p-6 space-y-4 bg-gradient-to-b from-slate-50/50 to-white">
      {children}
      {visibleMessages.map((message, index) => (
        <ChatMessageItem key={message.id || index} message={message} onOpenReport={onOpenReport} onSuggestedQuestion={onSuggestedQuestion} debugMode={debugMode} />
      ))}
      {sending && !hasLoadingMessage && <TypingIndicator />}
    </div>
  );
}
