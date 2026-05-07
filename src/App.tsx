import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Applications from './pages/Applications';
import ApplicationDetail from './pages/ApplicationDetail';
import NewApplication from './pages/NewApplication';
import GoldenRecords from './pages/GoldenRecords';
import Classifications from './pages/Classifications';
import AuditTrace from './pages/AuditTrace';
import MetadataGovernance from './pages/MetadataGovernance';

const App: React.FC = () => {
  return (
    <Router>
      <Toaster position="top-right" richColors />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/applications" element={<Applications />} />
          <Route path="/applications/new" element={<NewApplication />} />
          <Route path="/applications/:id" element={<ApplicationDetail />} />
          <Route path="/golden-records" element={<GoldenRecords />} />
          <Route path="/metadata-governance" element={<MetadataGovernance />} />
          <Route path="/classifications" element={<Classifications />} />
          <Route path="/audit/:id" element={<AuditTrace />} />
        </Route>
      </Routes>
    </Router>
  );
};

export default App;