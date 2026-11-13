import pathlib as _pl
HERE = _pl.Path(__file__).resolve().parent
import re, sys, pathlib

src = (HERE / 'original-bundle.js').read_text()
out = src

def rep(old, new, count=1):
    global out
    n = out.count(old)
    if n != count:
        sys.exit(f"expected {count} match(es), got {n}:\n{old[:300]}")
    out = out.replace(old, new)

# ---------- 1. Brand: boxed "AA" mark like the mockups ----------
rep("""      className: `brand`,
      children: [
        (0, N.jsx)(Ui, {}),
        (0, N.jsx)(`span`, { children: `Auto Apply` }),""",
"""      className: `brand`,
      children: [
        (0, N.jsx)(`span`, { className: `brand-mark`, "aria-hidden": `true`, children: `AA` }),
        (0, N.jsx)(`span`, { children: `Auto Apply` }),""")

# ---------- 2. Navigation map: Answer bank + Settings become top level ----------
rep("""      : e === `applications`
        ? `applications`
        : Ln.includes(e)""",
"""      : e === `applications`
        ? `applications`
        : e === `answers`
        ? `answers`
        : e === `controls`
        ? `settings`
        : Ln.includes(e)""")

rep("""    { key: `profile`, href: `#answers`, label: `Profile`, icon: `user` },
  ];""",
"""    { key: `profile`, href: `#contact`, label: `Profile`, icon: `user` },
    { key: `answers`, href: `#answers`, label: `Answer bank`, icon: `list` },
    { key: `settings`, href: `#controls`, label: `Settings`, icon: `sliders` },
  ];
  var aaProfileSubs = [`contact`, `education`, `experience`, `projects`, `skills`, `preferences`, `resume`];""")

# ---------- 3. Top bar -> left sidebar (the mockups' app frame) ----------
start = out.index("  function to() {")
end = out.index("  function no() {")
out = out[:start] + r"""  function to() {
    let { tab: e, inboxCount: t, readyCount: aaR } = eo(),
      aaRoute = j((e) => e.route),
      aaProf = j((e) => e.profile),
      aaWait = j((e) => ur(e).length),
      { signOut: aaOut } = M(),
      aaThin = aaProf.projects.some((e) => !e.detail),
      aaFlag = {
        contact: !(aaProf.name && aaProf.phone),
        education: !aaProf.school,
        projects: aaThin,
      };
    return (0, N.jsxs)(`aside`, {
      className: `appnav`,
      children: [
        (0, N.jsx)(`a`, {
          className: `brand-link`,
          href: `#inbox`,
          "aria-label": `Auto Apply, go to Inbox`,
          children: (0, N.jsx)(Wi, {}),
        }),
        (0, N.jsx)(`nav`, {
          className: `appnav-links`,
          "aria-label": `Main`,
          children: $a.map((n) =>
            (0, N.jsxs)(
              N.Fragment,
              {
                children: [
                  (0, N.jsxs)(`a`, {
                    href: n.href,
                    className: `appnav-link${e === n.key ? ` on` : ``}`,
                    "aria-current": e === n.key ? `page` : void 0,
                    children: [
                      (0, N.jsx)(`span`, { children: n.label }),
                      n.key === `inbox` &&
                        t > 0 &&
                        (0, N.jsx)(`span`, {
                          className: `count`,
                          "aria-label": `${t} waiting`,
                          children: t,
                        }),
                      n.key === `applications` &&
                        aaR > 0 &&
                        (0, N.jsx)(`span`, {
                          className: `count`,
                          "aria-label": `${aaR} ready to submit`,
                          children: aaR,
                        }),
                      n.key === `answers` &&
                        aaWait > 0 &&
                        (0, N.jsx)(`span`, {
                          className: `count warn`,
                          "aria-label": `${aaWait} waiting for an answer`,
                          children: aaWait,
                        }),
                    ],
                  }),
                ],
              },
              n.key,
            ),
          ),
        }),
        (0, N.jsx)(`div`, { className: `appnav-run`, children: (0, N.jsx)(zi, {}) }),
        (0, N.jsxs)(`div`, {
          className: `appnav-foot`,
          children: [
            (0, N.jsxs)(`div`, {
              className: `appnav-user`,
              children: [
                (0, N.jsx)(`span`, { children: `Joe Jobless` }),
                (0, N.jsx)(`span`, { children: `joe@example.com` }),
                (0, N.jsx)(`button`, {
                  type: `button`,
                  className: `link-btn`,
                  onClick: aaOut,
                  children: `Sign out`,
                }),
              ],
            }),
            (0, N.jsx)(Qa, {}),
          ],
        }),
      ],
    });
  }
""" + out[end:]

