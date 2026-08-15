import * as THREE from "./vendor/three.module.min.js";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const gallery = JSON.parse($("#gallery-data").textContent);
const works = gallery.items;
const motionReduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const storageKey = `laplacelajiang-collection:${gallery.session_id}`;
const state = {
  index: 0,
  entered: false,
  transitioning: false,
  draggingFrame: false,
  frameMoved: false,
  selected: new Set(),
  textures: new Map(),
  currentTexture: null,
  currentFrame: null,
  frameInteractive: [],
  quality: "auto",
  detectedQuality: "medium",
  lens: { enabled: false, scale: 1, x: 0, y: 0, dragging: false },
  catalogueSpread: 0,
  packaging: false,
};

let renderer;
let scene;
let camera;
let startTime = 0;
let raycaster;
let pointer;
let frameRoot;
let artworkMesh;
let spotKey;
let spotFill;
let dust;
let entranceDoors;
let renderRequested = true;
let toastTimer;
let statusTimer;

const ui = {
  canvas: $("#gallery-canvas"),
  loading: $("#loading-room"),
  loadingCopy: $("#loading-copy"),
  loadingProgress: $("#loading-progress"),
  loadingCurrent: $("#loading-current"),
  loadingTotal: $("#loading-total"),
  loadingCurrent: $("#loading-current"),
  entrance: $("#entrance"),
  curtain: $("#light-curtain"),
  unsupported: $("#unsupported"),
  unsupportedReason: $("#unsupported-reason"),
  currentNumber: $("#current-number"),
  placardNumber: $("#placard-number"),
  placardTitle: $("#placard-title"),
  placardDescription: $("#placard-description"),
  placardStyle: $("#placard-style"),
  placardCollect: $("#placard-collect"),
  count: $("#collection-count"),
  focus: $("#focus-view"),
  focusNumber: $("#focus-number"),
  focusTitle: $("#focus-title"),
  focusDescription: $("#focus-description"),
  focusStyle: $("#focus-style"),
  focusSource: $("#focus-source"),
  focusImage: $("#focus-image"),
  focusFrame: $("#focus-frame"),
  focusCollect: $("#focus-collect"),
  catalogue: $("#catalogue"),
  book: $("#catalogue-book"),
  cover: $("#catalogue-cover"),
  leftPage: $("#catalogue-left"),
  rightPage: $("#catalogue-right"),
  mirror: $("#mirror-room"),
  collection: $("#collection-room"),
  collectionList: $("#collection-list"),
  packingProgress: $("#packing-progress"),
  packingPercent: $("#packing-percent"),
  packingStatus: $("#packing-status"),
  packingPath: $("#packing-path"),
  confirmCollection: $("#confirm-collection"),
  toast: $("#toast"),
};

function showToast(message) {
  clearTimeout(toastTimer);
  ui.toast.textContent = message;
  ui.toast.classList.add("is-visible");
  toastTimer = setTimeout(() => ui.toast.classList.remove("is-visible"), 2600);
}

function fitTitle(node, minimum = 18) {
  if (!node) return;
  node.style.fontSize = "";
  let size = parseFloat(getComputedStyle(node).fontSize);
  let guard = 100;
  while (node.scrollWidth > node.clientWidth && size > minimum && guard > 0) {
    size -= 0.5;
    node.style.fontSize = `${size}px`;
    guard -= 1;
  }
}

function animate(target, vars) {
  if (window.gsap && !motionReduced) return window.gsap.to(target, vars);
  const duration = vars.duration || 0;
  const onComplete = vars.onComplete;
  Object.entries(vars).forEach(([key, value]) => {
    if (!["duration", "ease", "delay", "onComplete", "overwrite"].includes(key)) target[key] = value;
  });
  setTimeout(() => onComplete?.(), duration * 1000);
  return null;
}

function timeline(options = {}) {
  if (window.gsap && !motionReduced) return window.gsap.timeline(options);
  return {
    to(target, vars) { animate(target, vars); return this; },
    fromTo(target, from, to) { Object.assign(target, from); animate(target, to); return this; },
    set(target, vars) { Object.assign(target, vars); return this; },
  };
}

function supportsWebGL() {
  try {
    const probe = document.createElement("canvas");
    return Boolean(probe.getContext("webgl2") || probe.getContext("webgl"));
  } catch (_) {
    return false;
  }
}

function fail(reason) {
  ui.loading.hidden = true;
  ui.unsupported.hidden = false;
  ui.unsupportedReason.textContent = reason;
}

function setTextureRepeat(texture, x, y) {
  if (!texture) return;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(x, y);
  texture.needsUpdate = true;
}

function detectQuality() {
  const gl = renderer.getContext();
  const debug = gl.getExtension("WEBGL_debug_renderer_info");
  const gpu = debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : "";
  const cores = navigator.hardwareConcurrency || 4;
  const memory = navigator.deviceMemory || 4;
  if (/swiftshader|llvmpipe|microsoft basic/i.test(gpu) || cores <= 4 || memory <= 4) return "low";
  if (/rtx|radeon rx|apple m[2-9]|arc a/i.test(gpu) || (cores >= 12 && memory >= 8)) return "high";
  return "medium";
}

function applyQuality(level) {
  const effective = level === "auto" ? state.detectedQuality : level;
  const labels = { low: "流畅", medium: "均衡", high: "精细" };
  const dprCap = { low: 1, medium: 1.5, high: 2 }[effective];
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, dprCap));
  renderer.shadowMap.enabled = effective !== "low";
  renderer.shadowMap.type = THREE.PCFShadowMap;
  if (dust) dust.visible = effective !== "low";
  $("#quality-select").value = level;
  $("#quality-state").textContent = level === "auto" ? `自动 · ${labels[effective]}` : labels[effective];
  resize();
}

