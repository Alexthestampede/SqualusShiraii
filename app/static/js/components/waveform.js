export class WaveformRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.analyser = null;
    this.data = null;
    this.progress = 0;
    this.animId = null;
    this._resize();

    const ro = new ResizeObserver(() => this._resize());
    ro.observe(canvas);
  }

  _resize() {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.ctx.scale(dpr, dpr);
    this.w = rect.width;
    this.h = rect.height;
    this._draw();
  }

  connectAnalyser(analyser) {
    this.analyser = analyser;
    this.data = new Uint8Array(analyser.frequencyBinCount);
    this._animate();
  }

  disconnect() {
    this.analyser = null;
    this.data = null;
    if (this.animId) cancelAnimationFrame(this.animId);
    this.animId = null;
    this._draw();
  }

  setProgress(p) {
    this.progress = Math.max(0, Math.min(1, p));
    if (!this.animId) this._draw();
  }

  _animate() {
    if (!this.analyser) return;
    this.analyser.getByteFrequencyData(this.data);
    this._draw();
    this.animId = requestAnimationFrame(() => this._animate());
  }

  _draw() {
    const { ctx, w, h } = this;
    ctx.clearRect(0, 0, w, h);

    const style = getComputedStyle(document.documentElement);
    const accent = style.getPropertyValue('--accent').trim() || '#6c5ce7';
    const muted = style.getPropertyValue('--text-muted').trim() || '#666';

    const bars = 40;
    const gap = 2;
    const barW = (w - gap * (bars - 1)) / bars;

    for (let i = 0; i < bars; i++) {
      const x = i * (barW + gap);
      const frac = i / bars;

      let barH;
      if (this.data && this.analyser) {
        const idx = Math.floor(frac * this.data.length);
        barH = (this.data[idx] / 255) * h * 0.9 + h * 0.1;
      } else {
        barH = h * (0.15 + 0.2 * Math.sin(frac * Math.PI));
      }

      ctx.fillStyle = frac <= this.progress ? accent : muted;
      ctx.globalAlpha = frac <= this.progress ? 1 : 0.3;
      const y = (h - barH) / 2;
      ctx.beginPath();
      ctx.roundRect(x, y, barW, barH, 1);
      ctx.fill();
    }

    ctx.globalAlpha = 1;
  }
}
