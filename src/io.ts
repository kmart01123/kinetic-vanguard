import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
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

export async function replaceDirectoryAtomically(source: string, destination: string): Promise<void> {
  const prior = `${destination}.prior`;
  await rm(prior, { recursive: true, force: true });
  try { await rename(destination, prior); } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
  }
  await rename(source, destination);
  await rm(prior, { recursive: true, force: true });
}
