import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
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

function App() {
  return (
    <Router>
      {/* Global Background (from login style but moved to root layout) */}
      <div className="bg-grid"></div>
      <div className="orb orb-1"></div>
      <div className="orb orb-2"></div>
      <div className="orb orb-3"></div>
      
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
        </Route>

        {/* Root Redirect */}
        <Route path="/" element={<Navigate to="/login" replace />} />
        
        {/* Redirect unknown routes to login */}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
