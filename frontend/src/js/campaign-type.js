// The four campaign types, in one place.
//
// A campaign's type is chosen once in the composer and then drawn in three
// different surfaces: the composer's own preview, the bell, and — since the
// type stopped being decorative in DM mode — the chat bubble. The palette used
// to be written out in team-announcements.js and again in utils.js, byte for
// byte. Two copies of four hex values is not a style problem: the operator
// picks «تنبيه (أصفر)» in one file's amber and the member is shown another
// file's amber, and nobody finds out because both look yellow.
//
// So: one row per type, and every site reads the row rather than the colour.
// If you are adding a colour literal for a campaign type anywhere else, add it
// here instead.
//
// `faIcon` and `lucideIcon` are two fields of ONE row, not two tables. The
// icon sets genuinely differ by surface and it is deliberate: Font Awesome
// draws from a class name, so a bell row survives being re-rendered by the
// notification poll, while a Lucide icon is an inline SVG that would need
// `lucide.createIcons()` called again every time. The composer builds its own
// markup and calls createIcons anyway, so it uses Lucide.
window.CAMPAIGN_TYPES = {
  info:    { color: '#3f8ff9', label: 'معلومة',  faIcon: 'fa-circle-info',          lucideIcon: 'info' },
  success: { color: '#22c55e', label: 'خبر كويس', faIcon: 'fa-circle-check',         lucideIcon: 'check-circle' },
  warning: { color: '#f59e0b', label: 'تنبيه',   faIcon: 'fa-triangle-exclamation', lucideIcon: 'alert-triangle' },
  promo:   { color: '#c1ff11', label: 'عرض',     faIcon: 'fa-gift',                 lucideIcon: 'gift' },
};

// An unknown type is not an error — a campaign saved before a type existed, or
// a value from a newer version of the composer, still has to draw as
// something. Callers that need "info by default" use campaignType(); the bell
// keeps its own fallback for the separate case of an ordinary system
// notification, which has no campaign type at all and should stay a gold bell.
window.campaignType = function (t) {
  return window.CAMPAIGN_TYPES[t] || window.CAMPAIGN_TYPES.info;
};

// Is this a type we actually know how to draw? The chat asks this rather than
// campaignType(), because a message with no campaign type must be drawn as an
// ordinary message — falling back to info would put a blue stripe on every
// message a person typed.
window.isCampaignType = function (t) {
  return !!(t && Object.prototype.hasOwnProperty.call(window.CAMPAIGN_TYPES, t));
};
