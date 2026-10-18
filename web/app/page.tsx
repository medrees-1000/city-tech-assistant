import Link from "next/link";

import { FOOTER_LINE } from "../lib/notice";

const TOPICS = [
  {
    title: "Registration and deadlines",
    text: "Academic calendar dates, withdrawing from a class, readmission, applying to graduate.",
  },
  {
    title: "Prerequisites and degrees",
    text: "What comes before a course, program requirements and credits.",
  },
  {
    title: "Tuition and financial aid",
    text: "Payment deadlines, refunds, payment plans, TAP and satisfactory academic progress.",
  },
  {
    title: "The four departments",
    text: "Computer Systems Technology, Mathematics, Electrical and Telecommunications Engineering Technology, and Dental Hygiene.",
  },
];

export default function Welcome() {
  return (
    <main className="landing">
      <div className="rule" aria-hidden="true">
        <span />
        <span />
      </div>
      <h1>City Tech Assistant</h1>
      <p className="lede">
        Ask about registration, deadlines, advising, tuition and aid, and four departments. Every
        answer shows its source; when I don&rsquo;t know, I say so and point you to the right office.
      </p>
      <div className="cta-row">
        <Link href="/chat" className="btn">
          Start chatting
        </Link>
      </div>

      <h2 className="sr-only">What you can ask about</h2>
      <ul className="topics">
        {TOPICS.map((t) => (
          <li key={t.title} className="topic">
            <h2>{t.title}</h2>
            <p>{t.text}</p>
          </li>
        ))}
      </ul>

      <footer>
        <p className="unofficial">{FOOTER_LINE}</p>
      </footer>
    </main>
  );
}
