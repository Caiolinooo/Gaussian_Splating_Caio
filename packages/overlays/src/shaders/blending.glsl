// Modos de mistura enviados em uBlendMode:
//   0 = normal   → albedo = color * texel (tint)
//   1 = multiply → albedo = color * texel
//   2 = overlay  → Photoshop overlay(color, texel)
//
// Stickers usam alpha pré-multiplicado no final do fragment
// (evita halo escuro nas bordas de PNG com cobertura parcial).

#ifndef GS_OVERLAY_BLENDING
#define GS_OVERLAY_BLENDING

int GS_BLEND_NORMAL = 0;
int GS_BLEND_MULTIPLY = 1;
int GS_BLEND_OVERLAY = 2;

// Overlay por canal: se base < 0.5 → 2*base*blend; senão 1 - 2*(1-base)*(1-blend).
float overlayChannel(float base, float blend) {
  return base < 0.5
    ? (2.0 * base * blend)
    : (1.0 - 2.0 * (1.0 - base) * (1.0 - blend));
}

vec3 overlayBlend(vec3 base, vec3 blend) {
  return vec3(
    overlayChannel(base.r, blend.r),
    overlayChannel(base.g, blend.g),
    overlayChannel(base.b, blend.b)
  );
}

vec3 applyBlend(vec3 color, vec3 texel, int mode) {
  if (mode == GS_BLEND_MULTIPLY) {
    return color * texel;
  }
  if (mode == GS_BLEND_OVERLAY) {
    return overlayBlend(color, texel);
  }
  // normal: textura tintada pela cor (branco = textura pura)
  return color * texel;
}

#endif
