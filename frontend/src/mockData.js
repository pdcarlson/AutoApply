// Sample data matching the mockup, so the screens can be built before the
// backend has real data. Pages fall back to this when the API is empty or offline.
// TODO: delete once the agent produces real applications.

export const mockApplications = [
  { id: 1, company: "Tidewater Systems", role: "Software Engineer Intern", ats: "lever", status: "submitted", submitted_at: "2026-10-21", screenshot_path: "x" },
  { id: 2, company: "Northwind Data", role: "Data Engineering Intern", ats: "greenhouse", status: "needs_you", reason: 'No saved answer for "Are you willing to relocate to Austin, TX?"' },
  { id: 3, company: "Kestrel Health", role: "SWE Intern, Summer 2027", ats: "lever", status: "needs_you", reason: "Form has a CAPTCHA" },
  { id: 4, company: "Brightline Robotics", role: "Backend Co-op", ats: "ashby", status: "needs_you", reason: '"Why do you want to work here?" draft ready (confidence 74%)' },
  { id: 5, company: "Copperline Bank", role: "Technology Analyst", ats: "greenhouse", status: "submitted", submitted_at: "2026-10-19", screenshot_path: "x" },
  { id: 6, company: "Fieldnote", role: "Frontend Intern", ats: "ashby", status: "failed", reason: "Page timed out" },
  { id: 7, company: "Harbor Freight Analytics", role: "Platform Intern", ats: "greenhouse", status: "in_progress" },
];

export const mockAnswers = [
  { id: 1, question: "Are you legally authorized to work in the US?", answer: "Yes", times_used: 11 },
  { id: 2, question: "Will you now or in the future require sponsorship?", answer: "No", times_used: 9 },
  { id: 3, question: "Earliest start date", answer: "May 24, 2027", times_used: 7 },
  { id: 4, question: "Are you willing to relocate?", answer: "Yes, within the US", times_used: 4 },
  { id: 5, question: "How did you hear about us?", answer: "Company careers page", times_used: 12 },
  { id: 6, question: "Gender / race / veteran status (voluntary)", answer: "Decline to answer", times_used: 10 },
];

export const mockProfile = {
  first_name: "Joe",
  last_name: "Miller",
  email: "joe.miller@gmail.com",
  phone: "(518) 555-0147",
  school: "Rensselaer Polytechnic Institute",
  degree: "B.S. Computer Science",
  grad_date: "May 2027",
  experience: [
    { title: "Software Intern", company: "Tidepool Labs", dates: "Jun 2025 to Aug 2025" },
    { title: "IT Help Desk", company: "RPI DotCIO", dates: "Sep 2024 to present" },
  ],
  skills: ["Python", "Java", "SQL", "React", "Git"],
  flagged_fields: ["phone", "experience.1"],
  confirmed: false,
};
