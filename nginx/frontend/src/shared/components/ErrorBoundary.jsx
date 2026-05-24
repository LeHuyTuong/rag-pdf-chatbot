import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-slate-50 p-6 text-slate-800">
          <div className="mx-auto max-w-2xl rounded-xl border border-red-200 bg-white p-5 shadow-sm">
            <h1 className="text-lg font-semibold text-red-700">Frontend runtime error</h1>
            <p className="mt-2 text-sm text-slate-600">React crashed while rendering. Check the browser console for the full stack trace.</p>
            <pre className="mt-4 overflow-auto rounded-lg bg-slate-900 p-4 text-xs text-white">
              {String(this.state.error?.message || this.state.error)}
            </pre>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