# ---------- 4. App frame: sidebar + main column ----------
rep("""    return (0, N.jsxs)(`div`, {
      className: `shell`,
      children: [
        n && (0, N.jsx)(to, {}),
        t ? (0, N.jsx)(t, {}) : (0, N.jsx)(qa, { section: e }),
        n && (0, N.jsx)(no, {}),""",
"""    let aaPage = t ? (0, N.jsx)(t, {}) : (0, N.jsx)(qa, { section: e });
    return (0, N.jsxs)(`div`, {
      className: n ? `shell with-nav` : `shell`,
      children: [
        n && (0, N.jsx)(to, {}),
        n
          ? (0, N.jsxs)(`div`, {
              className: `shell-main`,
              children: [aaPage, (0, N.jsx)(no, {})],
            })
          : aaPage,""")

# ---------- 5. Inbox: no second rail; filters inline, "Applying now" under the table ----------
rep("""    return (0, N.jsxs)(`div`, {
      className: `app-body`,
      children: [
        (0, N.jsxs)(`aside`, {
          className: `sidebar`,
          "aria-label": `Inbox filters`,
          children: [(0, N.jsx)(Ri, {}), (0, N.jsx)(zi, {})],
        }),
        e,
      ],
    });""",
"""    return (0, N.jsx)(`div`, {
      className: `app-body single`,
      children: e,
    });""")

rep("""    return (0, N.jsx)(`div`, {
      className: `phone-only`,
      children: (0, N.jsx)(Ri, { asChips: !0 }),
    });""",
"""    return (0, N.jsx)(`div`, {
      className: `inbox-filters`,
      children: (0, N.jsx)(Ri, { asChips: !0 }),
    });""")

rep("""                (0, N.jsx)(Hi, {}),
                (0, N.jsx)(`div`, {
                  className: `phone-only`,
                  children: (0, N.jsx)(zi, { compact: !0 }),
                }),""",
"""                (0, N.jsx)(Hi, {}),""")

rep("""                    !e.length &&
                      (0, N.jsx)(`p`, {
                        className: `empty`,
                        children:
                          r === `all`
                            ? `Your Inbox is clear. Paste a job link to add one.`
                            : `Nothing in this filter.`,
                      }),
                  ],
                }),""",
"""                    !e.length &&
                      (0, N.jsx)(`p`, {
                        className: `empty`,
                        children:
                          r === `all`
                            ? `Your Inbox is clear. Paste a job link to add one.`
                            : `Nothing in this filter.`,
                      }),
                  ],
                }),
                (0, N.jsx)(`div`, { className: `phone-only`, children: (0, N.jsx)(zi, { compact: !0 }) }),""")

# Cards view keeps "Applying now" visible too
rep("""                  !n.length &&
                    (0, N.jsx)(`p`, {
                      className: `small muted`,
                      children: `Nothing else waiting.`,
                    }),
                ],
              }),
            ],
          }),
        ],""",
"""                  !n.length &&
                    (0, N.jsx)(`p`, {
                      className: `small muted`,
                      children: `Nothing else waiting.`,
                    }),
                ],
              }),
            ],
          }),
          (0, N.jsx)(`div`, { className: `phone-only`, children: (0, N.jsx)(zi, { compact: !0 }) }),
        ],""")

