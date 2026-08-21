import React, { Suspense, useSearchParams } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import AdminLogin from './pages/AdminLogin';
import Signup from './pages/Signup';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import Unsubscribe from './public_pages/Unsubscribe';
import UnsubscribeSuccess from './public_pages/UnsubscribeSuccess';
import Resubscribe from './public_pages/Resubscribe';

// Lazy-loaded pages (code-split for faster initial load)
const Dashboard = React.lazy(() => import('./pages/Dashboard'));
const Leads = React.lazy(() => import('./pages/Leads'));
const LeadDetail = React.lazy(() => import('./pages/LeadDetail'));
const Emails = React.lazy(() => import('./pages/Emails'));
const EditEmail = React.lazy(() => import('./pages/EditEmail'));
const Prompts = React.lazy(() => import('./pages/Prompts'));
const Signatures = React.lazy(() => import('./pages/Signatures'));
const Metrics = React.lazy(() => import('./pages/Metrics'));
const MisReportPage = React.lazy(() => import('./pages/MisReportPage'));
const Users = React.lazy(() => import('./pages/Users'));
const FamilyOffices = React.lazy(() => import('./pages/FamilyOffices'));
const FamilyOfficeDetail = React.lazy(() => import('./pages/FamilyOfficeDetail'));
const BulkSearch = React.lazy(() => import('./pages/BulkSearch'));
const CompanyDatabase = React.lazy(() => import('./pages/CompanyDatabase'));
const History = React.lazy(() => import('./pages/History'));
const Followups = React.lazy(() => import('./pages/Followups'));
const RocketReach = React.lazy(() => import('./pages/RocketReach'));
const Inbox = React.lazy(() => import('./pages/Inbox'));
const InboundDeals = React.lazy(() => import('./pages/InboundDeals'));
const DealIntelligence = React.lazy(() => import('./pages/DealIntelligence'));
const Meetings = React.lazy(() => import('./pages/Meetings'));
const GmailDrafts = React.lazy(() => import('./pages/GmailDrafts'));
const GmailSent = React.lazy(() => import('./pages/GmailSent'));
const AdminDashboard = React.lazy(() => import('./pages/AdminDashboard'));
const AdminAuditLogs = React.lazy(() => import('./pages/AdminAuditLogs'));

// Page loader component
const PageLoader = () => (
  <div className="min-h-screen bg-[#0b0f19] flex items-center justify-center">
    <div className="flex flex-col items-center gap-4">
      <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
      <p className="text-slate-500 font-black uppercase tracking-[4px] text-[10px]">Loading Page...</p>
    </div>
  </div>
);

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

function RootRedirect({ token }) {
  const [searchParams] = useSearchParams();
  const unsubToken = searchParams.get('token');
  if (unsubToken) {
    return <Unsubscribe />;
  }
  return <Navigate to={token ? "/dashboard" : "/login"} replace />;
}

function CatchAllRedirect({ token }) {
  const [searchParams] = useSearchParams();
  const unsubToken = searchParams.get('token');
  if (unsubToken) {
    return <Unsubscribe />;
  }
  return <Navigate to={token ? "/dashboard" : "/login"} replace />;
}

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

      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
          <Route path="/admin" element={<PublicRoute><AdminLogin /></PublicRoute>} />
          <Route path="/signup" element={<PublicRoute><Signup /></PublicRoute>} />

          {/* Authenticated Dashboard Routes */}
          <Route path="/dashboard" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="leads" element={<Leads />} />
            <Route path="leads/:leadId" element={<LeadDetail />} />
            <Route path="emails" element={<Emails />} />
            <Route path="emails/:draftId/edit" element={<EditEmail />} />
            <Route path="prompts" element={<Prompts />} />
            <Route path="signatures" element={<Signatures />} />
            <Route path="metrics" element={<Metrics />} />
            <Route path="users" element={<Users />} />
            <Route path="family-offices" element={<FamilyOffices />} />
            <Route path="family-offices/:officeId" element={<ErrorBoundary><FamilyOfficeDetail /></ErrorBoundary>} />
            <Route path="bulk-search" element={<BulkSearch />} />
            <Route path="companies" element={<CompanyDatabase />} />
            <Route path="followups" element={<Followups />} />
            <Route path="rocketreach" element={<RocketReach />} />
            <Route path="inbox" element={<Inbox />} />
            <Route path="deals" element={<InboundDeals />} />
            <Route path="intelligence" element={<DealIntelligence />} />
            <Route path="meetings" element={<Meetings />} />
            <Route path="gmail-drafts" element={<GmailDrafts />} />
            <Route path="gmail-sent" element={<GmailSent />} />
            <Route path="admin-intelligence" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
            <Route path="admin-audit-logs" element={<AdminRoute><AdminAuditLogs /></AdminRoute>} />
            <Route path="history" element={<AdminRoute><History /></AdminRoute>} />
          </Route>
          <Route path="/mis-report" element={<ProtectedRoute><MisReportPage /></ProtectedRoute>} />

          {/* Public Unsubscribe Pages — no auth required */}
          <Route path="/unsubscribe" element={<Unsubscribe />} />
          <Route path="/unsubscribe/success" element={<UnsubscribeSuccess />} />
          <Route path="/unsubscribe/resubscribe" element={<Resubscribe />} />

          {/* Root Redirect — also catch /index.html?token=... from Render 301 fallback */}
          <Route path="/" element={<RootRedirect token={token} />} />

          {/* Redirect unknown routes — but check for Render 301 fallback token */}
          <Route path="*" element={<CatchAllRedirect token={token} />} />
        </Routes>
      </Suspense>
    </Router>
  );
}

export default App;