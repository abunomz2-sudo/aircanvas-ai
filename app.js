// Web Air Canvas Engine
const videoElement = document.getElementById('webcam');
const canvasElement = document.getElementById('paint-canvas');
const canvasCtx = canvasElement.getContext('2d');
const loadingOverlay = document.getElementById('loading-overlay');
const toastMessage = document.getElementById('toast-message');

const sizeSlider = document.getElementById('size-slider');
const sizeValue = document.getElementById('size-value');
const fpsDisplay = document.getElementById('fps-display');
const toolDisplay = document.getElementById('active-tool-display');
const gestureBadge = document.getElementById('gesture-badge');

// ─── Constants ────────────────────────────────────────────────
const COLORS = {
    "Red":    [255, 60,   0],
    "Orange": [255, 140,  0],
    "Yellow": [255, 220,  0],
    "Green":  [50,  205, 50],
    "Cyan":   [0,   220, 255],
    "Blue":   [0,   80,  255],
    "Purple": [180,  0,  200],
    "Pink":   [255,  0,  180],
    "White":  [255, 255, 255]
};
const COLOR_NAMES = Object.keys(COLORS);

const TOOL_BRUSH  = "BRUSH";
const TOOL_NEON   = "NEON";
const TOOL_ERASER = "ERASER";
const TOOL_LINE   = "LINE";
const TOOL_RECT   = "RECT";
const TOOL_CIRCLE = "CIRCLE";
const TOOL_BUCKET = "BUCKET";

const BG_WEBCAM = "WEBCAM";
const BG_DARK   = "SOLID_DARK";
const BG_LIGHT  = "SOLID_LIGHT";

// Landmark IDs
const INDEX_TIP  = 8,  INDEX_PIP  = 6;
const MIDDLE_TIP = 12, MIDDLE_PIP = 10;
const RING_TIP   = 16, RING_PIP   = 14;
const PINKY_TIP  = 20, PINKY_PIP  = 18;
const THUMB_TIP  = 4,  THUMB_IP   = 3;

// ─── State Variables ──────────────────────────────────────────
let currentColorIdx = 0;
let brushSize = 8;
let currentTool = TOOL_BRUSH;
let bgMode = BG_WEBCAM;

let isDrawing = false;
let strokePoints = [];
let undoStack = [];
let redoStack = [];
const MAX_UNDO = 20;

// Shape Drawing State
let shapeStartPoint = null;
let shapeCurrentPoint = null;
let isDrawingShape = false;

// Dwell selection state
const DWELL_THRESHOLD = 15; // frames (0.5s)
let dwellBtn = null;
let dwellFrames = 0;
let dwellTriggered = false;

// Offscreen persistent canvas to store drawing strokes
const drawingCanvas = document.createElement('canvas');
const drawingCtx = drawingCanvas.getContext('2d');

// FPS counter variables
let lastFrameTime = performance.now();
let fps = 30;

// Setup layout and sizing
function resizeCanvas() {
    canvasElement.width = window.innerWidth;
    canvasElement.height = window.innerHeight;
    
    // Resize drawing canvas preservation
    if (drawingCanvas.width !== canvasElement.width || drawingCanvas.height !== canvasElement.height) {
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = drawingCanvas.width;
        tempCanvas.height = drawingCanvas.height;
        tempCanvas.getContext('2d').drawImage(drawingCanvas, 0, 0);
        
        drawingCanvas.width = canvasElement.width;
        drawingCanvas.height = canvasElement.height;
        drawingCtx.drawImage(tempCanvas, 0, 0);
    }
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

// ─── Generate Color Palette ──────────────────────────────────
const colorsContainer = document.querySelector('.colors-section');
COLOR_NAMES.forEach((name, idx) => {
    const swatch = document.createElement('div');
    swatch.className = `color-swatch ${idx === 0 ? 'active' : ''}`;
    const rgb = COLORS[name];
    swatch.style.backgroundColor = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
    swatch.style.setProperty('--swatch-color', `rgba(${rgb[0]},${rgb[1]},${rgb[2]}, 0.5)`);
    swatch.dataset.idx = idx;
    swatch.title = name;
    colorsContainer.appendChild(swatch);
});

// Click handlers for toolbar (Mouse fallback)
colorsContainer.addEventListener('click', (e) => {
    const target = e.target.closest('.color-swatch');
    if (target) selectColor(parseInt(target.dataset.idx));
});

document.querySelector('.tools-section').addEventListener('click', (e) => {
    const btn = e.target.closest('.dock-btn');
    if (btn) selectTool(btn.dataset.tool);
});

document.querySelector('.actions-section').addEventListener('click', (e) => {
    const btn = e.target.closest('.dock-btn');
    if (btn) triggerAction(btn.dataset.action);
});

sizeSlider.addEventListener('input', (e) => {
    brushSize = parseInt(e.target.value);
    sizeValue.textContent = `${brushSize}px`;
});

// ─── State Modifiers ──────────────────────────────────────────
function selectColor(idx) {
    document.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('active'));
    document.querySelector(`.color-swatch[data-idx="${idx}"]`).classList.add('active');
    currentColorIdx = idx;
    if (currentTool === TOOL_ERASER) {
        selectTool(TOOL_BRUSH);
    }
    showToast(`Color: ${COLOR_NAMES[idx]}`);
}