async function loadTexture(loader, path, { srgb = false, repeat = null } = {}) {
  const texture = await loader.loadAsync(path);
  if (srgb) texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  if (repeat) setTextureRepeat(texture, repeat[0], repeat[1]);
  return texture;
}

async function loadResources() {
  const loader = new THREE.TextureLoader();
  const assetJobs = [
    ["floorColor", "exhibition/textures/floor-color.jpg", { srgb: true, repeat: [3.2, 7] }],
    ["floorNormal", "exhibition/textures/floor-normal.jpg", { repeat: [3.2, 7] }],
    ["floorRough", "exhibition/textures/floor-roughness.jpg", { repeat: [3.2, 7] }],
    ["plasterColor", "exhibition/textures/plaster-color.jpg", { srgb: true, repeat: [4, 2] }],
    ["plasterNormal", "exhibition/textures/plaster-normal.jpg", { repeat: [4, 2] }],
    ["plasterRough", "exhibition/textures/plaster-roughness.jpg", { repeat: [4, 2] }],
    ["woodColor", "exhibition/textures/mahogany-color.jpg", { srgb: true, repeat: [1.5, 1.5] }],
    ["woodNormal", "exhibition/textures/mahogany-normal.jpg", { repeat: [1.5, 1.5] }],
    ["woodRough", "exhibition/textures/mahogany-roughness.jpg", { repeat: [1.5, 1.5] }],
  ];
  const total = assetJobs.length + works.length;
  let complete = 0;
  const tick = (copy) => {
    complete += 1;
    ui.loadingCurrent.textContent = String(complete).padStart(2, "0");
    ui.loadingTotal.textContent = String(total).padStart(2, "0");
    ui.loadingProgress.style.width = `${(complete / total) * 100}%`;
    ui.loadingCopy.textContent = copy;
  };

  await Promise.all(assetJobs.map(async ([name, path, options]) => {
    const value = await loadTexture(loader, path, options);
    state.textures.set(name, value);
    tick(`正在铺设材质 · ${complete + 1}/${total}`);
  }));

  for (const [index, work] of works.entries()) {
    try {
      const texture = await loadTexture(loader, work.image, { srgb: true });
      state.textures.set(work.id, texture);
      tick(`正在悬挂展品 ${String(index + 1).padStart(2, "0")} · ${work.curatorial_title}`);
    } catch (error) {
      throw new Error(`展品 ${work.number_text} 加载失败：${error.message}`);
    }
  }
}

function materialSet() {
  return {
    floor: new THREE.MeshStandardMaterial({
      map: state.textures.get("floorColor"),
      normalMap: state.textures.get("floorNormal"),
      roughnessMap: state.textures.get("floorRough"),
      roughness: 0.74,
      metalness: 0.02,
      color: 0xf2ddbd,
    }),
    plaster: new THREE.MeshStandardMaterial({
      map: state.textures.get("plasterColor"),
      normalMap: state.textures.get("plasterNormal"),
      roughnessMap: state.textures.get("plasterRough"),
      roughness: 0.9,
      color: 0xfff3dc,
    }),
    wood: new THREE.MeshStandardMaterial({
      map: state.textures.get("woodColor"),
      normalMap: state.textures.get("woodNormal"),
      roughnessMap: state.textures.get("woodRough"),
      roughness: 0.48,
      metalness: 0.03,
      color: 0x6a321f,
    }),
    brass: new THREE.MeshStandardMaterial({ color: 0xb78137, roughness: 0.28, metalness: 0.82 }),
    ceiling: new THREE.MeshStandardMaterial({ color: 0xe7d2b2, roughness: 0.72 }),
  };
}

function mesh(geometry, material, position, rotation = [0, 0, 0]) {
  const value = new THREE.Mesh(geometry, material);
  value.position.set(...position);
  value.rotation.set(...rotation);
  value.castShadow = true;
  value.receiveShadow = true;
  scene.add(value);
  return value;
}

function buildArchitecture(materials) {
  const floor = mesh(new THREE.PlaneGeometry(22, 28), materials.floor, [0, 0, 2.5], [-Math.PI / 2, 0, 0]);
  floor.receiveShadow = true;
  mesh(new THREE.BoxGeometry(18.5, 6.5, .28), materials.plaster, [0, 3.22, -4.25]);
  mesh(new THREE.PlaneGeometry(22, 28), materials.ceiling, [0, 6.5, 2.5], [Math.PI / 2, 0, 0]);

  const sideGeometry = new THREE.BoxGeometry(5.8, 6.5, .24);
  const leftWall = mesh(sideGeometry, materials.plaster, [-8.55, 3.2, -1.75], [0, -Math.PI / 2.8, 0]);
  const rightWall = mesh(sideGeometry, materials.plaster, [8.55, 3.2, -1.75], [0, Math.PI / 2.8, 0]);
  leftWall.receiveShadow = true;
  rightWall.receiveShadow = true;

  const slatGeometry = new THREE.BoxGeometry(.11, 5.6, .26);
  for (let index = 0; index < 11; index += 1) {
    const y = 3;
    const z = -1.2 + index * .47;
    mesh(slatGeometry, materials.wood, [-7.72 - index * .22, y, z], [0, -.35, 0]);
    mesh(slatGeometry, materials.wood, [7.72 + index * .22, y, z], [0, .35, 0]);
  }

  const beamGeometry = new THREE.BoxGeometry(17.2, .16, .22);
  for (const z of [-2.8, -.5, 1.8, 4.1]) mesh(beamGeometry, materials.wood, [0, 6.05, z]);
  const baseboard = new THREE.BoxGeometry(18.3, .18, .25);
  mesh(baseboard, materials.wood, [0, .13, -4.05]);

  const benchTop = mesh(new THREE.BoxGeometry(2.8, .18, .62), materials.wood, [5.8, .68, .8]);
  benchTop.castShadow = true;
  mesh(new THREE.BoxGeometry(.18, .68, .44), materials.wood, [4.78, .34, .8]);
  mesh(new THREE.BoxGeometry(.18, .68, .44), materials.wood, [6.82, .34, .8]);
}

