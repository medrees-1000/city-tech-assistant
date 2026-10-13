import type { AskResponse } from "../../lib/api";
import { describe } from "../../lib/howfound";

/** The collapsed "How this was found" toggle under an answer. Everything shown comes from the API's
 * how_found data, in plain sentences built by lib/howfound.ts. */
export function HowFound({ data }: { data: AskResponse }) {
  const view = describe(data);
  return (
    <details className="howfound">
      <summary>How this was found</summary>
      <div className="hf-body">
        {view.sections.map((section) => (
          <section key={section.title}>
            <h4 className="hf-title">{section.title}</h4>
            <ul>
              {section.lines.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </details>
  );
}
