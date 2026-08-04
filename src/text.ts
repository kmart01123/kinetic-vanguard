import type { AuthoritativeText, ComposedText, DerivedOutput, Placement, UiTextToken } from "./types.js";

interface UiEntry { id: string; placements: Placement[]; text?: string; template?: string; slots?: Record<string, "AuthoritativeText" | "DerivedOutput"> }
interface UiRegistry { tokens: UiEntry[] }
interface DerivedEntry { id: string; placements: Placement[] }
interface DerivedRegistry { derivations: DerivedEntry[] }

export class TextBoundary {
  private readonly ui = new Map<string, UiEntry>();
  private readonly derived = new Map<string, DerivedEntry>();
  constructor(ui: UiRegistry, derived: DerivedRegistry) {
    for (const token of ui.tokens) this.ui.set(token.id, token);
    for (const definition of derived.derivations) this.derived.set(definition.id, definition);
  }
  authoritative(text: string, sourcePath: string, placement: Placement): AuthoritativeText {
    return Object.freeze({ kind: "authoritative", text, sourcePath, placement });
  }
  token(tokenId: string, placement: Placement): UiTextToken {
    const token = this.ui.get(tokenId);
    if (!token?.text || !token.placements.includes(placement)) throw new Error(`UI token ${tokenId} is not valid for ${placement}`);
    return Object.freeze({ kind: "ui", text: token.text, tokenId, placement });
  }
  output(derivationId: string, value: string | number, placement: Placement): DerivedOutput {
    const definition = this.derived.get(derivationId);
    if (!definition?.placements.includes(placement)) throw new Error(`Derived output ${derivationId} is not valid for ${placement}`);
    return Object.freeze({ kind: "derived", text: String(value), derivationId, placement });
  }
  compose(templateId: string, placement: Placement, slots: Record<string, AuthoritativeText | DerivedOutput>): ComposedText {
    const definition = this.ui.get(templateId);
    if (!definition?.template || !definition.placements.includes(placement)) throw new Error(`UI template ${templateId} is not valid for ${placement}`);
    const expected = definition.slots ?? {};
    if (Object.keys(expected).sort().join() !== Object.keys(slots).sort().join()) throw new Error(`Template ${templateId} slot mismatch`);
    let text = definition.template;
    const constituents: Array<AuthoritativeText | DerivedOutput | UiTextToken> = [];
    for (const [name, expectedKind] of Object.entries(expected)) {
      const value = slots[name];
      if (!value || (expectedKind === "AuthoritativeText" ? value.kind !== "authoritative" : value.kind !== "derived")) throw new Error(`Template ${templateId} slot ${name} expects ${expectedKind}`);
      text = text.replace(`{${name}}`, value.text);
      constituents.push(value);
    }
    constituents.push(Object.freeze({ kind: "ui", text: definition.template.replace(/\{[^}]+\}/g, ""), tokenId: templateId, placement }));
    return Object.freeze({ kind: "composed", text, templateId, placement, constituents: Object.freeze(constituents) });
  }
}

export function escapeHtml(text: string): string {
  return text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}