function buildLights() {
  scene.add(new THREE.HemisphereLight(0xc8d8df, 0x4b2718, 1.18));
  const ambient = new THREE.AmbientLight(0xffd9aa, .46);
  scene.add(ambient);

  spotKey = new THREE.SpotLight(0xffc875, 105, 22, Math.PI / 6.2, .42, 1.35);
  spotKey.position.set(-2.2, 5.85, .6);
  spotKey.target.position.set(-2.2, 2.8, -4.05);
  spotKey.castShadow = true;
  spotKey.shadow.mapSize.set(1024, 1024);
  scene.add(spotKey, spotKey.target);

  spotFill = new THREE.SpotLight(0xffe0a5, 48, 20, Math.PI / 5.5, .58, 1.45);
  spotFill.position.set(4.2, 5.7, .4);
  spotFill.target.position.set(4.2, 2.5, -4.1);
  scene.add(spotFill, spotFill.target);

  const coolWindow = new THREE.DirectionalLight(0xb9d7df, .82);
  coolWindow.position.set(-8, 4.5, 3.5);
  scene.add(coolWindow);
  const warmPool = new THREE.PointLight(0xe6a95d, 18, 12, 2);
  warmPool.position.set(5.8, 1.3, .5);
  scene.add(warmPool);
}

function buildDust() {
  const count = 320;
  const positions = new Float32Array(count * 3);
  for (let index = 0; index < count; index += 1) {
    positions[index * 3] = (Math.random() - .5) * 16;
    positions[index * 3 + 1] = .4 + Math.random() * 5.5;
    positions[index * 3 + 2] = -3 + Math.random() * 10;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  dust = new THREE.Points(geometry, new THREE.PointsMaterial({ color: 0xffe0aa, size: .012, transparent: true, opacity: .32, depthWrite: false }));
  scene.add(dust);
}

function buildDoors(materials) {
  entranceDoors = new THREE.Group();
  const panelGeometry = new THREE.BoxGeometry(3.22, 6.2, .26);
  const leftPivot = new THREE.Group();
  const rightPivot = new THREE.Group();
  leftPivot.position.set(-3.24, 3.1, 4.4);
  rightPivot.position.set(3.24, 3.1, 4.4);
  const leftPanel = new THREE.Mesh(panelGeometry, materials.wood);
  const rightPanel = new THREE.Mesh(panelGeometry, materials.wood);
  leftPanel.position.x = 1.61;
  rightPanel.position.x = -1.61;
  leftPanel.castShadow = rightPanel.castShadow = true;
  leftPivot.add(leftPanel);
  rightPivot.add(rightPanel);

  const trimGeometry = new THREE.BoxGeometry(.1, 5.5, .31);
  for (const offset of [-1.25, 1.25]) {
    const leftTrim = new THREE.Mesh(trimGeometry, materials.brass);
    leftTrim.position.set(1.61 + offset, 0, .03);
    leftPivot.add(leftTrim);
    const rightTrim = new THREE.Mesh(trimGeometry, materials.brass);
    rightTrim.position.set(-1.61 + offset, 0, .03);
    rightPivot.add(rightTrim);
  }
  const handleGeometry = new THREE.SphereGeometry(.12, 24, 18);
  const leftHandle = new THREE.Mesh(handleGeometry, materials.brass);
  const rightHandle = new THREE.Mesh(handleGeometry, materials.brass);
  leftHandle.position.set(3.0, -.45, .22);
  rightHandle.position.set(-3.0, -.45, .22);
  leftPivot.add(leftHandle);
  rightPivot.add(rightHandle);
  entranceDoors.add(leftPivot, rightPivot);
  entranceDoors.userData = { leftPivot, rightPivot };
  scene.add(entranceDoors);
}

function frameDimensions(work) {
  const ratio = work.width / work.height;
  const maxWidth = 3.55;
  const maxHeight = 4.0;
  let width = maxWidth;
  let height = width / ratio;
  if (height > maxHeight) {
    height = maxHeight;
    width = height * ratio;
  }
  return { width, height };
}

function disposeFrame(group) {
  if (!group) return;
  group.traverse((child) => {
    if (child.geometry) child.geometry.dispose();
    if (child.material?.userData?.disposable) child.material.dispose();
  });
  scene.remove(group);
}

function buildFrame(work) {
  disposeFrame(frameRoot);
  state.frameInteractive = [];
  const dimensions = frameDimensions(work);
  const outer = { width: dimensions.width + .38, height: dimensions.height + .38 };
  frameRoot = new THREE.Group();
  frameRoot.position.set(-2.05, 2.95, -4.02);
  frameRoot.rotation.y = -.012;
  scene.add(frameRoot);

  const wood = new THREE.MeshStandardMaterial({
    map: state.textures.get("woodColor"),
    normalMap: state.textures.get("woodNormal"),
    roughnessMap: state.textures.get("woodRough"),
    roughness: .4,
    metalness: .02,
    color: 0x522718,
  });
  wood.userData.disposable = true;
  const matboard = new THREE.MeshStandardMaterial({ color: 0xece1cf, roughness: .78 });
  matboard.userData.disposable = true;
  const art = new THREE.MeshBasicMaterial({ map: state.textures.get(work.id), toneMapped: false });
  art.userData.disposable = true;
  const glass = new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: .04, transmission: .05, transparent: true, opacity: .12, clearcoat: 1, clearcoatRoughness: .08, depthWrite: false });
  glass.userData.disposable = true;

  const bar = .16;
  const depth = .13;
  const top = new THREE.Mesh(new THREE.BoxGeometry(outer.width, bar, depth), wood);
  const bottom = new THREE.Mesh(new THREE.BoxGeometry(outer.width, bar, depth), wood);
  const left = new THREE.Mesh(new THREE.BoxGeometry(bar, outer.height - bar * 2, depth), wood);
  const right = new THREE.Mesh(new THREE.BoxGeometry(bar, outer.height - bar * 2, depth), wood);
  top.position.y = outer.height / 2 - bar / 2;
  bottom.position.y = -outer.height / 2 + bar / 2;
  left.position.x = -outer.width / 2 + bar / 2;
  right.position.x = outer.width / 2 - bar / 2;
  [top, bottom, left, right].forEach((part) => { part.castShadow = true; frameRoot.add(part); });

  const board = new THREE.Mesh(new THREE.PlaneGeometry(outer.width - .26, outer.height - .26), matboard);
  board.position.z = .065;
  board.receiveShadow = true;
  frameRoot.add(board);
  artworkMesh = new THREE.Mesh(new THREE.PlaneGeometry(dimensions.width, dimensions.height), art);
  artworkMesh.position.z = .075;
  artworkMesh.userData.isArtwork = true;
  frameRoot.add(artworkMesh);
  const glazing = new THREE.Mesh(new THREE.PlaneGeometry(dimensions.width, dimensions.height), glass);
  glazing.position.z = .086;
  frameRoot.add(glazing);
  state.frameInteractive = [artworkMesh, glazing];
  state.currentFrame = frameRoot;
  state.currentTexture = art.map;
  return frameRoot;
}

