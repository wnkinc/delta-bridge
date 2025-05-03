// utils/encoding.ts

/**
 * Ensures a File is UTF-8–encoded. If it already is, returns itself;
 * otherwise decodes as latin-1 and re-encodes to UTF-8.
 */
export async function toUtf8Blob(file: File): Promise<Blob> {
  // Read the file into a buffer
  const buffer = await file.arrayBuffer();

  // Try decoding as UTF-8
  const utf8Decoder = new TextDecoder("utf-8", { fatal: true });
  try {
    utf8Decoder.decode(buffer);
    // No error → it is valid UTF-8 already
    return file;
  } catch {
    // Fallback: treat bytes as latin1, then re-encode as UTF-8
    const latin1Decoder = new TextDecoder("iso-8859-1");
    const text = latin1Decoder.decode(buffer);
    const encoder = new TextEncoder(); // defaults to UTF-8
    const utf8Buf = encoder.encode(text);
    return new Blob([utf8Buf], { type: file.type });
  }
}
