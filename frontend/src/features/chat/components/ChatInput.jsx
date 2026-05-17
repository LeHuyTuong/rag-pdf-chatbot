import React from 'react';

export default function ChatInput({ inputRef, value, setValue, disabled, sending, onSubmit, onClear }) {
  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  }

  return (
    <div className="border-t border-slate-100 p-4 bg-white">
      <div className="flex gap-3 items-end">
        <div className="flex-1 relative">
          <textarea
            ref={inputRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={disabled ? 'Select a document first...' : 'Type your question here... (Enter to send)'}
            disabled={disabled || sending}
            rows={1}
            className="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm resize-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all placeholder:text-slate-400 disabled:bg-slate-50 disabled:cursor-not-allowed"
            style={{ minHeight: '42px', maxHeight: '120px' }}
            onInput={(e) => {
              e.target.style.height = 'auto';
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
            }}
          />
        </div>
        <button onClick={onClear} className="p-2.5 rounded-xl border border-slate-200 text-slate-400 hover:text-slate-600 hover:bg-slate-50 transition-all" title="Clear chat">
          Clear
        </button>
        <button onClick={onSubmit} disabled={disabled || !value.trim() || sending} className="flex items-center justify-center w-[42px] h-[42px] rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md shadow-blue-200 shrink-0">
          Send
        </button>
      </div>
      <p className="text-[11px] text-slate-400 mt-2 text-center">Press Enter to send, Shift+Enter for new line</p>
    </div>
  );
}