function initScene() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0xc9a37d);
  scene.fog = new THREE.FogExp2(0xb99473, .017);
  camera = new THREE.PerspectiveCamera(39, innerWidth / innerHeight, .1, 80);
  camera.position.set(0, 2.8, 10.6);
  camera.lookAt(0, 2.75, -3.5);
  renderer = new THREE.WebGLRenderer({ canvas: ui.canvas, antialias: true, powerPreference: "high-performance" });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.08;
  renderer.setSize(innerWidth, innerHeight, false);
  renderer.shadowMap.autoUpdate = true;
  state.detectedQuality = detectQuality();
  startTime = performance.now();
  raycaster = new THREE.Raycaster();
  pointer = new THREE.Vector2();
}

function updateUi() {
  const work = works[state.index];
  ui.currentNumber.textContent = work.number_text;
  ui.placardNumber.textContent = work.number_text;
  ui.placardTitle.textContent = work.curatorial_title;
  ui.placardDescription.textContent = work.curatorial_description;
  ui.placardStyle.textContent = `风格 · ${work.style_note}`;
  ui.placardCollect.dataset.id = work.id;
  const selected = state.selected.has(work.id);
  ui.placardCollect.setAttribute("aria-pressed", String(selected));
  $("span", ui.placardCollect).textContent = selected ? "已收入收藏袋" : "收入收藏袋";
  fitTitle(ui.placardTitle, 24);
  history.replaceState(null, "", `#work-${work.number_text}`);
}

function showWork(nextIndex, direction = 1, immediate = false) {
  if (state.transitioning && !immediate) return;
  const normalized = (nextIndex + works.length) % works.length;
  if (normalized === state.index && frameRoot && !immediate) return;
  state.transitioning = true;
  const nextWork = works[normalized];
  const finish = () => {
    state.index = normalized;
    buildFrame(nextWork);
    updateUi();
    frameRoot.position.z = -3.85;
    frameRoot.rotation.y = direction > 0 ? -.05 : .05;
    animate(frameRoot.position, { z: -4.02, duration: .62, ease: "power3.out" });
    animate(frameRoot.rotation, { y: -.012, duration: .7, ease: "power3.out" });
    animate(ui.curtain, { opacity: 0, scaleX: .08, duration: .43, ease: "power2.out", onComplete: () => { state.transitioning = false; } });
  };
  if (immediate || motionReduced || !frameRoot) {
    finish();
    return;
  }
  const tl = timeline();
  tl.to(frameRoot.position, { z: -3.78, duration: .25, ease: "power2.in" })
    .to(ui.curtain, { opacity: .9, scaleX: 1, duration: .31, ease: "power2.inOut", onComplete: finish }, "-=.08");
}

