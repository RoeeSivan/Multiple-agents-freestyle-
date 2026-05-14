import * as THREE from 'three';
import { GLTFLoader } from 'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/jsm/loaders/GLTFLoader.js';
import { CFG } from './cfg.js';
import { scene } from './scene.js';
import { GEO, MAT } from './assets.js';
import { state } from './state.js';
import { playLaserShootSound } from './audio.js';
import { car } from './player.js';

// ── Obstacle definitions ───────────────────────────────────────
// Add / remove entries here to change which models appear as red obstacles.
// `scale` controls the rendered size — tune each independently.
const OBSTACLE_DEFS = [
  { file: 'Traffic Cone.glb',    scale: 3.0 }, //okay
  { file: 'Fire hydrant.glb',    scale: 0.01 },
  { file: 'Traffic Barrier.glb', scale: 2.1 },
  { file: 'Barricade.glb',       scale: 1.0 }, //okay
  { file: 'Barrel.glb',          scale: 2.0 },
];

// Loaded templates — populated asynchronously at startup.
const obstacleTemplates = [];
let boltTemplate = null;
const loader = new GLTFLoader();

loader.load(
  new URL('../Bolt.glb', import.meta.url).href,
  (gltf) => { boltTemplate = gltf.scene; },
  undefined,
  (err) => console.error('[bolt] Failed to load Bolt.glb:', err),
);

let droneTemplate = null;
loader.load(
  new URL('../obstacles/Drone.glb', import.meta.url).href,
  (gltf) => { droneTemplate = gltf.scene; },
  undefined,
  (err) => console.error('[drone] Failed to load Drone.glb:', err),
);

let heartTemplate = null;
loader.load(
  new URL('../Heart.glb', import.meta.url).href,
  (gltf) => { heartTemplate = gltf.scene; },
  undefined,
  (err) => console.error('[heart] Failed to load Heart.glb:', err),
);

let coinTemplate = null;
loader.load(
  new URL('../Coin.glb', import.meta.url).href,
  (gltf) => { coinTemplate = gltf.scene; },
  undefined,
  (err) => console.error('[coin] Failed to load Coin.glb:', err),
);

let copperCoinTemplate = null;
loader.load(
  new URL('../Copper Coin.glb', import.meta.url).href,
  (gltf) => { copperCoinTemplate = gltf.scene; },
  undefined,
  (err) => console.error('[copperCoin] Failed to load Copper Coin.glb:', err),
);


OBSTACLE_DEFS.forEach((def, i) => {
  loader.load(
    new URL(`../obstacles/${def.file}`, import.meta.url).href,
    (gltf) => { obstacleTemplates[i] = gltf.scene; },
    undefined,
    (err) => console.error(`[blocks] Failed to load obstacle "${def.file}":`, err),
  );
});

// Spawn patterns — [lane(0-2), blockType][] per beat. Private to this module.
const PATTERNS = [
  [[1, 'green']],
  [[0, 'green'], [2, 'red']],
  [[2, 'green']],
  [[1, 'red'],   [0, 'green']],
  [[0, 'green'], [1, 'green']],
  [[2, 'red'],   [1, 'green']],
  [[1, 'green'], [0, 'red']],
  [[0, 'green']],
  [[2, 'green'], [1, 'red']],
  [[1, 'green'], [2, 'green']],
  [[0, 'red'],   [2, 'green']],
  [[1, 'red']],
];

function spawnBlock(lane, type) {
  let mesh;
  const availableObstacles = obstacleTemplates.filter(Boolean);
  if (type === 'red' && availableObstacles.length > 0) {
    let idx = Math.floor(Math.random() * OBSTACLE_DEFS.length);
    if (!obstacleTemplates[idx]) {
      // Pick a loaded template instead so scale matches the model
      const loadedIndices = OBSTACLE_DEFS.map((_, i) => i).filter(i => obstacleTemplates[i]);
      idx = loadedIndices[Math.floor(Math.random() * loadedIndices.length)];
    }
    const def  = OBSTACLE_DEFS[idx];
    const tmpl = obstacleTemplates[idx];
    mesh = tmpl.clone(true);
    mesh.scale.setScalar(def.scale);
    mesh.position.set(CFG.LANES[lane], 0, CFG.SPAWN_Z);
    console.log(`[blocks] spawned "${def.file}" at lane`, lane);
  } else {
    const mat = (type === 'green' ? MAT.green : MAT.red).clone();
    mesh = new THREE.Mesh(GEO.block, mat);
    mesh.position.set(CFG.LANES[lane], CFG.BLOCK.H / 2, CFG.SPAWN_Z);
    mesh.castShadow = true;
  }
  scene.add(mesh);
  state.blocks.push({ mesh, lane, type, processed: false });
}

