# Landing: drop Lever from "What happens next" step 4
rep("`A Greenhouse, Lever, or Ashby link. The agent fills the form, and you approve it before it’s submitted.`",
    "`A Greenhouse or Ashby link. The agent fills the form, and you approve it before it’s submitted.`")

# Inbox: no digest line
rep("""                (0, N.jsx)(`p`, { className: `digest`, children: n }),
""", "")

# Contact: full address, one field per element (replaces the single Location field)
rep("""      location: `Troy, NY`,
      school: `Rensselaer Polytechnic Institute`,""", """      location: `Troy, NY`,
      street: `412 Hoosick Street`,
      street2: `Apt 3B`,
      city: `Troy`,
      state: `NY`,
      zip: `12180`,
      country: `United States`,
      school: `Rensselaer Polytechnic Institute`,""")
rep("""      phone: ``,
      location: ``,""", """      phone: ``,
      location: ``,
      street: ``,
      street2: ``,
      city: ``,
      state: ``,
      zip: ``,
      country: `United States`,""")
_s = out.index("  function ga({ idPrefix: e }) {")
_e = out.index("  function _a({ idPrefix: e }) {")
out = out[:_s] + """  function ga({ idPrefix: e }) {
    let t = j((e) => e.profile),
      { updateProfile: n } = M(),
      f = (k, l, ph, type = `text`) =>
        (0, N.jsx)(
          `div`,
          {
            className: `field-wrap ${k}`,
            children: (0, N.jsx)(pa, {
              id: `${e}-${k}`,
              label: l,
              type,
              value: t[k] ?? ``,
              placeholder: ph,
              onChange: (r) => {
                let i = { ...t, [k]: r };
                n(
                  k === `city` || k === `state`
                    ? { [k]: r, location: [i.city, i.state].filter(Boolean).join(`, `) }
                    : { [k]: r },
                );
              },
            }),
          },
          k,
        );
    return (0, N.jsxs)(`div`, {
      className: `contact-fields`,
      children: [
        (0, N.jsxs)(`div`, {
          className: `grid-2`,
          children: [
            f(`name`, `Full name`, `Your name`),
            f(`email`, `Email`, ``, `email`),
            f(`phone`, `Phone`, `(555) 555-5555`, `tel`),
          ],
        }),
        (0, N.jsx)(`span`, { className: `eyebrow address-head`, children: `Address` }),
        (0, N.jsxs)(`div`, {
          className: `address-grid`,
          children: [
            f(`street`, `Street address`, `e.g. 412 Hoosick Street`),
            f(`street2`, `Apt, suite, unit (optional)`, `e.g. Apt 3B`),
            f(`city`, `City`, `City`),
            f(`state`, `State`, `e.g. NY`),
            f(`zip`, `ZIP code`, `e.g. 12180`),
            f(`country`, `Country`, `Country`),
          ],
        }),
      ],
    });
  }
""" + out[_e:]
