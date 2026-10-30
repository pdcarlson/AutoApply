import { go } from "../nav.js";

export default function SignIn() {
  // TODO(US1): redirect to Google OAuth. For now this skips straight to setup.
  return (
    <div className="signin">
      <div className="signin-copy">
        <div className="logo logo-big"><span>AA</span> Auto Apply</div>
        <h1>Apply to jobs without retyping your resume 40 times.</h1>
        <p className="muted">
          Paste a job link. We fill the form from your profile and ask you when we are not sure.
        </p>
        <button className="btn" onClick={() => go("setup")}>Continue with Google</button>
        <p className="small muted">
          We never submit anything you haven't approved in your profile. Free for students.
        </p>
      </div>
      <div className="placeholder-img">screenshot of Inbox goes here</div>
    </div>
  );
}