# ---------- 6. Profile pages: section links now live in the main sidebar ----------
rep("""    return (0, N.jsxs)(`div`, {
      className: `app-body${t ? ` with-detail` : ``}`,
      children: [(0, N.jsx)(ja, {}), e],
    });""",
"""    return (0, N.jsx)(`div`, {
      className: `app-body single${t ? ` with-detail` : ``}`,
      children: e,
    });""")

# "Download my data" moves from the old profile rail into Settings
rep("""          children: `Removes your profile, resume file, saved answers, applications, and screenshots from our servers.`,
        }),
        (0, N.jsx)(`div`, {
          children: (0, N.jsxs)(`button`, {
            type: `button`,
            className: `btn sm danger`,
            onClick: () => e({ type: `deleteAccount` }),
            children: [
              (0, N.jsx)(F, { name: `trash`, size: 15 }),
              `Delete my account`,
            ],
          }),
        }),""",
"""          children: `Removes your profile, resume file, saved answers, applications, and screenshots from our servers.`,
        }),
        (0, N.jsxs)(`div`, {
          className: `row-actions`,
          children: [
            (0, N.jsx)(`button`, {
              type: `button`,
              className: `btn sm`,
              onClick: () =>
                aaNotify(
                  `Prototype: this downloads your profile, answers, and applications as one file.`,
                ),
              children: `Download my data`,
            }),
            (0, N.jsxs)(`button`, {
              type: `button`,
              className: `btn sm danger`,
              onClick: () => e({ type: `deleteAccount` }),
              children: [
                (0, N.jsx)(F, { name: `trash`, size: 15 }),
                `Delete my account`,
              ],
            }),
          ],
        }),""")
rep("""  function Wa() {
    let { openModal: e } = M();""",
"""  function Wa() {
    let { openModal: e, notify: aaNotify } = M();""")
rep("""              id: `delete-title`,
              children: `Delete your account`,""",
"""              id: `delete-title`,
              children: `Your data`,""")

# Settings page title matches the nav label
rep("""                  (0, N.jsx)(`h1`, {
                    className: `h1`,
                    children: `Agent controls`,
                  }),""",
"""                  (0, N.jsx)(`h1`, {
                    className: `h1`,
                    children: `Settings`,
                  }),""")

# ---------- 7. Setup header: "Step 2 of 3 · Resume → Check profile → ..." + progress bar ----------
rep("""    return (0, N.jsxs)(`header`, {
      className: `page-top`,
      children: [
        (0, N.jsx)(Wi, {}),
        (0, N.jsx)(`ol`, {
          className: `steps`,""",
"""    return (0, N.jsxs)(`header`, {
      className: `page-top setup-top`,
      children: [
        (0, N.jsx)(Wi, {}),
        (0, N.jsx)(`span`, {
          className: `setup-count`,
          children: `Step ${n + 1} of ${Vn.length}`,
        }),
        (0, N.jsx)(`span`, {
          className: `setup-bar`,
          "aria-hidden": `true`,
          children: (0, N.jsx)(`span`, {
            style: { width: `${Math.round((100 * (n + 1)) / Vn.length)}%` },
          }),
        }),
        (0, N.jsx)(`ol`, {
          className: `steps`,""")

# ---------- 8. Welcome: brand in the hero, no top bar ----------
rep("""      className: `page-frame`,
      children: [
        (0, N.jsxs)(`header`, {
          className: `page-top`,
          children: [
            (0, N.jsx)(Wi, {}),
            (0, N.jsx)(`span`, {
              className: `small muted`,
              children: `Free for students`,
            }),
          ],
        }),
        (0, N.jsxs)(`div`, {
          className: `welcome`,""",
"""      className: `page-frame welcome-frame`,
      children: [
        (0, N.jsxs)(`div`, {
          className: `welcome`,""")
