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
