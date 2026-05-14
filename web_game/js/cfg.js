export const MELODIES = Object.freeze({
  tetris: { label: 'Tetris Theme', notes: [
    // A section
    659,494,523,587,523,494,440,440,523,659,587,523,494,494,523,587,659,523,440,440,
    // B section
    587,698,880,784,698,659,523,659,587,523,494,494,523,587,659,523,440,440,
  ]},
  twinkle: { label: 'Twinkle Twinkle', notes: [
    262,262,392,392,440,440,392,   // Twinkle twinkle little star
    349,349,330,330,294,294,262,   // How I wonder what you are
    392,392,349,349,330,330,294,   // Up above the world so high
    392,392,349,349,330,330,294,   // Like a diamond in the sky
    262,262,392,392,440,440,392,   // Twinkle twinkle little star
    349,349,330,330,294,294,262,   // How I wonder what you are
  ]},
  furElise: { label: 'Fur Elise', notes: [
    659,622,659,622,659,494,587,523,440,  // opening motif
    262,330,440,494,                       // A minor arpeggio
    330,415,494,523,                       // E major
    659,622,659,622,659,494,587,523,440,  // motif repeat
    262,330,440,494,                       // A minor arpeggio
    330,523,494,440,                       // resolution
    494,523,554,523,494,440,523,440,415,  // middle passage
    440,466,523,440,392,349,440,494,523,  // descending run
    659,622,659,622,659,494,587,523,440,  // motif return
    262,330,440,494,330,523,494,440,      // final phrase
  ]},
  mario: { label: 'Super Mario', notes: [
    659,659,659,523,659,784,392,           // iconic opener
    523,392,330,440,494,466,440,           // first phrase
    392,659,784,880,698,784,              // ascending run
    659,523,587,494,                       // second phrase
    523,392,330,440,494,466,440,           // repeat first phrase
    392,659,784,880,698,784,              // ascending run repeat
    659,523,587,494,                       // closing phrase
  ]},
  gameOfThrones: { label: 'Game of Thrones', notes: [
    196,262,311,349,392,262,311,349,       // main motif
    415,466,415,392,349,392,               // tension phrase
    196,262,311,349,392,262,311,349,       // motif repeat
    311,349,294,311,                       // variation
    196,262,311,349,392,392,415,392,349,  // extended phrase
    311,349,262,311,196,                   // resolution
  ]},
  birthday: { label: 'Happy Birthday', notes: [
    262,262,294,262,349,330,   // Happy Birthday to you
    262,262,294,262,392,349,   // Happy Birthday to you
    262,262,523,440,349,330,294, // Happy Birthday dear [name]
    466,466,440,349,392,349,   // Happy Birthday to you
  ]},
  sevenNationArmy: { label: 'Seven Nation Army', notes: [
    165,165,196,165,147,131,123,        // main riff
    165,165,196,165,147,131,123,131,    // riff with tail
    165,165,196,165,147,131,147,131,123, // variation
    165,165,196,165,147,131,123,        // main riff
    131,131,131,123,131,123,121,        // lower variation
    165,165,196,165,147,131,123,        // main riff return
  ]},
  sweetChild: { label: "Sweet Child O' Mine", notes: [
    587,587,440,587,370,440,392,440,   // bar 1
    349,440,392,440,330,440,392,440,   // bar 2
    587,587,440,587,370,440,392,440,   // bar 1 repeat
    349,440,392,440,330,440,294,440,   // bar 2 variation
    587,587,440,587,370,440,392,440,   // bar 1
    330,440,392,440,294,440,330,392,   // bar 3
    587,587,440,587,370,440,392,440,   // bar 1 return
  ]},
  imperialMarch: { label: 'Imperial March', notes: [
    392,392,392,311,466,392,311,466,392,          // G-G-G-Eb-Bb-G-Eb-Bb-G
    587,587,587,622,466,392,311,466,392,          // D-D-D-Eb-Bb-G-Eb-Bb-G
    784,392,392,784,740,698,659,622,659,          // high G resolve, chromatic
    415,554,523,494,440,466,                      // Ab-Db-C-B-A-Bb
    311,392,311,466,392,                           // Eb-G-Eb-Bb-G
    784,392,392,784,740,698,659,622,659,          // high phrase repeat
    415,554,523,494,440,466,311,392,311,466,392,  // full resolve
  ]},
  takeOnMe: { label: 'Take On Me', notes: [
    740,740,587,494,494,659,659,659,740,740,740,659,659,440,440,440,  // phrase 1
    740,740,587,494,494,659,659,659,740,740,740,659,659,440,440,440,  // phrase 1 repeat
    587,587,587,587,554,554,554,494,                                    // bridge
    740,740,587,494,494,659,659,659,740,740,740,659,659,440,440,440,  // phrase 1 return
    494,494,523,587,659,740,784,880,                                    // ascending climax
  ]},
  odeToJoy: { label: 'Ode to Joy', notes: [
    330,330,349,392,392,349,330,294,              // E-E-F-G-G-F-E-D
    262,262,294,330,330,294,294,                  // C-C-D-E-E-D-D
    330,330,349,392,392,349,330,294,              // phrase 1 repeat
    262,262,294,330,294,262,262,                  // C-C-D-E-D-C-C
    294,294,330,262,294,349,330,262,              // bridge
    294,349,330,294,262,294,196,                  // descending resolve
    330,330,349,392,392,349,330,294,              // phrase 1 return
    262,262,294,330,294,262,262,                  // final resolve
  ]},
  hedwig: { label: "Hedwig's Theme", notes: [
    494,659,784,740,659,988,880,740,   // opening phrase
    659,784,740,622,698,494,           // second phrase
    494,698,659,622,466,494,           // third phrase
    659,784,740,659,988,1047,988,880,  // climax
    784,494,494,466,494,               // descent
    659,784,740,659,988,1047,988,784,  // return climax
    659,523,494,440,494,523,659,784,   // coda run
  ]},
  megalovania: { label: 'Megalovania', notes: [
    294,294,587,440,415,392,349,294,349,392,  // riff on D
    262,262,587,440,415,392,349,294,349,392,  // riff on C
    247,247,587,440,415,392,349,294,349,392,  // riff on B
    233,233,587,440,415,392,349,294,349,392,  // riff on Bb
    294,294,587,440,415,392,349,294,349,392,  // riff repeat
    392,415,440,466,523,587,622,659,          // ascending run
  ]},
  smokeOnWater: { label: 'Smoke on the Water', notes: [
    196,233,262,                              // da-da-DUM
    196,233,277,262,                          // da-da-DUM-DUM
    196,233,262,233,196,                      // da-da-DUM-da-da
    196,233,262,                              // da-da-DUM
    196,233,277,262,                          // da-da-DUM-DUM
    196,233,262,233,196,                      // da-da-DUM-da-da
    262,311,349,311,262,233,196,              // upper variation
    262,311,349,311,262,233,196,              // upper variation repeat
  ]},
  starWars: { label: 'Star Wars', notes: [
    392,392,392,311,466,                      // da-da-da-da-DAAA
    392,392,392,311,466,392,                  // repeat with resolution
    587,587,587,622,466,370,392,              // second phrase
    587,587,587,622,466,370,392,              // second phrase repeat
    784,392,392,784,740,698,659,622,          // high run
    659,523,622,587,523,466,523,392,          // descending close
  ]},
  greenHillZone: { label: 'Green Hill Zone', notes: [
    659,659,784,659,587,523,494,523,          // main phrase
    440,494,523,587,659,698,659,587,523,      // ascending run
    659,659,784,659,587,523,494,523,          // main phrase repeat
    440,523,587,659,784,659,587,523,440,      // extended run
    659,784,880,784,659,587,523,587,659,      // high phrase
    523,587,659,523,440,494,523,              // closing phrase
  ]},
  blueDaBaDee: { label: 'Blue (Da Ba Dee)', notes: [
    // "I'm blue da ba dee da ba di"
    330,392,440,494,440,392,330,              // I'm blue da ba dee
    330,392,440,494,440,392,330,294,          // da ba di repeat
    330,392,440,494,523,494,440,392,          // ascending phrase
    440,392,330,294,262,294,330,              // descending resolve
    330,392,440,494,440,392,330,              // chorus return
    523,523,494,440,392,440,494,440,          // upper melody
    330,392,440,494,523,587,523,494,440,      // big ascending
    392,330,294,330,392,440,392,330,          // closing run
  ]},
  canonInD: { label: 'Canon in D', notes: [
    587,523,494,440,392,349,392,440,              // D-C-B-A-G-F#-G-A (bass line)
    587,523,494,440,392,349,392,440,              // bass repeat
    587,659,587,523,494,440,494,523,587,          // melody over bass
    523,494,440,392,440,494,523,587,659,          // ascending melody
    784,740,698,659,587,523,494,440,              // high descending run
    392,440,494,523,587,659,698,784,              // big ascending
    587,659,587,523,494,440,392,440,              // melody return
    494,523,587,659,587,523,494,440,392,          // gentle close
  ]},
  nokiaTune: { label: 'Nokia Tune', notes: [
    659,587,370,415,                          // E-D-F#-G#
    523,494,294,330,                          // C-B-D-E
    494,440,330,370,                          // B-A-E-F#
    440,440,440,                              // A-A-A (hold)
    659,587,370,415,                          // E-D-F#-G# repeat
    523,494,294,330,                          // C-B-D-E
    494,440,330,370,                          // B-A-E-F#
    440,440,440,                              // final A
  ]},
  piratesOfCaribbean: { label: 'Pirates of the Caribbean', notes: [
    // "He's a Pirate" main theme
    294,330,349,349,349,330,294,330,349,      // da-da DUM dum dum da da-da DUM
    440,494,494,494,440,349,440,494,          // ascending phrase
    523,494,440,349,440,330,294,              // descending resolve
    294,330,349,349,349,330,294,330,349,      // theme repeat
    440,494,494,494,440,349,440,494,          // ascending repeat
    523,587,523,494,440,349,330,294,          // high descend
    587,523,494,440,349,330,294,262,294,      // final descent
    349,440,494,523,587,659,587,523,494,      // triumphant climax
  ]},
});

