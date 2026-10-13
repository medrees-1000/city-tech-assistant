// The privacy notice text. Each sentence is checked against the code (migration 005, the log
// writer, the purge command) by tests/test_requestlog.py; change them together.

export const NOTICE_SHORT =
  "Your questions are saved without emails, phone numbers or ID numbers, to improve this assistant. Please don't type personal information.";

export const NOTICE_TITLE = "What is saved?";

export const NOTICE_POINTS: string[] = [
  "Questions and answers are saved for 30 days with emails, phone numbers and ID numbers removed. Older ones are deleted by a clean-up command that is run by hand for now.",
  "Names are not removed, so please don't type personal information.",
  "Also saved: which pages were used, how long each step took, and what the request cost (numbers only).",
  "If you press the thumbs up or down, that vote is saved with the answer. Nothing else is saved with it.",
  "No IP address and no cookies are stored.",
  "This is an unofficial student project, not affiliated with City Tech.",
];
