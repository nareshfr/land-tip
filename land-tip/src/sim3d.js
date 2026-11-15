// 3D City & Development Simulation Engine
// Built for UrbanAlpha Bengaluru GeoAI

export class CitySimulation3D {
  constructor(options = {}) {
    this.container = options.container || document.getElementById('three-container');
    this.canvas = options.canvas || document.getElementById('three-canvas');
    this.activeArea = options.activeArea || null;
    this.offset = options.offset || 0;
    this.infraList = options.infraList || [];
    this.onProjectClick = options.onProjectClick || null;

    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.animId = null;
    this.clock = null;

    // Camera spherical controls
    this.isMouseDown = false;
    this.isRightDown = false;
    this.prevMouseX = 0;
    this.prevMouseY = 0;
    this.spherical = { radius: 380, theta: Math.PI / 4, phi: Math.PI / 3.2 };
    this.target = { x: 0, y: 0, z: 0 };
    this.targetPos = { radius: 380, theta: Math.PI / 4, phi: Math.PI / 3.2 };
    this.autoOrbit = false;

    // Scene groups
    this.cityGroup = null;
    this.parcelGroup = null;
    this.infraGroup = null;
    this.animatedObjects = []; // { update(time, delta) }
    this.raycastMeshes = [];

    // Raycasting
    this.raycaster = null;
    this.mouse = null;
    this.hoveredMesh = null;

    // State
    this.initialized = false;
    this.running = false;
  }

  isReady() {
    return typeof window !== 'undefined' && !!window.THREE;
  }

  init() {
    const THREE = window.THREE;
    if (!THREE) return false;
    if (this.initialized) return true;

    const width = this.container.clientWidth || window.innerWidth;
    const height = this.container.clientHeight || window.innerHeight;

    // 1. Scene setup
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x070b14);
    this.scene.fog = new THREE.FogExp2(0x070b14, 0.0024);

    // 2. Camera setup
    this.camera = new THREE.PerspectiveCamera(45, width / height, 1, 3500);
    this.updateCameraPosition();

