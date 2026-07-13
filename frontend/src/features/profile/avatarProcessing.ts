const MAX_OUTPUT_BYTES = 380_000
const INITIAL_SIZE = 640
const MIN_SIZE = 320

function loadImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const image = new Image()
    image.onload = () => {
      URL.revokeObjectURL(url)
      resolve(image)
    }
    image.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('Não foi possível abrir essa imagem.'))
    }
    image.src = url
  })
}

function canvasToBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob)
      else reject(new Error('Não foi possível preparar essa imagem.'))
    }, 'image/jpeg', quality)
  })
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = typeof reader.result === 'string' ? reader.result : ''
      const separator = result.indexOf(',')
      if (separator < 0) reject(new Error('Imagem inválida.'))
      else resolve(result.slice(separator + 1))
    }
    reader.onerror = () => reject(new Error('Não foi possível ler essa imagem.'))
    reader.readAsDataURL(blob)
  })
}

function drawSquare(image: HTMLImageElement, size: number): HTMLCanvasElement {
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const context = canvas.getContext('2d')
  if (!context) throw new Error('Seu navegador não conseguiu preparar a imagem.')

  const sourceSize = Math.min(image.naturalWidth, image.naturalHeight)
  const sourceX = Math.max(0, (image.naturalWidth - sourceSize) / 2)
  const sourceY = Math.max(0, (image.naturalHeight - sourceSize) / 2)
  context.drawImage(
    image,
    sourceX,
    sourceY,
    sourceSize,
    sourceSize,
    0,
    0,
    size,
    size,
  )
  return canvas
}

export async function prepareAvatar(file: File): Promise<{ base64: string; previewUrl: string }> {
  if (!file.type.startsWith('image/')) {
    throw new Error('Escolha um arquivo de imagem.')
  }
  if (file.size > 15_000_000) {
    throw new Error('A imagem original é grande demais.')
  }

  const image = await loadImage(file)
  if (!image.naturalWidth || !image.naturalHeight) {
    throw new Error('Imagem inválida.')
  }

  let size = INITIAL_SIZE
  let quality = 0.88
  let blob = await canvasToBlob(drawSquare(image, size), quality)

  while (blob.size > MAX_OUTPUT_BYTES && quality > 0.56) {
    quality -= 0.08
    blob = await canvasToBlob(drawSquare(image, size), quality)
  }

  while (blob.size > MAX_OUTPUT_BYTES && size > MIN_SIZE) {
    size = Math.max(MIN_SIZE, Math.round(size * 0.82))
    quality = 0.72
    blob = await canvasToBlob(drawSquare(image, size), quality)
  }

  if (blob.size > MAX_OUTPUT_BYTES) {
    throw new Error('Não foi possível reduzir essa imagem o suficiente.')
  }

  return {
    base64: await blobToBase64(blob),
    previewUrl: URL.createObjectURL(blob),
  }
}