function openFocus() {
  const work = works[state.index];
  ui.focusNumber.textContent = work.number_text;
  ui.focusTitle.textContent = work.curatorial_title;
  ui.focusDescription.textContent = work.curatorial_description;
  ui.focusStyle.textContent = work.style_note;
  ui.focusSource.textContent = work.source_display || work.source || "LaplaceLajiang Photo Card";
  ui.focusImage.src = work.image;
  ui.focusImage.alt = `${work.number_text} ${work.curatorial_title}`;
  ui.focusCollect.dataset.id = work.id;
  ui.focusCollect.setAttribute("aria-pressed", String(state.selected.has(work.id)));
  ui.focusCollect.textContent = state.selected.has(work.id) ? "已收入收藏袋" : "收入收藏袋";
  resetLens();
  ui.focus.showModal();
  requestAnimationFrame(() => {
    fitTitle(ui.focusTitle, 28);
    animate($(".focus-copy", ui.focus), { opacity: 1, x: 0, duration: .55, ease: "power3.out" });
    animate(ui.focusFrame, { opacity: 1, scale: 1, duration: .62, ease: "power3.out" });
  });
}

function closeDialog(dialog) {
  if (!dialog?.open) return;
  dialog.close();
  if (dialog === ui.catalogue) {
    ui.book.classList.remove("is-open");
    ui.cover.style.transform = "";
    state.catalogueSpread = 0;
  }
  if (dialog === ui.collection) stopStatusPolling();
}

function loadSavedSelection() {
  try {
    const ids = JSON.parse(localStorage.getItem(storageKey) || "[]");
    ids.filter((id) => works.some((work) => work.id === id)).slice(0, 6).forEach((id) => state.selected.add(id));
  } catch (_) {
    localStorage.removeItem(storageKey);
  }
  updateSelectionUi();
}

function saveSelection() {
  localStorage.setItem(storageKey, JSON.stringify([...state.selected]));
}

function toggleSelection(id) {
  if (state.selected.has(id)) state.selected.delete(id);
  else if (state.selected.size >= 6) {
    showToast("收藏袋一次最多放入 6 幅作品");
    return;
  } else state.selected.add(id);
  saveSelection();
  updateSelectionUi();
}

function updateSelectionUi() {
  const work = works[state.index];
  const selected = state.selected.has(work.id);
  ui.count.textContent = `${state.selected.size} / 6`;
  ui.placardCollect.setAttribute("aria-pressed", String(selected));
  $("span", ui.placardCollect).textContent = selected ? "已收入收藏袋" : "收入收藏袋";
  if (ui.focus.open) {
    ui.focusCollect.setAttribute("aria-pressed", String(selected));
    ui.focusCollect.textContent = selected ? "已收入收藏袋" : "收入收藏袋";
  }
  renderCollection();
  renderCatalogue();
}

function catalogueCard(work) {
  const selected = state.selected.has(work.id) ? "<i aria-label=\"已收藏\"></i>" : "";
  return `<button class="catalogue-card" type="button" data-catalogue-work="${work.id}">
    <span class="catalogue-card__image"><img src="${work.image}" alt="">${selected}</span>
    <span>${work.number_text}</span><strong>${work.curatorial_title}</strong><small>${work.style_note}</small>
  </button>`;
}

function renderCatalogue() {
  const start = state.catalogueSpread * 4;
  const group = works.slice(start, start + 4);
  ui.leftPage.innerHTML = group.slice(0, 2).map(catalogueCard).join("");
  ui.rightPage.innerHTML = group.slice(2, 4).map(catalogueCard).join("");
  $("#catalogue-chapter").textContent = gallery.chapters[state.catalogueSpread]?.title || `第 ${state.catalogueSpread + 1} 章`;
  $("#catalogue-range").textContent = `${String(start + 1).padStart(2, "0")}—${String(Math.min(start + 4, works.length)).padStart(2, "0")}`;
  $("#catalogue-left-page").textContent = String(state.catalogueSpread * 2 + 1).padStart(2, "0");
  $("#catalogue-right-page").textContent = String(state.catalogueSpread * 2 + 2).padStart(2, "0");
  $("#catalogue-current-spread").textContent = String(state.catalogueSpread + 1);
  $("#catalogue-total-spreads").textContent = String(Math.ceil(works.length / 4));
  $("#catalogue-previous").disabled = state.catalogueSpread === 0;
  $("#catalogue-next").disabled = state.catalogueSpread >= Math.ceil(works.length / 4) - 1;
}

function turnCatalogue(direction) {
  const next = state.catalogueSpread + direction;
  const total = Math.ceil(works.length / 4);
  if (next < 0 || next >= total) return;
  const turn = $("#page-turn");
  state.catalogueSpread = next;
  if (motionReduced || !window.gsap) {
    renderCatalogue();
    return;
  }
  window.gsap.set(turn, { rotateY: direction > 0 ? 0 : -180, transformOrigin: direction > 0 ? "left center" : "right center" });
  window.gsap.to(turn, {
    rotateY: direction > 0 ? -180 : 0,
    duration: .78,
    ease: "power2.inOut",
    onUpdate: () => {
      if (Math.abs(window.gsap.getProperty(turn, "rotateY")) > 88) renderCatalogue();
    },
    onComplete: () => window.gsap.set(turn, { rotateY: 90 }),
  });
}

function openCatalogue() {
  renderCatalogue();
  ui.catalogue.showModal();
  requestAnimationFrame(() => animate(ui.book, { opacity: 1, scale: 1, rotateX: 0, duration: .55, ease: "power3.out" }));
}

function openBook() {
  ui.book.classList.add("is-open");
  if (window.gsap && !motionReduced) window.gsap.to(ui.cover, { rotateY: -168, duration: 1.15, ease: "power3.inOut" });
  else ui.cover.style.transform = "rotateY(-168deg)";
}

function mirrorIndexButton(work, index) {
  return `<button class="mirror-index-button" type="button" data-mirror-index="${index}" aria-current="${index === state.index}"><span>${work.number_text} · ${work.group_short}</span><strong>${work.curatorial_title}</strong></button>`;
}

