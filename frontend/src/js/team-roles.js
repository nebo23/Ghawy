// Every role colour in the team dashboard, in one place.
//
// A person's role is drawn on four surfaces: the members table, the role
// modal's option list, the permissions tab, and the feedback cards. The
// palette used to live in three files with three different sets of values,
// so the same person was described differently depending on which tab you
// had open — the owner was #a855f7 in the members table, and the permissions
// tab painted every non-owner the same blue regardless of role, so a Community
// Manager was purple on one screen and blue on the next.
//
// So: one row per role, and every surface reads the row. If you are about to
// write a role colour literal anywhere else, add it here instead. This is the
// same shape as campaign-type.js, for the same reason.
//
// `tint` is the rgb triplet behind the translucent background and border. It
// is stored separately from `color` because the background is the same hue at
// 15% and the border at 30% — one value, three uses, so they cannot drift.
//
// The keys ARE the CSS class names, which is why the three server-side roles
// carry underscores (that is what `GET /admin/staff/roles` returns) while the
// synthetic states use the hyphen the markup already had.
//
// Chosen from the values already in the codebase, not invented:
//   owner              #a855f7  the members-table purple — the one actually
//                               rendered, and the hue of every rgba(168,85,247)
//                               background already in team.css. The dead
//                               `.perm-role.owner` #c084fc rule is gone.
//   community_manager  #a78bfa  unchanged.
//   technical_engineer #60a5fa  was #3f8ff9, which is the dashboard's brand
//                               primary and the colour of its buttons and the
//                               `.role-badge.admin` chip. A role must not wear
//                               the primary. #60a5fa is the blue the
//                               permissions tab was already using.
//   customer_success   #22c55e  unchanged.
//   no-role            #f59e0b  unchanged — "in the dashboard, but nobody has
//                               named their role yet".
//   member             #aaa     unchanged — no dashboard access at all.
window.TEAM_ROLES = {
  owner:              { color: '#a855f7', tint: '168,85,247'  },
  community_manager:  { color: '#a78bfa', tint: '139,92,246'  },
  technical_engineer: { color: '#60a5fa', tint: '59,130,246'  },
  customer_success:   { color: '#22c55e', tint: '34,197,94'   },
  'no-role':          { color: '#f59e0b', tint: '245,158,11'  },
  member:             { color: '#aaaaaa', tint: '255,255,255' },
};

// A role the front end has never heard of is not an error. The role catalog is
// the server's (`GET /admin/staff/roles`), so a role added there ships before
// this file knows about it — and the old code turned that into
// `ROLE_COLORS[key] || ''`, i.e. no class, no colour, silently. Grey and
// legible is the right answer: plain, not broken.
window.TEAM_ROLE_UNKNOWN = { color: '#aaaaaa', tint: '255,255,255' };

window.teamRole = function (key) {
  return window.TEAM_ROLES[key] || window.TEAM_ROLE_UNKNOWN;
};

// The class name to stamp on a badge. Empty for a role we do not have a row
// for, so the badge falls back to the neutral base rule in team.css rather
// than to whatever the previous sibling happened to be styled as.
window.teamRoleClass = function (key) {
  return Object.prototype.hasOwnProperty.call(window.TEAM_ROLES, key) ? key : '';
};

// The three badge shapes are styled from the table rather than from three
// hand-written CSS blocks. Generating them is what makes "one palette" true:
// the members table (.role-badge / .rc-role-badge), the permissions tab
// (.perm-role) and the feedback cards (.rc-role-badge) cannot disagree,
// because there is only one place left to edit.
(function injectRoleStyles() {
  const rules = Object.keys(window.TEAM_ROLES).map(function (key) {
    const r = window.TEAM_ROLES[key];
    // `#tab-permissions .perm-role` carries an ID, so a bare `.perm-role.key`
    // loses to it and the permissions tab stays grey. The scope has to be
    // repeated here to outrank the base rule — this is the one place the
    // generated selector is not simply the class name.
    return `.role-badge.${key},.rc-role-badge.${key},#tab-permissions .perm-role.${key}{` +
           `background:rgba(${r.tint},0.15);` +
           `color:${r.color};` +
           `border:1px solid rgba(${r.tint},0.30);}`;
  });
  const style = document.createElement('style');
  style.id = 'team-role-palette';
  style.textContent = rules.join('\n');
  document.head.appendChild(style);
})();
