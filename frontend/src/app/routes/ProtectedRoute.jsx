import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../features/auth/providers/AuthProvider';

export default function ProtectedRoute({ children }) {
  const auth = useAuth();
  return auth.token ? children : <Navigate to="/login" replace />;
}
