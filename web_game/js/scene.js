import * as THREE from 'three';
import { CFG } from './cfg.js';
import { MAT } from './assets.js';

// ── Renderer ─────────────────────────────────────────────────
export const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

// ── Scene ─────────────────────────────────────────────────────
export const scene = new THREE.Scene();
scene.background = new THREE.Color(0x03001a);
scene.fog = new THREE.FogExp2(0x03001a, 0.011);

// ── Camera ────────────────────────────────────────────────────
export const camera = new THREE.PerspectiveCamera(
  68,
  window.innerWidth / window.innerHeight,
  0.1,
  300,
);
camera.position.set(0, 5, 13);
camera.lookAt(0, 0.5, -25);

// ── Lights ────────────────────────────────────────────────────
export const ambientLight = new THREE.AmbientLight(0x1a0933, 3.5);
scene.add(ambientLight);

const sunLight = new THREE.DirectionalLight(0xffffff, 0.7);
sunLight.position.set(4, 14, 6);
sunLight.castShadow = true;
scene.add(sunLight);

const fillLight = new THREE.DirectionalLight(0xffffff, 0.8);
fillLight.position.set(0, 6, 20);
scene.add(fillLight);

// Exported so main.js can animate their intensity on the beat.
export const pinkLight = new THREE.PointLight(0xff00ff, 2.5, 35);
pinkLight.position.set(0, 4, CFG.PLAYER_Z);
scene.add(pinkLight);

export const cyanLight = new THREE.PointLight(0x00ffff, 1.8, 40);
cyanLight.position.set(0, 4, -12);
scene.add(cyanLight);

// ── Theme ─────────────────────────────────────────────────────
const texLoader = new THREE.TextureLoader();

export function applyCarTheme(theme) {
  // Background: image takes priority over solid colour
  if (theme.backgroundImage) {
    texLoader.load(
      theme.backgroundImage,
      (tex) => { scene.background = tex; },
      undefined,
      () => { scene.background = new THREE.Color(theme.sky); },
    );
  } else {
    scene.background = new THREE.Color(theme.sky);
  }

  scene.fog.color.set(theme.sky);
  ambientLight.color.set(theme.ambient);
  pinkLight.color.set(theme.light1);
  cyanLight.color.set(theme.light2);
  MAT.road.color.set(theme.road);
  MAT.wall.color.set(theme.wall.color);
  MAT.wall.emissive.set(theme.wall.emissive);
  MAT.markerMag.color.set(theme.marker1);
  MAT.markerBlue.color.set(theme.marker2);
}

export function setBackground(path) {
  texLoader.load(path, tex => { scene.background = tex; }, undefined, () => {});
}

// ── Responsive resize ────────────────────────────────────────
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});