    // 3. Renderer setup
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance'
    });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    this.clock = new THREE.Clock();
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2(-999, -999);

    // 4. Lighting
    this.setupLights();

    // 5. Ground grid
    this.setupGround();

    // 6. Setup groups
    this.cityGroup = new THREE.Group();
    this.parcelGroup = new THREE.Group();
    this.infraGroup = new THREE.Group();
    this.scene.add(this.cityGroup);
    this.scene.add(this.parcelGroup);
    this.scene.add(this.infraGroup);

    // 7. Event listeners
    this.bindEvents();

    this.initialized = true;
    return true;
  }

  setupLights() {
    const THREE = window.THREE;
    const ambient = new THREE.AmbientLight(0x475569, 1.4);
    this.scene.add(ambient);

    const sun = new THREE.DirectionalLight(0xfff7ed, 1.8);
    sun.position.set(250, 400, 200);
    sun.castShadow = true;
    sun.shadow.mapSize.width = 1024;
    sun.shadow.mapSize.height = 1024;
    sun.shadow.camera.near = 10;
    sun.shadow.camera.far = 1000;
    const d = 400;
    sun.shadow.camera.left = -d;
    sun.shadow.camera.right = d;
    sun.shadow.camera.top = d;
    sun.shadow.camera.bottom = -d;
    this.scene.add(sun);

    // Blue/Cyan night rim light
    const rimLight = new THREE.DirectionalLight(0x38bdf8, 1.2);
    rimLight.position.set(-300, 150, -200);
    this.scene.add(rimLight);

    // Dynamic ground glow light near parcel
    const parcelLight = new THREE.PointLight(0x10b981, 2.5, 200);
    parcelLight.position.set(0, 15, 0);
    this.scene.add(parcelLight);
  }

  setupGround() {
    const THREE = window.THREE;

    // Dark grid ground
    const groundGeo = new THREE.PlaneGeometry(1600, 1600, 32, 32);
    const groundMat = new THREE.MeshStandardMaterial({
      color: 0x090d16,
      roughness: 0.9,
      metalness: 0.2
    });
    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.5;
    ground.receiveShadow = true;
    this.scene.add(ground);

    // Grid helper overlay
    const grid = new THREE.GridHelper(1600, 80, 0x1e293b, 0x0f172a);
    grid.position.y = 0;
    this.scene.add(grid);

    // Radial radar distance rings (500m, 1km, 1.5km, 2km in 3D scale)
    const radii = [60, 120, 180, 240];
    radii.forEach((r, i) => {
      const ringGeo = new THREE.RingGeometry(r - 0.6, r + 0.6, 64);
      const ringMat = new THREE.MeshBasicMaterial({
        color: i === 0 ? 0x10b981 : 0xea580c,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.28 - i * 0.05
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.rotation.x = -Math.PI / 2;
      ring.position.y = 0.2;
      this.scene.add(ring);
    });
  }

  // Generate 3D procedural buildings around the parcel matching locality density
  buildCity(activeArea) {
    const THREE = window.THREE;
    if (!this.initialized || !THREE) return;

    // Clear old city
    while (this.cityGroup.children.length > 0) {
      const obj = this.cityGroup.children.pop();
      if (obj.geometry) obj.geometry.dispose();
    }
    this.raycastMeshes = this.raycastMeshes.filter((m) => m.userData.type === 'infra');

    const builtUp = (activeArea && activeArea.builtUp) || 70;
    const cat = (activeArea && activeArea.category) || 'General';

    // Base height modifier based on locality category
    let heightMultiplier = 1.0;
    if (cat.includes('Tech') || cat.includes('Central') || activeArea?.name?.includes('Koramangala') || activeArea?.name?.includes('Indiranagar')) {
      heightMultiplier = 1.6;
    } else if (cat.includes('Peripheral') || activeArea?.name?.includes('Devanahalli') || activeArea?.name?.includes('Doddaballapur')) {
      heightMultiplier = 0.65;
    }

    const buildingMat = new THREE.MeshStandardMaterial({
      color: 0x172033,
      roughness: 0.35,
      metalness: 0.65
    });

    const windowEmissiveMat = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      emissive: 0x38bdf8,
      emissiveIntensity: 0.18,
      roughness: 0.2,
      metalness: 0.8
    });

    const edgeMat = new THREE.LineBasicMaterial({
      color: 0x334155,
      transparent: true,
      opacity: 0.4
    });

    // Create block clusters
    const blockSize = 32;
    const streetWidth = 10;
    const extent = 10; // -10 to +10 blocks

    for (let x = -extent; x <= extent; x++) {
      for (let z = -extent; z <= extent; z++) {
        // Leave center open for target parcel
        if (Math.abs(x) <= 1 && Math.abs(z) <= 1) continue;

        const distFromCenter = Math.hypot(x, z);
        // Probability of building existing based on built-up density and radial decay
        const prob = (builtUp / 100) * Math.max(0.3, 1 - distFromCenter * 0.05);
        if (Math.random() > prob) continue;

        const posX = x * (blockSize + streetWidth) + (Math.random() - 0.5) * 6;
        const posZ = z * (blockSize + streetWidth) + (Math.random() - 0.5) * 6;

        // Height varies with density and random seed
        const baseH = (12 + Math.random() * 45) * heightMultiplier;
        const h = Math.max(8, baseH * (1 - distFromCenter * 0.04));
        const w = 14 + Math.random() * 16;
        const d = 14 + Math.random() * 16;

        const geo = new THREE.BoxGeometry(w, h, d);
        const useEmissive = Math.random() > 0.45;
        const bMesh = new THREE.Mesh(geo, useEmissive ? windowEmissiveMat : buildingMat);
        bMesh.position.set(posX, h / 2, posZ);
        bMesh.castShadow = true;
        bMesh.receiveShadow = true;

        // Architectural edges
        const edges = new THREE.EdgesGeometry(geo);
        const wire = new THREE.LineSegments(edges, edgeMat);
        bMesh.add(wire);

        this.cityGroup.add(bMesh);
      }
    }
  }

  // Highlight the Selected Target Parcel in 3D
  buildParcel(activeArea, maskedArea) {
    const THREE = window.THREE;
    if (!this.initialized || !THREE) return;

    while (this.parcelGroup.children.length > 0) {
      const obj = this.parcelGroup.children.pop();
      if (obj.geometry) obj.geometry.dispose();
    }

    // 1. Parcel Foundation / Plot Outline
    const plotW = 34;
    const plotD = 34;
    const plotH = 2.5;

    const plotGeo = new THREE.BoxGeometry(plotW, plotH, plotD);
    const plotMat = new THREE.MeshStandardMaterial({
      color: 0x064e3b,
      emissive: 0x059669,
      emissiveIntensity: 0.45,
      roughness: 0.3,
      metalness: 0.5
    });
    const plotMesh = new THREE.Mesh(plotGeo, plotMat);
    plotMesh.position.set(0, plotH / 2, 0);
    plotMesh.receiveShadow = true;
    this.parcelGroup.add(plotMesh);

    // Glowing boundary wireframe
    const plotEdges = new THREE.EdgesGeometry(plotGeo);
    const plotWireMat = new THREE.LineBasicMaterial({
      color: 0x10b981,
      linewidth: 2
    });
    const plotWire = new THREE.LineSegments(plotEdges, plotWireMat);
    plotMesh.add(plotWire);

    // 2. Center holographic beacon pillar
    const beaconGeo = new THREE.CylinderGeometry(0.8, 1.6, 90, 16);
    const beaconMat = new THREE.MeshBasicMaterial({
      color: 0x10b981,
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending
    });
    const beacon = new THREE.Mesh(beaconGeo, beaconMat);
    beacon.position.set(0, 45, 0);
    this.parcelGroup.add(beacon);

    // 3. Floating 3D Holographic Diamond marker above plot
    const diamondGeo = new THREE.OctahedronGeometry(4.5, 0);
    const diamondMat = new THREE.MeshStandardMaterial({
      color: 0x34d399,
      emissive: 0x10b981,
      emissiveIntensity: 0.8,
      roughness: 0.1,
      metalness: 0.9
    });
    const diamond = new THREE.Mesh(diamondGeo, diamondMat);
    diamond.position.set(0, 48, 0);
    this.parcelGroup.add(diamond);

    // Animation hook for diamond
    this.animatedObjects.push({
      update: (time) => {
        diamond.rotation.y = time * 1.5;
        diamond.position.y = 48 + Math.sin(time * 2.5) * 3;
        beaconMat.opacity = 0.25 + 0.15 * Math.sin(time * 3);
      }
    });
  }

  // BUILD & ANIMATE NEW DEVELOPMENTS IN 3D
  buildDevelopments(infraList, activeArea, currentOffset = 0) {
    const THREE = window.THREE;
    if (!this.initialized || !THREE) return;

    // Clear old developments
    while (this.infraGroup.children.length > 0) {
      const obj = this.infraGroup.children.pop();
      if (obj.geometry) obj.geometry.dispose();
    }
    this.animatedObjects = this.animatedObjects.filter((o) => !o.isInfra);
    this.raycastMeshes = this.raycastMeshes.filter((m) => m.userData.type !== 'infra');

    if (!infraList || infraList.length === 0) return;

    const centerCoords = (activeArea && activeArea.coords) || [13.0617, 77.5872];
    const centerLat = centerCoords[0];
    const centerLng = centerCoords[1];

    let deliveredCount = 0;
    let underConCount = 0;
    let proposedCount = 0;

    infraList.forEach((project, idx) => {
      const pCoords = project.coords;
      if (!pCoords || !Array.isArray(pCoords) || pCoords.length < 2) return;

      // Project geo coordinates to 3D local coordinates (1 km ≈ 45 units in 3D)
      const latDiff = pCoords[0] - centerLat;
      const lngDiff = pCoords[1] - centerLng;
      const cosLat = Math.cos((centerLat * Math.PI) / 180);

      const posX = lngDiff * 111.32 * cosLat * 45;
      const posZ = -latDiff * 110.57 * 45;

      // Distance limit to keep inside 3D viewport (within ~4 km)
      const dist = Math.hypot(posX, posZ);
      if (dist > 520) return;

      const pOffset = project.yearOffset !== undefined ? project.yearOffset : (project.deliveryYear ? project.deliveryYear - 2026 : 2);
      const isDelivered = currentOffset >= pOffset;
      const isUnderConstruction = !isDelivered && (project.status === 'UNDER_CONSTRUCTION' || currentOffset >= pOffset - 2);

      if (isDelivered) deliveredCount++;
      else if (isUnderConstruction) underConCount++;
      else proposedCount++;

      // Color scheme based on status
      const themeColor = isDelivered ? 0x10b981 : (isUnderConstruction ? 0xf59e0b : 0xa855f7);
      const hexString = isDelivered ? '#10b981' : (isUnderConstruction ? '#f59e0b' : '#a855f7');

      const devGroup = new THREE.Group();
      devGroup.position.set(posX, 0, posZ);
      devGroup.userData = {
        type: 'infra',
        project: project,
        isDelivered: isDelivered,
        statusLabel: isDelivered ? 'OPERATIONAL' : (isUnderConstruction ? 'UNDER CONSTRUCTION' : 'PROPOSED'),
        themeColor: hexString
      };

      // 1. PHYSICAL 3D STRUCTURE
      const isCorridor = project.type === 'corridor' || /metro|rail|road|flyover/i.test(project.category || '');
      let mainMesh = null;
      const targetHeight = isCorridor ? 26 : 42;

      if (isCorridor) {
        // Elevated 3D Transit Viaduct & Pillars
        const viaductGeo = new THREE.BoxGeometry(14, 4, 38);
        const viaductMat = new THREE.MeshStandardMaterial({
          color: themeColor,
          emissive: themeColor,
          emissiveIntensity: isDelivered ? 0.6 : 0.25,
          roughness: 0.2,
          metalness: 0.8
        });
        mainMesh = new THREE.Mesh(viaductGeo, viaductMat);
        mainMesh.position.y = targetHeight;
        devGroup.add(mainMesh);

        // Concrete support pillars
        const pillarGeo = new THREE.CylinderGeometry(2, 2.5, targetHeight, 8);
        const pillarMat = new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.7 });
        const pillar1 = new THREE.Mesh(pillarGeo, pillarMat);
        pillar1.position.set(0, targetHeight / 2, -12);
        const pillar2 = new THREE.Mesh(pillarGeo, pillarMat);
        pillar2.position.set(0, targetHeight / 2, 12);
        devGroup.add(pillar1);
        devGroup.add(pillar2);

        // Animated Energy Transit Pulse along corridor
        const pulseGeo = new THREE.SphereGeometry(2.5, 12, 12);
        const pulseMat = new THREE.MeshBasicMaterial({
          color: 0xffffff,
          transparent: true,
          opacity: 0.9
        });
        const pulseMesh = new THREE.Mesh(pulseGeo, pulseMat);
        pulseMesh.position.y = targetHeight + 3;
        devGroup.add(pulseMesh);

        this.animatedObjects.push({
          isInfra: true,
          update: (time) => {
            pulseMesh.position.z = Math.sin(time * 3 + idx) * 16;
          }
        });
      } else {
        // Modern Node / Tech Hub Architecture
        const towerGeo = new THREE.CylinderGeometry(8, 12, targetHeight, 16);
        const towerMat = new THREE.MeshStandardMaterial({
          color: themeColor,
          emissive: themeColor,
          emissiveIntensity: isDelivered ? 0.65 : 0.3,
          roughness: 0.15,
          metalness: 0.85
        });
        mainMesh = new THREE.Mesh(towerGeo, towerMat);
        mainMesh.position.y = targetHeight / 2;
        devGroup.add(mainMesh);

        // Tiered roof crown
        const crownGeo = new THREE.ConeGeometry(9, 8, 16);
        const crownMat = new THREE.MeshBasicMaterial({ color: 0xffffff, wireframe: true });
        const crown = new THREE.Mesh(crownGeo, crownMat);
        crown.position.y = targetHeight + 4;
        devGroup.add(crown);
      }

      // Construction Rise Animation: scale Y smoothly based on delivery state
      mainMesh.scale.y = isDelivered ? 1.0 : (isUnderConstruction ? 0.6 : 0.25);
      mainMesh.userData = devGroup.userData;
      this.raycastMeshes.push(mainMesh);

      // 2. ANIMATED VOLUMETRIC LIGHT BEACON (Pillar reaching into sky)
      const beamHeight = 160;
      const beamGeo = new THREE.CylinderGeometry(1.5, 7, beamHeight, 16, 1, true);
      const beamMat = new THREE.MeshBasicMaterial({
        color: themeColor,
        transparent: true,
        opacity: isDelivered ? 0.45 : 0.25,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide
      });
      const beam = new THREE.Mesh(beamGeo, beamMat);
      beam.position.y = beamHeight / 2;
      devGroup.add(beam);

      // 3. ANIMATED EXPANDING GROUND SHOCKWAVE RIPPLES
      const rippleGeo = new THREE.RingGeometry(1, 2.5, 32);
      const rippleMat = new THREE.MeshBasicMaterial({
        color: themeColor,
        transparent: true,
        opacity: 0.7,
        side: THREE.DoubleSide
      });
      const ripple = new THREE.Mesh(rippleGeo, rippleMat);
      ripple.rotation.x = -Math.PI / 2;
      ripple.position.y = 0.4;
      devGroup.add(ripple);

      // Animation handler for beacon breath and expanding ground ripples
      const rippleSpeed = 1.2 + (idx % 3) * 0.3;
      const phaseOffset = idx * 1.8;

      this.animatedObjects.push({
        isInfra: true,
        update: (time) => {
          // Pulse beacon intensity
          beamMat.opacity = (isDelivered ? 0.4 : 0.2) + 0.18 * Math.sin(time * 3.5 + phaseOffset);
          beam.rotation.y = time * 0.5;

          // Expand shockwave ring
          const cycle = ((time * rippleSpeed + phaseOffset) % 2.5) / 2.5; // 0..1
          const scale = 1 + cycle * 45;
          ripple.scale.set(scale, scale, 1);
          rippleMat.opacity = Math.max(0, (1 - cycle) * (isDelivered ? 0.65 : 0.4));
        }
      });

      this.infraGroup.add(devGroup);
    });

    // Update 3D Legend Counters in DOM
    const statDelivered = document.getElementById('three-stat-delivered');
    const statUndercon = document.getElementById('three-stat-undercon');
    const statProposed = document.getElementById('three-stat-proposed');
    if (statDelivered) statDelivered.textContent = deliveredCount.toString();
    if (statUndercon) statUndercon.textContent = underConCount.toString();
    if (statProposed) statProposed.textContent = proposedCount.toString();
  }

  // Camera preset modes
  setCameraPreset(preset) {
    switch (preset) {
      case 'iso':
        this.targetPos = { radius: 380, theta: Math.PI / 4, phi: Math.PI / 3.2 };
        this.autoOrbit = false;
        break;
      case 'street':
        this.targetPos = { radius: 140, theta: Math.PI / 3, phi: Math.PI / 2.3 };
        this.autoOrbit = false;
        break;
      case 'top':
        this.targetPos = { radius: 520, theta: Math.PI / 4, phi: 0.15 };
        this.autoOrbit = false;
        break;
      case 'orbit':
        this.autoOrbit = !this.autoOrbit;
        break;
      default:
        break;
    }
  }

  updateCameraPosition() {
    const { radius, theta, phi } = this.spherical;
    this.camera.position.x = this.target.x + radius * Math.sin(phi) * Math.sin(theta);
    this.camera.position.y = this.target.y + radius * Math.cos(phi);
    this.camera.position.z = this.target.z + radius * Math.sin(phi) * Math.cos(theta);
    this.camera.lookAt(this.target.x, this.target.y, this.target.z);
  }

  // Mouse & Touch Interaction Events
  bindEvents() {
    const el = this.canvas;

    const onPointerDown = (e) => {
      this.isMouseDown = e.button === 0;
      this.isRightDown = e.button === 2;
      this.prevMouseX = e.clientX;
      this.prevMouseY = e.clientY;
      this.autoOrbit = false;
    };

    const onPointerMove = (e) => {
      const rect = el.getBoundingClientRect();
      this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      if (this.isMouseDown) {
        const dx = e.clientX - this.prevMouseX;
        const dy = e.clientY - this.prevMouseY;
        this.spherical.theta -= dx * 0.006;
        this.spherical.phi = Math.max(0.12, Math.min(Math.PI / 2.05, this.spherical.phi - dy * 0.006));
        this.targetPos.theta = this.spherical.theta;
        this.targetPos.phi = this.spherical.phi;
      } else if (this.isRightDown) {
        const dx = e.clientX - this.prevMouseX;
        const dy = e.clientY - this.prevMouseY;
        this.target.x -= dx * 0.4;
        this.target.z -= dy * 0.4;
      }
      this.prevMouseX = e.clientX;
      this.prevMouseY = e.clientY;

      // Handle hover raycast
      this.checkHover(e.clientX, e.clientY);
    };

    const onPointerUp = () => {
      this.isMouseDown = false;
      this.isRightDown = false;
    };

    const onWheel = (e) => {
      e.preventDefault();
      this.spherical.radius = Math.max(60, Math.min(900, this.spherical.radius + e.deltaY * 0.5));
      this.targetPos.radius = this.spherical.radius;
    };

    const onClick = () => {
      if (this.hoveredMesh && this.hoveredMesh.userData?.project) {
        if (typeof this.onProjectClick === 'function') {
          this.onProjectClick(this.hoveredMesh.userData.project);
        }
      }
    };

    el.addEventListener('mousedown', onPointerDown);
    window.addEventListener('mousemove', onPointerMove);
    window.addEventListener('mouseup', onPointerUp);
    el.addEventListener('wheel', onWheel, { passive: false });
    el.addEventListener('click', onClick);
    el.addEventListener('contextmenu', (e) => e.preventDefault());

    // Window resize
    window.addEventListener('resize', () => {
      if (!this.initialized || !this.renderer) return;
      const w = this.container.clientWidth || window.innerWidth;
      const h = this.container.clientHeight || window.innerHeight;
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(w, h);
    });
  }

  checkHover(clientX, clientY) {
    if (!this.raycaster || !this.camera || this.raycastMeshes.length === 0) return;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.raycastMeshes, false);

    const tooltip = document.getElementById('three-tooltip');

    if (intersects.length > 0) {
      const hit = intersects[0].object;
      this.hoveredMesh = hit;
      const data = hit.userData?.project;
      if (data && tooltip) {
        document.body.style.cursor = 'pointer';
        tooltip.classList.remove('hidden');
        tooltip.style.left = `${clientX}px`;
        tooltip.style.top = `${clientY}px`;

        const title = document.getElementById('three-tt-title');
        const status = document.getElementById('three-tt-status');
        const year = document.getElementById('three-tt-year');
        const uplift = document.getElementById('three-tt-uplift');
        const source = document.getElementById('three-tt-source');

        if (title) title.textContent = data.title || data.name || 'Infra Project';
        if (status) {
          status.textContent = hit.userData.statusLabel || data.status || 'ACTIVE';
          status.style.color = hit.userData.themeColor || '#10b981';
        }
        if (year) year.textContent = data.expectedDate || (data.deliveryYear ? `${data.deliveryYear}` : '2028');
        if (uplift) uplift.textContent = `+${((data.baseUplift || 0.08) * 100).toFixed(1)}%`;
        if (source) source.textContent = data.source || 'BMRCL / BDA';
      }
    } else {
      this.hoveredMesh = null;
      document.body.style.cursor = 'default';
      if (tooltip) tooltip.classList.add('hidden');
    }
  }

  // Animation render loop
  start() {
    if (!this.initialized) {
      const ok = this.init();
      if (!ok) return;
    }
    this.running = true;

    const render = () => {
      if (!this.running) return;

      const delta = this.clock.getDelta();
      const time = this.clock.getElapsedTime();

      // Auto-orbit camera
      if (this.autoOrbit) {
        this.spherical.theta += 0.004;
        this.targetPos.theta = this.spherical.theta;
      }

      // Smooth camera interpolation towards targetPos
      this.spherical.radius += (this.targetPos.radius - this.spherical.radius) * 0.08;
      this.spherical.theta += (this.targetPos.theta - this.spherical.theta) * 0.08;
      this.spherical.phi += (this.targetPos.phi - this.spherical.phi) * 0.08;
      this.updateCameraPosition();

      // Run animated objects (light beams, ripple shockwaves, moving pulses)
      for (let i = 0; i < this.animatedObjects.length; i++) {
        this.animatedObjects[i].update(time, delta);
      }

      this.renderer.render(this.scene, this.camera);
      this.animId = requestAnimationFrame(render);
    };

    this.animId = requestAnimationFrame(render);
  }

  stop() {
    this.running = false;
    if (this.animId) {
      cancelAnimationFrame(this.animId);
      this.animId = null;
    }
    const tooltip = document.getElementById('three-tooltip');
    if (tooltip) tooltip.classList.add('hidden');
    document.body.style.cursor = 'default';
  }

  update(activeArea, infraList, offset = 0) {
    this.activeArea = activeArea;
    this.infraList = infraList;
    this.offset = offset;

    const locLabel = document.getElementById('three-active-loc');
    if (locLabel && activeArea) {
      locLabel.textContent = activeArea.name;
    }

    this.buildCity(activeArea);
    this.buildParcel(activeArea);
    this.buildDevelopments(infraList, activeArea, offset);
  }

  destroy() {
    this.stop();
    if (this.renderer) {
      this.renderer.dispose();
      this.renderer = null;
    }
    this.initialized = false;
  }
}
