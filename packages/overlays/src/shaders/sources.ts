/**
 * Fontes GLSL inlined para o emit do `tsc` (o app Vite não precisa de plugin `?raw`).
 * Os arquivos `.glsl` irmãos são a cópia editável / com syntax highlight.
 */

export const blendingGlsl = /* glsl */ `
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
`;

export const overlayVertexShader = /* glsl */ `
// Projetor virtual: uProjectorMatrix = P_proj * V_proj (mundo → clip do projetor).
// A malha proxy é desenhada com a câmera da cena; o UV vem da projeção, não de UV da malha.

uniform mat4 uProjectorMatrix;

varying vec3 vWorldPosition;
varying vec3 vWorldNormal;
varying vec4 vProjectorCoord;

void main() {
  vec4 worldPosition = modelMatrix * vec4(position, 1.0);
  vWorldPosition = worldPosition.xyz;

  // Normal de mundo (malha proxy sem shear; suficiente para o recorte por ângulo).
  vWorldNormal = normalize(mat3(modelMatrix) * normal);

  vProjectorCoord = uProjectorMatrix * worldPosition;

  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

export const overlayFragmentBody = /* glsl */ `
// Fragmento projetivo. blending.glsl é prependido em runtime (applyBlend).
//
// uKind: 0 paint | 1 wallpaper | 2 sticker
// Wallpaper envolve UV (fract); paint/sticker descartam fora de [0,1].
// Máscara por normal: discard se N·(−D) < uNormalThreshold (anti-sangramento).

uniform sampler2D uMap;
uniform vec3 uColor;
uniform float uOpacity;
uniform vec2 uRepeat;
uniform vec2 uOffset;
uniform int uBlendMode;
uniform int uKind;
uniform bool uHasTexture;
uniform bool uMaskByNormal;
uniform float uNormalThreshold;
uniform vec3 uProjectorDirection;
uniform bool uPremultiply;

varying vec3 vWorldPosition;
varying vec3 vWorldNormal;
varying vec4 vProjectorCoord;

void main() {
  // Atrás do projetor ou w inválido.
  if (vProjectorCoord.w <= 0.0) {
    discard;
  }

  vec3 ndc = vProjectorCoord.xyz / vProjectorCoord.w;

  // Fora do frustum (profundidade NDC).
  if (ndc.z < -1.0 || ndc.z > 1.0) {
    discard;
  }

  vec2 uv = ndc.xy * 0.5 + 0.5;

  // Paint e sticker: clip duro na caixa. Wallpaper: wrap.
  bool outside = uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0;
  if (uKind != 1 && outside) {
    discard;
  }

  // Recorte por ângulo: quinas com normal ~perpendicular ao projetor somem.
  if (uMaskByNormal) {
    float facing = dot(normalize(vWorldNormal), normalize(-uProjectorDirection));
    if (facing < uNormalThreshold) {
      discard;
    }
  }

  vec2 tiledUv = uv * uRepeat + uOffset;
  if (uKind == 1) {
    tiledUv = fract(tiledUv);
  }

  vec3 albedo = uColor;
  float alpha = uOpacity;

  if (uHasTexture && uKind != 0) {
    vec4 texel = texture2D(uMap, tiledUv);
    albedo = applyBlend(uColor, texel.rgb, uBlendMode);
    alpha = texel.a * uOpacity;

    // Sticker: descarta cobertura quase nula (halo de PNG comprimido).
    if (uKind == 2 && alpha < 0.002) {
      discard;
    }
  } else if (uKind == 0 && uHasTexture) {
    vec4 texel = texture2D(uMap, tiledUv);
    albedo = applyBlend(uColor, texel.rgb, uBlendMode);
    alpha = texel.a * uOpacity;
  }

  if (uPremultiply) {
    gl_FragColor = vec4(albedo * alpha, alpha);
  } else {
    gl_FragColor = vec4(albedo, alpha);
  }
}
`;

/** Fragment shader completo (blending + corpo). */
export const overlayFragmentShader = `${blendingGlsl}\n${overlayFragmentBody}`;
