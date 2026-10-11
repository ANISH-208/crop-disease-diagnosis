const MAX_BYTES = 4 * 1024 * 1024;
const MAX_PIXELS = 40_000_000;
const MAX_EDGE = 1024;
const JPEG_QUALITIES = [0.85, 0.75, 0.65];
const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/jpg"]);

export async function validatePhotoFile(file) {
  const supportedName = /\.(jpe?g|png)$/i.test(file?.name || "");
  if (!supportedName || (file.type && !ALLOWED_TYPES.has(file.type))) {
    throw new Error("Choose a JPG or PNG photo. Photos in other formats are not supported yet.");
  }

  let image;
  try {
    image = await loadImage(file);
  } catch {
    throw new Error("This file could not be opened as a photo. Choose another JPG or PNG.");
  }

  try {
    if (image.width <= 0 || image.height <= 0 || image.width * image.height > MAX_PIXELS) {
      throw new Error("This photo is too large to check. Choose an image with fewer pixels.");
    }

    const scale = Math.min(1, MAX_EDGE / Math.max(image.width, image.height));
    const width = Math.max(1, Math.round(image.width * scale));
    const height = Math.max(1, Math.round(image.height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("This browser cannot prepare the photo. Try another browser.");

    context.fillStyle = "#fff";
    context.fillRect(0, 0, width, height);
    context.drawImage(image.source, 0, 0, width, height);

    let blob;
    for (const quality of JPEG_QUALITIES) {
      blob = await encodeJpeg(canvas, quality);
      if (blob.size <= MAX_BYTES) break;
    }
    if (!blob || blob.size > MAX_BYTES) {
      throw new Error("This photo could not be reduced below the 4 MB upload limit.");
    }

    const filename = file.name.replace(/\.(jpe?g|png)$/i, ".jpg");
    return new File([blob], filename, { type: "image/jpeg", lastModified: file.lastModified });
  } finally {
    image.close();
  }
}

async function loadImage(file) {
  if (typeof createImageBitmap === "function") {
    try {
      const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
      return { source: bitmap, width: bitmap.width, height: bitmap.height, close: () => bitmap.close() };
    } catch {
      return loadImageElement(file);
    }
  }
  return loadImageElement(file);
}

function loadImageElement(file) {
  return new Promise((resolve, reject) => {
    const source = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(source);
      resolve({
        source: image,
        width: image.naturalWidth,
        height: image.naturalHeight,
        close: () => {},
      });
    };
    image.onerror = () => {
      URL.revokeObjectURL(source);
      reject(new Error("Image decode failed."));
    };
    image.src = source;
  });
}

function encodeJpeg(canvas, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error("The photo could not be encoded."));
    }, "image/jpeg", quality);
  });
}