function selectTool(tool) {
    document.querySelectorAll('.tools-section .dock-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`tool-${tool}`).classList.add('active');
    currentTool = tool;
    
    // UI Label Update
    const toolLabels = {
        BRUSH: "Brush", NEON: "Neon Glow", ERASER: "Eraser",
        LINE: "Line Tool", RECT: "Rectangle", CIRCLE: "Circle", BUCKET: "Paint Bucket"
    };
    toolDisplay.textContent = `TOOL: ${toolLabels[tool]}`;
    showToast(`Tool: ${toolLabels[tool]}`);
}

function triggerAction(action) {
    if (action === "UNDO") {
        if (undoStack.length > 0) {
            saveState(redoStack);
            restoreState(undoStack.pop());
            showToast("Undo Done");
        } else {
            showToast("Nothing to Undo");
        }
    } else if (action === "REDO") {
        if (redoStack.length > 0) {
            saveState(undoStack);
            restoreState(redoStack.pop());
            showToast("Redo Done");
        } else {
            showToast("Nothing to Redo");
        }
    } else if (action === "BG_MODE") {
        if (bgMode === BG_WEBCAM) {
            bgMode = BG_DARK;
            videoElement.style.display = 'none';
            showToast("Mode: Solid Dark");
        } else if (bgMode === BG_DARK) {
            bgMode = BG_LIGHT;
            videoElement.style.display = 'none';
            showToast("Mode: Solid Light");
        } else {
            bgMode = BG_WEBCAM;
            videoElement.style.display = 'block';
            showToast("Mode: Webcam Feed");
        }
    } else if (action === "SAVE") {
        saveDrawing();
    }
}

// ─── Save & Undo/Redo Engine ──────────────────────────────────
function saveState(stack) {
    if (stack.length >= MAX_UNDO) stack.shift();
    // Save state as image data
    stack.push(drawingCtx.getImageData(0, 0, drawingCanvas.width, drawingCanvas.height));
}

function restoreState(imgData) {
    drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
    drawingCtx.putImageData(imgData, 0, 0);
}

function showToast(msg) {
    toastMessage.textContent = msg;
    toastMessage.classList.add('show');
    clearTimeout(toastMessage.timeoutId);
    toastMessage.timeoutId = setTimeout(() => {
        toastMessage.classList.remove('show');
    }, 2000);
}

function saveDrawing() {
    // Generate clean canvas merge
    const exportCanvas = document.createElement('canvas');
    exportCanvas.width = drawingCanvas.width;
    exportCanvas.height = drawingCanvas.height - 80; // crop out toolbar top 80px
    const exportCtx = exportCanvas.getContext('2d');
    
    // Draw background
    if (bgMode === BG_WEBCAM) {
        exportCtx.fillStyle = '#000000'; // black bg fallback for webcam screenshots
        exportCtx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);
    } else {
        exportCtx.fillStyle = bgMode === BG_DARK ? '#1c1414' : '#faf4f4';
        exportCtx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);
    }
    
    // Draw canvas overlay shifted
    exportCtx.save();
    exportCtx.scale(-1, 1); // Flip x coordinate to download normal drawings (not mirrored)
    exportCtx.drawImage(drawingCanvas, 0, 80, drawingCanvas.width, drawingCanvas.height - 80, -exportCanvas.width, 0, exportCanvas.width, exportCanvas.height);
    exportCtx.restore();
    
    // Download link trigger
    const link = document.createElement('a');
    link.download = `air_drawing_${new Date().toISOString().slice(0,19).replace(/T|:/g,"_")}.png`;
    link.href = exportCanvas.toDataURL();
    link.click();
    showToast("Drawing saved successfully!");
}

