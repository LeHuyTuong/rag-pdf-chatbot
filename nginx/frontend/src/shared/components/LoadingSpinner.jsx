import React from 'react';

export default function LoadingSpinner({ large = false }) {
  return <div className={`spinner ${large ? 'spinner-lg' : ''}`} />;
}
