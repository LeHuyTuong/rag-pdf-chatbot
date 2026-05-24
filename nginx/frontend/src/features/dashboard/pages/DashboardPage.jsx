import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getDashboard } from '../api/dashboardApi';
import ErrorState from '../../../shared/components/ErrorState';
import LoadingSpinner from '../../../shared/components/LoadingSpinner';
import { getErrorMessage } from '../../../shared/utils/errors';

const statDefinitions = [
  { key: 'totalDocuments', label: 'Documents', color: 'from-blue-500 to-blue-600', bg: 'bg-blue-50', textColor: 'text-blue-600' },
  { key: 'totalChatSessions', label: 'Chat Sessions', color: 'from-violet-500 to-violet-600', bg: 'bg-violet-50', textColor: 'text-violet-600' },
  { key: 'totalMessages', label: 'Messages', color: 'from-emerald-500 to-emerald-600', bg: 'bg-emerald-50', textColor: 'text-emerald-600' },
];

const quickActions = [
  { label: 'Upload Document', to: '/upload', color: 'hover:bg-blue-50 hover:text-blue-600' },
  { label: 'View Documents', to: '/docs', color: 'hover:bg-violet-50 hover:text-violet-600' },
  { label: 'Start Chatting', to: '/chat', color: 'hover:bg-emerald-50 hover:text-emerald-600' },
  { label: 'View Evaluation', to: '/eval', color: 'hover:bg-amber-50 hover:text-amber-600' },
];

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getDashboard()
      .then((dashboard) => {
        if (active) {
          setData(dashboard);
          setError('');
        }
      })
      .catch((err) => active && setError(getErrorMessage(err, 'Failed to load dashboard.')))
      .finally(() => active && setLoading(false));

    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner large />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
        <p className="text-slate-500 mt-1">Overview of your RAG chatbot workspace</p>
      </div>

      <ErrorState message={error} />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {statDefinitions.map((stat, index) => {
          const value = data?.[stat.key] || 0;
          return (
            <div key={stat.key} className="bg-white rounded-2xl border border-slate-100 p-6 card-hover animate-fade-in" style={{ animationDelay: `${index * 100}ms` }}>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-500">{stat.label}</p>
                  <p className={`text-3xl font-bold mt-1 ${stat.textColor}`}>{value.toLocaleString()}</p>
                </div>
                <div className={`w-12 h-12 rounded-xl ${stat.bg} ${stat.textColor} flex items-center justify-center font-semibold`}>{stat.label[0]}</div>
              </div>
              <div className="mt-4 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div className={`h-full rounded-full bg-gradient-to-r ${stat.color} transition-all duration-500`} style={{ width: `${Math.min(value * 10, 100)}%` }} />
              </div>
            </div>
          );
        })}
      </div>

      <section className="bg-white rounded-2xl border border-slate-100 p-6">
        <h2 className="text-lg font-semibold text-slate-800 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {quickActions.map((action) => (
            <Link key={action.to} to={action.to} className={`flex items-center gap-3 p-3.5 rounded-xl bg-slate-50 transition-all group cursor-pointer ${action.color}`}>
              <span className="w-10 h-10 rounded-lg bg-white shadow-sm flex items-center justify-center text-slate-400 group-hover:text-current transition-colors">Go</span>
              <span className="text-sm font-medium">{action.label}</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
