# Onboarding + profile redesign (applied inside transform.py; uses rep/out from there)

def cut_between(start_marker, end_marker, replacement=""):
    global out
    s = out.index(start_marker)
    e = out.index(end_marker, s)
    out = out[:s] + replacement + out[e:]

# ---------- No walkthrough / story tags: this is the real design ----------
rep("""  function P({ ids: e }) {
    return j((e) => e.tags)
      ? (0, N.jsx)(`span`, {""", """  function P({ ids: e }) {
    return !1
      ? (0, N.jsx)(`span`, {""")
rep("""        (0, N.jsx)(ro, {}),
""", "")

# ---------- Login: no checkmark bullets ----------
cut_between("""                  (0, N.jsx)(`ul`, {
                    className: `promises`,
                    children: Ea.map(""", """                  (0, N.jsx)(`p`, {
                    className: `fine-print`,""")

# ---------- Setup header: Sign out instead of Save and exit ----------
rep("""      { saveAndExit: t } = M(),
      n = Vn.findIndex""", """      { saveAndExit: t, signOut: aaSignOut } = M(),
      n = Vn.findIndex""")
rep("""          className: `link-btn small`,
          onClick: t,
          children: `Save and exit`,""", """          className: `link-btn small`,
          onClick: aaSignOut,
          children: `Sign out`,""")

# ---------- Setup pages scroll as one page; the continue button sits under the content ----------
rep("""      className: `page-frame`,
      children: [
        (0, N.jsx)(oa, {}),
        (0, N.jsx)(`div`, {
          className: `page-scroll`,
          children: (0, N.jsx)(`main`, {
            className: `onboarding-main`,
            id: `main`,
            children: e,
          }),
        }),
        t,
      ],""", """      className: `page-frame onboarding-frame`,
      children: [
        (0, N.jsx)(oa, {}),
        (0, N.jsxs)(`main`, {
          className: `onboarding-main`,
          id: `main`,
          children: [e, t],
        }),
      ],""")
rep("`.main, .page-scroll, .welcome`", "`.main, .page-scroll, .welcome, .page-frame`")
rep("""        (0, N.jsx)(`button`, {
          type: `button`,
          className: `btn ghost`,
          onClick: e,
          children: `Back`,
        }),
        (0, N.jsxs)(`div`, {
          className: `page-foot-right`,""", """        e
          ? (0, N.jsx)(`button`, {
              type: `button`,
              className: `btn ghost`,
              onClick: e,
              children: `Back`,
            })
          : null,
        (0, N.jsxs)(`div`, {
          className: `page-foot-right`,""")

# Resume upload: no Back, shorter note
rep("""        onBack: () => t(`welcome`),
        onNext: () => t(`review`),""", """        onNext: () => t(`review`),""")
rep("children: `Your resume file is stored encrypted and attached to applications exactly as uploaded. You can delete it at any time.`",
    "children: `Your resume is encrypted and attached to applications exactly as uploaded.`")

# Check profile: no Back (Replace already goes back to upload)
rep("""        onBack: () => t(`upload`),
        onNext: () => t(`questions`),""", """        onNext: () => t(`questions`),""")

# ---------- Common questions ----------
rep("children: `Almost every application asks them. Your answers go into your Answer bank, and you can change them any time.`",
    "children: `Your answers go into your Answer bank, and you can change them any time.`")
rep("""            (0, N.jsxs)(`span`, {
              className: `small muted`,
              children: [
                ca,
                ` questions · every one can be skipped`,
                i ? ` · ${i} skipped` : ``,
              ],
            }),
""", "")
cut_between("""            (0, N.jsxs)(`aside`, {
              className: `aside-note`,""", """          ],
        }),
      ],
    });
  }
  function ua(""", "")
