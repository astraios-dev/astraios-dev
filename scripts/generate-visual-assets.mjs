import { deflateSync } from "node:zlib";
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";

const width = 1600;
const height = 1180;
const pixels = Buffer.alloc(width * height * 4);

const palette = {
  ink: [14, 15, 21],
  violet: [35, 29, 48],
  gold: [216, 184, 106],
  teal: [71, 198, 179],
  coral: [228, 120, 103],
  paper: [247, 240, 229],
  blue: [125, 183, 255],
};

function mix(a, b, t) {
  return [
    Math.round(a[0] * (1 - t) + b[0] * t),
    Math.round(a[1] * (1 - t) + b[1] * t),
    Math.round(a[2] * (1 - t) + b[2] * t),
  ];
}

function noise(x, y) {
  const n = Math.sin(x * 12.9898 + y * 78.233) * 43758.5453;
  return n - Math.floor(n);
}

function setPixel(x, y, color, alpha = 1) {
  if (x < 0 || y < 0 || x >= width || y >= height) return;
  const index = (Math.floor(y) * width + Math.floor(x)) * 4;
  const inv = 1 - alpha;
  pixels[index] = Math.round(color[0] * alpha + pixels[index] * inv);
  pixels[index + 1] = Math.round(color[1] * alpha + pixels[index + 1] * inv);
  pixels[index + 2] = Math.round(color[2] * alpha + pixels[index + 2] * inv);
  pixels[index + 3] = 255;
}

function drawDisc(cx, cy, radius, color, alpha = 1) {
  const minX = Math.floor(cx - radius);
  const maxX = Math.ceil(cx + radius);
  const minY = Math.floor(cy - radius);
  const maxY = Math.ceil(cy + radius);
  for (let y = minY; y <= maxY; y += 1) {
    for (let x = minX; x <= maxX; x += 1) {
      const dx = x - cx;
      const dy = y - cy;
      const distance = Math.sqrt(dx * dx + dy * dy);
      if (distance <= radius) {
        const edge = Math.max(0, Math.min(1, (radius - distance) / 1.8));
        setPixel(x, y, color, alpha * edge);
      }
    }
  }
}

function drawLine(x1, y1, x2, y2, color, alpha = 1, thickness = 1) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const steps = Math.max(Math.abs(dx), Math.abs(dy));
  for (let i = 0; i <= steps; i += 1) {
    const t = i / steps;
    const x = x1 + dx * t;
    const y = y1 + dy * t;
    drawDisc(x, y, thickness, color, alpha);
  }
}

function drawRect(x, y, w, h, color, alpha = 1, borderOnly = false) {
  for (let yy = y; yy < y + h; yy += 1) {
    for (let xx = x; xx < x + w; xx += 1) {
      const border = xx === x || yy === y || xx === x + w - 1 || yy === y + h - 1;
      if (!borderOnly || border) setPixel(xx, yy, color, alpha);
    }
  }
}

function drawArc(cx, cy, radius, start, end, color, alpha = 1, thickness = 1) {
  const steps = Math.max(80, Math.floor(radius * Math.abs(end - start)));
  let prev = null;
  for (let i = 0; i <= steps; i += 1) {
    const t = start + (end - start) * (i / steps);
    const point = [cx + Math.cos(t) * radius, cy + Math.sin(t) * radius];
    if (prev) drawLine(prev[0], prev[1], point[0], point[1], color, alpha, thickness);
    prev = point;
  }
}

for (let y = 0; y < height; y += 1) {
  for (let x = 0; x < width; x += 1) {
    const nx = x / width;
    const ny = y / height;
    const diagonal = (nx * 0.65 + ny * 0.35);
    const base = mix(palette.ink, palette.violet, diagonal * 0.7);
    const glow = Math.max(0, 1 - Math.hypot(nx - 0.72, ny - 0.28) * 1.65);
    const withGlow = mix(base, palette.gold, glow * 0.18);
    const grain = (noise(x * 0.015, y * 0.015) - 0.5) * 10;
    setPixel(x, y, [
      Math.max(0, Math.min(255, withGlow[0] + grain)),
      Math.max(0, Math.min(255, withGlow[1] + grain)),
      Math.max(0, Math.min(255, withGlow[2] + grain)),
    ]);
  }
}

