import type { ApiError } from "../../lib/api";

/** Shows the API's own message and request id, or the fixed "could not reach" message. Nothing else. */
export function ErrorView({ error }: { error: ApiError }) {
  return (
    <div className="card error" role="alert">
      <p className="state-label">Something went wrong</p>
      <p>{error.message}</p>
      {error.request_id ? <p className="muted small">Request id: {error.request_id}</p> : null}
    </div>
  );
}
