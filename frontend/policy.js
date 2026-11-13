'use strict';
/* The privacy policy, in plain English. One source: shown in the first-run screen, in Support and in Panel settings.
   Change the text here, and raise POLICY_VERSION in backend/brand.py when people must accept it again. */
const POLICY = {
  updated: '13 November 2026',
  intro: () => `${BRAND.name} is made by ${BRAND.publisher} (${BRAND.publisherName}). It runs Minecraft servers on your own computer. This page says what it stores, what it sends over the internet, and what you can control.`,
  sections: () => [
    { h: 'The short version', p: [
      'Everything stays on your PC. There is no account, no sign-in to us and no advertising.',
      `${BRAND.publisher} does not receive your servers, worlds, player names, IP address or settings. This version sends nothing to ${BRAND.publisher}.`,
      'The app only goes online to fetch Minecraft files and, if you use it, to share a public address. The list is below.',
    ] },
    { h: 'What is stored on your PC', p: [
      'Servers, worlds, backups, settings, logs and downloaded helpers are kept in your Windows user folder: %APPDATA%\\zighost. You can open it from Support or Panel settings.',
      'Your playit key and Discord link are encrypted with your Windows account (DPAPI). Another Windows user cannot read them.',
      'Server logs can contain the names and IP addresses of the people who join your server. They stay on your PC. As the host, you are responsible for how you use them.',
    ] },
    { h: 'What the app sends over the internet', p: [
      'Only when you use the matching feature. Each of these is a connection from your PC to the service named, and that service sees your IP address.',
    ], list: [
      'Minecraft downloads: Mojang, PaperMC, Fabric and similar official sources, for the server type you pick. PaperMC asks who is downloading, so the email or website you type in Panel settings is sent to it (optional).',
      'Plugins and mods: Modrinth, for search and downloads.',
      'Java: Eclipse Temurin (Adoptium), if no suitable Java is found on your PC.',
      'Public address: playit.gg. Its helper makes a tunnel so friends can join from outside your home network. playit sees your IP address and the traffic of players who connect through it. Using it is under playit.gg\'s own terms and privacy policy. You can choose "Use my own playit app" or skip it.',
      'Discord notices (off by default): if you paste a webhook link, the app posts messages such as "server started" and, only if you switch it on, player names. They go to Discord.',
      'Player head pictures (off by default): if you switch this on, player names are sent to minotar.net and mc-heads.net to get the small face images. If it is off, the app draws a simple face instead.',
    ] },
    { h: 'What is never done', p: [
      `No tracking, no analytics and no crash reports are sent in this version. If a later version adds update checks or anonymous statistics, it will ask you first and this policy will change. You will be asked to accept the new version.`,
      'The support report (Support > Copy support report) is only copied to your clipboard. You decide whether to send it. It leaves out your Windows user name and your secrets.',
    ] },
    { h: 'Your choices', p: [
      'You can switch player heads on or off at any time in Panel settings > Privacy.',
      'To remove your data, close the app and delete the %APPDATA%\\zighost folder, or uninstall the app and choose to remove its data. Nothing is kept anywhere else by us.',
      'If you do not accept this policy, close the app. It cannot be used without it.',
    ] },
    { h: 'Minecraft and other companies', p: [
      `${BRAND.name} is not made by or connected to Mojang, Microsoft, PaperMC, Fabric, Modrinth, playit.gg or Discord. Minecraft is a trademark of Mojang AB. You must accept the Minecraft EULA yourself when you create a server.`,
      'The software is provided as it is, without a warranty. Keep your own backups of worlds you care about.',
    ] },
    { h: 'Contact', p: [
      `Questions, bug reports or a request about your data: ${BRAND.supportEmail}`,
      `${BRAND.copyright}. Policy version ${BRAND.policyVersion}, updated ${POLICY.updated}.`,
    ] },
  ],
};

function policyView() {
  return h('div', { class: 'policy' },
    h('p', { class: 'policy-intro', text: POLICY.intro() }),
    POLICY.sections().map(s => h('section', {}, h('h3', { text: s.h }),
      (s.p || []).map(t => h('p', { text: t })),
      s.list ? h('ul', {}, s.list.map(t => h('li', { text: t }))) : null)));
}
