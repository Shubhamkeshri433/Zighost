'use strict';
/* Every setting of server.properties that the panel knows, grouped, with defaults and plain-language hints.
   Only the settings people actually change are listed. Other keys in the file are never shown and never touched. */
window.MCP_SCHEMA = {
  groups: [
    { id: 'basics', title: 'Basics', desc: 'What players see first and the main rules.', fields: [
      { k: 'motd', label: 'Message in the server list', type: 'text', def: 'A Minecraft Server', hint: 'Supports colour codes like §a for green.' },
      { k: 'gamemode', label: 'Game mode', type: 'select', def: 'survival', opts: ['survival', 'creative', 'adventure', 'spectator'] },
      { k: 'difficulty', label: 'Difficulty', type: 'select', def: 'easy', opts: ['peaceful', 'easy', 'normal', 'hard'] },
      { k: 'max-players', label: 'Most players at once', type: 'number', def: '20', min: 1, max: 1000 },
      { k: 'white-list', label: 'Only listed players can join', type: 'bool', def: 'false', hint: 'Manage the list on the Players page.' },
      { k: 'online-mode', label: 'Only allow real Minecraft accounts', type: 'bool', def: 'true', hint: 'Turn this off only if you know why. Anyone could then join with any name.' },
    ] },
    { id: 'world', title: 'World', desc: 'Most of these only apply when a new world is created.', fields: [
      { k: 'level-seed', label: 'World seed', type: 'text', def: '', hint: 'Leave empty for a random world.' },
      { k: 'level-type', label: 'World type', type: 'select', def: 'minecraft:normal', opts: ['minecraft:normal', 'minecraft:flat', 'minecraft:large_biomes', 'minecraft:amplified'] },
      { k: 'generate-structures', label: 'Villages, temples and other structures', type: 'bool', def: 'true' },
      { k: 'allow-nether', label: 'Nether enabled', type: 'bool', def: 'true' },
      { k: 'hardcore', label: 'Hardcore', type: 'bool', def: 'false', hint: 'Players cannot respawn after they die.' },
      { k: 'spawn-protection', label: 'Spawn protection (blocks)', type: 'number', def: '16', min: 0, max: 1000, hint: 'Only operators can build this close to spawn. 0 turns it off.' },
      { k: 'allow-flight', label: 'Allow flying', type: 'bool', def: 'false', hint: 'Needed by some mods and plugins. Otherwise flying players are kicked.' },
      { k: 'enable-command-block', label: 'Command blocks', type: 'bool', def: 'false' },
    ] },
    { id: 'players', title: 'Players and mobs', desc: 'Rules for the people and creatures in the world.', fields: [
      { k: 'pvp', label: 'Players can fight each other', type: 'bool', def: 'true' },
      { k: 'force-gamemode', label: 'Reset game mode on every join', type: 'bool', def: 'false' },
      { k: 'spawn-monsters', label: 'Monsters spawn', type: 'bool', def: 'true' },
      { k: 'spawn-animals', label: 'Animals spawn', type: 'bool', def: 'true' },
      { k: 'spawn-npcs', label: 'Villagers spawn', type: 'bool', def: 'true' },
      { k: 'player-idle-timeout', label: 'Kick idle players after (minutes)', type: 'number', def: '0', min: 0, hint: '0 means never.' },
    ] },
    { id: 'performance', title: 'Performance', desc: 'Lower these on a slower PC. Memory is set in Server options above.', fields: [
      { k: 'view-distance', label: 'View distance (chunks)', type: 'number', def: '10', min: 3, max: 32 },
      { k: 'simulation-distance', label: 'Simulation distance (chunks)', type: 'number', def: '10', min: 3, max: 32 },
    ] },
  ],
  presets: [
    { id: 'survival', title: 'Survival with friends', note: 'Normal difficulty, 10 players.', set: { gamemode: 'survival', difficulty: 'normal', pvp: 'true', 'max-players': '10', hardcore: 'false', 'spawn-monsters': 'true' } },
    { id: 'creative', title: 'Creative builders', note: 'No mobs, flying, command blocks.', set: { gamemode: 'creative', difficulty: 'peaceful', pvp: 'false', 'spawn-monsters': 'false', 'allow-flight': 'true', 'enable-command-block': 'true' } },
    { id: 'hardcore', title: 'Hardcore', note: 'Hard difficulty, one life.', set: { hardcore: 'true', difficulty: 'hard', pvp: 'true', 'max-players': '5' } },
    { id: 'lobby', title: 'Lobby or minigames', note: 'Adventure mode, peaceful, nothing spawns.', set: { gamemode: 'adventure', difficulty: 'peaceful', 'spawn-monsters': 'false', 'spawn-animals': 'false', 'spawn-npcs': 'false', 'spawn-protection': '0', 'force-gamemode': 'true' } },
    { id: 'private', title: 'Private (whitelist)', note: 'Only people you add can join.', set: { 'white-list': 'true', 'enforce-whitelist': 'true', 'max-players': '8' } },
    { id: 'lowend', title: 'Slower PC', note: 'Shorter view distance, fewer players.', set: { 'view-distance': '6', 'simulation-distance': '5', 'max-players': '8' } },
  ],
};
