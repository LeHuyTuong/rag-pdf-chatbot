import React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import Sidebar from './layout/Sidebar';
import ProtectedRoute from './routes/ProtectedRoute';
import LoginPage from '../features/auth/pages/LoginPage';
import DashboardPage from '../features/dashboard/pages/DashboardPage';
import UploadPage from '../features/documents/pages/UploadPage';
import DocumentsPage from '../features/documents/pages/DocumentsPage';
import ChatPage from '../features/chat/pages/ChatPage';
import EvalPage from '../features/evaluation/pages/EvalPage';
import { useAuth } from '../features/auth/providers/AuthProvider';

export default function App() {
  const auth = useAuth();

  if (!auth.token) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100">
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100 flex">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="p-6 lg:p-8 max-w-7xl mx-auto">
          <Routes>
            <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
            <Route path="/upload" element={<ProtectedRoute><UploadPage /></ProtectedRoute>} />
            <Route path="/docs" element={<ProtectedRoute><DocumentsPage /></ProtectedRoute>} />
            <Route path="/chat" element={<ProtectedRoute><ChatPage /></ProtectedRoute>} />
            <Route path="/eval" element={<ProtectedRoute><EvalPage /></ProtectedRoute>} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}
