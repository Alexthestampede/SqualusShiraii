import { WaveformRenderer } from './waveform.js';
import { api } from '../api.js';

const ICON_PLAY = `<svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>`;
const ICON_PAUSE = `<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>`;

class Player {
  constructor(container) {
    this.container = container;
    this.audio = new Audio();
    this.audioCtx = null;
    this.analyser = null;
    this.source = null;
    this.waveform = null;
    this.currentSongId = null;
    this.render();
    this._bindEvents();
  }

  render() {
    this.container.innerHTML = `
      <div class="player hidden" id="player-bar">
        <div class="player-art" id="player-art">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
          </svg>
        </div>
        <div class="player-info">
          <div class="player-title" id="player-title">No song playing</div>
          <canvas class="player-waveform" id="player-waveform"></canvas>
        </div>
        <div class="player-controls">
          <span class="player-time" id="player-time">0:00</span>
          <button class="btn btn-ghost btn-icon" id="player-toggle">${ICON_PLAY}</button>
        </div>
      </div>
    `;

    this.bar = document.getElementById('player-bar');
    this.artEl = document.getElementById('player-art');
    this.titleEl = document.getElementById('player-title');
    this.canvasEl = document.getElementById('player-waveform');
    this.timeEl = document.getElementById('player-time');
    this.toggleBtn = document.getElementById('player-toggle');
    this.waveform = new WaveformRenderer(this.canvasEl);
  }

  _bindEvents() {
    this.toggleBtn.addEventListener('click', () => this.togglePlay());

    this.audio.addEventListener('timeupdate', () => {
      if (this.audio.duration) {
        this.waveform.setProgress(this.audio.currentTime / this.audio.duration);
        this.timeEl.textContent = this._fmt(this.audio.currentTime);
      }
    });

    this.audio.addEventListener('ended', () => {
      this.toggleBtn.innerHTML = ICON_PLAY;
    });

    this.audio.addEventListener('play', () => {
      this.toggleBtn.innerHTML = ICON_PAUSE;
    });

    this.audio.addEventListener('pause', () => {
      this.toggleBtn.innerHTML = ICON_PLAY;
    });

    this.canvasEl.addEventListener('click', (e) => {
      if (!this.audio.duration) return;
      const rect = this.canvasEl.getBoundingClientRect();
      const frac = (e.clientX - rect.left) / rect.width;
      this.audio.currentTime = frac * this.audio.duration;
    });
  }

  _initAudioCtx() {
    if (this.audioCtx) return;
    this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    this.analyser = this.audioCtx.createAnalyser();
    this.analyser.fftSize = 128;
    this.source = this.audioCtx.createMediaElementSource(this.audio);
    this.source.connect(this.analyser);
    this.analyser.connect(this.audioCtx.destination);
    this.waveform.connectAnalyser(this.analyser);
  }

  play(songId, title, hasArt) {
    if (this.currentSongId === songId && !this.audio.paused) {
      return;
    }

    this.bar.classList.remove('hidden');

    if (this.currentSongId !== songId) {
      this.currentSongId = songId;
      this.audio.src = api.audioUrl(songId);
      this.titleEl.textContent = title || 'Untitled';

      if (hasArt) {
        this.artEl.innerHTML = `<img src="${api.artUrl(songId)}" class="player-art" alt="">`;
      }
    }

    this._initAudioCtx();
    if (this.audioCtx.state === 'suspended') this.audioCtx.resume();
    this.audio.play();
  }

  togglePlay() {
    if (!this.audio.src) return;
    if (this.audio.paused) {
      this._initAudioCtx();
      if (this.audioCtx.state === 'suspended') this.audioCtx.resume();
      this.audio.play();
    } else {
      this.audio.pause();
    }
  }

  _fmt(s) {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  }
}

let instance = null;

export function initPlayer(container) {
  instance = new Player(container);
  return instance;
}

export function getPlayer() {
  return instance;
}