// ─── Gesture Math & Analysis ──────────────────────────────────
function dist3d(lm, a, b) {
    return Math.sqrt(
        Math.pow(lm[a].x - lm[b].x, 2) +
        Math.pow(lm[a].y - lm[b].y, 2) +
        Math.pow(lm[a].z - lm[b].z, 2)
    );
}

function fingerUp(lm, tip, pip, isThumb = false) {
    if (isThumb) {
        return dist3d(lm, tip, 0) > dist3d(lm, 2, 0) * 1.08;
    }
    return dist3d(lm, tip, 0) > dist3d(lm, pip, 0) * 1.05;
}

function getGesture(lm) {
    const index  = fingerUp(lm, INDEX_TIP,  INDEX_PIP);
    const middle = fingerUp(lm, MIDDLE_TIP, MIDDLE_PIP);
    const ring   = fingerUp(lm, RING_TIP,   RING_PIP);
    const pinky  = fingerUp(lm, PINKY_TIP,  PINKY_PIP);
    const thumb  = fingerUp(lm, THUMB_TIP,  THUMB_IP, true);

    if (index && !middle && !ring && !pinky) return "DRAW";
    if (index && middle && !ring && !pinky) return "HOVER";
    if (!index && !middle && !ring && !pinky) return "FIST";
    if (index && middle && ring && pinky) return "CLEAR";
    if (thumb && !index && !middle && !ring && !pinky) return "UNDO";
    return "NONE";
}

// ─── Drawing helpers ──────────────────────────────────────────
function getRGBColorString(idx, alpha = 1.0) {
    const rgb = COLORS[COLOR_NAMES[idx]];
    return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})`;
}

function drawLineNeon(ctx, p1, p2, colorIdx, size) {
    const rgb = COLORS[COLOR_NAMES[colorIdx]];
    const colorStr = `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
    const coreStr = `rgb(${Math.min(255, rgb[0] + 150)}, ${Math.min(255, rgb[1] + 150)}, ${Math.min(255, rgb[2] + 150)})`;
    
    // Core white/bright line
    ctx.shadowBlur = size * 2.5;
    ctx.shadowColor = colorStr;
    ctx.strokeStyle = coreStr;
    ctx.lineWidth = size * 0.4;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    
    ctx.beginPath();
    ctx.moveTo(p1[0], p1[1]);
    ctx.lineTo(p2[0], p2[1]);
    ctx.stroke();
    
    // Reset shadow
    ctx.shadowBlur = 0;
}

function drawBezierCurve(ctx, p0, p1, p2, colorIdx, size, tool) {
    const steps = 15;
    const pts = [];
    for (let i = 0; i <= steps; i++) {
        const t = i / steps;
        const x = Math.pow(1 - t, 2) * p0[0] + 2 * (1 - t) * t * p1[0] + Math.pow(t, 2) * p2[0];
        const y = Math.pow(1 - t, 2) * p0[1] + 2 * (1 - t) * t * p1[1] + Math.pow(t, 2) * p2[1];
        pts.push([x, y]);
    }
    
    for (let j = 0; j < pts.length - 1; j++) {
        if (tool === TOOL_NEON) {
            drawLineNeon(ctx, pts[j], pts[j+1], colorIdx, size);
        } else {
            ctx.beginPath();
            ctx.moveTo(pts[j][0], pts[j][1]);
            ctx.lineTo(pts[j+1][0], pts[j+1][1]);
            ctx.strokeStyle = tool === TOOL_ERASER ? '#000000' : getRGBColorString(currentColorIdx);
            ctx.lineWidth = tool === TOOL_ERASER ? size * 3 : size;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            ctx.stroke();
        }
    }
}