rep("""                  (0, N.jsxs)(`div`, {
                    className: `stack`,
                    children: [
                      (0, N.jsxs)(`div`, {
                        className: `title-row`,
                        children: [
                          (0, N.jsx)(`h1`, {
                            className: `h1`,
                            children: `Sign in to Auto Apply`,""",
"""                  (0, N.jsx)(`span`, { className: `welcome-brand`, children: (0, N.jsx)(Wi, {}) }),
                  (0, N.jsxs)(`div`, {
                    className: `stack`,
                    children: [
                      (0, N.jsxs)(`div`, {
                        className: `title-row`,
                        children: [
                          (0, N.jsx)(`h1`, {
                            className: `h1`,
                            children: `Sign in to Auto Apply`,""")
rep("""                    className: `fine-print`,
                    children: `By continuing you agree to the Terms and Privacy policy. You’re responsible for what the agent sends in your name, so it shows you everything it sent.`,
                  }),""",
"""                    className: `fine-print`,
                    children: `By continuing you agree to the Terms and Privacy policy.`,
                  }),""")


# Phone profile-section picker only lists profile sections (Answer bank / Settings are top level now)
rep("""      { go: t } = M();
    return (0, N.jsx)(`div`, {
      className: `phone-only`,
      children: (0, N.jsxs)(`label`, {
        className: `section-select`,""",
"""      { go: t } = M();
    return aaProfileSubs.includes(e) ? (0, N.jsx)(`div`, {
      className: `phone-only`,
      children: (0, N.jsxs)(`label`, {
        className: `section-select`,""")
rep("""            children: Ln.map((e) =>
              (0, N.jsx)(`option`, { value: e, children: Bn[e] }, e),
            ),
          }),
        ],
      }),
    });""",
"""            children: aaProfileSubs.map((e) =>
              (0, N.jsx)(`option`, { value: e, children: Bn[e] }, e),
            ),
          }),
        ],
      }),
    }) : null;""")


# ---------- Profile: one scrollable page with every section ----------
rep("""  function qa({ section: e }) {
    return (0, N.jsx)(Aa, {
      children: (0, N.jsxs)(`main`, {
        className: `main`,
        id: `main`,
        children: [
          (0, N.jsx)(Ma, {}),
          (0, N.jsxs)(`div`, {
            className: `stack narrow`,
            children: [
              (0, N.jsx)(`h1`, { className: `h1`, children: Bn[e] }),
              (0, N.jsx)(`p`, { className: `ink2`, children: Ka[e] }),
            ],
          }),
          (0, N.jsx)(`div`, {
            className: `narrow section-body`,
            children: (0, N.jsx)(Ja, { section: e }),
          }),
        ],
      }),
    });
  }""",
"""  function qa({ section: e }) {
    (0, b.useEffect)(() => {
      let t = setTimeout(() => {
        e !== `contact` &&
          document.getElementById(`profile-${e}`)?.scrollIntoView({ block: `start` });
      }, 40);
      return () => clearTimeout(t);
    }, [e]);
    return (0, N.jsx)(Aa, {
      children: (0, N.jsxs)(`main`, {
        className: `main profile-page`,
        id: `main`,
        children: [
          (0, N.jsxs)(`div`, {
            className: `stack narrow`,
            children: [
              (0, N.jsx)(`h1`, { className: `h1`, children: `Profile` }),
              (0, N.jsx)(`p`, {
                className: `ink2`,
                children: `Everything the agent fills forms from, on one page. Pulled from your resume; every field is editable.`,
              }),
            ],
          }),
          ...aaProfileSubs.map((s) =>
            (0, N.jsxs)(
              `section`,
              {
                className: `narrow profile-section`,
                id: `profile-${s}`,
                "aria-labelledby": `profile-${s}-title`,
                children: [
                  (0, N.jsxs)(`div`, {
                    className: `profile-section-head`,
                    children: [
                      (0, N.jsx)(`h2`, {
                        className: `h2`,
                        id: `profile-${s}-title`,
                        children: Bn[s],
                      }),
                      (0, N.jsx)(`p`, { className: `small ink2`, children: Ka[s] }),
                    ],
                  }),
                  (0, N.jsx)(`div`, {
                    className: `section-body`,
                    children: (0, N.jsx)(Ja, { section: s }),
                  }),
                ],
              },
              s,
            ),
          ),
        ],
      }),
    });
  }""")


