import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useSearchParams, useNavigate } from 'react-router-dom';
import Login from './pages/Login';
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

const AuthHandler = ({ children }) => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const token = searchParams.get('token');
    const userStr = searchParams.get('user');

    if (token && token !== 'undefined') {
      localStorage.setItem('token', token);
      if (userStr) {
        try {
          // Verify it's valid JSON
          JSON.parse(decodeURIComponent(userStr));
          localStorage.setItem('user', decodeURIComponent(userStr));
        } catch (e) {
          console.error("Failed to parse user data from Google login", e);
        }
      }
      // Clean URL and refresh dashboard state
      navigate('/dashboard', { replace: true });
    }
  }, [searchParams, navigate]);

  return children;
};

function App() {
  return (
    <Router>
      {/* Global Background (from login style but moved to root layout) */}
      <div className="bg-grid"></div>
      <div className="orb orb-1"></div>
      <div className="orb orb-2"></div>
      <div className="orb orb-3"></div>

      <AuthHandler>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />

          {/* Authenticated Dashboard Routes */}
          <Route path="/dashboard" element={<Layout />}>
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
            <Route path="generate" element={<GenerateSector />} />
            <Route path="bulk-search" element={<BulkSearch />} />
            <Route path="companies" element={<CompanyDatabase />} />
          </Route>

          {/* Root Redirect */}
          <Route path="/" element={<Navigate to="/login" replace />} />

          {/* Redirect unknown routes to login */}
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </AuthHandler>
    </Router>
  );
}

export default App;