// Selectable cars. Paths are relative to the project root (one level above js/).
export const CARS = Object.freeze([
  {
    file: 'Ambulance.glb', label: 'Ambulance', scale: 0.05, rotationY: Math.PI,
    unlockScore: 0,
    theme: {
      sky: 0x1a0000, ambient: 0x330000,
      light1: 0xff0000, light2: 0xffffff,
      road: 0x0d0000, wall: { color: 0x200000, emissive: 0x440000 },
      marker1: 0xff2200, marker2: 0xff6600,
    },
  },
  {
    file: 'Blue car.glb', label: 'Blue Car', scale: 0.07, rotationY: Math.PI,
    unlockScore: 0,
    theme: {
      sky: 0x00060f, ambient: 0x001133,
      light1: 0x0066ff, light2: 0x00ffff,
      road: 0x000810, wall: { color: 0x001020, emissive: 0x002244 },
      marker1: 0x0088ff, marker2: 0x00ffff,
    },
  },
  {
    file: 'Mazarati car.glb', label: 'Lamborghini', scale: 0.015, rotationY: Math.PI,
    unlockScore: 0,
    theme: {
      sky: 0x0d0020, ambient: 0x1a0033,
      light1: 0xaa00ff, light2: 0xffd700,
      road: 0x070010, wall: { color: 0x0f0020, emissive: 0x2a0055 },
      marker1: 0xaa00ff, marker2: 0xffd700,
    },
  },
  {
    file: 'Police Car.glb', label: 'Police Car', scale: 2, rotationY: Math.PI,
    unlockScore: 0,
    theme: {
      sky: 0x000814, ambient: 0x00001a,
      light1: 0xff0033, light2: 0x0044ff,
      road: 0x050508, wall: { color: 0x060615, emissive: 0x000044 },
      marker1: 0xff0033, marker2: 0x0044ff,
    },
  },
  {
    file: 'Red Car.glb', label: 'Red Car', scale: 2.5, rotationY: 0,
    unlockScore: 0,
    theme: {
      sky: 0x1a0500, ambient: 0x2a0800,
      light1: 0xff4400, light2: 0xff8800,
      road: 0x0d0200, wall: { color: 0x1a0400, emissive: 0x440800 },
      marker1: 0xff4400, marker2: 0xff8800,
    },
  },
  {
    file: 'Taxi.glb', label: 'Taxi', scale: 0.05, rotationY: Math.PI,
    unlockScore: 0,
    theme: {
      sky: 0x0d0a00, ambient: 0x1a1200,
      light1: 0xffdd00, light2: 0xff8800,
      road: 0x090800, wall: { color: 0x120f00, emissive: 0x332200 },
      marker1: 0xffdd00, marker2: 0xff8800,
    },
  },
  {
    file: 'Humvee.glb', label: 'Humvee', scale: 1.3, rotationY: -Math.PI / 2,
    unlockScore: 5000,
    theme: {
      sky: 0x0a0d00, ambient: 0x1a2200,
      light1: 0x88cc00, light2: 0x44ff00,
      road: 0x060800, wall: { color: 0x0f1500, emissive: 0x223300 },
      marker1: 0x88cc00, marker2: 0x44ff00,
    },
  },
  {
    file: 'Tank.glb', label: 'Tank', scale: 0.4, rotationY: -Math.PI/2,
    unlockScore: 15000,
    theme: {
      sky: 0x0f0505, ambient: 0x200a0a,
      light1: 0xff3300, light2: 0xff9900,
      road: 0x0a0303, wall: { color: 0x180505, emissive: 0x331000 },
      marker1: 0xff3300, marker2: 0xff9900,
    },
  },
  {
    file: 'Dominus.glb', label: 'Dominus', scale: 2.6, rotationY: -Math.PI * 1.2,
    unlockScore: 30000,
    theme: {
      sky: 0x05000f, ambient: 0x0a001a,
      light1: 0x8800ff, light2: 0xff0088,
      road: 0x030008, wall: { color: 0x080014, emissive: 0x110033 },
      marker1: 0x8800ff, marker2: 0xff0088,
    },
  },
  {
    file: 'Truck.glb', label: 'Truck', scale: 0.25, rotationY: Math.PI,
    unlockScore: 50000,
    theme: {
      sky: 0x000a0d, ambient: 0x001520,
      light1: 0x00bbff, light2: 0x0055ff,
      road: 0x000608, wall: { color: 0x000d14, emissive: 0x002233 },
      marker1: 0x00bbff, marker2: 0x0055ff,
    },
  },
  {
    file: 'Motorcycle.glb', label: 'Motorcycle', scale: 0.04, rotationY: 0,
    unlockScore: 100000,
    theme: {
      sky: 0x0d0800, ambient: 0x1a1000,
      light1: 0xffaa00, light2: 0xff5500,
      road: 0x080500, wall: { color: 0x140a00, emissive: 0x331500 },
      marker1: 0xffaa00, marker2: 0xff5500,
    },
  },
  {
    file: 'Speeder Bike.glb', label: 'Speeder Bike', scale: 4.5, rotationY: -Math.PI*1.5,
    unlockScore: 150000,
    theme: {
      sky: 0x000d0d, ambient: 0x001a1a,
      light1: 0x00ffcc, light2: 0x00ff66,
      road: 0x000806, wall: { color: 0x001410, emissive: 0x003322 },
      marker1: 0x00ffcc, marker2: 0x00ff66,
    },
  },
]);

