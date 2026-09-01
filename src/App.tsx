import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import DataStandards from './pages/DataStandards';
import QualityChecks from './pages/QualityChecks';
import QualityReport from './pages/QualityReport';
import Copilot from './pages/Copilot';
import GovernanceDashboard from './pages/GovernanceDashboard';
import AgentActivity from './pages/AgentActivity';
import DisputeView from './pages/DisputeView';

const App: React.FC = () => {
  return (
    <Router>
      <Toaster position="top-right" richColors />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/quality" element={<Navigate to="/quality/standards" replace />} />
          <Route path="/quality/standards" element={<DataStandards />} />
          <Route path="/quality/checks" element={<QualityChecks />} />
          <Route path="/quality/checks/report" element={<QualityReport />} />
          <Route path="/copilot" element={<Copilot />} />
          <Route path="/governance" element={<GovernanceDashboard />} />
          <Route path="/agents" element={<AgentActivity />} />
          <Route path="/disputes" element={<DisputeView />} />
        </Route>
      </Routes>
    </Router>
  );
};

export default App;