function drawShapeOn(ctx, p1, p2, colorIdx, size, tool) {
    ctx.strokeStyle = getRGBColorString(colorIdx);
    ctx.lineWidth = size;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    
    ctx.beginPath();
    if (tool === TOOL_LINE) {
        ctx.moveTo(p1[0], p1[1]);
        ctx.lineTo(p2[0], p2[1]);
        ctx.stroke();
    } else if (tool === TOOL_RECT) {
        ctx.rect(p1[0], p1[1], p2[0] - p1[0], p2[1] - p1[1]);
        ctx.stroke();
    } else if (tool === TOOL_CIRCLE) {
        const radius = Math.sqrt(Math.pow(p1[0]-p2[0], 2) + Math.pow(p1[1]-p2[1], 2));
        ctx.arc(p1[0], p1[1], radius, 0, 2 * Math.PI);
        ctx.stroke();
    }
}

// ─── Button Bounding Box Dwell Checks ─────────────────────────
function getHoveredButton(cx, cy) {
    const btns = document.querySelectorAll('.dock-btn, .color-swatch');
    for (let btn of btns) {
        const rect = btn.getBoundingClientRect();
        if (cx >= rect.left && cx <= rect.right && cy >= rect.top && cy <= rect.bottom) {
            return btn;
        }
    }
    
    // Check Slider Track Box
    const sliderRect = sizeSlider.getBoundingClientRect();
    if (cx >= sliderRect.left && cx <= sliderRect.right && cy >= sliderRect.top && cy <= sliderRect.bottom) {
        return sizeSlider;
    }
    
    return null;
}

function executeDwellTrigger(btn) {
    if (btn.classList.contains('color-swatch')) {
        selectColor(parseInt(btn.dataset.idx));
    } else if (btn.dataset.tool) {
        selectTool(btn.dataset.tool);
    } else if (btn.dataset.action) {
        triggerAction(btn.dataset.action);
    }
}

// ─── MediaPipe Model Hand Results Callback ───────────────────
let undoLastTime = 0;
let clearStartTime = null;

