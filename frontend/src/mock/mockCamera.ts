export type MockCameraRef = {
  canvas: HTMLCanvasElement;
  stop: () => void;
};

export function createMockCamera(
  canvas: HTMLCanvasElement,
  fps = 15
): MockCameraRef {
  const ctx = canvas.getContext("2d")!;
  let running = true;
  let frame = 0;

  const colors = ["#0f766e", "#14b8a6", "#f59e0b", "#ef4444", "#3b82f6"];
  const objects = [
    { x: 160, y: 140, w: 80, h: 60, label: "backpack", color: "#0f766e" },
    { x: 480, y: 200, w: 50, h: 40, label: "phone", color: "#f59e0b" },
    { x: 700, y: 300, w: 100, h: 80, label: "keyboard", color: "#3b82f6" },
    { x: 320, y: 380, w: 70, h: 90, label: "cup", color: "#14b8a6" },
  ];

  function draw() {
    if (!running) return;

    ctx.fillStyle = "#1e293b";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    for (let i = 0; i < 20; i++) {
      ctx.fillStyle = `rgba(255,255,255,${0.02 + (i % 5) * 0.01})`;
      ctx.fillRect(
        Math.random() * canvas.width,
        Math.random() * canvas.height,
        Math.random() * 40 + 10,
        1
      );
    }

    const gridSize = 60;
    ctx.strokeStyle = "rgba(255,255,255,0.04)";
    ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += gridSize) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += gridSize) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }

    objects.forEach((obj, idx) => {
      const wobble = Math.sin(frame * 0.05 + idx) * 5;
      const x = obj.x + wobble;
      const y = obj.y + Math.cos(frame * 0.03 + idx) * 3;

      ctx.strokeStyle = obj.color;
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 3]);
      ctx.strokeRect(x, y, obj.w, obj.h);

      ctx.fillStyle = obj.color;
      ctx.font = "11px monospace";
      ctx.fillText(obj.label, x, y - 4);

      ctx.fillStyle = `${obj.color}33`;
      ctx.fillRect(x, y, obj.w, obj.h);
    });
    ctx.setLineDash([]);

    const ts = new Date().toISOString().replace("T", " ").substring(0, 19);
    ctx.fillStyle = "rgba(255,255,255,0.9)";
    ctx.font = "14px monospace";
    ctx.fillText(`MockCamera · ${ts} · FPS: ${fps}`, 16, 30);

    ctx.fillStyle = "rgba(255,255,255,0.5)";
    ctx.font = "12px monospace";
    ctx.fillText("1920×1080 · 摄像头: cam-001 · 客厅", 16, 50);

    const statusColor = colors[Math.floor(frame / 30) % colors.length];
    ctx.fillStyle = statusColor;
    ctx.beginPath();
    ctx.arc(canvas.width - 30, 30, 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,0.8)";
    ctx.font = "12px monospace";
    ctx.fillText("● REC", canvas.width - 60, 34);

    frame++;
    requestAnimationFrame(draw);
  }

  draw();

  return {
    canvas,
    stop: () => {
      running = false;
    },
  };
}