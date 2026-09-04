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