// Spawns the next pattern from PATTERNS on the current beat.
export function spawnPatternBeat() {
  PATTERNS[state.patternIdx % PATTERNS.length].forEach(([lane, type]) => spawnBlock(lane, type));
  state.patternIdx++;
}

// Spawns a bolt power-up in a random lane.
export function spawnHeart() {
  if (!heartTemplate) return;
  const lane = Math.floor(Math.random() * 3);
  const mesh = heartTemplate.clone(true);
  mesh.scale.setScalar(CFG.HEART_SCALE);
  mesh.position.set(CFG.LANES[lane], 1.5, CFG.SPAWN_Z);
  scene.add(mesh);
  state.blocks.push({ mesh, lane, type: 'heart', processed: false });
}

function buildBirdMesh() {
  const group = new THREE.Group();
  const birdMat = new THREE.MeshStandardMaterial({
    color: 0xff8800, emissive: 0xff4400, emissiveIntensity: 0.8,
    roughness: 0.3, metalness: 0.4,
  });

  const body = new THREE.Mesh(new THREE.SphereGeometry(0.35, 8, 6), birdMat);
  body.scale.set(1.6, 0.9, 1.0);
  group.add(body);

  const wingGeo = new THREE.BoxGeometry(1.4, 0.08, 0.6);
  const lPivot = new THREE.Group(); lPivot.position.set(-0.56, 0, 0); lPivot.name = 'leftWingPivot';
  const rPivot = new THREE.Group(); rPivot.position.set( 0.56, 0, 0); rPivot.name = 'rightWingPivot';
  const lWing = new THREE.Mesh(wingGeo, birdMat); lWing.position.set(-0.7, 0, 0);
  const rWing = new THREE.Mesh(wingGeo, birdMat); rWing.position.set( 0.7, 0, 0);
  lPivot.add(lWing); rPivot.add(rWing);
  group.add(lPivot); group.add(rPivot);

  return group;
}

export function spawnBird() {
  const lane = Math.floor(Math.random() * 3);
  const mesh = buildBirdMesh();
  mesh.position.set(CFG.LANES[lane], CFG.BIRD_Y, CFG.SPAWN_Z);
  scene.add(mesh);
  state.blocks.push({ mesh, lane, type: 'bird', processed: false });
}

export function spawnDrone() {
  if (!droneTemplate) return;
  const lane = Math.floor(Math.random() * 3);
  const mesh = droneTemplate.clone(true);
  mesh.scale.setScalar(3);
  mesh.position.set(CFG.LANES[lane], CFG.BIRD_Y, CFG.SPAWN_Z);
  scene.add(mesh);
  state.blocks.push({ mesh, lane, type: 'drone', processed: false, lastShot: 0 });
}

// ── Laser projectiles ────────────────────────────────────────────
const LASER_SPEED  = 55;   // units/s toward player
const LASER_COOLDOWN = 0.6; // seconds between shots per drone

const laserGeo = new THREE.BoxGeometry(0.12, 0.12, 1.8);
const laserMat = new THREE.MeshBasicMaterial({
  color: 0xff0000,
  transparent: true,
  opacity: 0.9,
});

export function spawnLaser(x, y, z) {
  const mesh = new THREE.Mesh(laserGeo, laserMat.clone());
  mesh.position.set(x, y, z);

  // Direction vector from drone toward car's exact position
  const dx = car.position.x - x;
  const dy = car.position.y - y;
  const dz = car.position.z - z;
  const len = Math.sqrt(dx * dx + dy * dy + dz * dz);
  const dir = { x: dx / len, y: dy / len, z: dz / len };

  // Orient the mesh along the flight path
  mesh.lookAt(car.position.x, car.position.y, car.position.z);

  scene.add(mesh);
  state.lasers.push({ mesh, dir });
}

