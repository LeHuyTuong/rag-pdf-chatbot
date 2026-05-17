import React from 'react';
import ChatMessageItem from './ChatMessageItem';
import TypingIndicator from './TypingIndicator';

export default function ChatMessageList({ messages, sending, onOpenReport, children }) {
  return (
    <div className="flex-1 overflow-y-auto p-4 lg:p-6 space-y-4 bg-gradient-to-b from-slate-50/50 to-white">
      {children}
      {messages.map((message, index) => (
        <ChatMessageItem key={message.id || index} message={message} onOpenReport={onOpenReport} />
      ))}
      {sending && <TypingIndicator />}
    </div>
  );
}
