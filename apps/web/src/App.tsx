import { useEffect } from 'react';
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from 'react-router-dom';

import { AppShell } from './components/AppShell';
import { SetupScreen } from './components/SetupScreen';
import { AUTH_PATHS, AuthRoute, useAuthStore } from './features/auth';
import { CalibrationRoute } from './features/calibration';
import { EditingRoute } from './features/editing';
import { JobProgressRoute, JobsRoute, UploadRoute } from './features/jobs';
import { OverlayRoute } from './features/overlays';
import { ViewerRoute } from './features/viewer';
import { usePageTitle } from './hooks/usePageTitle';
import { titleForPath } from './lib/pageTitle';

function AuthBootstrap() {
  const initialize = useAuthStore((state) => state.initialize);
  useEffect(() => {
    void initialize();
  }, [initialize]);
  return null;
}

function AuthPages({ page }: { page: 'login' | 'signup' | 'reset' }) {
  const navigate = useNavigate();
  return (
    <AuthRoute
      page={page}
      onAuthenticated={() => navigate('/jobs', { replace: true })}
      onNavigate={(next) => navigate(AUTH_PATHS[next])}
    />
  );
}

function RouteTitle() {
  const { pathname } = useLocation();
  usePageTitle(titleForPath(pathname));
  return null;
}

function JobsPage() {
  const navigate = useNavigate();
  return (
    <JobsRoute
      onOpenJob={(id) => navigate(`/jobs/${id}`)}
      onNewUpload={() => navigate('/upload')}
      onOpenScene={(id) => navigate(`/viewer?job=${encodeURIComponent(id)}`)}
    />
  );
}

function UploadPage() {
  const navigate = useNavigate();
  return (
    <UploadRoute onSubmitted={(id) => navigate(`/jobs/${id}`)} onCancel={() => navigate('/jobs')} />
  );
}

function JobProgressPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  return (
    <JobProgressRoute
      jobId={id}
      onOpenScene={(jobId) => navigate(`/viewer?job=${encodeURIComponent(jobId)}`)}
      onBack={() => navigate('/jobs')}
    />
  );
}

function ViewerPage() {
  const { jobId: pathId } = useParams();
  const [search] = useSearchParams();
  const jobId = pathId ?? search.get('job') ?? search.get('jobId') ?? undefined;
  const sceneId = search.get('sceneId') ?? undefined;
  return <ViewerRoute jobId={jobId} sceneId={sceneId} />;
}

function EditingPage() {
  const [search] = useSearchParams();
  return (
    <EditingRoute
      jobId={search.get('job') ?? search.get('jobId') ?? undefined}
      sceneId={search.get('sceneId') ?? undefined}
    />
  );
}

function CalibrationPage() {
  const [search] = useSearchParams();
  return (
    <CalibrationRoute
      jobId={search.get('job') ?? search.get('jobId') ?? undefined}
      sceneId={search.get('sceneId') ?? undefined}
    />
  );
}

function OverlayPage() {
  const [search] = useSearchParams();
  return (
    <OverlayRoute
      jobId={search.get('job') ?? search.get('jobId') ?? undefined}
      sceneId={search.get('sceneId') ?? undefined}
    />
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthBootstrap />
      <RouteTitle />
      <Routes>
        <Route path="/login" element={<AuthPages page="login" />} />
        <Route path="/signup" element={<AuthPages page="signup" />} />
        <Route path="/reset" element={<AuthPages page="reset" />} />
        <Route path="/setup" element={<SetupScreen />} />
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/jobs" replace />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/jobs/:id" element={<JobProgressPage />} />
          <Route path="/viewer" element={<ViewerPage />} />
          <Route path="/viewer/:jobId" element={<ViewerPage />} />
          <Route path="/editing" element={<EditingPage />} />
          <Route path="/calibration" element={<CalibrationPage />} />
          <Route path="/overlays" element={<OverlayPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/jobs" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
