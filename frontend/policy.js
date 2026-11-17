'use strict';
/* The privacy policy and terms of use, in plain English. One source: shown in the first-run screen, in Support and in Panel settings.
   Change the text here, and raise POLICY_VERSION in backend/brand.py when people must accept it again. */
const POLICY = {
  updated: '17 November 2026',
  intro: () => `${BRAND.name} is made by ${BRAND.publisher} (${BRAND.publisherName}). It runs Minecraft servers on your own computer. This page has two parts: the privacy policy (what it stores, what it sends over the internet, what you can control) and the terms of use.`,
  sections: () => [
    { h: 'The short version', p: [
      'Everything stays on your PC. There is no account, no sign-in to us and no advertising.',
      `Your servers, worlds, player names and settings are never sent to ${BRAND.publisher}. There is no usage counting and no tracking. The only thing that can reach the developer is a support report, and only if you press Send in Support. The app also checks GitHub for new versions. Both are described below.`,
      'The app also goes online to fetch Minecraft files and, if you use it, to share a public address. The list is below.',
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
      'Update check: GitHub, to see if a newer version has been released. Nothing about you or your servers is sent. The app only tells you; it never installs anything by itself.',
      'Public address: playit.gg. Its helper makes a tunnel so friends can join from outside your home network. playit sees your IP address and the traffic of players who connect through it. Using it is under playit.gg\'s own terms and privacy policy. You can choose "Use my own playit app" or skip it.',
      'Discord notices (off by default): if you paste a webhook link, the app posts messages such as "server started" and, only if you switch it on, player names. They go to Discord.',
      'Player head pictures (off by default): if you switch this on, player names are sent to minotar.net and mc-heads.net to get the small face images. If it is off, the app draws a simple face instead.',
    ] },
    { h: 'What can reach the developer', p: [
      'Only one thing, and only when you press a button. The service is a small server on Cloudflare that the developer runs. Cloudflare handles the connection like any website, but the developer\'s server does not store your IP address.',
    ], list: [
      'Send report (only when you press Send in Support): the text you see in the box is sent, and nothing else. It has the version, Windows version, Java status and the last lines of the app log. You can edit or delete anything in the box first, and add an email address if you want a reply. The app log can contain a server name or a player name, so read it before you send.',
    ] },
    { h: 'What is never done', p: [
      'No advertising, no tracking of what you do inside the app, and no automatic crash reports. Apart from the check for new versions, which sends nothing about you, nothing goes to the developer unless you press Send.',
      'The support report can also just be copied to your clipboard. It leaves out your Windows user name and your secrets either way.',
    ] },
    { h: 'Your choices', p: [
      'You can switch player heads on or off at any time in Panel settings > Privacy.',
      'To stop everything, close the app and uninstall it. To remove your data from your PC, delete the %APPDATA%\\zighost folder, or uninstall and choose to remove the data. Email the address below if you want a report you sent to be deleted.',
      'If you do not accept the privacy policy and the terms, close the app. It cannot be used without them.',
    ] },
    { h: 'Terms of use', p: [
      `These terms are between you and ${BRAND.publisherName}, an independent developer in India, who makes ${BRAND.name}. By installing or using the app you agree to them.`,
      'You may install the app on your own computers and use it to host Minecraft servers for yourself and the people you invite. Please do not use it to break the law, to harm people, or to attack other servers or networks; to spread malware or collect other people\'s personal data without their knowledge; or to pass it off, or a changed copy, as an official Minecraft product or as made by someone else.',
    ] },
    { h: 'Minecraft and other companies', p: [
      `${BRAND.name} is not made by or connected to Mojang, Microsoft, PaperMC, Fabric, Modrinth, playit.gg, Discord, GitHub or Cloudflare. Minecraft is a trademark of Mojang AB. You must accept the Minecraft EULA yourself when you create a server and follow Mojang's usage guidelines, including its rules about charging money for a server.`,
      'The app works with software and services made by others. Each has its own terms, and you must follow them. They can change or stop at any time, and the developer is not responsible for them.',
    ] },
    { h: 'Your server, no warranty, liability', p: [
      'Your worlds stay on your PC and are yours. You are responsible for your server: who you let in, what they do there, and following the laws that apply to you. Keep your own backups of worlds you care about.',
      'The app is provided as it is and as available, without a warranty. It may contain bugs or stop working after an update to Windows, Java or Minecraft.',
      'As far as the law allows, the developer is not liable for loss of worlds, files or data, for downtime, or for any indirect loss from using or not being able to use the app. Nothing here limits a right that the law does not allow to be limited.',
    ] },
    { h: 'Changes and governing law', p: [
      'The app and these terms may change. If they change in a way that matters, the date below changes and you will be asked to accept the new version. The full terms are also on the Zighost website.',
      'These terms follow the laws of India. Courts in Delhi, India have jurisdiction over disputes about them, unless the law gives you the right to go elsewhere.',
    ] },
    { h: 'Contact', p: [
      `Questions, bug reports or a request about your data: ${BRAND.supportEmail}`,
      `${BRAND.copyright}. Privacy policy and terms version ${BRAND.policyVersion}, updated ${POLICY.updated}.`,
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