function renderMirror(index = state.index) {
  const work = works[index];
  $("#mirror-index-list").innerHTML = works.map(mirrorIndexButton).join("");
  $("#mirror-number").textContent = work.number_text;
  $("#mirror-title").textContent = work.curatorial_title;
  $("#mirror-summary").textContent = work.style_summary;
  $("#recipe-basic").textContent = work.recipe_basic;
  $("#recipe-advanced").textContent = work.recipe_advanced;
  $("#copy-recipe").dataset.text = `${work.recipe_basic}\n\n进阶控制：\n${work.recipe_advanced}`;
  fitTitle($("#mirror-title"), 29);
}

function openMirror() {
  renderMirror();
  ui.mirror.showModal();
}

function renderCollection() {
  if (!state.selected.size) {
    ui.collectionList.innerHTML = '<div class="collection-empty"><p>收藏袋还是空的。<br>回到展厅，把心动的作品收入其中。</p></div>';
    ui.confirmCollection.disabled = true;
    return;
  }
  const selectedWorks = [...state.selected].map((id) => works.find((work) => work.id === id)).filter(Boolean);
  ui.collectionList.innerHTML = selectedWorks.map((work) => `<article class="collection-item"><img src="${work.image}" alt=""><strong>${work.curatorial_title}</strong><small>${work.number_text} · ${work.style_note}</small><button type="button" data-remove-selection="${work.id}" aria-label="移出收藏">×</button></article>`).join("");
  ui.confirmCollection.disabled = state.packaging;
}

function openCollection() {
  renderCollection();
  ui.collection.showModal();
  startStatusPolling();
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `请求失败 ${response.status}`);
  return payload;
}

function applyPackingStatus(payload) {
  const packing = payload.packing || payload;
  const percent = Number.isFinite(packing.percent) ? packing.percent : 0;
  ui.packingProgress.style.width = `${Math.max(0, Math.min(100, percent))}%`;
  ui.packingPercent.textContent = `${Math.round(percent)}%`;
  ui.packingStatus.textContent = packing.message || "尚未提交高清制作";
  ui.packingPath.textContent = packing.path || gallery.take_home_path || "确认收藏后显示取件路径";
  state.packaging = ["queued", "rendering", "packaging"].includes(packing.stage);
  ui.confirmCollection.disabled = state.packaging || !state.selected.size;
  if (packing.stage === "complete") {
    ui.confirmCollection.textContent = "精装完成 · 已可取件";
    state.packaging = false;
  }
}

async function pollStatus() {
  if (location.protocol === "file:") return;
  try {
    applyPackingStatus(await requestJson("/api/status"));
  } catch (_) {
    ui.packingStatus.textContent = "本地状态服务暂未响应；展览浏览不受影响。";
  }
}

function startStatusPolling() {
  stopStatusPolling();
  pollStatus();
  statusTimer = setInterval(pollStatus, 1700);
}

function stopStatusPolling() {
  clearInterval(statusTimer);
  statusTimer = null;
}

async function confirmCollection() {
  if (!state.selected.size) return showToast("请先收藏至少一幅作品");
  if (location.protocol === "file:") return showToast("请通过“打开廿四境展厅.cmd”进入，才能提交高清制作");
  ui.confirmCollection.disabled = true;
  ui.confirmCollection.textContent = "正在递交收藏单…";
  try {
    const payload = await requestJson("/api/selection", { method: "POST", body: JSON.stringify({ presets: [...state.selected] }) });
    state.packaging = true;
    applyPackingStatus(payload);
    ui.confirmCollection.textContent = "收藏单已递交 · 等待精装";
    showToast("收藏单已锁定，正在准备高清制作与精装包装");
    startStatusPolling();
  } catch (error) {
    ui.confirmCollection.disabled = false;
    ui.confirmCollection.textContent = "确认收藏并开始精装";
    showToast(error.message);
  }
}

function enterGallery() {
  if (state.entered) return;
  state.entered = true;
  document.body.classList.add("is-entered");
  const { leftPivot, rightPivot } = entranceDoors.userData;
  const finish = () => {
    ui.entrance.hidden = true;
    entranceDoors.visible = false;
    showWork(0, 1, true);
  };
  if (window.gsap && !motionReduced) {
    const tl = window.gsap.timeline({ onComplete: finish });
    tl.to(leftPivot.rotation, { y: -1.22, duration: 1.08, ease: "power3.inOut" }, 0)
      .to(rightPivot.rotation, { y: 1.22, duration: 1.08, ease: "power3.inOut" }, 0)
      .to(ui.entrance, { opacity: 0, duration: .65, ease: "power2.out" }, .35)
      .to(camera.position, { z: 5.45, y: 2.75, duration: 1.58, ease: "power3.inOut" }, .22);
  } else {
    leftPivot.rotation.y = -1.22;
    rightPivot.rotation.y = 1.22;
    camera.position.z = 5.45;
    finish();
  }
}

function setPointer(event) {
  const rect = ui.canvas.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
}

function hitArtwork(event) {
  if (!state.entered || !artworkMesh) return false;
  setPointer(event);
  raycaster.setFromCamera(pointer, camera);
  return raycaster.intersectObjects(state.frameInteractive, false).length > 0;
}

function onCanvasPointerDown(event) {
  if (!hitArtwork(event)) return;
  state.draggingFrame = true;
  state.frameMoved = false;
  state.dragStart = { x: event.clientX, y: event.clientY, rotationY: frameRoot.rotation.y, rotationZ: frameRoot.rotation.z };
  ui.canvas.setPointerCapture(event.pointerId);
  ui.canvas.style.cursor = "grabbing";
}

