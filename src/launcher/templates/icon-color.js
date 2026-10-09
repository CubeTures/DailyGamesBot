// Finds an icon's dominant color, to tint its game's card and scoreboard.
var iconColor = (function () {
  var SIZE = 32;

  // Hue in sixths of a turn, [0, 6).
  function hue(r, g, b, max, chroma) {
    var h = max === r ? (g - b) / chroma : max === g ? 2 + (b - r) / chroma : 4 + (r - g) / chroma;
    return (h + 6) % 6;
  }

  // The icon is drawn small, its opaque and not-too-grey pixels are binned
  // by hue (weighted by saturation), and the heaviest bin's pixels are
  // averaged. Returns a CSS hsl() color, or null for a grey icon.
  function dominant(img) {
    var canvas = document.createElement("canvas");
    canvas.width = canvas.height = SIZE;
    var ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(img, 0, 0, SIZE, SIZE);
    var pixels = ctx.getImageData(0, 0, SIZE, SIZE).data;
    var bins = [];
    for (var i = 0; i < pixels.length; i += 4) {
      var r = pixels[i], g = pixels[i + 1], b = pixels[i + 2];
      if (pixels[i + 3] < 128) continue;
      var max = Math.max(r, g, b), chroma = max - Math.min(r, g, b);
      if (chroma < 40 || max < 40) continue;
      var index = Math.floor(hue(r, g, b, max, chroma) * 2);
      var bin = bins[index] || (bins[index] = { weight: 0, r: 0, g: 0, b: 0 });
      var weight = chroma / max;
      bin.weight += weight; bin.r += r * weight; bin.g += g * weight; bin.b += b * weight;
    }
    var best = bins.reduce(function (a, c) { return c && (!a || c.weight > a.weight) ? c : a; }, null);
    return best ? toHsl(best.r / best.weight, best.g / best.weight, best.b / best.weight) : null;
  }

  // Keeps the hue and saturation but fixes the lightness, so pale and dark
  // icons tint equally.
  function toHsl(r, g, b) {
    var max = Math.max(r, g, b), min = Math.min(r, g, b), chroma = max - min;
    var sat = chroma / (255 - Math.abs(max + min - 255));
    return "hsl(" + Math.round(hue(r, g, b, max, chroma) * 60) + " " + Math.round(sat * 100) + "% 50%)";
  }

  return { dominant: dominant };
})();
