// The privacy notice text. Each sentence is checked against the code (migration 005, the log
// writer, the purge command) by tests/test_requestlog.py; change them together.

export const NOTICE_SHORT =
  "Your questions are saved without emails, phone numbers or ID numbers, to improve this assistant. Please don't type personal information.";

export const NOTICE_TITLE = "What is saved?";

export const NOTICE_POINTS: string[] = [
  "Questions and answers are saved for 30 days with emails, phone numbers and ID numbers removed. Older ones are deleted by a clean-up command that is run by hand for now.",
  "A name is removed only when it follows \"my name is\"; other names are not removed, so please don't type personal information.",
  "Also saved: which pages were used, how long each step took, and what the request cost (numbers only).",
  "If you press the thumbs up or down, that vote is saved with the answer. Nothing else is saved with it.",
  "No IP address and no cookies are stored.",
  "To prevent abuse, requests are counted in memory per visitor using a scrambled form of the network address that is never saved; the count is cleared when the service restarts.",
  "Optional developer tracing is off by default. If it is switched on for debugging, only the question text after personal details are removed, and the assistant's reply, are sent to LangSmith (a third party); no IP address and no cookies are sent.",
  "This is an unofficial student project, not affiliated with City Tech.",
];
