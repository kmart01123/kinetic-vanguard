import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname } from "node:path";

export async function readUtf8(path: string): Promise<string> {
  const bytes = await readFile(path);
  const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  if (text.includes("\r")) throw new Error(`${path}: CR bytes are prohibited; use LF newlines`);
  return text;
}

export async function writeAtomic(path: string, bytes: string | Uint8Array): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  const temporary = `${path}.tmp`;
  await writeFile(temporary, bytes);
  await rename(temporary, path);
}