export function tickLasers(dt) {
  for (let i = state.lasers.length - 1; i >= 0; i--) {
    const l = state.lasers[i];
    l.mesh.position.x += l.dir.x * LASER_SPEED * dt;
    l.mesh.position.y += l.dir.y * LASER_SPEED * dt;
    l.mesh.position.z += l.dir.z * LASER_SPEED * dt;
    // Pulse glow
    l.mesh.material.opacity = 0.7 + 0.3 * Math.sin(state.elapsed * 20);
    if (l.mesh.position.z > CFG.DESPAWN_Z || l.mesh.position.y < -5) {
      scene.remove(l.mesh);
      state.lasers.splice(i, 1);
    }
  }
}

export function clearLasers() {
  state.lasers.forEach(l => scene.remove(l.mesh));
  state.lasers.length = 0;
}

export function spawnBolt() {
  if (!boltTemplate) return;
  const lane = Math.floor(Math.random() * 3);
  const mesh = boltTemplate.clone(true);
  mesh.scale.setScalar(CFG.BOLT_SCALE);
  mesh.position.set(CFG.LANES[lane], 1.5, CFG.SPAWN_Z);
  scene.add(mesh);
  state.blocks.push({ mesh, lane, type: 'bolt', processed: false });
}


export function spawnCoin() {
  if (!coinTemplate) return;
  const lane = Math.floor(Math.random() * 3);
  const isCopper = state.perkDoubleCoins && copperCoinTemplate;
  const template = isCopper ? copperCoinTemplate : coinTemplate;
  const mesh = template.clone(true);
  mesh.scale.setScalar(isCopper ? CFG.COPPER_COIN_SCALE : CFG.COIN_SCALE);
  mesh.position.set(CFG.LANES[lane], CFG.COIN_Y, CFG.SPAWN_Z);

  scene.add(mesh);
  state.blocks.push({ mesh, lane, type: 'coin', processed: false });
}

// Removes all active blocks from the scene and clears the state array.
export function clearBlocks() {
  state.blocks.forEach(b => scene.remove(b.mesh));
  state.blocks.length = 0;
  clearLasers();
}

// Advances block positions, pulses emissive intensity, and despawns passed blocks.
// Collision detection is NOT performed here — it lives in main.js to avoid
// the circular dependency that would arise from importing ui.js here.
export function tickBlocks(dt) {
  for (let i = state.blocks.length - 1; i >= 0; i--) {
    const b = state.blocks[i];
    b.mesh.position.z += state.speed * dt;

    if (b.type === 'coin') {
      b.mesh.rotation.y += dt * 3;
    }

    if (b.type === 'bird') {
      const flapAngle = Math.sin(state.elapsed * 8) * 0.7;
      const lPivot = b.mesh.getObjectByName('leftWingPivot');
      const rPivot = b.mesh.getObjectByName('rightWingPivot');
      if (lPivot) lPivot.rotation.z =  flapAngle;
      if (rPivot) rPivot.rotation.z = -flapAngle;
    }

    // Drone shooting — fires lasers toward the player when in range
    if (b.type === 'drone' && b.mesh.position.z > -30 && b.mesh.position.z < CFG.PLAYER_Z) {
      if (state.elapsed - (b.lastShot || 0) >= LASER_COOLDOWN) {
        b.lastShot = state.elapsed;
        spawnLaser(b.mesh.position.x, b.mesh.position.y, b.mesh.position.z);
        playLaserShootSound();
      }
    }

    if (b.knockbackVZ) {
      b.mesh.position.z += b.knockbackVZ * dt;
      b.mesh.rotation.y += b.knockbackRotY * dt;
      b.knockbackVZ     *= Math.pow(0.15, dt);
      if (b.knockbackVZ < 0.5) b.knockbackVZ = 0;
    }

    if (!b.processed && b.mesh.material) {
      const pulse = 0.5 + 0.5 * Math.sin(state.elapsed * 9 + i);
      b.mesh.material.emissiveIntensity = 0.4 + pulse * 0.55;
    }

    if (b.mesh.position.z > CFG.DESPAWN_Z) {
      scene.remove(b.mesh);
      state.blocks.splice(i, 1);
    }
  }
}