export function isCarUnlocked(carIdx, personalBest) {
  return (CARS[carIdx].unlockScore ?? 0) <= personalBest;
}

export const STORE_ITEMS = Object.freeze([
  { id: 'extra_life',   label: 'Extra Life',   price: 50,  description: 'Start with 4 lives (1 use)'              },
  { id: 'double_coins', label: 'Double Coins', price: 100, description: '2x coin value for 1 round'              },
  { id: 'magnet',       label: 'Coin Magnet',  price: 120, description: 'Collect coins from nearby lanes (1 use)' },
  { id: 'head_start',   label: 'Head Start',   price: 40,  description: 'Boost to Level 2 (stackable)'           },
]);

// All game-wide constants. Domain-specific constants (PATTERNS, BASS_NOTES)
// live in their respective modules.
export const CFG = Object.freeze({
  LANES:             [-4.2, 0, 4.2],
  PLAYER_Z:          5,
  SPAWN_Z:           -90,
  DESPAWN_Z:         13,
  LEVEL_DURATION:    30,      // seconds per level
  // Per-level config — speed (units/s), beatMs (obstacle spawn interval), and scene theme.
  // Add more entries to extend the difficulty curve; the last entry is reused beyond it.
  LEVELS: Object.freeze([
    { speed: 35, beatMs: 480, theme: { sky: 0x03001a, ambient: 0x1a0933, light1: 0xff00ff, light2: 0x00ffff, road: 0x07071a, wall: { color: 0x0f0020, emissive: 0x2a0044 }, marker1: 0xff00ff, marker2: 0x00ffff } },
    { speed: 44, beatMs: 440, theme: { sky: 0x1a0800, ambient: 0x331200, light1: 0xff6600, light2: 0xffcc00, road: 0x0d0400, wall: { color: 0x200800, emissive: 0x441500 }, marker1: 0xff6600, marker2: 0xffcc00 } },
    { speed: 53, beatMs: 395, theme: { sky: 0x00060f, ambient: 0x001133, light1: 0x0066ff, light2: 0x00ffee, road: 0x000810, wall: { color: 0x001020, emissive: 0x002244 }, marker1: 0x0066ff, marker2: 0x00ffee } },
    { speed: 62, beatMs: 350, theme: { sky: 0x001400, ambient: 0x002200, light1: 0x00ff44, light2: 0xaaff00, road: 0x000d00, wall: { color: 0x001500, emissive: 0x003300 }, marker1: 0x00ff44, marker2: 0xaaff00 } },
    { speed: 72, beatMs: 310, theme: { sky: 0x1a0000, ambient: 0x330000, light1: 0xff0033, light2: 0xff4400, road: 0x0d0000, wall: { color: 0x200000, emissive: 0x440000 }, marker1: 0xff0033, marker2: 0xff4400 } },
    { speed: 80, beatMs: 275, theme: { sky: 0x0d0d0d, ambient: 0x1a1a1a, light1: 0xffffff, light2: 0xffd700, road: 0x080808, wall: { color: 0x151515, emissive: 0x333300 }, marker1: 0xffffff, marker2: 0xffd700 } },
  ]),
  BACKGROUNDS: Object.freeze([
    'background/ambulance.jpg',
    'background/new-york.jpg',
    'background/Monaco.jpg',
    'background/Dubai.jpg',
    'background/Tel aviv.jpg',
    'background/Cali.jpg',
    'background/paris.jpg',
    'background/rio.jpg',
  ]),
  LIVES:             3,
  HIT_WINDOW:        1.6,     // z-units from player centre for collision detection
  BLOCK:             Object.freeze({ W: 3.0, H: 1.0, D: 1.4 }),
  POINTS_BASE:       150,
  COMBO_MULTS:       Object.freeze([1, 2, 4, 8, 16, 32]),
  ROAD_SEGS:         24,
  SEG_LEN:           6,
  ROAD_W:            14.6,
  ROAD_MARKER_EVERY: 2,       // place lane markers every N segments
  JUMP_FORCE:        12,      // initial upward velocity on jump
  GRAVITY:           28,      // downward acceleration
  GROUND_Y:          0.5,     // resting Y position of the car
  BOLT_SCALE:        3.0,     // adjust if bolt GLB is too big/small
  BOLT_INTERVAL_MS:  8000,    // ms between bolt spawns
  BOOST_DURATION:    3,       // seconds the speed boost lasts
  BOOST_SPEED_MULT:  1.5,     // speed multiplier during boost
  HEART_SCALE:       .005,     // adjust if heart GLB is too big/small
  HEART_INTERVAL_MS: 15000,   // ms between heart spawns
  BIRD_Y:            3.0,     // world-space Y the bird flies at (single jump peak)
  BIRD_HIT_MIN_Y:    2.0,     // bottom of kill zone (above car roof on ground)
  BIRD_HIT_MAX_Y:    4.1,     // top of kill zone (below double-jump peak ~5.64)
  BIRD_INTERVAL_MS:  12000,   // ms between bird spawns
  COIN_INTERVAL_MS:  3000,    // ms between coin spawns
  COIN_SCALE:        2.0,     // torus radius
  COPPER_COIN_SCALE:  0.3,     // copper coin size
  COIN_VALUE:        1,       // base coins per pickup
  COIN_Y:            1.2,     // float height above road
});