for (let x = 120; x < width; x += 84) {
  drawLine(x, 0, x, height, palette.paper, 0.035, 0.45);
}

for (let y = 96; y < height; y += 84) {
  drawLine(0, y, width, y, palette.paper, 0.035, 0.45);
}

const nodes = [
  [260, 780, palette.gold],
  [430, 595, palette.teal],
  [605, 420, palette.blue],
  [790, 590, palette.gold],
  [990, 380, palette.coral],
  [1180, 550, palette.teal],
  [1328, 300, palette.gold],
  [1140, 825, palette.blue],
  [835, 880, palette.teal],
  [520, 900, palette.coral],
];

for (let i = 0; i < nodes.length - 1; i += 1) {
  const a = nodes[i];
  const b = nodes[i + 1];
  drawLine(a[0], a[1], b[0], b[1], mix(a[2], b[2], 0.5), 0.45, 1.4);
}

drawArc(780, 620, 470, Math.PI * 1.02, Math.PI * 1.88, palette.gold, 0.32, 1.4);
drawArc(870, 630, 350, Math.PI * 0.1, Math.PI * 0.78, palette.teal, 0.3, 1.2);
drawArc(1020, 650, 530, Math.PI * 1.18, Math.PI * 1.62, palette.blue, 0.24, 1);

for (const [x, y, color] of nodes) {
  drawDisc(x, y, 21, palette.ink, 0.88);
  drawDisc(x, y, 16, color, 0.58);
  drawDisc(x, y, 5, palette.paper, 0.95);
}

for (let i = 0; i < 210; i += 1) {
  const x = 80 + noise(i, 9) * (width - 160);
  const y = 70 + noise(i, 19) * (height - 140);
  const color = [palette.paper, palette.gold, palette.teal, palette.blue][i % 4];
  drawDisc(x, y, 0.8 + noise(i, 29) * 2.4, color, 0.32 + noise(i, 39) * 0.34);
}

const panels = [
  [104, 112, 360, 210, palette.gold],
  [1060, 720, 402, 232, palette.teal],
  [918, 136, 312, 154, palette.coral],
];

for (const [x, y, w, h, color] of panels) {
  drawRect(x, y, w, h, palette.ink, 0.55);
  drawRect(x, y, w, h, color, 0.42, true);
  for (let row = 0; row < 5; row += 1) {
    const yy = y + 38 + row * 28;
    const ww = 78 + noise(row + x, y) * (w - 130);
    drawRect(x + 28, yy, ww, 3, mix(color, palette.paper, 0.35), 0.46);
  }
}

for (let y = 0; y < height; y += 1) {
  for (let x = 0; x < width; x += 1) {
    const nx = x / width - 0.5;
    const ny = y / height - 0.5;
    const vignette = Math.min(0.52, Math.hypot(nx, ny) * 0.68);
    const index = (y * width + x) * 4;
    pixels[index] *= 1 - vignette;
    pixels[index + 1] *= 1 - vignette;
    pixels[index + 2] *= 1 - vignette;
  }
}

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let i = 0; i < 8; i += 1) {
      crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const typeBuffer = Buffer.from(type);
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const checksum = Buffer.alloc(4);
  checksum.writeUInt32BE(crc32(Buffer.concat([typeBuffer, data])));
  return Buffer.concat([length, typeBuffer, data, checksum]);
}

const raw = Buffer.alloc((width * 4 + 1) * height);
for (let y = 0; y < height; y += 1) {
  raw[y * (width * 4 + 1)] = 0;
  pixels.copy(raw, y * (width * 4 + 1) + 1, y * width * 4, (y + 1) * width * 4);
}

const header = Buffer.alloc(13);
header.writeUInt32BE(width, 0);
header.writeUInt32BE(height, 4);
header[8] = 8;
header[9] = 6;
header[10] = 0;
header[11] = 0;
header[12] = 0;

const outputPath = resolve("public/astraios-system-map.png");
mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(
  outputPath,
  Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(raw, { level: 9 })),
    chunk("IEND", Buffer.alloc(0)),
  ]),
);

console.log(`Generated ${outputPath}`);
