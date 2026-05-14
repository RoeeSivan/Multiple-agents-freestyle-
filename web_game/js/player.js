import * as THREE from 'three';
import { GLTFLoader } from 'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/jsm/loaders/GLTFLoader.js';
import { CFG, CARS } from './cfg.js';
import { scene, camera } from './scene.js';

// Exported so main.js and tickPlayer() can operate on the car Group directly.
export const car = new THREE.Group();

// Adds the car Group to the scene at the player position. Call once at boot.
export function buildPlayer() {
  car.position.set(CFG.LANES[1], 0.5, CFG.PLAYER_Z);
  scene.add(car);
}

// Clears any previously loaded model and loads the GLB for the given car index.
// The group stays in the scene; the async load drops the new model in when ready.
export function loadCarModel(carIdx) {
  while (car.children.length) car.remove(car.children[0]);

  const { file, scale, rotationY } = CARS[carIdx];
  // URL constructor percent-encodes spaces in folder/file names automatically.
  const modelUrl = new URL(`../Cars GLB files/${file}`, import.meta.url).href;

  const loader = new GLTFLoader();
  loader.load(
    modelUrl,
    (gltf) => {
      const model = gltf.scene;
      model.scale.setScalar(scale);
      model.rotation.y = rotationY;
      car.add(model);
    },
    undefined,
    (err) => console.error(`[player] GLB load failed (${file}):`, err),
  );
}

// Smoothly moves the car toward targetX and tilts it on lane changes.
// Also nudges the camera to follow the car laterally.
// Receives targetX and jumpVelocity by reference via state-independent params.
export function tickPlayer(dt, targetX, state) {
  car.position.x += (targetX - car.position.x) * Math.min(dt * 13, 1);

  const tiltTarget = (targetX - car.position.x) * -0.28;
  car.rotation.z  += (tiltTarget - car.rotation.z) * dt * 9;

  camera.position.x += (car.position.x * 0.25 - camera.position.x) * dt * 3;

  if (state.shakeUntil > state.elapsed) {
    const t   = (state.shakeUntil - state.elapsed) / 0.35;
    const mag = state.shakeMag * t;
    camera.position.x += (Math.random() - 0.5) * mag * 2;
    camera.position.y += (Math.random() - 0.5) * mag;
  }

  // Jump physics
  if (state.jumpVelocity !== 0 || car.position.y > CFG.GROUND_Y) {
    state.jumpVelocity  -= CFG.GRAVITY * dt;
    car.position.y      += state.jumpVelocity * dt;
    if (car.position.y <= CFG.GROUND_Y) {
      car.position.y     = CFG.GROUND_Y;
      state.jumpVelocity = 0;
      state.jumpsUsed    = 0;
    }
  }
}
