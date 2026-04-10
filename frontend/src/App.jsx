import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useSearchParams, useNavigate } from 'react-router-dom';
import Login from './pages/Login';
import AdminLogin from './pages/AdminLogin';
import Signup from './pages/Signup';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';

// Dashboard Pages
import Dashboard from './pages/Dashboard';
import Leads from './pages/Leads';
import LeadDetail from './pages/LeadDetail';
import Campaigns from './pages/Campaigns';
import Emails from './pages/Emails';
import EditEmail from './pages/EditEmail';
import Prompts from './pages/Prompts';
import Metrics from './pages/Metrics';
import Users from './pages/Users';
import FamilyOffices from './pages/FamilyOffices';
import FamilyOfficeDetail from './pages/FamilyOfficeDetail';
import GenerateSector from './pages/GenerateSector';
import BulkSearch from './pages/BulkSearch';
import CompanyDatabase from './pages/CompanyDatabase';
import History from './pages/History';

const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('token') || localStorage.getItem('token_admin');
  if (!token || token === 'undefined') {
    return <Navigate to="/login" replace />;
  }
  return children;
};

const AdminRoute = ({ children }) => {
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const token = localStorage.getItem('token') || localStorage.getItem('token_admin');
  if (!token || user.role !== 'ADMIN') {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
};

const PublicRoute = ({ children }) => {
  const token = localStorage.getItem('token') || localStorage.getItem('token_admin');
  if (token && token !== 'undefined') {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
};

function App() {
  const [isInitializing, setIsInitializing] = React.useState(true);
  const [token, setToken] = React.useState(null);

  React.useEffect(() => {
    // Synchronous-like initialization to prevent refresh-redirect bug
    const storedToken = localStorage.getItem('token') || localStorage.getItem('token_admin');
    setToken(storedToken);
    setIsInitializing(false);
  }, []);

  if (isInitializing) {
    return (
      <div className="min-h-screen bg-[#0b0f19] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-slate-500 font-black uppercase tracking-[4px] text-[10px]">Synchronizing Session...</p>
        </div>
      </div>
    );
  }

  return (
    <Router>
      {/* Global Background */}
      <div className="bg-grid"></div>
      <div className="orb orb-1"></div>
      <div className="orb orb-2"></div>
      <div className="orb orb-3"></div>

      <Routes>
        <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
        <Route path="/admin" element={<PublicRoute><AdminLogin /></PublicRoute>} />
        <Route path="/signup" element={<PublicRoute><Signup /></PublicRoute>} />

        {/* Authenticated Dashboard Routes */}
        <Route path="/dashboard" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<Dashboard />} />
          <Route path="leads" element={<Leads />} />
          <Route path="leads/:leadId" element={<LeadDetail />} />
          <Route path="campaigns" element={<Campaigns />} />
          <Route path="emails" element={<Emails />} />
          <Route path="emails/:draftId/edit" element={<EditEmail />} />
          <Route path="prompts" element={<Prompts />} />
          <Route path="metrics" element={<Metrics />} />
          <Route path="users" element={<Users />} />
          <Route path="family-offices" element={<FamilyOffices />} />
          <Route path="family-offices/:officeId" element={<ErrorBoundary><FamilyOfficeDetail /></ErrorBoundary>} />
          {/* <Route path="generate" element={<GenerateSector />} /> */}
          <Route path="bulk-search" element={<BulkSearch />} />
          <Route path="companies" element={<CompanyDatabase />} />
          <Route path="history" element={<AdminRoute><History /></AdminRoute>} />
        </Route>

        {/* Root Redirect */}
        <Route path="/" element={<Navigate to={token ? "/dashboard" : "/login"} replace />} />

        {/* Redirect unknown routes */}
        <Route path="*" element={<Navigate to={token ? "/dashboard" : "/login"} replace />} />
      </Routes>
    </Router>
  );
}

export default App;
