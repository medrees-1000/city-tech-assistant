// The privacy notice text. Each sentence is checked against the code (migration 005, the log
// writer, the purge command) by tests/test_requestlog.py; change them together.

export const NOTICE_SHORT =
  "Your questions are saved to improve this assistant, with emails, phone numbers, ID numbers and names removed where we can detect them. Please don't type personal information.";

/** The one footer line (landing page and chat page). The saved-questions line under it asks for no personal information. */
export const FOOTER_LINE = "Independent student project, not affiliated with City Tech or CUNY";

/** Under the chat bar: the full notice on the landing screen, one short line once a question has been
 * sent. "New chat" empties the list, so it returns to the full notice. */
export type FooterNotice = "full" | "short";

export function footerNotice(messageCount: number): FooterNotice {
  return messageCount > 0 ? "short" : "full";
}

/** The sentence of the short notice; the "What is saved?" link follows it on the same line. */
export const NOTICE_AFTER_FIRST = `City Tech Assistant is AI and can make mistakes. ${FOOTER_LINE}.`;

export const NOTICE_TITLE = "What is saved?";

export const NOTICE_POINTS: string[] = [
  "Questions and answers are saved for 30 days with emails, phone numbers and ID numbers removed. Older ones are deleted automatically every day.",
  "Names are removed from your question where we can detect them (for example after \"my name is\", \"I'm\" or \"this is\"). A name written another way may be saved, so please don't type personal information.",
  "Also saved: which pages were used, how long each step took, and what the request cost (numbers only).",
  "If you press the thumbs up or down, that vote is saved with the answer. Nothing else is saved with it.",
  "Sign-in is by an emailed code through Clerk, a third-party sign-in service, and only Gmail addresses (@gmail.com) can use the assistant. Clerk sets the cookies needed to keep you signed in. We use only the domain of your email to allow Gmail.",
  "No IP address is stored. The assistant's server receives an opaque user id only to confirm that you are signed in. Ids and emails are not stored in our logs, and our own records hold no network address at all.",
  "To prevent abuse, requests are counted in memory per visitor using a scrambled (hashed) form of the network address that is never saved with your questions; the count is cleared when the service restarts.",
  "Your question (after the removals above) and the assistant's reply are also sent to LangSmith, a third-party tracing service, so mistakes can be found and fixed. LangSmith keeps them for 14 days. Messages that the safety checks handle (for example about self-harm, danger or a death), and the fixed reply to off-topic requests, are not sent. No IP address and no cookies are sent.",
  "The page is hosted on Vercel and the assistant runs on Amazon Web Services. They keep ordinary server logs that may include IP addresses, under their own policies.",
  "This is an independent student project, not affiliated with City Tech or CUNY.",
];
