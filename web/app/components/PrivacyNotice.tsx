import { NOTICE_POINTS, NOTICE_SHORT, NOTICE_TITLE } from "../../lib/notice";

/** One short line and an expandable list; the text lives in lib/notice.ts. */
export function PrivacyNotice() {
  return (
    <div className="privacy">
      <p>{NOTICE_SHORT}</p>
      <details>
        <summary>{NOTICE_TITLE}</summary>
        <ul>
          {NOTICE_POINTS.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}
