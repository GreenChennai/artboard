/*
 * Artboard's thin WebGPU host for the official shader-effects-inc/shaders runtime.
 * Rendering, shader components, and WebGPU pipelines come from upstream.js; this file
 * only maps Artboard effect slugs, forwards options, and exposes capture readiness.
 *
 * Upstream: https://github.com/shader-effects-inc/shaders
 * Version: 4.0.4 · source commit 81fd4ece5d493ca6c424a2af41f0e2c361ec8258
 * License: MIT · Copyright (c) 2026 Shader Effects Inc.
 * Full license: LICENSES/shaders-LICENSE
 */
(function (global) {
  'use strict';

  var EFFECT_META = {
    "aurora": {"label":"Aurora","components":["Aurora"],"description":"Layered aurora curtains and rays.","params":["colorA","colorB","colorC","colorSpace","balance","intensity","curtainCount","speed","waviness","rayDensity","height","center","seed"]},
    "mesh-gradient": {"label":"Mesh Gradient","components":["MeshGradient"],"description":"Soft multi-stop mesh gradient.","params":["colorA","colorB","stops","colorSpace","count","smoothness","variation","swirl","drift","wrapping","speed","seed"]},
    "flowing-gradient": {"label":"Flowing Gradient","components":["FlowingGradient"],"description":"Flowing, distorted color fields.","params":["colorA","colorB","colorC","colorD","colorSpace","speed","distortion","seed"]},
    "godrays": {"label":"Godrays","components":["Godrays"],"description":"Volumetric light rays.","params":["center","density","intensity","spotty","speed","rayColor","backgroundColor"]},
    "curl-noise": {"label":"Curl Noise","components":["CurlNoise"],"description":"Flow-map texture driven by curl noise.","params":["colorA","colorB","stops","colorSpace","scale","contrast","balance","seed","speed"]},
    "bokeh": {"label":"Bokeh Blur","components":["BokehBlur"],"description":"Bokeh lens blur; use with source content.","params":["radius","highlightGain","highlightThreshold","bladeShape","bladeCount","bladeRotation","chromaticFringe","catEye","backdropColorA","backdropColorB"]},
    "dot-grid": {"label":"Dot Grid","components":["DotGrid"],"description":"Animated or static dot-grid texture.","params":["color","density","dotSize","offset","speed","speedVariance","twinkle"]},
    "halftone": {"label":"Halftone","components":["Halftone"],"description":"Classic or CMYK halftone print texture.","params":["style","frequency","angle","cyanAngle","magentaAngle","yellowAngle","blackAngle","misprint","misprintAngle","paperColor","cyanColor","magentaColor","yellowColor","blackColor","backdropColorA","backdropColorB"]},
    "truchet": {"label":"Truchet","components":["Truchet"],"description":"Seeded Truchet tile pattern.","params":["colorA","colorB","cells","thickness","rotation","softness","seed","colorSpace"]},
    "vignette-grain": {"label":"Vignette + Film Grain","components":["Vignette","FilmGrain"],"description":"Combined vignette and film-grain finish.","params":["color","center","radius","falloff","intensity","strength","bias","animated","grainStrength","grainBias","backdropColorA","backdropColorB"]},
    "water": {"label":"Water","components":["Water"],"description":"Water surface, waves, reflection, and caustics.","params":["origin","center","scale","rotation","waterColor","clarity","depth","shallows","caustics","causticScale","choppiness","waveScale","swirl","speed","reflection","envRotation","sharpness","lightAngle","foam","edgeSoftness","shape","shapeSdfUrl","shapeType"]}
  };

  var pendingUpstream = null;
  var mounted = new WeakMap();
  var runtimeUrl = document.currentScript && document.currentScript.src ? document.currentScript.src : '';

  function upstreamApi() {
    if (global.ArtboardShadersUpstream && typeof global.ArtboardShadersUpstream.mount === 'function') {
      return Promise.resolve(global.ArtboardShadersUpstream);
    }
    if (pendingUpstream) return pendingUpstream;
    pendingUpstream = new Promise(function (resolve, reject) {
      var script = document.createElement('script');
      var base = runtimeUrl || global.location.href;
      script.src = new URL('upstream.js', base).href;
      script.async = true;
      script.onload = function () {
        if (global.ArtboardShadersUpstream && typeof global.ArtboardShadersUpstream.mount === 'function') {
          resolve(global.ArtboardShadersUpstream);
        } else {
          reject(new Error('Official upstream runtime did not expose ArtboardShadersUpstream.mount'));
        }
      };
      script.onerror = function () { reject(new Error('Failed to load local vendor/shaders/upstream.js')); };
      (document.head || document.documentElement).appendChild(script);
    });
    return pendingUpstream;
  }

  function readParams(canvas, options) {
    var value = options && options.params && typeof options.params === 'object' ? options.params : null;
    if (!value) {
      try { value = JSON.parse(canvas.getAttribute('data-params') || '{}'); }
      catch (error) { throw new Error('Invalid data-params JSON: ' + String(error && error.message || error)); }
    }
    var params = Object.assign({}, value || {});
    if (options && options.speed != null) params.speed = options.speed;
    return params;
  }

  function setStatus(canvas, status, error) {
    canvas.dataset.webgpuRequired = 'true';
    canvas.dataset.webgpuStatus = status;
    canvas.dataset.webgpuReady = status === 'ready' ? 'true' : 'false';
    if (error) {
      canvas.dataset.webgpuError = String(error && error.message || error);
      global.__ARTBOARD_WEBGPU_ERRORS__ = global.__ARTBOARD_WEBGPU_ERRORS__ || [];
      global.__ARTBOARD_WEBGPU_ERRORS__.push({ effect: canvas.dataset.fx || '', error: canvas.dataset.webgpuError });
    } else {
      delete canvas.dataset.webgpuError;
    }
  }

  function mount(canvas, fxName, options) {
    if (!canvas || typeof canvas.getAttribute !== 'function') {
      throw new TypeError('ArtboardShaders.mount requires a canvas element');
    }
    var name = fxName || canvas.dataset.fx || '';
    var meta = EFFECT_META[name];
    if (!meta) throw new Error('Unknown upstream effect slug: ' + name);
    if (mounted.has(canvas)) return mounted.get(canvas);

    options = options || {};
    var params = readParams(canvas, options);
    var freeze = options.freeze != null ? Boolean(options.freeze) : canvas.dataset.freeze === 'true';
    if (freeze && meta.params.indexOf('speed') >= 0 && params.speed == null) params.speed = 0;
    canvas.dataset.fx = name;
    setStatus(canvas, 'pending');

    var handle = { instance: null, ready: null };
    handle.ready = upstreamApi().then(function (api) {
      return api.mount(canvas, name, params, freeze);
    }).then(function (instance) {
      var failure = instance && typeof instance.getFailureReason === 'function'
        ? instance.getFailureReason() : null;
      if (failure) throw new Error('Official upstream WebGPU renderer unavailable: ' + failure);
      handle.instance = instance;
      setStatus(canvas, 'ready');
      canvas.dispatchEvent(new CustomEvent('artboard:webgpu-ready', { detail: { effect: name } }));
      return instance;
    }).catch(function (error) {
      setStatus(canvas, 'failed', error);
      canvas.dispatchEvent(new CustomEvent('artboard:webgpu-error', { detail: { effect: name, error: canvas.dataset.webgpuError } }));
      throw error;
    });
    handle.pause = function () { if (handle.instance) handle.instance.pause(); };
    handle.resume = function () { if (handle.instance) handle.instance.resume(); };
    handle.destroy = function () { if (handle.instance) handle.instance.destroy(); mounted.delete(canvas); };
    mounted.set(canvas, handle);
    return handle;
  }

  function boot(root) {
    root = root || document;
    var canvases = root.querySelectorAll('canvas.ab-shader[data-fx]');
    var jobs = [];
    for (var i = 0; i < canvases.length; i++) {
      try {
        jobs.push(mount(canvases[i], canvases[i].dataset.fx).ready.catch(function () { return null; }));
      } catch (error) {
        setStatus(canvases[i], 'failed', error);
        jobs.push(Promise.resolve(null));
      }
    }
    return Promise.all(jobs);
  }

  function hexToRgb(hex) {
    var match = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(String(hex || ''));
    return match ? [parseInt(match[1], 16) / 255, parseInt(match[2], 16) / 255, parseInt(match[3], 16) / 255] : [0, 0, 0];
  }

  global.ArtboardShaders = {
    version: '4.0.4',
    source: 'shader-effects-inc/shaders@81fd4ece5d493ca6c424a2af41f0e2c361ec8258',
    effects: Object.keys(EFFECT_META),
    meta: EFFECT_META,
    mount: mount,
    boot: boot,
    hexToRgb: hexToRgb
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { void boot(document); }, { once: true });
  } else {
    void boot(document);
  }
})(window);
