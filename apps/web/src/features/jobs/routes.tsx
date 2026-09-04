import { JobProgressScreen, type JobProgressScreenProps } from './JobProgressScreen';
import { JobsListPage, type JobsListPageProps } from './JobsListPage';
import { UploadWizard, type UploadWizardProps } from './UploadWizard';

export function JobsRoute(props: JobsListPageProps) {
  return <JobsListPage {...props} />;
}

export function UploadRoute(props: UploadWizardProps) {
  return <UploadWizard {...props} />;
}

export interface JobProgressRouteProps extends Omit<JobProgressScreenProps, 'jobId'> {
  jobId?: string;
}

function jobIdFromSearch(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  const params = new URLSearchParams(window.location.search);
  return params.get('job') ?? params.get('id');
}

function jobIdFromPath(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  const match = window.location.pathname.match(/\/jobs\/([^/]+)/);
  return match?.[1] ?? null;
}

export function JobProgressRoute({ jobId, ...props }: JobProgressRouteProps) {
  const resolved = jobId ?? jobIdFromPath() ?? jobIdFromSearch();
  if (!resolved) {
    return (
      <main className="jobs-screen">
        <h1>Job não informado</h1>
        <p className="muted">A consolidação deve passar `jobId` ou usar a rota `/jobs/:id`.</p>
      </main>
    );
  }
  return <JobProgressScreen jobId={resolved} {...props} />;
}
