import type { ApiError } from "../../lib/api";
import { friendlyMessage } from "../../lib/errors";

/** A plain sentence for the visitor (lib/errors.ts). The request id is shown only in the details
 * view (?details=1), for debugging; it is never part of the normal page. */
export function ErrorView({ error, details }: { error: ApiError; details: boolean }) {
  return (
    <div className="card error" role="alert">
      <p className="state-label">I couldn&rsquo;t answer that</p>
      <p>{friendlyMessage(error)}</p>
      {details && error.request_id ? <p className="muted small">Request id: {error.request_id}</p> : null}
    </div>
  );
}
