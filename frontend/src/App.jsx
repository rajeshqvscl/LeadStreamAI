import React, { Suspense, useSearchParams, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';

// Lazy-loaded ALL pages (code-split for faster initial load)
const Login = lazy(() => import('./pages/Login'));
const AdminLogin = lazy(() => import('./pages/AdminLogin'));
const Signup = lazy(() => import('./pages/Signup'));
const Layout = lazy(() => import('./components/Layout'));
const Unsubscribe = lazy(() => import('./public_pages/Unsubscribe'));
const UnsubscribeSuccess = lazy(() => import('./public_pages/UnsubscribeSuccess'));
const Resubscribe = lazy(() => import('./public_pages/Resubscribe'));

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Leads = lazy(() => import('./pages/Leads'));
const LeadDetail = lazy(() => import('./pages/LeadDetail'));
const Emails = lazy(() => import('./pages/Emails'));
const EditEmail = lazy(() => import('./pages/EditEmail'));
const Prompts = lazy(() => import('./pages/Prompts'));
const Signatures = lazy(() => import('./pages/Signatures'));
const Metrics = lazy(() => import('./pages/Metrics'));
const MisReportPage = lazy(() => import('./pages/MisReportPage'));
const Users = lazy(() => import('./pages/Users'));
const FamilyOffices = lazy(() => import('./pages/FamilyOffices'));
const FamilyOfficeDetail = lazy(() => import('./pages/FamilyOfficeDetail'));
const BulkSearch = lazy(() => import('./pages/BulkSearch'));
const CompanyDatabase = lazy(() => import('./pages/CompanyDatabase'));
const History = lazy(() => import('./pages/History'));
const Followups = lazy(() => import('./pages/Followups'));
const RocketReach = lazy(() => import('./pages/RocketReach'));
const Inbox = lazy(() => import('./pages/Inbox'));
const InboundDeals = lazy(() => import('./pages/InboundDeals'));
const DealIntelligence = lazy(() => import('./pages/DealIntelligence'));
const Meetings = lazy(() => import('./pages/Meetings'));
const GmailDrafts = lazy(() => import('./pages/GmailDrafts'));
const GmailSent = lazy(() => import('./pages/GmailSent'));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));
const AdminAuditLogs = lazy(() => import('./pages/AdminAuditLogs'));
const Settings = lazy(() => import('./pages/Settings'));

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
            <Route path="settings" element={<Settings />} />
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