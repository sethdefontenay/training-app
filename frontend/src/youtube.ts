/** YouTube video IDs found in some text (watch / youtu.be / embed forms). */
export function youtubeIds(text: string): string[] {
  const re = /(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)([\w-]{11})/g;
  const ids = new Set<string>();
  for (const m of text.matchAll(re)) ids.add(m[1]);
  return [...ids];
}