rep("children: (0, N.jsx)(fa, { id: `start`, options: L }),", "children: (0, N.jsx)(aaDate, { id: `start` }),")
rep("start: `June 2027`,", "start: `2027-06-01`,")
rep("""  function ua({ id: e, label: t, hint: n, children: r }) {""", """  function aaDate({ id: e }) {
    let n = j((t) => t.commonAnswers[e]),
      { updateCommonAnswers: r } = M();
    return (0, N.jsxs)(`label`, {
      className: `date-field`,
      onClick: (t) => {
        let i = t.currentTarget.querySelector(`input`);
        try {
          i && i.showPicker && i.showPicker();
        } catch {}
      },
      children: [
        (0, N.jsx)(F, { name: `calendar`, size: 18, stroke: 1.8 }),
        (0, N.jsx)(`input`, {
          type: `date`,
          className: `input date-input`,
          "aria-labelledby": `q-${e}`,
          value: n ?? ``,
          onChange: (t) => r({ [e]: t.target.value }),
        }),
      ],
    });
  }
  function ua({ id: e, label: t, hint: n, children: r }) {""")
rep("""  var ii = {
    link:""", """  var ii = {
    calendar: (0, N.jsxs)(N.Fragment, {
      children: [
        (0, N.jsx)(`rect`, { x: `3`, y: `5`, width: `18`, height: `16`, rx: `2` }),
        (0, N.jsx)(`path`, { d: `M16 3v4M8 3v4M3 10h18` }),
      ],
    }),
    link:""")

# ---------- Profile data: dated experience, multiple educations, links, custom fields ----------
rep("""      coursework: ``,
      experience: [
        {
          id: `x1`,
          title: `Crew Member`,
          org: `Chipotle`,
          when: `Part-time · 2024 – present`,
          detail: `Trained 4 new crew members. Weekend closing shift lead.`,
        },
      ],""", """      coursework: ``,
      links: aaLinkDefaults(!0),
      custom: [],
      education: [
        {
          id: `ed1`,
          school: `Rensselaer Polytechnic Institute`,
          degreeType: `Bachelor of Science (B.S.)`,
          major: `Computer Science`,
          gpa: `3.4`,
          location: `Troy, NY`,
          start: `2023-08-28`,
          end: `2027-05-15`,
          coursework: ``,
        },
      ],
      experience: [
        {
          id: `x1`,
          title: `Crew Member`,
          org: `Chipotle`,
          location: `Troy, NY`,
          start: `2024-05-13`,
          end: ``,
          current: !0,
          when: `Part-time · 2024 – present`,
          detail: `Trained 4 new crew members\\nWeekend closing shift lead`,
        },
      ],""")
rep("""      grad: ``,
      experience: [],
      projects: [],""", """      grad: ``,
      experience: [],
      education: [
        {
          id: `ed1`,
          school: ``,
          degreeType: ``,
          major: ``,
          gpa: ``,
          location: ``,
          start: ``,
          end: ``,
          coursework: ``,
        },
      ],
      links: aaLinkDefaults(!1),
      custom: [],
      projects: [],""")
rep("""    Dr = `Joe_Resume_Fall2026.pdf`,""", """    Dr = `Joe_Resume_Fall2026.pdf`,
    aaLinkDefaults = (e) => [
      { id: `web`, label: `Website / portfolio`, fixed: !0, url: ``, ph: `https://yourname.dev` },
      { id: `linkedin`, label: `LinkedIn`, fixed: !0, url: e ? `https://linkedin.com/in/joejobless` : ``, ph: `https://linkedin.com/in/…` },
      { id: `github`, label: `GitHub`, fixed: !0, url: e ? `https://github.com/joejobless` : ``, ph: `https://github.com/…` },
    ],""")
# "Add to Education" puts the unplaced coursework on the first school
rep("""            ? ((e.profile.coursework = e.profile.unparsed.replace(""",
    """            ? (e.profile.education?.[0] &&
                (e.profile.education[0].coursework = e.profile.unparsed.replace(
                  /^Relevant Coursework:\\s*/,
                  ``,
                )),
              (e.profile.coursework = e.profile.unparsed.replace(""")

