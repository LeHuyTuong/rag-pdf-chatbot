import React from 'react';
import { Link } from 'react-router-dom';

const metrics = [
  { name: 'Answer Accuracy', desc: 'Measures how accurate the generated answers are', color: 'bg-blue-50 text-blue-700 border-blue-100' },
  { name: 'Retrieval Hit Rate', desc: 'Checks if relevant chunks are retrieved properly', color: 'bg-violet-50 text-violet-700 border-violet-100' },
  { name: 'Citation Accuracy', desc: 'Verifies that citations match the source content', color: 'bg-emerald-50 text-emerald-700 border-emerald-100' },
  { name: 'Faithfulness Score', desc: 'Ensures answers stay faithful to the source documents', color: 'bg-amber-50 text-amber-700 border-amber-100' },
  { name: 'Refusal Accuracy', desc: 'Measures how well the system refuses out-of-scope questions', color: 'bg-rose-50 text-rose-700 border-rose-100' },
];

export default function EvalPage() {
  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Evaluation</h1>
        <p className="text-slate-500 mt-1">System evaluation metrics and reports</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="lg:col-span-2 bg-white rounded-2xl border border-slate-100 p-6 space-y-5">
          <div>
            <h2 className="text-lg font-semibold text-slate-800">How to Run Evaluation</h2>
            <p className="text-sm text-slate-500 mt-1">The evaluation command checks answer quality against prepared test data.</p>
          </div>

          <div className="bg-slate-50 rounded-xl p-4">
            <p className="text-sm font-medium text-slate-700 mb-2">Run the evaluation command:</p>
            <div className="bg-slate-800 rounded-xl p-4">
              <code className="text-sm text-emerald-400 font-mono">python eval/run_eval.py</code>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">Available Metrics</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {metrics.map((metric) => (
                <div key={metric.name} className={`rounded-xl border p-3.5 ${metric.color}`}>
                  <p className="text-sm font-semibold">{metric.name}</p>
                  <p className="text-xs mt-0.5 opacity-80">{metric.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <aside className="space-y-4">
          <div className="bg-white rounded-2xl border border-slate-100 p-5">
            <h3 className="font-semibold text-slate-800 mb-3">Quick Links</h3>
            <div className="space-y-2">
              <Link to="/docs" className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-slate-50 text-sm text-slate-600 hover:text-slate-800 transition-all">
                View Documents
              </Link>
              <Link to="/chat" className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-slate-50 text-sm text-slate-600 hover:text-slate-800 transition-all">
                Test with Chat
              </Link>
            </div>
          </div>

          <div className="bg-gradient-to-br from-blue-600 to-indigo-600 rounded-2xl p-5 text-white">
            <h3 className="font-semibold mb-1">Evaluation Status</h3>
            <p className="text-sm text-blue-100">Use the script-based report for now; UI-driven eval dashboards can be added later.</p>
          </div>
        </aside>
      </div>
    </div>
  );
}