function onResults(results) {
    // Calculate FPS
    const currTime = performance.now();
    fps = Math.round(1000 / (currTime - lastFrameTime));
    lastFrameTime = currTime;
    fpsDisplay.textContent = `FPS: ${fps}`;

    // Clear main render canvas
    canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);

    // Draw active background if solid colors
    if (bgMode === BG_DARK) {
        canvasCtx.fillStyle = '#1c1414';
        canvasCtx.fillRect(0, 0, canvasElement.width, canvasElement.height);
    } else if (bgMode === BG_LIGHT) {
        canvasCtx.fillStyle = '#faf4f4';
        canvasCtx.fillRect(0, 0, canvasElement.width, canvasElement.height);
    }

    // Render persistent canvas layers onto view
    canvasCtx.drawImage(drawingCanvas, 0, 0);

    let gesture = "NONE";
    let cx = -1, cy = -1;

    if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
        const landmarks = results.multiHandLandmarks[0];
        
        // Mirror coordinates mathematically in JS (Matches Mirrored display)
        cx = (1 - landmarks[INDEX_TIP].x) * canvasElement.width;
        cy = landmarks[INDEX_TIP].y * canvasElement.height;
        
        gesture = getGesture(landmarks);
    }

    // Update status badge UI
    gestureBadge.textContent = gesture;
    gestureBadge.className = `badge ${gesture.toLowerCase()}`;

    // ── GESTURE ACTIONS ENGINE ──
    
    // 1. HOVER selection (Dwell triggers)
    if (gesture === "HOVER" && cy < TOOLBAR_H && cx > 0) {
        const hovered = getHoveredButton(cx, cy);
        if (hovered) {
            if (hovered === sizeSlider) {
                // Adjust brush thickness continuously without dwell
                const rect = sizeSlider.getBoundingClientRect();
                const pct = (cx - rect.left) / rect.width;
                brushSize = Math.max(2, Math.min(40, Math.round(pct * 38) + 2));
                sizeSlider.value = brushSize;
                sizeValue.textContent = `${brushSize}px`;
            } else {
                if (dwellBtn === hovered) {
                    if (!dwellTriggered) {
                        dwellFrames++;
                        if (dwellFrames >= DWELL_THRESHOLD) {
                            executeDwellTrigger(hovered);
                            dwellTriggered = true;
                        }
                    }
                } else {
                    dwellBtn = hovered;
                    dwellFrames = 0;
                    dwellTriggered = false;
                }
            }
        } else {
            dwellBtn = null;
            dwellFrames = 0;
            dwellTriggered = false;
        }
    } else {
        dwellBtn = null;
        dwellFrames = 0;
        dwellTriggered = false;
    }

    // 2. CLEAR hold
    if (gesture === "CLEAR") {
        if (!clearStartTime) {
            clearStartTime = performance.now();
        } else if (performance.now() - clearStartTime > 1500) {
            saveState(undoStack);
            redoStack = [];
            drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
            clearStartTime = null;
            showToast("Canvas Cleared");
        }
    } else {
        clearStartTime = null;
    }

    // 3. UNDO trigger
    if (gesture === "UNDO") {
        if (performance.now() - undoLastTime > 1000) {
            triggerAction("UNDO");
            undoLastTime = performance.now();
        }
    }

    // 4. DRAW lines/shapes
    const isShapeTool = [TOOL_LINE, TOOL_RECT, TOOL_CIRCLE].includes(currentTool);
    
    if (gesture === "DRAW" && cy > TOOLBAR_H && cx > 0) {
        if (currentTool === TOOL_ERASER) {
            if (!isDrawing) {
                saveState(undoStack);
                redoStack = [];
            }
            drawingCtx.beginPath();
            drawingCtx.arc(cx, cy, brushSize * 3, 0, 2 * Math.PI);
            drawingCtx.fillStyle = '#000000';
            drawingCtx.fill();
            isDrawing = true;
            
        } else if (currentTool === TOOL_BUCKET) {
            if (!isDrawing) {
                saveState(undoStack);
                redoStack = [];
                const rgb = COLORS[COLOR_NAMES[currentColorIdx]];
                // Canvas bucket flood fill
                floodFill(drawingCanvas, Math.round(cx), Math.round(cy), rgb);
            }
            isDrawing = true;
            
        } else if (isShapeTool) {
            if (!isDrawingShape) {
                shapeStartPoint = [cx, cy];
                isDrawingShape = true;
                saveState(undoStack);
                redoStack = [];
            }
            shapeCurrentPoint = [cx, cy];
            isDrawing = true;
            
        } else {
            // Freehand Brush & Neon Glow Brush
            if (!isDrawing) {
                saveState(undoStack);
                redoStack = [];
                strokePoints = [];
            }
            
            strokePoints.push([cx, cy]);
            
            if (strokePoints.length === 1) {
                if (currentTool === TOOL_NEON) {
                    drawCircleNeon(drawingCtx, strokePoints[0], currentColorIdx, brushSize);
                } else {
                    drawingCtx.beginPath();
                    drawingCtx.arc(cx, cy, brushSize / 2, 0, 2 * Math.PI);
                    drawingCtx.fillStyle = getRGBColorString(currentColorIdx);
                    drawingCtx.fill();
                }
            } else if (strokePoints.length === 2) {
                if (currentTool === TOOL_NEON) {
                    drawLineNeon(drawingCtx, strokePoints[0], strokePoints[1], currentColorIdx, brushSize);
                } else {
                    drawingCtx.beginPath();
                    drawingCtx.moveTo(strokePoints[0][0], strokePoints[0][1]);
                    drawingCtx.lineTo(strokePoints[1][0], strokePoints[1][1]);
                    drawingCtx.strokeStyle = getRGBColorString(currentColorIdx);
                    drawingCtx.lineWidth = brushSize;
                    drawingCtx.lineCap = 'round';
                    drawingCtx.lineJoin = 'round';
                    drawingCtx.stroke();
                }
            } else {
                // Bezier curve calculations
                const p0 = strokePoints[strokePoints.length - 3];
                const p1 = strokePoints[strokePoints.length - 2];
                const p2 = strokePoints[strokePoints.length - 1];
                const mid1 = [(p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2];
                const mid2 = [(p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2];
                drawBezierCurve(drawingCtx, mid1, p1, mid2, currentColorIdx, brushSize, currentTool);
            }
            
            isDrawing = true;
        }
    } else {
        // Drawing release
        if (isDrawingShape && shapeStartPoint && shapeCurrentPoint) {
            drawShapeOn(drawingCtx, shapeStartPoint, shapeCurrentPoint, currentColorIdx, brushSize, currentTool);
            isDrawingShape = false;
            shapeStartPoint = null;
            shapeCurrentPoint = null;
        }
        
        isDrawing = false;
        strokePoints = [];
    }

    // ── Overlay shape previews on view ──
    if (isDrawingShape && shapeStartPoint && shapeCurrentPoint) {
        drawShapeOn(canvasCtx, shapeStartPoint, shapeCurrentPoint, currentColorIdx, brushSize, currentTool);
    }

    // ── Render Cursor Indicators ──
    if (cx > 0 && cy > 0) {
        canvasCtx.save();
        const rgb = COLORS[COLOR_NAMES[currentColorIdx]];
        const cursorCol = `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
        
        if (gesture === "DRAW") {
            if (currentTool === TOOL_ERASER) {
                canvasCtx.beginPath();
                canvasCtx.arc(cx, cy, brushSize * 3, 0, 2 * Math.PI);
                canvasCtx.strokeStyle = 'rgba(255, 64, 96, 0.6)';
                canvasCtx.lineWidth = 1.5;
                canvasCtx.stroke();
            } else if (currentTool === TOOL_BUCKET) {
                canvasCtx.beginPath();
                canvasCtx.arc(cx, cy, 6, 0, 2 * Math.PI);
                canvasCtx.strokeStyle = cursorCol;
                canvasCtx.lineWidth = 1;
                canvasCtx.stroke();
            } else if (isShapeTool) {
                // Crosshairs cursor
                canvasCtx.strokeStyle = cursorCol;
                canvasCtx.lineWidth = 1;
                canvasCtx.beginPath();
                canvasCtx.moveTo(cx - 10, cy); canvasCtx.lineTo(cx + 10, cy);
                canvasCtx.moveTo(cx, cy - 10); canvasCtx.lineTo(cx, cy + 10);
                canvasCtx.stroke();
            } else {
                // standard glowing cursor bubble
                canvasCtx.beginPath();
                canvasCtx.arc(cx, cy, brushSize + 4, 0, 2 * Math.PI);
                canvasCtx.strokeStyle = `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, 0.3)`;
                canvasCtx.lineWidth = 2;
                canvasCtx.stroke();
                
                canvasCtx.beginPath();
                canvasCtx.arc(cx, cy, brushSize / 2, 0, 2 * Math.PI);
                canvasCtx.fillStyle = cursorCol;
                canvasCtx.fill();
            }
        } else if (gesture === "HOVER") {
            // Target selector with dwell progress arc
            canvasCtx.beginPath();
            canvasCtx.arc(cx, cy, 14, 0, 2 * Math.PI);
            canvasCtx.strokeStyle = '#00e5ff';
            canvasCtx.lineWidth = 1;
            canvasCtx.stroke();
            
            if (dwellBtn && !dwellTriggered) {
                const progress = dwellFrames / DWELL_THRESHOLD;
                canvasCtx.beginPath();
                canvasCtx.arc(cx, cy, 14, -0.5 * Math.PI, (-0.5 + progress * 2) * Math.PI);
                canvasCtx.strokeStyle = '#00e5ff';
                canvasCtx.lineWidth = 2.5;
                canvasCtx.stroke();
            } else {
                // target reticle
                canvasCtx.beginPath();
                canvasCtx.moveTo(cx - 18, cy); canvasCtx.lineTo(cx + 18, cy);
                canvasCtx.moveTo(cx, cy - 18); canvasCtx.lineTo(cx, cy + 18);
                canvasCtx.strokeStyle = 'rgba(160, 150, 180, 0.6)';
                canvasCtx.lineWidth = 1;
                canvasCtx.stroke();
            }
        } else if (gesture === "FIST") {
            canvasCtx.beginPath();
            canvasCtx.arc(cx, cy, 10, 0, 2 * Math.PI);
            canvasCtx.strokeStyle = 'rgba(100, 100, 120, 0.6)';
            canvasCtx.lineWidth = 1;
            canvasCtx.stroke();
        }
        
        canvasCtx.restore();
    }

    // ── Clear progress bar rendering ──
    if (clearStartTime) {
        const progress = Math.min(1.0, (performance.now() - clearStartTime) / 1500);
        canvasCtx.fillStyle = 'rgba(255, 180, 60, 0.8)';
        canvasCtx.fillRect(0, TOOLBAR_H + 1, canvasElement.width * progress, 3);
        
        canvasCtx.fillStyle = '#ffb43c';
        canvasCtx.font = '500 13px Inter';
        canvasCtx.textAlign = 'center';
        canvasCtx.fillText("HOLDING TO CLEAR...", canvasElement.width / 2, TOOLBAR_H + 28);
    }
}

// ─── Paint Bucket Flood Fill in JS ────────────────────────────
function floodFill(canvas, startX, startY, fillRGB) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    // Bounds check
    if (startX < 0 || startX >= width || startY < 0 || startY >= height) return;
    
    const imgData = ctx.getImageData(0, 0, width, height);
    const data = imgData.data;
    
    const startIdx = (startY * width + startX) * 4;
    const startR = data[startIdx];
    const startG = data[startIdx+1];
    const startB = data[startIdx+2];
    
    // Target same color check
    if (startR === fillRGB[0] && startG === fillRGB[1] && startB === fillRGB[2]) return;
    
    const queue = [[startX, startY]];
    const targetColor = (startR << 16) | (startG << 8) | startB;
    
    while (queue.length > 0) {
        const [x, y] = queue.pop();
        let idx = (y * width + x) * 4;
        
        // Match color check with small tolerance
        const currentR = data[idx];
        const currentG = data[idx+1];
        const currentB = data[idx+2];
        
        const diff = Math.abs(currentR - startR) + Math.abs(currentG - startG) + Math.abs(currentB - startB);
        
        if (diff <= 60) {
            data[idx]   = fillRGB[0];
            data[idx+1] = fillRGB[1];
            data[idx+2] = fillRGB[2];
            data[idx+3] = 255;
            
            if (x > 0) queue.push([x - 1, y]);
            if (x < width - 1) queue.push([x + 1, y]);
            if (y > 0) queue.push([x, y - 1]);
            if (y < height - 1) queue.push([x, y + 1]);
        }
    }
    
    ctx.putImageData(imgData, 0, 0);
}

// ─── Keyboard Hotkeys Bindings ──────────────────────────────
window.addEventListener('keydown', (e) => {
    const key = e.key.toUpperCase();
    if (key === 'Z') triggerAction("UNDO");
    if (key === 'Y') triggerAction("REDO");
    if (key === 'B') triggerAction("BG_MODE");
    if (key === 'S') triggerAction("SAVE");
    if (key === 'C') {
        saveState(undoStack);
        redoStack = [];
        drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
        showToast("Canvas Cleared");
    }
    if (key === 'T') {
        const tools = [TOOL_BRUSH, TOOL_NEON, TOOL_ERASER, TOOL_LINE, TOOL_RECT, TOOL_CIRCLE, TOOL_BUCKET];
        const nextIdx = (tools.indexOf(currentTool) + 1) % tools.length;
        selectTool(tools[nextIdx]);
    }
    if (key === '[') {
        brushSize = Math.max(2, brushSize - 2);
        sizeSlider.value = brushSize;
        sizeValue.textContent = `${brushSize}px`;
    }
    if (key === ']') {
        brushSize = Math.min(40, brushSize + 2);
        sizeSlider.value = brushSize;
        sizeValue.textContent = `${brushSize}px`;
    }
    if (e.key >= '1' && e.key <= '9') {
        const idx = parseInt(e.key) - 1;
        if (idx < COLOR_NAMES.length) selectColor(idx);
    }
});

// ─── Initialize MediaPipe Hands ──────────────────────────────
const hands = new Hands({
    locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`
});

hands.setOptions({
    maxNumHands: 1,
    modelComplexity: 1,
    minDetectionConfidence: 0.75,
    minTrackingConfidence: 0.75
});

hands.onResults(onResults);

// Setup webcam camera capture
const camera = new Camera(videoElement, {
    onFrame: async () => {
        await hands.send({ image: videoElement });
    },
    width: 1280,
    height: 720
});

// Start detector loop
camera.start().then(() => {
    loadingOverlay.style.opacity = '0';
    setTimeout(() => {
        loadingOverlay.style.display = 'none';
    }, 500);
}).catch(err => {
    alert("Camera initialization failed. Please make sure camera is connected and permissions are granted.");
});
