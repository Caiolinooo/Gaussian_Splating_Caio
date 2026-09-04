export const VIDEO_EXTENSIONS = ['.mp4', '.mov', '.webm'] as const;
export const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.heic', '.heif'] as const;

export const VIDEO_ACCEPT = '.mp4,.mov,.webm,video/mp4,video/quicktime,video/webm';
export const IMAGE_ACCEPT = '.jpg,.jpeg,.png,.heic,.heif,image/jpeg,image/png,image/heic';
export const MEDIA_ACCEPT = `${VIDEO_ACCEPT},${IMAGE_ACCEPT}`;

/** 2 GiB — walkthrough 4K de alguns minutos. */
export const MAX_VIDEO_BYTES = 2 * 1024 * 1024 * 1024;
/** 40 MiB por foto (HEIC/JPEG de celular em alta). */
export const MAX_IMAGE_BYTES = 40 * 1024 * 1024;
export const MAX_IMAGES_TOTAL_BYTES = 2 * 1024 * 1024 * 1024;

/** SfM precisa de sobreposição; o pipeline de referência usa ~200 fotos. */
export const MIN_IMAGES = 20;
export const MAX_IMAGES = 500;

export const MIN_VIDEO_DURATION_S = 10;
export const MAX_VIDEO_DURATION_S = 15 * 60;

export const MIN_IMAGE_WIDTH = 640;
export const MIN_IMAGE_HEIGHT = 480;

export const HEIGHT_MIN_M = 0.5;
export const HEIGHT_MAX_M = 2.8;
