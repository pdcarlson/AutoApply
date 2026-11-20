/** Draws the live view's pictures onto a canvas, newest first. */

/** Draws frames into a canvas; `stop` makes it ignore anything still decoding. */
export interface FrameDrawer {
  draw: (frame: Blob) => void;
  stop: () => void;
}

/** Makes a drawer that resizes the canvas to each picture and reports the picture's shape. */
export function createFrameDrawer(
  canvas: HTMLCanvasElement,
  onShape: (widthOverHeight: number) => void,
  onDrawn: () => void,
): FrameDrawer {
  const context = canvas.getContext('2d');
  let nextFrame: Blob | null = null;
  let isDrawing = false;
  let isStopped = false;

  // Decoding is async, so only the newest picture is drawn and older ones are skipped.
  const drawLatest = async () => {
    isDrawing = true;
    while (nextFrame && !isStopped) {
      const blob = nextFrame;
      nextFrame = null;
      try {
        const bitmap = await createImageBitmap(blob);
        if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
          canvas.width = bitmap.width;
          canvas.height = bitmap.height;
          if (!isStopped) onShape(bitmap.width / bitmap.height);
        }
        context?.drawImage(bitmap, 0, 0);
        bitmap.close();
        onDrawn();
      } catch {
        // A picture that can't be decoded is skipped; the next one replaces it.
      }
    }
    isDrawing = false;
  };

  return {
    draw: (frame) => {
      nextFrame = frame;
      if (!isDrawing) void drawLatest();
    },
    stop: () => {
      isStopped = true;
    },
  };
}