# ---------- Entry editor (education / experience / projects) ----------
s_ = out.index("  var ma = {\n    experience: {")
e_ = out.index("  function ga({ idPrefix: e }) {")
out = out[:s_] + r"""  var aaFmt = (e) => {
      if (!e) return ``;
      let [t, n, r] = e.split(`-`).map(Number);
      return t
        ? new Date(t, (n || 1) - 1, r || 1).toLocaleDateString(`en-US`, {
            month: `short`,
            day: `numeric`,
            year: `numeric`,
          })
        : e;
    },
    aaSpan = (e, t) =>
      e.start || e.end || t
        ? `${aaFmt(e.start) || `Start ?`} – ${t ? `Present` : aaFmt(e.end) || `End ?`}`
        : ``,
    aaBullets = (e) =>
      (e || ``)
        .split(/\n+/)
        .map((e) => e.replace(/^\s*[-•*]\s*/, ``).trim())
        .filter(Boolean);
  var ma = {
      experience: {
        add: `Add experience`,
        title: (e) => [e.title, e.org].filter(Boolean).join(` · `) || `New experience`,
        sub: (e) => [aaSpan(e, e.current), e.location].filter(Boolean).join(` · `),
        blank: () => ({ title: ``, org: ``, location: ``, start: ``, end: ``, current: !1, detail: `` }),
      },
      education: {
        add: `Add education`,
        title: (e) => e.school || `New education`,
        sub: (e) =>
          [
            [e.degreeType, e.major].filter(Boolean).join(`, `),
            e.gpa && `GPA ${e.gpa}`,
            e.location,
            aaSpan(e, !1),
          ]
            .filter(Boolean)
            .join(` · `),
        blank: () => ({ school: ``, degreeType: ``, major: ``, gpa: ``, location: ``, start: ``, end: ``, coursework: `` }),
      },
      projects: {
        add: `Add project`,
        title: (e) => e.name || `New project`,
        sub: (e) => e.tech,
        blank: () => ({ name: ``, tech: ``, detail: `` }),
      },
    },
    aaFields = {
      experience: [
        [`title`, `Title`, `text`, `e.g. Software Intern`],
        [`org`, `Employer`, `text`, `Company name`],
        [`location`, `Location`, `text`, `City, State or Remote`],
        [`start`, `Start date`, `date`],
        [`end`, `End date`, `date`],
        [`detail`, `Description`, `textarea`, `One bullet per line, e.g.\nBuilt the Python service that tracked robot telemetry\nCut report time from 2 hours to 10 minutes`],
      ],
      education: [
        [`school`, `School`, `text`, `School name`],
        [`location`, `Location`, `text`, `City, State`],
        [`degreeType`, `Degree type`, `text`, `e.g. Bachelor of Science (B.S.)`],
        [`major`, `Major`, `text`, `e.g. Computer Science`],
        [`gpa`, `GPA`, `text`, `e.g. 3.4`],
        [`start`, `Start date`, `date`],
        [`end`, `End date (or expected)`, `date`],
        [`coursework`, `Relevant coursework`, `textarea`, `e.g. Data Structures, Operating Systems, Software Design`],
      ],
      projects: [
        [`name`, `Project`, `text`, `Project name`],
        [`tech`, `Tools`, `text`, `e.g. React, Firebase`],
        [`detail`, `Description`, `textarea`, `One bullet per line, e.g.\nBuilt the frontend with one other student\nUsed by about 40 people in the climbing club`],
      ],
    };
  function ha({ kind: e }) {
    let t = j((t) => t.profile[e]) ?? [],
      { updateEntry: n, updateProfile: u, notify: i } = M(),
      [a, o] = (0, b.useState)(null),
      s = ma[e],
      fl = aaFields[e];
    return (0, N.jsxs)(`div`, {
      className: `entry-list`,
      children: [
        t.map((r) =>
          a === r.id
            ? (0, N.jsxs)(
                `div`,
                {
                  className: `panel entry-edit`,
                  children: [
                    (0, N.jsx)(`div`, {
                      className: `grid-2`,
                      children: fl.map(([k, l, ty, ph]) => {
                        let id = `${e}-${k}-${r.id}`,
                          off = k === `end` && !!r.current;
                        return (0, N.jsxs)(
                          `div`,
                          {
                            className: `field${ty === `textarea` ? ` wide` : ``}`,
                            children: [
                              (0, N.jsx)(`label`, { htmlFor: id, children: l }),
                              ty === `textarea`
                                ? (0, N.jsx)(`textarea`, {
                                    id,
                                    className: `input`,
                                    rows: k === `coursework` ? 2 : 4,
                                    value: r[k] ?? ``,
                                    placeholder: ph,
                                    onChange: (t) => n(e, r.id, { [k]: t.target.value }),
                                  })
                                : (0, N.jsx)(`input`, {
                                    id,
                                    className: `input`,
                                    type: off ? `text` : ty,
                                    value: off ? `Present` : (r[k] ?? ``),
                                    disabled: off,
                                    placeholder: ph ?? ``,
                                    onChange: (t) => n(e, r.id, { [k]: t.target.value }),
                                  }),
                              k === `detail` &&
                                (0, N.jsx)(`span`, {
                                  className: `tiny muted`,
                                  children: `Each line becomes a bullet. The agent writes answers only from what’s here.`,
                                }),
                            ],
                          },
                          k,
                        );
                      }),
                    }),
                    e === `experience` &&
                      (0, N.jsxs)(`label`, {
                        className: `check`,
                        children: [
                          (0, N.jsx)(`input`, {
                            type: `checkbox`,
                            checked: !!r.current,
                            onChange: () => n(e, r.id, { current: !r.current, end: `` }),
                          }),
                          `I currently work here`,
                        ],
                      }),
                    (0, N.jsxs)(`div`, {
                      className: `row-actions`,
                      children: [
                        (0, N.jsx)(`button`, {
                          type: `button`,
                          className: `btn primary sm`,
                          onClick: () => {
                            (o(null), i(`Saved. Applications use this from now on.`));
                          },
                          children: `Save`,
                        }),
                        (0, N.jsx)(`button`, {
                          type: `button`,
                          className: `btn sm danger`,
                          onClick: () => {
                            (u({ [e]: t.filter((t) => t.id !== r.id) }), o(null));
                          },
                          children: `Remove`,
                        }),
                      ],
                    }),
                  ],
                },
                r.id,
              )
            : (0, N.jsxs)(
                `div`,
                {
                  className: `entry`,
                  children: [
                    (0, N.jsxs)(`div`, {
                      className: `entry-text`,
                      children: [
                        (0, N.jsx)(`b`, { children: s.title(r) }),
                        s.sub(r) && (0, N.jsx)(`span`, { children: s.sub(r) }),
                        e === `education` &&
                          r.coursework &&
                          (0, N.jsxs)(`span`, {
                            className: `entry-course`,
                            children: [`Coursework: `, r.coursework],
                          }),
                        e === `projects` && !r.detail
                          ? (0, N.jsxs)(`span`, {
                              className: `thin-hint`,
                              children: [
                                (0, N.jsx)(`span`, { className: `dot amber` }),
                                `No description yet. Forms often ask what your part was and who used it.`,
                              ],
                            })
                          : e !== `education` &&
                            aaBullets(r.detail).length > 0 &&
                            (0, N.jsx)(`ul`, {
                              className: `entry-bullets`,
                              children: aaBullets(r.detail).map((t, n) =>
                                (0, N.jsx)(`li`, { children: t }, n),
                              ),
                            }),
                      ],
                    }),
                    (0, N.jsx)(`button`, {
                      type: `button`,
                      className: `icon-btn`,
                      "aria-label": `Edit ${s.title(r)}`,
                      onClick: () => o(r.id),
                      children: (0, N.jsx)(F, { name: `pencil`, size: 16, stroke: 1.75 }),
                    }),
                  ],
                },
                r.id,
              ),
        ),
        !t.length &&
          (0, N.jsx)(`p`, { className: `small muted`, children: `Nothing here yet.` }),
        (0, N.jsxs)(`button`, {
          type: `button`,
          className: `btn sm ghost add-entry`,
          onClick: () => {
            let n = `${e}-${Date.now()}`;
            (u({ [e]: [...t, { id: n, ...s.blank() }] }), o(n));
          },
          children: [(0, N.jsx)(F, { name: `plus`, size: 16, stroke: 2 }), s.add],
        }),
      ],
    });
  }
  function aaLinks() {
    let t = j((e) => e.profile.links) ?? [],
      { updateProfile: u } = M(),
      set = (n, r) => u({ links: t.map((e) => (e.id === n ? { ...e, ...r } : e)) });
    return (0, N.jsxs)(`div`, {
      className: `kv-list`,
      children: [
        ...t.map((l) =>
          (0, N.jsxs)(
            `div`,
            {
              className: `kv-row`,
              children: [
                l.fixed
                  ? (0, N.jsx)(`label`, {
                      className: `kv-label`,
                      htmlFor: `link-${l.id}`,
                      children: l.label,
                    })
                  : (0, N.jsx)(`input`, {
                      className: `input`,
                      "aria-label": `Link name`,
                      placeholder: `Name, e.g. Blog`,
                      value: l.label,
                      onChange: (e) => set(l.id, { label: e.target.value }),
                    }),
                (0, N.jsx)(`input`, {
                  id: `link-${l.id}`,
                  className: `input`,
                  type: `url`,
                  inputMode: `url`,
                  placeholder: l.ph ?? `https://`,
                  value: l.url,
                  onChange: (e) => set(l.id, { url: e.target.value }),
                }),
                l.fixed
                  ? (0, N.jsx)(`span`, {})
                  : (0, N.jsx)(`button`, {
                      type: `button`,
                      className: `icon-btn plain`,
                      "aria-label": `Remove ${l.label || `link`}`,
                      onClick: () => u({ links: t.filter((e) => e.id !== l.id) }),
                      children: (0, N.jsx)(F, { name: `close`, size: 16 }),
                    }),
              ],
            },
            l.id,
          ),
        ),
        (0, N.jsxs)(`button`, {
          type: `button`,
          className: `btn sm ghost add-entry`,
          onClick: () => u({ links: [...t, { id: `link-${Date.now()}`, label: ``, url: `` }] }),
          children: [(0, N.jsx)(F, { name: `plus`, size: 16, stroke: 2 }), `Add another link`],
        }),
      ],
    });
  }
  function aaCustom() {
    let t = j((e) => e.profile.custom) ?? [],
      { updateProfile: u } = M(),
      set = (n, r) => u({ custom: t.map((e) => (e.id === n ? { ...e, ...r } : e)) });
    return (0, N.jsxs)(`div`, {
      className: `kv-list`,
      children: [
        t.length
          ? (0, N.jsxs)(`div`, {
              className: `kv-row kv-head`,
              "aria-hidden": `true`,
              children: [
                (0, N.jsx)(`span`, { children: `Field` }),
                (0, N.jsx)(`span`, { children: `Value` }),
                (0, N.jsx)(`span`, {}),
              ],
            })
          : (0, N.jsx)(`p`, {
              className: `small muted`,
              children: `Anything else forms ask for, like pronouns, a preferred name, or citizenship. The agent fills a field when a form asks for it by this name.`,
            }),
        ...t.map((c) =>
          (0, N.jsxs)(
            `div`,
            {
              className: `kv-row`,
              children: [
                (0, N.jsx)(`input`, {
                  className: `input`,
                  "aria-label": `Field name`,
                  placeholder: `Field name, e.g. Pronouns`,
                  value: c.label,
                  onChange: (e) => set(c.id, { label: e.target.value }),
                }),
                (0, N.jsx)(`input`, {
                  className: `input`,
                  "aria-label": `Value for ${c.label || `this field`}`,
                  placeholder: `Value, e.g. he/him`,
                  value: c.value,
                  onChange: (e) => set(c.id, { value: e.target.value }),
                }),
                (0, N.jsx)(`button`, {
                  type: `button`,
                  className: `icon-btn plain`,
                  "aria-label": `Remove ${c.label || `field`}`,
                  onClick: () => u({ custom: t.filter((e) => e.id !== c.id) }),
                  children: (0, N.jsx)(F, { name: `close`, size: 16 }),
                }),
              ],
            },
            c.id,
          ),
        ),
        (0, N.jsxs)(`button`, {
          type: `button`,
          className: `btn sm ghost add-entry`,
          onClick: () => u({ custom: [...t, { id: `cf-${Date.now()}`, label: ``, value: `` }] }),
          children: [(0, N.jsx)(F, { name: `plus`, size: 16, stroke: 2 }), `Add a custom field`],
        }),
      ],
    });
  }
""" + out[e_:]