function onCanvasPointerMove(event) {
  if (!state.draggingFrame) {
    ui.canvas.style.cursor = hitArtwork(event) ? "grab" : "default";
    return;
  }
  const dx = event.clientX - state.dragStart.x;
  const dy = event.clientY - state.dragStart.y;
  if (Math.abs(dx) + Math.abs(dy) > 6) state.frameMoved = true;
  frameRoot.rotation.y = THREE.MathUtils.clamp(state.dragStart.rotationY + dx * .0025, -.14, .14);
  frameRoot.rotation.z = THREE.MathUtils.clamp(state.dragStart.rotationZ + dx * .0009, -.045, .045);
  frameRoot.position.z = THREE.MathUtils.clamp(-4.02 + Math.abs(dx) * .0012 + Math.abs(dy) * .0004, -4.02, -3.78);
}

function onCanvasPointerUp(event) {
  if (!state.draggingFrame) return;
  state.draggingFrame = false;
  ui.canvas.releasePointerCapture?.(event.pointerId);
  ui.canvas.style.cursor = "grab";
  animate(frameRoot.rotation, { y: -.012, z: 0, duration: .85, ease: "elastic.out(1,.45)" });
  animate(frameRoot.position, { z: -4.02, duration: .72, ease: "power3.out" });
  if (!state.frameMoved) openFocus();
}

function resetLens() {
  state.lens = { enabled: false, scale: 1, x: 0, y: 0, dragging: false };
  $("#toggle-lens").setAttribute("aria-pressed", "false");
  ui.focusImage.style.transform = "translate(0px, 0px) scale(1)";
  ui.focusFrame.style.transform = "";
}

function updateLens() {
  ui.focusImage.style.transform = `translate(${state.lens.x}px, ${state.lens.y}px) scale(${state.lens.scale})`;
}

function bindFocusInteractions() {
  let start;
  ui.focusFrame.addEventListener("pointerdown", (event) => {
    if (state.lens.enabled) {
      state.lens.dragging = true;
      start = { x: event.clientX, y: event.clientY, px: state.lens.x, py: state.lens.y };
    } else {
      start = { x: event.clientX, y: event.clientY };
    }
    ui.focusFrame.setPointerCapture(event.pointerId);
  });
  ui.focusFrame.addEventListener("pointermove", (event) => {
    if (!start) return;
    const dx = event.clientX - start.x;
    const dy = event.clientY - start.y;
    if (state.lens.enabled && state.lens.dragging) {
      state.lens.x = start.px + dx;
      state.lens.y = start.py + dy;
      updateLens();
      return;
    }
    const rotateY = THREE.MathUtils.clamp(dx * .035, -7, 7);
    const rotateZ = THREE.MathUtils.clamp(dx * .012, -2.4, 2.4);
    const gap = Math.min(24, Math.abs(dx) * .11 + Math.abs(dy) * .04);
    ui.focusFrame.style.transform = `perspective(1200px) translateZ(${gap}px) rotateY(${rotateY}deg) rotateZ(${rotateZ}deg)`;
    ui.focusFrame.style.boxShadow = `${-dx * .08}px 36px ${80 + gap}px rgba(24,11,7,.42)`;
  });
  const release = () => {
    start = null;
    state.lens.dragging = false;
    if (!state.lens.enabled) {
      ui.focusFrame.animate([
        { transform: ui.focusFrame.style.transform },
        { transform: "perspective(1200px) translateZ(0) rotateY(0) rotateZ(0)" },
      ], { duration: motionReduced ? 1 : 720, easing: "cubic-bezier(.22,.78,.24,1)" });
      ui.focusFrame.style.transform = "";
      ui.focusFrame.style.boxShadow = "";
    }
  };
  ui.focusFrame.addEventListener("pointerup", release);
  ui.focusFrame.addEventListener("pointercancel", release);
  ui.focusFrame.addEventListener("wheel", (event) => {
    if (!state.lens.enabled) return;
    event.preventDefault();
    state.lens.scale = THREE.MathUtils.clamp(state.lens.scale + (event.deltaY < 0 ? .18 : -.18), 1, 3.2);
    if (state.lens.scale === 1) state.lens.x = state.lens.y = 0;
    updateLens();
  }, { passive: false });
}