# Default appearance: light (not system) unless the viewer picked one
rep("""      return localStorage.getItem(St) ?? `system`;
    } catch {
      return `system`;
    }""", """      return localStorage.getItem(St) ?? `light`;
    } catch {
      return `light`;
    }""")


# ---------- List view only: drop the "One at a time" cards view ----------
rep("""            (0, N.jsxs)(`div`, {
              className: `segmented`,
              role: `group`,
              "aria-label": `Inbox view`,
              children: [
                (0, N.jsx)(`a`, {
                  href: `#inbox`,
                  className: e === `list` ? `on` : ``,
                  "aria-current": e === `list` ? `page` : void 0,
                  children: `List`,
                }),
                (0, N.jsx)(`a`, {
                  href: `#cards`,
                  className: e === `cards` ? `on` : ``,
                  "aria-current": e === `cards` ? `page` : void 0,
                  children: `One at a time`,
                }),
              ],
            }),""", "")
# old #cards links land on the list
rep("""  function A(e, t) {
    zn.includes(t) &&""", """  function A(e, t) {
    t === `cards` && (t = `inbox`);
    zn.includes(t) &&""")
rep("""    cards: Ji,
""", "")
# walkthrough step for the removed view
rep("""      {
        title: `Clear the Inbox one at a time`,
        ids: `US-4 · US-5 · US-6`,
        say: `The same jobs as cards, one decision each. Handy on a phone.`,
        setup: Gr(`cards`),
      },
""", "")

exec(open(HERE / 'patch2.py').read())

exec(open(HERE / 'patch3.py').read())

# ---------- 9. Styles ----------
css_start = out.index("((e.textContent = `") + len("((e.textContent = `")
css_end = out.index("`), document.head.appendChild(e));", css_start)
css = out[css_start:css_end]

# a) palette + type tokens (light, dark-by-media, dark-by-attribute)
light = open(HERE / 'tokens_light.css').read().strip()
dark = open(HERE / 'tokens_dark.css').read().strip()
m = re.match(r":root\{[^}]*\}", css); css = light + css[m.end():]
css = re.sub(r"(@media \(prefers-color-scheme:dark\)\{:root:not\(\[data-theme=light\]\))\{[^}]*\}",
             lambda mm: mm.group(1) + "{" + dark + "color-scheme:dark}", css, count=1)
css = re.sub(r"(:root\[data-theme=dark\])\{[^}]*\}",
             lambda mm: mm.group(1) + "{" + dark + "color-scheme:dark}", css, count=1)

# b) squarer corners: wireframe radii
def rad(mm):
    v = mm.group(1)
    px = {'6px':'3px','7px':'3px','8px':'4px','9px':'4px','10px':'4px','11px':'4px','12px':'4px','14px':'5px','16px':'6px','18px':'6px','20px':'6px'}
    return 'border-radius:' + px.get(v, v)
css = re.sub(r"border-radius:(\d+px)(?=[;}])", rad, css)
css = re.sub(r"border-radius:((?:\d+(?:px)? ?){2,4})(?=[;}])", lambda mm: "border-radius:" + " ".join(("4px" if p not in ("0","0px") and int(p[:-2])>4 and p!="999px" else p) for p in mm.group(1).split()), css)

out = out[:css_start] + css + out[css_end:]

overrides = open(HERE / 'overrides.css').read().replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
anchor = "  var po = wt();"
rep(anchor, "  {\n    let e = document.createElement(`style`);\n    ((e.textContent = `" + overrides + "`), document.head.appendChild(e));\n  }\n" + anchor)

pathlib.Path(HERE.parent / 'dist' / 'assets' / 'app.js').write_text(out)
print("ok", len(out))