# ---------- Check profile page: Links, multi-education, Additional information ----------
rep("""                    (0, N.jsx)(ga, { idPrefix: `review` }),
                  ],
                }),""", """                    (0, N.jsx)(ga, { idPrefix: `review` }),
                  ],
                }),
                (0, N.jsxs)(`section`, {
                  className: `panel`,
                  "aria-labelledby": `review-links`,
                  children: [
                    (0, N.jsx)(`h2`, {
                      className: `eyebrow`,
                      id: `review-links`,
                      children: `Links`,
                    }),
                    (0, N.jsx)(aaLinks, {}),
                  ],
                }),""")
rep("""                    (0, N.jsx)(_a, { idPrefix: `review` }),""", """                    (0, N.jsx)(ha, { kind: `education` }),""")
rep("""                    (0, N.jsx)(ia, {
                      items: e.skills,
                      onChange: (e) => n({ skills: e }),
                      label: `Skills`,
                      addLabel: `Add skill`,
                      placeholder: `e.g. Docker`,
                    }),
                  ],
                }),""", """                    (0, N.jsx)(ia, {
                      items: e.skills,
                      onChange: (e) => n({ skills: e }),
                      label: `Skills`,
                      addLabel: `Add skill`,
                      placeholder: `e.g. Docker`,
                    }),
                  ],
                }),
                (0, N.jsxs)(`section`, {
                  className: `panel`,
                  "aria-labelledby": `review-custom`,
                  children: [
                    (0, N.jsx)(`h2`, {
                      className: `eyebrow`,
                      id: `review-custom`,
                      children: `Additional information`,
                    }),
                    (0, N.jsx)(aaCustom, {}),
                  ],
                }),""")