function bindUi() {
  $("#enter-gallery").addEventListener("click", enterGallery);
  $("#next-artwork").addEventListener("click", () => showWork(state.index + 1, 1));
  $("#previous-artwork").addEventListener("click", () => showWork(state.index - 1, -1));
  ui.placardCollect.addEventListener("click", () => toggleSelection(works[state.index].id));
  ui.focusCollect.addEventListener("click", () => toggleSelection(works[state.index].id));
  $("#open-catalog").addEventListener("click", openCatalogue);
  $("#open-book").addEventListener("click", openBook);
  $("#catalogue-next").addEventListener("click", () => turnCatalogue(1));
  $("#catalogue-previous").addEventListener("click", () => turnCatalogue(-1));
  $("#open-mirror").addEventListener("click", openMirror);
  $("#open-collection").addEventListener("click", openCollection);
  ui.confirmCollection.addEventListener("click", confirmCollection);
  $("#quality-select").addEventListener("change", (event) => {
    state.quality = event.target.value;
    localStorage.setItem("laplacelajiang-gallery-quality", state.quality);
    applyQuality(state.quality);
    showToast(`展厅画质已切换为：${$("#quality-state").textContent}`);
  });

  $$('[data-close-dialog]').forEach((button) => button.addEventListener("click", () => closeDialog($(`#${button.dataset.closeDialog}`))));
  ui.catalogue.addEventListener("click", (event) => {
    const card = event.target.closest("[data-catalogue-work]");
    if (!card) return;
    const index = works.findIndex((work) => work.id === card.dataset.catalogueWork);
    closeDialog(ui.catalogue);
    showWork(index, index >= state.index ? 1 : -1);
  });
  ui.collection.addEventListener("click", (event) => {
    const button = event.target.closest("[data-remove-selection]");
    if (button) toggleSelection(button.dataset.removeSelection);
  });
  ui.mirror.addEventListener("click", (event) => {
    const button = event.target.closest("[data-mirror-index]");
    if (button) renderMirror(Number(button.dataset.mirrorIndex));
  });

  $("#recipe-basic-tab").addEventListener("click", () => setRecipeTab("basic"));
  $("#recipe-advanced-tab").addEventListener("click", () => setRecipeTab("advanced"));
  $("#copy-recipe").addEventListener("click", async (event) => {
    try {
      await navigator.clipboard.writeText(event.currentTarget.dataset.text);
      showToast("当前风格配方已复制");
    } catch (_) {
      showToast("浏览器未允许剪贴板，请手动选择配方文字");
    }
  });

  const compare = $("#compare-source");
  const startCompare = () => ui.focusFrame.classList.add("is-comparing");
  const endCompare = () => ui.focusFrame.classList.remove("is-comparing");
  compare.addEventListener("pointerdown", startCompare);
  compare.addEventListener("pointerup", endCompare);
  compare.addEventListener("pointerleave", endCompare);
  compare.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) startCompare(); });
  compare.addEventListener("keyup", endCompare);
  $("#toggle-lens").addEventListener("click", (event) => {
    state.lens.enabled = !state.lens.enabled;
    event.currentTarget.setAttribute("aria-pressed", String(state.lens.enabled));
    if (!state.lens.enabled) resetLens();
  });

  document.addEventListener("keydown", (event) => {
    const openDialog = $("dialog[open]");
    if (event.key === "Escape" && openDialog) return closeDialog(openDialog);
    if (openDialog || !state.entered || /INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) return;
    if (event.key === "ArrowRight") showWork(state.index + 1, 1);
    if (event.key === "ArrowLeft") showWork(state.index - 1, -1);
    if (event.key.toLowerCase() === "e") openFocus();
    if (event.key.toLowerCase() === "c") openCatalogue();
    if (event.key.toLowerCase() === "m") openMirror();
  });

  ui.canvas.addEventListener("pointerdown", onCanvasPointerDown);
  ui.canvas.addEventListener("pointermove", onCanvasPointerMove);
  ui.canvas.addEventListener("pointerup", onCanvasPointerUp);
  ui.canvas.addEventListener("pointercancel", onCanvasPointerUp);
  bindFocusInteractions();
  addEventListener("resize", resize);
  document.addEventListener("visibilitychange", () => { renderRequested = !document.hidden; });
}

function setRecipeTab(tab) {
  const basic = tab === "basic";
  $("#recipe-basic-tab").setAttribute("aria-selected", String(basic));
  $("#recipe-advanced-tab").setAttribute("aria-selected", String(!basic));
  $("#recipe-basic").hidden = !basic;
  $("#recipe-advanced").hidden = basic;
}

function resize() {
  if (!renderer || !camera) return;
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight, false);
  fitTitle(ui.placardTitle, 24);
}

function loop() {
  requestAnimationFrame(loop);
  if (!renderRequested || !renderer) return;
  const elapsed = (performance.now() - startTime) / 1000;
  if (dust?.visible) {
    dust.rotation.y = elapsed * .006;
    dust.position.y = Math.sin(elapsed * .19) * .04;
  }
  if (spotKey) spotKey.intensity = 105 + Math.sin(elapsed * .48) * 3.2;
  if (spotFill) spotFill.intensity = 48 + Math.sin(elapsed * .31 + 1.1) * 1.7;
  if (frameRoot && !state.draggingFrame) frameRoot.rotation.z = Math.sin(elapsed * .38) * .0008;
  camera.lookAt(0, 2.75, -3.5);
  renderer.render(scene, camera);
}

async function boot() {
  if (location.protocol === "file:") return;
  if (!supportsWebGL()) return fail("浏览器未能启用 WebGL，请更新显卡驱动，或打开展品清单模式。");
  try {
    initScene();
    await loadResources();
    const materials = materialSet();
    buildArchitecture(materials);
    buildLights();
    buildDust();
    buildDoors(materials);
    buildFrame(works[0]);
    bindUi();
    loadSavedSelection();
    renderCatalogue();
    renderMirror();
    state.quality = localStorage.getItem("laplacelajiang-gallery-quality") || "auto";
    applyQuality(state.quality);
    updateUi();
    ui.loadingCopy.textContent = "展厅已点亮";
    ui.loadingProgress.style.width = "100%";
    fetch("/api/heartbeat").catch(() => {});
    setInterval(() => fetch("/api/heartbeat").catch(() => {}), 45000);
    loop();
    setTimeout(() => {
      if (window.gsap && !motionReduced) window.gsap.to(ui.loading, { opacity: 0, duration: .72, ease: "power2.out", onComplete: () => { ui.loading.hidden = true; } });
      else ui.loading.hidden = true;
    }, motionReduced ? 0 : 360);
  } catch (error) {
    console.error(error);
    fail(`展厅资源核验未通过：${error.message}`);
  }
}

boot();