# ---------- Profile page gets the same sections ----------
rep("""      `contact`,
      `education`,
      `experience`,
      `projects`,
      `skills`,
      `preferences`,""", """      `contact`,
      `links`,
      `education`,
      `experience`,
      `projects`,
      `skills`,
      `custom`,
      `preferences`,""")
rep("""      contact: `Contact`,
      education: `Education`,""", """      contact: `Contact`,
      links: `Links`,
      custom: `Additional information`,
      education: `Education`,""")
rep("""    education: `Used for school, degree, and graduation questions.`,""", """    education: `Every school with degree, major, GPA, dates, and coursework.`,
    links: `Portfolio, LinkedIn, GitHub, and anything else forms ask you to link.`,
    custom: `Your own fields. Name it the way forms ask for it, then type the value.`,""")
rep("var aaProfileSubs = [`contact`, `education`, `experience`, `projects`, `skills`, `preferences`, `resume`];",
    "var aaProfileSubs = [`contact`, `links`, `education`, `experience`, `projects`, `skills`, `custom`, `preferences`, `resume`];")
rep("""      case `education`:
        return (0, N.jsxs)(N.Fragment, {
          children: [
            (0, N.jsx)(`div`, {
              className: `panel`,
              children: (0, N.jsx)(_a, { idPrefix: `profile` }),
            }),
            i,
          ],
        });""", """      case `education`:
        return (0, N.jsx)(ha, { kind: `education` });
      case `links`:
        return (0, N.jsx)(`div`, { className: `panel`, children: (0, N.jsx)(aaLinks, {}) });
      case `custom`:
        return (0, N.jsx)(`div`, { className: `panel`, children: (0, N.jsx)(aaCustom, {}) });""")
